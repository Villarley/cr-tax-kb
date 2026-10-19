# Instructions for AI agents

This repo is a knowledge base of Costa Rican tax and accounting rules. Use it to answer questions and to build software that applies those rules.

## How to find things

1. If the `cr-tax-kb` MCP server is available, call `search_tax_kb` first, then `get_document` for the full text.
2. Otherwise read [llms.txt](llms.txt) for the map, or search `corpus/` directly. Each `## ` section is self-contained.
3. `data/chunks.jsonl` has the same sections with metadata, one JSON object per line.
4. Verbatim legal texts live in `laws/<norm-id>/articles.jsonl` (one article per line). Use `get_article` for an exact article and `search_law` to find one; `list_norms` shows what is stored and what is only registered.

## How to answer

- Cite every claim with the chunk id (`iva-exports#1`) or document path, plus the source URL from the frontmatter.
- State the strength of the backing: `primary` (law or decree), `official` (Hacienda or CCSS document), `secondary` (firm or press analysis). Flag DGT oficios as informative, not binding (art. 119 CNPT).
- Never present a bill (`status: proyecto` or a "Pending legislation" section) as law.
- Amounts, brackets and rates change yearly: check `as_of` and `effective_from`, and say which year a number applies to.
- When an article is stored in `laws/`, quote it and cite its id (`ley-2:art-29`) and version date. Guides in `corpus/` explain; the article is the authority.
- If the corpus does not cover a question, say so instead of filling the gap from memory, and suggest adding it (see SOURCES.md).
- Final positions on a client's return are for a licensed contador público.

## How to edit

- One topic per file under `corpus/<topic>/<id>.md`. Keep the frontmatter fields used by the other files (see CONTRIBUTING.md).
- Write sections that stand alone: a retrieved section should make sense without the rest of the file.
- Right under each `## ` heading, add one line `<!-- es: ... -->` with Spanish terms and phrasings people would use to ask about that section. It is hidden when rendered and is what lets Spanish questions find the right section.
- Body in English, Spanish legal terms and short quotes from the law kept verbatim. Put Spanish search terms and typical questions in `keywords_es`.
- `[[id]]` links point to other documents by id.
- No em dashes.
- `laws/concepts.json` maps everyday questions to the central articles ("tengo jefe pero facturo" to `ley-2:art-18`). Add a concept only after reading its anchor articles; list registered but missing norms under `pending` so search warns. Check with the colloquial questions in `benchmark/questions.json`.
- Never edit `laws/<norm-id>/` by hand: re-run `cli ingest` so text, hashes and notes stay tied to the source. Add new norms to `laws/registry.json` first.
- After editing: `PYTHONPATH=src python3 -m cr_tax_kb.cli export` and `python3 -m unittest discover -s tests`.
