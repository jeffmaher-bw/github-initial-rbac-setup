import csv
import os
import re
import sys

from github import Github, GithubException

ORG_NAME = "bloom-works"
CSV_FILE = "rbac_groups.csv"


def main():
    # --- Phase 1: Parse CSV (no API calls) ---

    # Load the CSV. Each row is a person; columns after Person/Emails are team names.
    # "x" = member, "o" = maintainer, empty = not on that team.
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    group_columns = [col for col in fieldnames if col not in ("Person", "Emails")]

    # Build a plan entry for each person. Entries with no email or no team
    # assignments are separated out so they show up clearly in the preview.
    plan = []
    skipped = []
    for row in rows:
        name = row.get("Person", "").strip()
        email = row.get("Emails", "").strip()
        if not email:
            skipped.append((name, "no email"))
            continue

        member_cols = [col for col in group_columns if row.get(col, "").strip().lower() == "x"]
        maintainer_cols = [col for col in group_columns if row.get(col, "").strip().lower() == "o"]

        if not member_cols and not maintainer_cols:
            skipped.append((name, "no team assignments"))
            continue

        plan.append({"name": name, "email": email, "member": member_cols, "maintainer": maintainer_cols})

    # --- Phase 2: Print preview ---

    print(f"=== Preview: {len(group_columns)} teams ===\n")
    for col in group_columns:
        print(f"  {col}")

    print(f"\n=== Preview: {len(plan)} people to process ({len(skipped)} skipped) ===")
    for entry in plan:
        print(f"\n  {entry['name']} <{entry['email']}>")
        if entry["member"]:
            print(f"    member:     {', '.join(entry['member'])}")
        if entry["maintainer"]:
            print(f"    maintainer: {', '.join(entry['maintainer'])}")

    if skipped:
        print(f"\n=== Skipped ({len(skipped)}) ===")
        for name, reason in skipped:
            print(f"  {name}: {reason}")

    # --- Phase 3: Confirm before making any changes ---

    print()
    answer = input("Proceed? [y/N]: ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return

    # --- Phase 4: Connect to GitHub and execute the plan ---

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("Error: GITHUB_TOKEN environment variable is not set")

    g = Github(token)
    org = g.get_organization(ORG_NAME)

    # Fetch all existing org teams once so we can match without repeated API calls.
    print("\n=== Fetching existing teams ===")
    existing_by_slug: dict[str, object] = {t.slug: t for t in org.get_teams()}

    # For each group column, reuse the existing GitHub team or create a new one.
    # GitHub auto-generates a slug from the team name, so we normalize the column
    # name the same way to detect matches.
    print("\n=== Setting up teams ===")
    teams: dict[str, object] = {}
    for col in group_columns:
        slug = re.sub(r"[^a-z0-9]+", "-", col.lower()).strip("-")
        if slug in existing_by_slug:
            teams[col] = existing_by_slug[slug]
            print(f"  [exists]  {col}")
        else:
            team = org.create_team(col, privacy="closed")
            existing_by_slug[team.slug] = team
            teams[col] = team
            print(f"  [created] {col}")

    # Invite or add each person to their assigned teams.
    print("\n=== Processing members ===")
    for entry in plan:
        name = entry["name"]
        email = entry["email"]
        member_teams = [teams[col] for col in entry["member"]]
        maintainer_teams = [teams[col] for col in entry["maintainer"]]
        all_teams = member_teams + maintainer_teams
        team_names = ", ".join(t.name for t in all_teams)

        try:
            # Send an org invitation that pre-assigns the person to their teams.
            # The invitation API doesn't support setting team roles, so maintainer
            # assignments must be applied manually after the person accepts.
            org.invite_user(email=email, teams=all_teams)
            note = ""
            if maintainer_teams:
                maintainer_names = ", ".join(t.name for t in maintainer_teams)
                note = f"\n           ^ set maintainer role after acceptance: {maintainer_names}"
            print(f"  INVITED  {name} ({email}) → {team_names}{note}")

        except GithubException as e:
            data = e.data or {}
            msg = str(data.get("message", "")).lower()

            if "already a member" in msg:
                # Person is already in the org, so invitations don't apply.
                # Look them up by email and add directly with the correct role.
                user = _find_user_by_email(g, email)
                if user:
                    for team in member_teams:
                        team.add_membership(user, role="member")
                    for team in maintainer_teams:
                        team.add_membership(user, role="maintainer")
                    print(f"  ADDED    {name} ({email}) → {team_names}")
                else:
                    print(
                        f"  WARN     {name} ({email}): already a member but GitHub user "
                        f"not found by email; add manually to: {team_names}"
                    )
            else:
                print(f"  ERROR    {name} ({email}): {data.get('message', e)}")


def _find_user_by_email(g: Github, email: str):
    # GitHub user search only matches public emails, so this may not find everyone.
    try:
        results = g.search_users(f"{email} in:email")
        for user in results:
            if (user.email or "").lower() == email.lower():
                return user
    except GithubException:
        pass
    return None


if __name__ == "__main__":
    main()
