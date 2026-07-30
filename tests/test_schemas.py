from reviewer.schemas import (
    Severity,
    VerifiedFinding,
    VerifiedReview,
    sort_by_severity,
)


def _finding(severity: Severity, title: str = "t") -> VerifiedFinding:
    return VerifiedFinding(
        file="app.py",
        line=10,
        severity=severity,
        title=title,
        body="body",
        category="correctness",
        verification_note="checked against the diff",
    )


def test_sort_by_severity_orders_critical_first():
    findings = [
        _finding(Severity.LOW, "low"),
        _finding(Severity.CRITICAL, "critical"),
        _finding(Severity.MEDIUM, "medium"),
        _finding(Severity.HIGH, "high"),
    ]
    ordered = [f.title for f in sort_by_severity(findings)]
    assert ordered == ["critical", "high", "medium", "low"]


def test_verified_review_accepts_empty_findings():
    review = VerifiedReview.model_validate({"findings": []})
    assert review.findings == []


def test_verified_review_parses_full_finding():
    review = VerifiedReview.model_validate(
        {
            "findings": [
                {
                    "file": "src/db.py",
                    "line": 42,
                    "severity": "high",
                    "title": "SQL built with string formatting",
                    "body": "Use a parameterized query instead.",
                    "category": "security",
                    "verification_note": "The interpolated value comes from a request param.",
                }
            ]
        }
    )
    assert review.findings[0].severity is Severity.HIGH
    assert review.findings[0].category == "security"
