import os
import sys
from datetime import datetime

from github import Github, GithubException

ORG_NAME = "bloom-works"
TEAM_NAME = "everyone"


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
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("Error: GITHUB_TOKEN environment variable is not set")

    g = Github(token)
    org = g.get_organization(ORG_NAME)

    # Find the "everyone" team.
    team = next((t for t in org.get_teams() if t.slug == TEAM_NAME), None)
    if not team:
        sys.exit(f"Error: team '{TEAM_NAME}' not found in {ORG_NAME}")

    # Get all current org members and filter out anyone already on the team.
    all_members = list(org.get_members())
    existing = {m.login for m in team.get_members()}
    to_add = [m for m in all_members if m.login not in existing]

    # --- Preview onward: tee all output to a log file ---

    os.makedirs("backup", exist_ok=True)
    log_path = f"backup/backfill-everyone-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    log_file = open(log_path, "w")
    original_stdout = sys.stdout
    sys.stdout = _Tee(log_file)

    try:
        # --- Preview ---

        print(f"=== Preview ===\n")
        print(f"  Team:            {team.name}")
        print(f"  Already members: {len(existing)}")
        print(f"  To add:          {len(to_add)}")
        if to_add:
            print()
            for member in to_add:
                print(f"  {member.login}")

        if not to_add:
            print("\nNothing to do.")
            return

        # --- Confirm ---

        print()
        answer = input("Proceed? [y/N]: ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return

        # --- Execute ---

        print()
        for member in to_add:
            try:
                team.add_membership(member, role="member")
                print(f"  ADDED  {member.login}")
            except GithubException as e:
                data = e.data or {}
                print(f"  ERROR  {member.login}: {data.get('message', e)}")

    finally:
        sys.stdout = original_stdout
        log_file.close()
        print(f"Output saved to {log_path}")


if __name__ == "__main__":
    main()
