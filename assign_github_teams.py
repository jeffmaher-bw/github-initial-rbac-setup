import csv
import os
import re
import sys
from datetime import datetime

from github import Github, GithubException

ORG_NAME = "bloom-works"
CSV_FILE = "github_users.csv"


class _Tee:
    """Mirrors all writes to both stdout and a file."""
    def __init__(self, file):
        self._file = file
        self._stdout = sys.stdout

    def write(self, data):
        self._stdout.write(data)
        self._file.write(data)

    def flush(self):
        self._stdout.flush()
        self._file.flush()


def main():
    # --- Phase 1: Parse CSV (no API calls) ---

    # Load the CSV. Each row is a person; columns after Person/GitHub ID are team names.
    # "x" = member, "o" = maintainer, empty = not on that team.
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [{k.strip(): v.strip() for k, v in row.items() if k is not None} for row in reader]
        fieldnames = [f.strip() for f in (reader.fieldnames or [])]

    group_columns = [col for col in fieldnames if col not in ("Person", "GitHub ID")]

    # Build a plan entry for each person. Entries with no GitHub ID or no team
    # assignments are separated out so they show up clearly in the preview.
    plan = []
    skipped = []
    for row in rows:
        name = row.get("Person", "").strip()
        github_id = row.get("GitHub ID", "").strip()
        if not github_id:
            skipped.append((name, "no GitHub ID"))
            continue

        member_cols = [col for col in group_columns if row.get(col, "").strip().lower() == "x"]
        maintainer_cols = [col for col in group_columns if row.get(col, "").strip().lower() == "o"]

        if not member_cols and not maintainer_cols:
            skipped.append((name, "no team assignments"))
            continue

        plan.append({"name": name, "github_id": github_id, "member": member_cols, "maintainer": maintainer_cols})

    # --- Phase 2 onward: tee all output to a log file ---

    os.makedirs("backup", exist_ok=True)
    log_path = f"backup/assign-github-teams-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    log_file = open(log_path, "w")
    original_stdout = sys.stdout
    sys.stdout = _Tee(log_file)

    try:
        # --- Phase 2: Print preview ---

        print(f"=== Preview: {len(group_columns)} teams ===\n")
        for col in group_columns:
            print(f"  {col}")

        print(f"\n=== Preview: {len(plan)} people to process ({len(skipped)} skipped) ===")
        for entry in plan:
            print(f"\n  {entry['name']} (@{entry['github_id']})")
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

        # Assign each person to their teams directly using their GitHub username.
        print("\n=== Assigning members ===")
        for entry in plan:
            name = entry["name"]
            github_id = entry["github_id"]
            member_teams = [teams[col] for col in entry["member"]]
            maintainer_teams = [teams[col] for col in entry["maintainer"]]
            team_names = ", ".join(t.name for t in member_teams + maintainer_teams)

            try:
                user = g.get_user(github_id)
            except GithubException:
                print(f"  WARN     {name} (@{github_id}): GitHub user not found, skipping")
                continue

            try:
                for team in member_teams:
                    team.add_membership(user, role="member")
                for team in maintainer_teams:
                    team.add_membership(user, role="maintainer")
                print(f"  ASSIGNED {name} (@{github_id}) → {team_names}")
            except GithubException as e:
                data = e.data or {}
                print(f"  ERROR    {name} (@{github_id}): {data.get('message', e)}")

    finally:
        sys.stdout = original_stdout
        log_file.close()
        print(f"Output saved to {log_path}")


if __name__ == "__main__":
    main()
