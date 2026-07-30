"""CLI entry point. Run `python -m reviewer --help` for usage.

Used both by the GitHub Action (action.yml calls this) and locally with
--dry-run to tune prompts without posting anything.
"""

import argparse
import asyncio
import logging
import os
import sys

from .github_client import GitHubClient
from .pipeline import run_review
from .schemas import sort_by_severity

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="reviewer",
        description="Multi-agent AI review of a GitHub pull request.",
    )
    parser.add_argument("--repo", required=True, help="owner/name, e.g. zumrywahid/ai-pr-reviewer")
    parser.add_argument("--pr", required=True, type=int, help="pull request number")
    parser.add_argument("--model", default="gemini-3.5-flash", help="model used by all agents")
    parser.add_argument("--max-findings", type=int, default=10, help="cap on findings posted per PR")
    parser.add_argument(
        "--skip-labels",
        default="no-ai-review",
        help="comma-separated PR labels that skip the review",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print findings instead of posting them to the PR",
    )
    return parser.parse_args()


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"error: {name} environment variable is not set")
    return value


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args()

    github_token = _require_env("GITHUB_TOKEN")
    # ADK's Gemini client reads GOOGLE_API_KEY; we accept the more obvious
    # GEMINI_API_KEY name too.
    if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
    _require_env("GOOGLE_API_KEY")

    client = GitHubClient(args.repo, github_token)
    pr = client.get_pr(args.pr)

    skip_labels = {label.strip() for label in args.skip_labels.split(",") if label.strip()}
    pr_labels = {label["name"] for label in pr.get("labels", [])}
    if skip_labels & pr_labels:
        logger.info("skipping: PR has label(s) %s", skip_labels & pr_labels)
        return

    diff = client.get_diff(args.pr)
    if not diff.strip():
        logger.info("skipping: empty diff")
        return

    review, truncated = asyncio.run(
        run_review(
            diff=diff,
            pr_title=pr.get("title", ""),
            pr_description=pr.get("body", ""),
            model=args.model,
        )
    )

    findings = sort_by_severity(review.findings)[: args.max_findings]
    if len(review.findings) > args.max_findings:
        logger.info(
            "capping findings: %d survived, posting top %d by severity",
            len(review.findings),
            args.max_findings,
        )

    if args.dry_run:
        if not findings:
            print("No findings survived verification.")
        for f in findings:
            print(f"\n[{f.severity.value}] ({f.category}) {f.file}:{f.line}")
            print(f"  {f.title}")
            print(f"  {f.body}")
            print(f"  survived because: {f.verification_note}")
        return

    client.post_review(
        number=args.pr,
        commit_sha=pr["head"]["sha"],
        findings=findings,
        truncated=truncated,
    )
    logger.info("posted %d finding(s) to %s#%d", len(findings), args.repo, args.pr)


if __name__ == "__main__":
    main()
