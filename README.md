# github-initial-rbac-setup
Creates GitHub Teams in the `bloom-works` org and invites members based on a CSV of RBAC group assignments.

## Requirements

- Python 3.9+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A GitHub personal access token with the `admin:org` scope

## Setup

Install dependencies:

```bash
uv sync
```

Set your GitHub token:

```bash
export GITHUB_TOKEN=your_token_here
```

## CSV format

The script reads `rbac_groups.csv`. The first two columns are `Person` and `Emails`. Every column after that is a team name. Use `x` for member and `o` for maintainer; leave blank if the person doesn't belong to that team.

```
Person,Emails,team-a,team-b
Alice,alice@example.com,x,
Bob,bob@example.com,x,o
```

## Usage

### 1. Pre-flight check

Run this before the main script to verify your token, snapshot existing teams and members, and surface any pending invitations:

```bash
uv run python precheck.py
```

Snapshots are saved to the `backup/` folder.

### 2. Run

Previews the full plan from the CSV and asks for confirmation before making any changes:

```bash
uv run python main.py
```

Review the output, then enter `y` to proceed or anything else to abort.

## Notes

- Teams that already exist are reused without modification.
- Users who are already org members are added to teams directly instead of re-invited.
- The GitHub invitation API does not support setting team roles at invite time. Users assigned as maintainer (`o`) will be invited as regular members — their maintainer role must be set manually after they accept.
- The "already a member" fallback uses GitHub's public email search, which only works if the user has a public email on their GitHub account.
