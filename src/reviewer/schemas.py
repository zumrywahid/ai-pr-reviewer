"""Pydantic models shared by every agent in the pipeline.

Specialists emit `ReviewFindings`. The verifier consumes all of them and
emits `VerifiedReview`, which is the only thing that ever reaches the PR.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Used to sort findings before applying the max_findings cap.
SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


class Finding(BaseModel):
    file: str = Field(description="Path of the file the finding applies to, exactly as it appears in the diff")
    line: int = Field(description="Line number in the NEW version of the file (the right side of the diff)")
    severity: Severity = Field(description="How bad this is if it ships: critical, high, medium or low")
    title: str = Field(description="One-line summary of the problem")
    body: str = Field(description="Explanation of the problem and a concrete suggestion for fixing it")


class ReviewFindings(BaseModel):
    """What each specialist returns."""

    findings: list[Finding] = Field(default_factory=list)


class VerifiedFinding(Finding):
    category: str = Field(description="Which specialist raised it: correctness, security or test-coverage")
    verification_note: str = Field(description="One sentence on why this finding survived adversarial verification")


class VerifiedReview(BaseModel):
    """What the verifier returns: only the findings it could not refute."""

    findings: list[VerifiedFinding] = Field(default_factory=list)


def sort_by_severity(findings: list[VerifiedFinding]) -> list[VerifiedFinding]:
    return sorted(findings, key=lambda f: SEVERITY_RANK[f.severity])
