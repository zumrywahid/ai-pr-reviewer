"""Thin GitHub REST client - just the four calls this project needs.

Deliberately not using PyGithub: the surface we need is tiny and keeping it
explicit makes the Action easier to debug when the API says no.
"""

import logging

import requests

from .schemas import VerifiedFinding

logger = logging.getLogger(__name__)

# Hidden marker so we can find and remove our own previous summary comment
# instead of stacking a new one on every push.
COMMENT_MARKER = "<!-- ai-pr-reviewer -->"

_SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
}


class GitHubClient:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.base = f"https://api.github.com/repos/{repo}"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "Accept": "application/vnd.github+json",
            }
        )

    def get_pr(self, number: int) -> dict:
        resp = self.session.get(f"{self.base}/pulls/{number}")
        resp.raise_for_status()
        return resp.json()

    def get_diff(self, number: int) -> str:
        resp = self.session.get(
            f"{self.base}/pulls/{number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    def post_review(
        self,
        number: int,
        commit_sha: str,
        findings: list[VerifiedFinding],
        truncated: bool,
    ) -> None:
        """Post findings as inline review comments where GitHub lets us,
        and everything else (plus a summary) as one regular comment."""
        leftovers = []
        inline_count = 0
        for finding in findings:
            if self._post_inline_comment(number, commit_sha, finding):
                inline_count += 1
            else:
                leftovers.append(finding)

        self._replace_summary_comment(
            number, self._summary_body(findings, leftovers, inline_count, truncated)
        )

    def _post_inline_comment(
        self, number: int, commit_sha: str, finding: VerifiedFinding
    ) -> bool:
        """GitHub rejects comments on lines that are not part of the diff
        (422). When that happens we fall back to the summary comment rather
        than failing the whole review."""
        resp = self.session.post(
            f"{self.base}/pulls/{number}/comments",
            json={
                "commit_id": commit_sha,
                "path": finding.file,
                "line": finding.line,
                "side": "RIGHT",
                "body": _inline_body(finding),
            },
        )
        if resp.status_code == 422:
            logger.warning(
                "could not anchor comment at %s:%s, moving it to the summary",
                finding.file,
                finding.line,
            )
            return False
        resp.raise_for_status()
        return True

    def _replace_summary_comment(self, number: int, body: str) -> None:
        # Remove our previous summary so re-pushes do not pile up comments.
        resp = self.session.get(
            f"{self.base}/issues/{number}/comments", params={"per_page": 100}
        )
        resp.raise_for_status()
        for comment in resp.json():
            if COMMENT_MARKER in (comment.get("body") or ""):
                self.session.delete(f"{self.base}/issues/comments/{comment['id']}")

        resp = self.session.post(
            f"{self.base}/issues/{number}/comments", json={"body": body}
        )
        resp.raise_for_status()

    @staticmethod
    def _summary_body(
        findings: list[VerifiedFinding],
        leftovers: list[VerifiedFinding],
        inline_count: int,
        truncated: bool,
    ) -> str:
        lines = [COMMENT_MARKER, "## 🤖 AI PR Review", ""]

        if not findings:
            lines.append(
                "The specialist reviewers raised no findings that survived "
                "adversarial verification. Nice."
            )
        else:
            lines.append(
                f"**{len(findings)} finding(s)** survived adversarial "
                f"verification ({inline_count} posted inline)."
            )
            lines.append("")
            lines.append("| Severity | Category | File | Finding |")
            lines.append("|---|---|---|---|")
            for f in findings:
                emoji = _SEVERITY_EMOJI.get(f.severity.value, "")
                lines.append(
                    f"| {emoji} {f.severity.value} | {f.category} "
                    f"| `{f.file}:{f.line}` | {f.title} |"
                )

        if leftovers:
            lines.append("")
            lines.append(
                "### Findings that could not be anchored to a diff line"
            )
            for f in leftovers:
                lines.append("")
                lines.append(f"**`{f.file}:{f.line}` — {f.title}**")
                lines.append("")
                lines.append(f.body)

        if truncated:
            lines.append("")
            lines.append(
                "> ⚠️ This PR's diff was too large to review in full - "
                "only the first part was reviewed."
            )

        lines.append("")
        lines.append(
            "<sub>Reviewed by [ai-pr-reviewer]"
            "(https://github.com/zumrywahid/ai-pr-reviewer) — three "
            "specialist agents + an adversarial verifier, built with "
            "Google ADK.</sub>"
        )
        return "\n".join(lines)


def _inline_body(finding: VerifiedFinding) -> str:
    emoji = _SEVERITY_EMOJI.get(finding.severity.value, "")
    return (
        f"{emoji} **{finding.severity.value} · {finding.category}** — "
        f"{finding.title}\n\n{finding.body}\n\n"
        f"<sub>Survived verification: {finding.verification_note}</sub>"
    )
