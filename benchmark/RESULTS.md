# Benchmark results

Run of 2026-10-12 on the ten phase 2 norms (1,914 units): Código de Trabajo, Ley de Protección al Trabajador, Ley Constitutiva de la CCSS, Código Tributario, Reglamento de Procedimiento Tributario, Ley del Impuesto sobre la Renta and its reglamento, Ley 9635, Ley del IVA and its reglamento. Question set: [questions.json](questions.json), 62 questions, **pending professional review**. Raw numbers: [results/retrieval-2026-10-12.json](results/retrieval-2026-10-12.json). How to re-run: [README.md](README.md).

## Headline

| | Engine | Reading the whole norm |
| --- | --- | --- |
| Text an agent reads per question | about 3,500 tokens (search with 5 results + one article) | about 105,000 tokens on average for these questions; 194,000 for the Código de Trabajo |
| Local latency | 1.7 ms p50, 2.7 ms p95 per search; about 100 ms per CLI call | network fetch of a 0.2 to 5 MB page per question |
| Verbatim, versioned citation | yes, unit id + version date on every result | depends on the model copying correctly |
| Fits a 200k context | always | not for the Código de Trabajo |

That is roughly **30 times less text per question**. When an agent scraped the raw SCIJ HTML instead of clean text, it read about 3.6 million tokens to cover these ten norms.

## Retrieval (`retrieval.py`, 52 covered questions)

| Metric | No area filter | With area filter |
| --- | --- | --- |
| recall@1 | 42% | 46% |
| recall@3 | 75% | 77% |
| recall@5 | 83% | 83% |
| MRR@10 | 0.59 | 0.62 |

By area (no filter): labor 79% recall@3 (24 questions), tax 71% (24), CCSS 75% (4).
By phrasing: professional 88% recall@3 (17), client 69% (35).

The synonym list in `search.py` was tuned on the first 20 questions. On those 20, recall@3 is 80%. On the 32 questions added afterwards it is 72%, which is the more honest number.

There are 9 questions where the expected unit is not in the top 5. In most of them a neighbouring article wins, for example art. 82 instead of art. 81, or 31 bis instead of 31 ter. The other cause is client wording that shares no words with the article ("dar de mamar" vs "lactancia", "rebajan del salario" vs "retención"). Semantic search (embeddings) is the planned fix (docs/legal-engine.md, phase 4).

**Refusal.** The top-1 BM25 score is 29 on average for covered questions and 22 for not-covered ones, and the two ranges overlap (covered 10 to 59, not covered 13 to 44). A score threshold alone cannot detect "not covered". Refusal has to come from the model checking `list_norms` and reading the article, which is what the agent benchmark measures.

## Agent benchmark (`agent.py`, run of 2026-10-12/13)

Model: `claude-sonnet-5` through the Claude Code CLI in headless mode (2.1.212), judged by the same model. Raw records, prompts and the judge prompt: [results/agent-2026-10-12.json](results/agent-2026-10-12.json).

Condition A (engine tools only) ran all 62 questions. Condition B (model memory, no tools) stopped at 34 of 62 questions when the budget cap was reached: the 28 labor and CCSS questions plus the first 6 tax questions. Condition C (whole law pasted) was not run.

**Paired, on the 34 questions both conditions answered (all covered):**

| | A, engine | B, memory |
| --- | --- | --- |
| Expected article cited | 34 / 34 | 21 / 34 |
| Quotes verbatim (checked against `articles.jsonl`) | 32 / 34 | 1 / 34 |
| Judge: correct / partial / incorrect | 31 / 0 / 2 (1 unjudged) | 22 / 4 / 7 (1 unjudged) |
| Said "not covered" when it was covered | 0 | 4 |

**Condition A on all 62 questions:**

| Measure | Result |
| --- | --- |
| Expected article cited (52 covered) | 96% (50 / 52) |
| Quotes verbatim | 85% (44 / 52) |
| Judge correct (51 judged) | 94% correct, 6% incorrect |
| Correct "not covered" (10 uncovered) | 9 / 10 (the 10th omitted its answer block) |
| False refusals | 0 |

**Cost and time per answer:**

| | A, engine | B, memory |
| --- | --- | --- |
| Input tokens, mean (median) | 41,300 (34,800) | 12,300 (12,300) |
| Output tokens, mean | 1,570 | 3,380 |
| Tool calls, mean | 1.9 | 0 |
| Cost, mean (median) | $0.128 ($0.118) | $0.106 ($0.099) |
| Wall time, mean (median) | 21 s (19 s) | 44 s (37 s) |

The judge adds about $0.12 per answer. The whole run cost $22.06.

**How to read this.**
- Without the engine, the same model cites the right article in only 62% of answers and almost never quotes the law word for word. It also refuses 12% of answerable questions. With the engine it cites the right article in 96% of answers, quotes verbatim in 85% and is judged correct in 94%.
- With the engine, answers are faster and shorter. Each one costs a little more because the article text comes into the context.
- About 19,000 of the engine's input tokens are Claude Code's own fixed context. A leaner client (direct API with only the three tools) would pay mostly for the 3,500 tokens of law text measured above.

**Known failures with the engine.**
- lab-02: the model read the cesantía table of art. 29 as cumulative.
- lab-07: the model stitched two sentences of art. 94 bis into one quote.
- 2 covered questions where the expected article was not cited.
- Remaining non-verbatim quotes: mostly paraphrases inside quotation marks.
- Each case is in the results file with the grader's per-quote detail.

**Earlier manual run.** Before `agent.py` existed, a fresh agent using only the CLI answered 22 of these questions. It cited the expected article in 20 / 20, quoted verbatim in 20 / 20 and refused both uncovered questions correctly.

## Limits

- The questions and reference answers were written by the engine's authors from the stored articles. They need professional review, and questions written blind, before they are quoted externally.
- Token figures in this file are characters / 4. `agent.py` records API-reported tokens.
- Latency was measured on an Apple Silicon laptop with the in-memory SQLite index (index build 41 ms).
