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

## CSV formats

Both scripts use the same column conventions: `x` for member, `o` for maintainer, blank for no membership.

### `rbac_groups.csv` — invite by email

Used by `main.py`. The first two columns are `Person` and `Emails`. Every column after that is a team name.

```
Person,Emails,team-a,team-b
Alice,alice@example.com,x,
Bob,bob@example.com,x,o
```

### `github_users.csv` — assign by GitHub username

Used by `assign_github_teams.py`. The first two columns are `Person` and `GitHub ID`. Every column after that is a team name.

```
Person,GitHub ID,team-a,team-b
Alice,alice-gh,x,
Bob,bobcodes,x,o
```

## Usage

### 1. Pre-flight check

Run this before any other script to verify your token, snapshot existing teams and members, and surface any pending invitations:

```bash
uv run python precheck.py
```

Snapshots are saved to the `backup/` folder.

### 2. Invite members by email

Reads `rbac_groups.csv`, creates any missing teams, and sends org invitations. Previews the full plan and asks for confirmation before making any changes:

```bash
uv run python main.py
```

### 3. Assign members by GitHub username

Reads `github_users.csv`, creates any missing teams, and assigns members directly using their GitHub username. Useful for org members who have already accepted their invitation:

```bash
uv run python assign_github_teams.py
```

Both scripts write a timestamped log of their output to `backup/`.

## Notes

- Teams that already exist are reused without modification.
- Users who are already org members are added to teams directly instead of re-invited.
- The GitHub invitation API does not support setting team roles at invite time. Users assigned as maintainer (`o`) will be invited as regular members — their maintainer role must be set manually after they accept.
- The "already a member" fallback in `main.py` uses GitHub's public email search, which only works if the user has a public email on their GitHub account.
