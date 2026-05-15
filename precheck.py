import json
import os
import sys
import urllib.request
from datetime import datetime

from github import Github, GithubException

ORG_NAME = "bloom-works"


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("Error: GITHUB_TOKEN environment variable is not set")

    g = Github(token)

    # --- 1. Verify token and check scopes ---
    print("=== Token & Scopes ===")
    try:
        user = g.get_user()
        print(f"  Authenticated as: {user.login}")
    except GithubException as e:
        sys.exit(f"  ERROR: could not authenticate: {e}")

    # oauth_scopes is populated after the first API call above.
    # Note: fine-grained PATs report permissions differently — scopes may appear empty.
    scopes = g.oauth_scopes or []
    if scopes:
        print(f"  Scopes: {', '.join(scopes)}")
        if "admin:org" not in scopes:
            print("  WARN: admin:org scope not found — team creation and invitations may fail")
        else:
            print("  OK: admin:org scope present")
    else:
        print("  Scopes: (not reported — token may be a fine-grained PAT)")

    org = g.get_organization(ORG_NAME)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = "backup"
    os.makedirs(backup_dir, exist_ok=True)

    # --- 2. Export current teams ---
    print("\n=== Current Teams ===")
    teams = list(org.get_teams())
    team_data = [{"name": t.name, "slug": t.slug, "privacy": t.privacy} for t in teams]
    teams_file = f"{backup_dir}/teams-before-{timestamp}.json"
    with open(teams_file, "w") as f:
        json.dump(team_data, f, indent=2)
    if teams:
        for t in teams:
            print(f"  {t.name}")
    else:
        print("  (none)")
    print(f"  → saved to {teams_file}")

    # --- 3. Export current org members ---
    print("\n=== Current Org Members ===")
    members = list(org.get_members())
    member_data = [{"login": m.login} for m in members]
    members_file = f"{backup_dir}/members-before-{timestamp}.json"
    with open(members_file, "w") as f:
        json.dump(member_data, f, indent=2)
    print(f"  {len(members)} members → saved to {members_file}")

    # --- 4. Check pending invitations ---
    # PyGithub doesn't wrap this endpoint, so we call it directly via urllib.
    print("\n=== Pending Invitations ===")
    req = urllib.request.Request(
        f"https://api.github.com/orgs/{ORG_NAME}/invitations?per_page=100",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            invitations = json.loads(resp.read())
        if not invitations:
            print("  None")
        else:
            print(f"  {len(invitations)} pending:")
            for inv in invitations:
                print(f"    {inv.get('email') or inv.get('login')}")
    except Exception as e:
        print(f"  ERROR fetching invitations: {e}")


if __name__ == "__main__":
    main()
