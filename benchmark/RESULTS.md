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

## Agent, preliminary (manual run, not yet `agent.py`)

Before `agent.py` existed, a fresh agent with no project context answered 22 of these questions (20 covered, 2 not covered). It used only the CLI equivalents of `search_law` and `get_article`.

| Measure | Result |
| --- | --- |
| Expected unit cited | 20 / 20 |
| Quotes verbatim (checked against `articles.jsonl`) | 20 / 20 |
| Correct "not covered" (aguinaldo, impuesto a personas jurídicas) | 2 / 2 |
| Cost | about 128,000 tokens for all 22 questions (about 5,800 per question, including the agent's own context); 17 tool calls; 141 s (about 6.4 s per question) |

In one case the agent read the article more carefully than the reference answer did. With three years of service, cesantía is 20.5 days per year (art. 29 c), not 19.5. The reference answer has been corrected.

## Agent benchmark (`agent.py`), pending

This run compares conditions A (engine), B (model memory) and C (whole norm pasted), with programmatic quote checks and an LLM judge. It has been built and dry-run, but not run yet: headless `claude` on the benchmark machine needs `claude /login`. The dry run already shows one result for condition C. Every Código de Trabajo question needs about 194,000 tokens of prompt and is skipped at the 180,000 limit.

## Limits

- The questions and reference answers were written by the engine's authors from the stored articles. They need professional review, and questions written blind, before they are quoted externally.
- Token figures in this file are characters / 4. `agent.py` records API-reported tokens.
- Latency was measured on an Apple Silicon laptop with the in-memory SQLite index (index build 41 ms).
