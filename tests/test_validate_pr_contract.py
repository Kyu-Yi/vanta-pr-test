import importlib
import unittest


def make_event(
    *,
    body: str,
    draft: bool,
    base_sha: str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    head_sha: str = "cccccccccccccccccccccccccccccccccccccccc",
) -> dict:
    return {
        "pull_request": {
            "number": 7,
            "title": "test: create validation PR",
            "body": body,
            "draft": draft,
            "base": {"sha": base_sha},
            "head": {"sha": head_sha},
        }
    }


def make_commit(message: str, sha: str = "dddddddddddddddddddddddddddddddddddddddd") -> dict:
    return {
        "sha": sha,
        "commit": {
            "message": message,
        },
    }


def load_validator_module(test_case: unittest.TestCase):
    try:
        return importlib.import_module("scripts.validate_pr_contract")
    except ModuleNotFoundError as exc:
        test_case.fail(f"validator module is missing: {exc}")


class ParseContractTests(unittest.TestCase):
    def test_parses_markdown_bullets(self) -> None:
        validator = load_validator_module(self)
        body = """
        ## Vanta PR Contract
        - Tested commit: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        - Commit transport: github-api
        - PR mode: draft
        - Base moved since tested commit: no
        """
        contract = validator.parse_contract(body)
        self.assertEqual(contract["tested_commit"], "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertEqual(contract["commit_transport"], "github-api")
        self.assertEqual(contract["pr_mode"], "draft")
        self.assertEqual(contract["base_moved"], "no")


class EvaluatePullRequestTests(unittest.TestCase):
    def test_accepts_valid_draft_pull_request(self) -> None:
        validator = load_validator_module(self)
        body = """
        - Tested commit: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        - Commit transport: github-api
        - PR mode: draft
        - Base moved since tested commit: no
        """
        event = make_event(body=body, draft=True)
        commits = [make_commit("test: sandbox commit")]

        violations = validator.evaluate_pull_request(
            event,
            commits,
            merge_base_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )

        self.assertEqual(violations, [])

    def test_flags_missing_contract_fields(self) -> None:
        validator = load_validator_module(self)
        event = make_event(body="- Tested commit: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", draft=True)
        commits = [make_commit("test: sandbox commit")]

        violations = validator.evaluate_pull_request(
            event,
            commits,
            merge_base_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )

        self.assertTrue(any("commit_transport" in item for item in violations))
        self.assertTrue(any("pr_mode" in item for item in violations))
        self.assertTrue(any("base_moved" in item for item in violations))

    def test_flags_draft_mode_mismatch(self) -> None:
        validator = load_validator_module(self)
        body = """
        - Tested commit: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        - Commit transport: github-api
        - PR mode: ready
        - Base moved since tested commit: no
        """
        event = make_event(body=body, draft=True)
        commits = [make_commit("test: sandbox commit")]

        violations = validator.evaluate_pull_request(
            event,
            commits,
            merge_base_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )

        self.assertTrue(any("PR mode mismatch" in item for item in violations))

    def test_flags_base_movement_mismatch(self) -> None:
        validator = load_validator_module(self)
        body = """
        - Tested commit: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        - Commit transport: github-api
        - PR mode: draft
        - Base moved since tested commit: no
        """
        event = make_event(body=body, draft=True)
        commits = [make_commit("test: sandbox commit")]

        violations = validator.evaluate_pull_request(
            event,
            commits,
            merge_base_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

        self.assertTrue(any("Base movement mismatch" in item for item in violations))

    def test_flags_branch_lineage_mismatch(self) -> None:
        validator = load_validator_module(self)
        body = """
        - Tested commit: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        - Commit transport: github-api
        - PR mode: draft
        - Base moved since tested commit: no
        """
        event = make_event(body=body, draft=True)
        commits = [make_commit("test: sandbox commit")]

        violations = validator.evaluate_pull_request(
            event,
            commits,
            merge_base_sha="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        )

        self.assertTrue(any("Branch lineage mismatch" in item for item in violations))

    def test_flags_secret_in_pr_body(self) -> None:
        validator = load_validator_module(self)
        body = """
        - Tested commit: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        - Commit transport: github-api
        - PR mode: draft
        - Base moved since tested commit: no

        ghp_123456789012345678901234567890123456
        """
        event = make_event(body=body, draft=True)
        commits = [make_commit("test: sandbox commit")]

        violations = validator.evaluate_pull_request(
            event,
            commits,
            merge_base_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )

        self.assertTrue(any("PR body appears to contain" in item for item in violations))

    def test_flags_secret_in_commit_message(self) -> None:
        validator = load_validator_module(self)
        body = """
        - Tested commit: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        - Commit transport: github-api
        - PR mode: draft
        - Base moved since tested commit: no
        """
        event = make_event(body=body, draft=True)
        commits = [make_commit("add token ghp_123456789012345678901234567890123456")]

        violations = validator.evaluate_pull_request(
            event,
            commits,
            merge_base_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )

        self.assertTrue(any("Commit " in item for item in violations))


if __name__ == "__main__":
    unittest.main()
