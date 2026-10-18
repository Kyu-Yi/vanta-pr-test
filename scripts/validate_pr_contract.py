from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from typing import Any

KEY_ALIASES = {
    "tested commit": "tested_commit",
    "commit transport": "commit_transport",
    "pr mode": "pr_mode",
    "base moved since tested commit": "base_moved",
}

REQUIRED_FIELDS = ("tested_commit", "commit_transport", "pr_mode", "base_moved")
VALID_PR_MODES = {"draft", "ready"}
VALID_BASE_MOVED = {"yes", "no"}

SECRET_PATTERNS = [
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI-style key", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----")),
    ("Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b", re.IGNORECASE)),
]


def normalize_sha(value: str) -> str:
    return value.strip().lower()


def sha_matches(expected: str, actual: str) -> bool:
    return normalize_sha(actual).startswith(normalize_sha(expected))


def parse_contract(body: str | None) -> dict[str, str]:
    contract: dict[str, str] = {}
    if not body:
        return contract

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        line = re.sub(r"^[-*]\s*", "", line)
        match = re.match(r"(?P<key>[A-Za-z][A-Za-z\s-]+):\s*(?P<value>.+?)\s*$", line)
        if not match:
            continue

        key = match.group("key").strip().lower()
        alias = KEY_ALIASES.get(key)
        if not alias:
            continue

        contract[alias] = match.group("value").strip().strip("`").lower()

    return contract


def find_secret_violations(label: str, text: str | None) -> list[str]:
    if not text:
        return []

    violations: list[str] = []
    for pattern_name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            violations.append(f"{label} appears to contain a {pattern_name}.")
    return violations


def validate_required_fields(contract: dict[str, str]) -> list[str]:
    return [
        f"PR body is missing required contract field: {field}."
        for field in REQUIRED_FIELDS
        if field not in contract
    ]


def validate_tested_commit(contract: dict[str, str]) -> list[str]:
    tested_commit = contract.get("tested_commit")
    if not tested_commit:
        return []

    if not re.fullmatch(r"[0-9a-f]{7,40}", tested_commit):
        return ["`Tested commit` must be a 7 to 40 character hexadecimal SHA."]
    return []


def validate_commit_transport(contract: dict[str, str]) -> list[str]:
    transport = contract.get("commit_transport")
    if not transport:
        return []

    if transport != "github-api":
        return ["`Commit transport` must be `github-api` for this sandbox."]
    return []


def validate_pr_mode(pr: dict[str, Any], contract: dict[str, str]) -> list[str]:
    expected_mode = contract.get("pr_mode")
    if not expected_mode:
        return []

    if expected_mode not in VALID_PR_MODES:
        return ["`PR mode` must be either `draft` or `ready`."]

    actual_mode = "draft" if pr.get("draft") else "ready"
    if actual_mode != expected_mode:
        return [f"PR mode mismatch: contract says `{expected_mode}`, GitHub reports `{actual_mode}`."]
    return []


def validate_base_moved(pr: dict[str, Any], contract: dict[str, str]) -> list[str]:
    reported = contract.get("base_moved")
    tested_commit = contract.get("tested_commit")
    if not reported or not tested_commit:
        return []

    if reported not in VALID_BASE_MOVED:
        return ["`Base moved since tested commit` must be `yes` or `no`."]

    base_sha = pr["base"]["sha"]
    actual = "no" if sha_matches(tested_commit, base_sha) else "yes"
    if actual != reported:
        return [
            "Base movement mismatch: "
            f"contract says `{reported}`, but comparing `Tested commit` to `base.sha` gives `{actual}`."
        ]
    return []


def validate_branch_lineage(contract: dict[str, str], merge_base_sha: str | None) -> list[str]:
    tested_commit = contract.get("tested_commit")
    if not tested_commit or not merge_base_sha:
        return []

    if not sha_matches(tested_commit, merge_base_sha):
        return ["Branch lineage mismatch: compare API merge base does not match `Tested commit`."]
    return []


def evaluate_pull_request(
    event: dict[str, Any],
    commits: list[dict[str, Any]],
    merge_base_sha: str | None,
) -> list[str]:
    pr = event["pull_request"]
    contract = parse_contract(pr.get("body", ""))

    violations: list[str] = []
    violations.extend(validate_required_fields(contract))
    violations.extend(validate_tested_commit(contract))
    violations.extend(validate_commit_transport(contract))
    violations.extend(validate_pr_mode(pr, contract))
    violations.extend(validate_base_moved(pr, contract))
    violations.extend(validate_branch_lineage(contract, merge_base_sha))

    violations.extend(find_secret_violations("PR title", pr.get("title")))
    violations.extend(find_secret_violations("PR body", pr.get("body")))

    if not commits:
        violations.append("PR branch does not contain any commits.")
    else:
        for commit in commits:
            message = commit.get("commit", {}).get("message", "")
            sha = commit.get("sha", "<unknown>")
            violations.extend(find_secret_violations(f"Commit {sha}", message))

    return violations


def github_get_json(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "vanta-pr-test-contract-validator",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def write_summary(lines: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")

    if not event_path or not token or not repository:
        print("Missing required GitHub Actions environment variables.", file=sys.stderr)
        return 2

    with open(event_path, "r", encoding="utf-8") as handle:
        event = json.load(handle)

    pr = event.get("pull_request")
    if not pr:
        print("No pull_request payload found; nothing to validate.")
        return 0

    commits = github_get_json(pr["commits_url"], token)
    compare = github_get_json(
        f"https://api.github.com/repos/{repository}/compare/{pr['base']['sha']}...{pr['head']['sha']}",
        token,
    )
    merge_base_sha = compare.get("merge_base_commit", {}).get("sha")

    violations = evaluate_pull_request(event, commits, merge_base_sha)

    if violations:
        output = ["## Contract validation failed", *[f"- {item}" for item in violations]]
        print("\n".join(output))
        write_summary(output)
        return 1

    output = [
        "## Contract validation passed",
        f"- PR #{pr['number']} matches the sandbox contract.",
        f"- Merge base: {merge_base_sha}",
        f"- Checked commits: {len(commits)}",
    ]
    print("\n".join(output))
    write_summary(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
