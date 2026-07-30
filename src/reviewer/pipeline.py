"""Wires the agents together and runs the whole review.

Shape of the pipeline:

    SequentialAgent
    ├── ParallelAgent          (the three specialists, concurrently)
    │   ├── correctness_reviewer
    │   ├── security_reviewer
    │   └── test_coverage_reviewer
    └── adversarial_verifier   (reads their findings from session state)

The diff goes in as the user message, so every specialist sees it. Each
specialist writes structured findings to session state via output_key; the
verifier gets them injected into its instruction and returns the survivors.
"""

import json
import logging

from google.adk.agents import ParallelAgent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from .agents import build_specialists, build_verifier
from .schemas import VerifiedReview

logger = logging.getLogger(__name__)

APP_NAME = "ai-pr-reviewer"

# Keeps us inside the model context window on huge PRs. If a diff is bigger
# than this we review what fits and say so in the summary comment.
MAX_DIFF_CHARS = 80_000


def build_pipeline(model: str) -> SequentialAgent:
    review_panel = ParallelAgent(
        name="review_panel",
        sub_agents=build_specialists(model),
    )
    return SequentialAgent(
        name="pr_review_pipeline",
        sub_agents=[review_panel, build_verifier(model)],
    )


def _as_review(raw) -> VerifiedReview:
    """State values can come back as a dict or a JSON string depending on
    the ADK version - accept both."""
    if raw is None:
        return VerifiedReview()
    if isinstance(raw, str):
        raw = json.loads(raw)
    return VerifiedReview.model_validate(raw)


def truncate_diff(diff: str) -> tuple[str, bool]:
    if len(diff) <= MAX_DIFF_CHARS:
        return diff, False
    # Cut at a file boundary where possible so we do not hand the model
    # half a hunk.
    cut = diff.rfind("\ndiff --git", 0, MAX_DIFF_CHARS)
    if cut <= 0:
        cut = MAX_DIFF_CHARS
    return diff[:cut], True


async def run_review(
    diff: str,
    pr_title: str,
    pr_description: str,
    model: str,
) -> tuple[VerifiedReview, bool]:
    """Run the full pipeline over one PR. Returns the surviving findings
    and whether the diff had to be truncated."""
    diff, truncated = truncate_diff(diff)

    prompt = (
        f"Review this pull request.\n\n"
        f"Title: {pr_title}\n\n"
        f"Description:\n{pr_description or '(no description)'}\n\n"
        f"Diff:\n```diff\n{diff}\n```"
    )

    runner = InMemoryRunner(agent=build_pipeline(model), app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id="ci"
    )

    async for event in runner.run_async(
        user_id="ci",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if event.author and event.is_final_response():
            logger.info("agent %s finished", event.author)

    session = await runner.session_service.get_session(
        app_name=APP_NAME, user_id="ci", session_id=session.id
    )
    review = _as_review(session.state.get("verified_review"))
    logger.info("verifier kept %d finding(s)", len(review.findings))
    return review, truncated
