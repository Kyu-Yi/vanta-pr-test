# vanta-pr-test

Checkpoint F moved-base validation commit.

Throwaway sandbox repository for validating Vanta's GitHub PR integration.

## What this repo validates

This sandbox validates that Vanta can:

- create a branch from a specific tested commit
- create at least one commit for the PR branch
- open a draft pull request by default
- open a ready-for-review pull request when requested
- report when the base branch has moved since the tested commit
- avoid leaking credentials into pull request titles, bodies, or commit messages

## Important limitation

GitHub does not expose a reliable repository-side signal that proves a commit was created via the GitHub commit API instead of being pushed normally.

Because of that, this sandbox treats commit transport as a declared contract field in the PR body:

- `Commit transport: github-api`

This validates that Vanta explicitly reports the transport it intended to use, but it does not cryptographically prove the transport origin.

## Required PR body contract

Vanta-created PRs in this sandbox should include these lines somewhere in the PR body:

- `Tested commit: <sha>`
- `Commit transport: github-api`
- `PR mode: draft` or `PR mode: ready`
- `Base moved since tested commit: yes` or `Base moved since tested commit: no`

Example:

```text
## Vanta PR Contract
- Tested commit: 0123456789abcdef0123456789abcdef01234567
- Commit transport: github-api
- PR mode: draft
- Base moved since tested commit: no
```

## How validation works

The GitHub Action in `.github/workflows/validate-vanta-pr.yml` checks:

1. The PR body contains the required contract fields.
2. The actual PR draft state matches `PR mode`.
3. The reported base movement matches whether `pull_request.base.sha` differs from `Tested commit`.
4. The compare API merge base between `base.sha` and `head.sha` matches `Tested commit`.
5. The PR title, PR body, and commit messages do not contain obvious secret patterns.

## Local test command

```bash
python3 -m unittest discover -s tests -v
```

## Runbook

For the exact sandbox smoke-test checklist, see [CHECKPOINT_F_TEST_RUNBOOK.md](file:///Users/kyu-yi/Documents/trae_projects/vanta-pr-test/CHECKPOINT_F_TEST_RUNBOOK.md).
