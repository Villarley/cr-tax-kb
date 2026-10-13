# Benchmark

Measures how well the legal engine (`laws/` plus `search_law` / `get_article`) answers Costa Rican labor, social security and tax questions, and what it costs compared with an agent that reads the whole law or answers from memory.

Results and method: [RESULTS.md](RESULTS.md). Raw numbers: `results/`.

## Files

| File | What it is |
| --- | --- |
| `questions.json` | 62 questions (52 covered by the stored norms, 10 not covered), client and professional phrasing, with expected unit ids and a short reference answer. Status: pending professional review. |
| `retrieval.py` | Retrieval benchmark. No network, no model calls, deterministic apart from latency. Runs in CI through `tests/test_benchmark.py`. |
| `agent.py` | End-to-end benchmark with a real model through the `claude` CLI in headless mode, under three conditions. Not run in CI. |
| `results/` | One JSON file per run: `retrieval-<date>.json`, `agent-<date>.json`. |

## Retrieval benchmark

```
python3 benchmark/retrieval.py --out benchmark/results/retrieval-$(date +%F).json
```

Reports recall@1/3/5 and MRR@10 for `search_law` (with and without the area filter, by area and by phrasing style), p50/p95 search latency, approximate tokens returned per call (characters / 4), the top-1 score of covered versus not covered questions, and the tokens an agent would read if it loaded the whole norm instead (`laws/<id>/text.md`, and the raw SCIJ page when `laws/.cache/` is present).

`tests/test_benchmark.py` fails if recall@3 or MRR drop below the thresholds set there. Raise them when retrieval improves.

## Agent benchmark

Needs the Claude Code CLI logged in (`claude /login`). Check first without spending anything:

```
python3 benchmark/agent.py --dry-run --limit 3
```

Full run (about 62 questions x 3 conditions plus one judge call per covered answer):

```
python3 benchmark/agent.py --model sonnet --jobs 2
```

Conditions:

- **A, engine.** Only the `cr-tax-kb` MCP tools (`search_law`, `get_article`, `list_norms`); no other tools, no web.
- **B, memory.** No tools. The model answers from what it knows.
- **C, page.** No tools. The full text of the relevant norm (`laws/<id>/text.md`, the same body as the SCIJ page) is pasted into the prompt, which is what a scraping agent would have to read. Prompts above 180,000 approximate tokens are not sent and are recorded as `skipped_context`.

Every answer must end with a JSON block of cited unit ids, verbatim quotes and a `covered` flag. Grading:

- `right_unit`: an expected unit id is cited.
- `quote_verbatim`: every quote appears word for word in a cited stored unit (programmatic check against `laws/<id>/articles.jsonl`).
- `refusal_correct` / `false_refusal`: whether the model said "not covered" when it should and only then.
- Judge verdict (correct, partial, incorrect) from a separate model call that sees the question, the reference answer and the candidate. The judge prompt is stored in the results file.

The results file also records input and output tokens (including cache reads), cost, wall time, tool calls, the model names the CLI reported, `claude --version` and the git commit.

Useful flags: `--conditions A,C`, `--ids lab-01,tax-04`, `--limit 10`, `--judge-model opus`.

## Limits

- The question set was written from the stored articles by the same team that built the engine. It needs review by a lawyer or contador, and new questions written blind, before the numbers are quoted outside the project.
- Token counts in `retrieval.py` are characters / 4. They are approximate for Spanish; `agent.py` uses the counts the API reports.
- Retrieval is lexical (BM25 with a small synonym list). Questions phrased far from the law's wording are the known weak spot.
