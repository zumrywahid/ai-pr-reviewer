import json

from reviewer.pipeline import MAX_DIFF_CHARS, _as_review, truncate_diff
from reviewer.schemas import VerifiedReview


def test_truncate_diff_leaves_small_diffs_alone():
    diff = "diff --git a/x b/x\n+hello\n"
    result, truncated = truncate_diff(diff)
    assert result == diff
    assert truncated is False


def test_truncate_diff_cuts_at_file_boundary():
    file_block = "diff --git a/f b/f\n" + ("+line\n" * 2000)
    diff = "\n".join([file_block] * 20)
    result, truncated = truncate_diff(diff)
    assert truncated is True
    assert len(result) <= MAX_DIFF_CHARS
    # The cut should land at the start of a file block, not mid-hunk.
    assert result.endswith("+line\n") or result.rstrip().endswith("+line")


def test_as_review_accepts_dict_and_json_string():
    payload = {"findings": []}
    assert _as_review(payload) == VerifiedReview()
    assert _as_review(json.dumps(payload)) == VerifiedReview()
    assert _as_review(None) == VerifiedReview()
