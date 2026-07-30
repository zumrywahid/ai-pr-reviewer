# AI PR Reviewer

[![CI](https://github.com/zumrywahid/ai-pr-reviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/zumrywahid/ai-pr-reviewer/actions/workflows/ci.yml)

> A GitHub Action that reviews your pull requests with a team of AI agents built on [Google ADK](https://google.github.io/adk-docs/). Three specialist reviewers run in parallel, an adversarial verifier throws out weak findings, and only the ones that survive get posted as comments on your PR.

**This repo reviews itself.** Open any pull request here and you'll see the action run and leave comments — check the [PRs tab](../../pulls) for live examples.

## Why this exists

Single-prompt AI code review has two problems I kept running into:

1. **One prompt trying to do everything does nothing well.** Ask a model to check correctness, security, and tests in one go and it gives you a shallow pass over each.
2. **False positives kill trust.** If the bot leaves ten comments and seven are noise, people stop reading all of them by the second PR.

This project fixes both with structure instead of a bigger prompt: specialists that each do one job, and a verifier whose only job is to attack their findings before you ever see them.

## How it works

```
PR opened / updated
        │
        ▼
  Fetch the diff (GitHub API)
        │
        ▼
┌──────────────────────────────────────────────┐
│               ParallelAgent                  │
│ ┌───────────┐ ┌──────────┐ ┌───────────────┐ │
│ │Correctness│ │ Security │ │ Test coverage │ │
│ └───────────┘ └──────────┘ └───────────────┘ │
└──────────────────────────────────────────────┘
        │  (all findings, structured JSON)
        ▼
  Adversarial verifier — tries to refute
  every finding; weak ones are dropped
        │
        ▼
  Surviving findings posted to the PR
```

Each specialist only sees the diff and its own instructions. The verifier sees everything and is prompted to *disprove* each finding — if it can't, the finding ships.

## Why Google ADK

I picked [ADK](https://google.github.io/adk-docs/) over raw API calls or other frameworks for a few concrete reasons:

- **Orchestration is a first-class primitive.** `ParallelAgent` runs the three specialists concurrently and `SequentialAgent` chains the review → verify pipeline. That's the whole orchestration layer — no hand-rolled asyncio, no queues.
- **Code-first, no YAML graphs.** Agents are plain Python objects. You can diff them, test them, and review changes to them like any other code — which matters for a tool that lives in CI.
- **Structured output built in.** Each agent returns findings against a Pydantic schema, so the pipeline passes typed data around instead of parsing markdown out of chat responses.
- **Agents share state cleanly.** Specialists write findings to session state with `output_key`; the verifier reads them straight from its instruction template. No glue code.
- **Model-agnostic.** It runs on Gemini out of the box (cheap and fast for this workload), but ADK can point at other models without rewriting the pipeline.

## Use it on your own repo

**1.** Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) and add it to your repo secrets as `GEMINI_API_KEY`.

**2.** Add `.github/workflows/pr-review.yml`:

```yaml
name: AI PR Review
on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: zumrywahid/ai-pr-reviewer@v1
        with:
          gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

That's it. The next PR gets reviewed.

### Configuration

| Input | Default | What it does |
|---|---|---|
| `gemini_api_key` | *(required)* | Gemini API key for the agents |
| `github_token` | *(required)* | Token used to read the diff and post comments |
| `model` | `gemini-2.5-flash` | Model used by all agents |
| `max_findings` | `10` | Cap on comments posted per PR |
| `skip_labels` | `no-ai-review` | PRs with this label are skipped |

## Where this is useful in real life

- **Small teams without enough reviewers.** The bot handles the first pass — obvious bugs, missing tests, injection risks — so the human review can focus on design.
- **Solo projects.** You get a second pair of eyes on every PR without asking anyone.
- **Big teams as a pre-filter.** Run it before requesting human review, so trivial issues are already fixed by the time a teammate looks.
- **Security-sensitive repos.** The security specialist consistently checks every diff for the boring-but-critical stuff (secrets in code, injection, authz mistakes) that humans skim past on Friday afternoons.

It's not a replacement for human review. It's a floor — nothing below a certain quality bar reaches your reviewers.

## Cost

Each PR review makes 4 model calls (3 specialists + 1 verifier) over the diff. On Gemini Flash that's typically under a cent per PR, and the free tier covers a hobby project comfortably.

## Running locally

```bash
git clone https://github.com/zumrywahid/ai-pr-reviewer
cd ai-pr-reviewer
pip install -e ".[dev]"

export GEMINI_API_KEY=your-key
export GITHUB_TOKEN=your-token

# Review any PR from your terminal
python -m reviewer --repo owner/name --pr 42 --dry-run
```

`--dry-run` prints the findings instead of posting them — useful for tuning prompts. Run the tests with `pytest`.

## Project structure

```
├── action.yml              # GitHub Action definition (composite action)
├── src/reviewer/
│   ├── agents.py           # The 3 specialists + verifier (ADK agents)
│   ├── schemas.py          # Pydantic models for findings
│   ├── github_client.py    # Fetch diff, post comments
│   ├── pipeline.py         # ParallelAgent + SequentialAgent wiring
│   └── __main__.py         # CLI entry point
├── tests/                  # Unit tests for the non-LLM parts
└── .github/workflows/
    ├── pr-review.yml       # This repo reviewing itself
    └── ci.yml              # Tests
```

## License

MIT
