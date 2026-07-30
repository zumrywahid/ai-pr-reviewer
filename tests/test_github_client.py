from reviewer.github_client import COMMENT_MARKER, GitHubClient, _inline_body
from reviewer.schemas import Severity, VerifiedFinding


def _finding(**overrides) -> VerifiedFinding:
    defaults = dict(
        file="src/app.py",
        line=7,
        severity=Severity.HIGH,
        title="Unvalidated input reaches the shell",
        body="Pass args as a list to subprocess.run instead of shell=True.",
        category="security",
        verification_note="The input comes straight from the request body.",
    )
    defaults.update(overrides)
    return VerifiedFinding(**defaults)


def test_inline_body_contains_the_essentials():
    body = _inline_body(_finding())
    assert "high" in body
    assert "security" in body
    assert "Unvalidated input reaches the shell" in body
    assert "Survived verification" in body


def test_summary_body_with_no_findings_is_positive():
    body = GitHubClient._summary_body([], [], 0, truncated=False)
    assert COMMENT_MARKER in body
    assert "no findings" in body.lower()


def test_summary_body_lists_findings_and_leftovers():
    kept = _finding()
    leftover = _finding(file="src/other.py", title="Missing test for the error path")
    body = GitHubClient._summary_body([kept, leftover], [leftover], 1, truncated=True)
    assert "2 finding(s)" in body
    assert "src/app.py:7" in body
    assert "Missing test for the error path" in body
    assert "too large" in body  # truncation warning
