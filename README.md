# cr-tax-kb

Costa Rica tax and accounting knowledge base, written so any AI (or person) can read it, search it and cite it. Built for [Fact3](#used-by), useful to anyone working on Costa Rican taxes.

As of 2026-10-08. Not legal or tax advice: final positions on a return belong to a licensed contador público.

## What's inside

| Topic | Documents |
| --- | --- |
| general | [authority-and-sources](corpus/general/authority-and-sources.md): hierarchy of norms, binding force of DGT rulings, record keeping |
| iva | [iva-general](corpus/iva/iva-general.md), [iva-exports](corpus/iva/iva-exports.md), [regimen-simplificado](corpus/iva/regimen-simplificado.md) |
| renta | [renta-territoriality](corpus/renta/renta-territoriality.md) (ISU, 2026 brackets), [renta-capital](corpus/renta/renta-capital.md), [remesas-exterior](corpus/renta/remesas-exterior.md) |
| cripto | [crypto-assets](corpus/cripto/crypto-assets.md) |
| facturacion | [facturacion-electronica-v44](corpus/facturacion/facturacion-electronica-v44.md) |
| procedimiento | [tribu-cr](corpus/procedimiento/tribu-cr.md) (form codes), [calendar](corpus/procedimiento/calendar.md) |
| ccss | [ccss-independientes](corpus/ccss/ccss-independientes.md) |

**Legal texts** ([laws/](laws/)): verbatim laws, decrees and reglamentos stored article by article, with version date, reform notes, status (vigente or derogado) and source hash. The catalog of norms to hold (labor, CCSS, tax, accounting, commercial, general) is [laws/registry.json](laws/registry.json); the design is in [docs/legal-engine.md](docs/legal-engine.md). Ingestion is set up; texts are added as sources become reachable.

Every document has YAML frontmatter with its sources, the date it was checked, whether the rule is in force, and how strong its backing is (`primary` law text, `official` Hacienda/CCSS document, or `secondary` analysis). Gaps and pending primary texts are tracked in [SOURCES.md](SOURCES.md).

## Ways to use it

**1. Read the files.** Plain Markdown. Start at [llms.txt](llms.txt) or [AGENTS.md](AGENTS.md).

**2. MCP server** (any MCP client: Claude Desktop, Claude Code, Cursor, others). Python 3.10+, no dependencies.

```json
{
  "mcpServers": {
    "cr-tax-kb": {
      "command": "python3",
      "args": ["/absolute/path/to/cr-tax-kb/src/cr_tax_kb/mcp_server.py"]
    }
  }
}
```

Claude Code: `claude mcp add cr-tax-kb -- python3 /absolute/path/to/cr-tax-kb/src/cr_tax_kb/mcp_server.py`. Inside this repo the bundled [.mcp.json](.mcp.json) already registers it.

Tools: `search_tax_kb(query, k?, topic?)`, `get_document(id)`, `list_documents(topic?)`, `get_sources(id?)` for the guides, and `search_law(query, k?, area?, norm?)`, `get_article(norm, article)`, `list_norms(area?)` for the verbatim legal texts. Each document is also a resource at `crtax://doc/<id>`.

**3. Command line**

```
PYTHONPATH=src python3 -m cr_tax_kb.cli search "¿cómo tributa la venta de bitcoin?"
PYTHONPATH=src python3 -m cr_tax_kb.cli show crypto-assets
PYTHONPATH=src python3 -m cr_tax_kb.cli list
PYTHONPATH=src python3 -m cr_tax_kb.cli norms
PYTHONPATH=src python3 -m cr_tax_kb.cli article ley-2 29
PYTHONPATH=src python3 -m cr_tax_kb.cli law "preaviso despido" --area laboral
```

Ingest a norm from the registry, from its SCIJ id or from a file saved in a browser (HTML or PDF):

```
PYTHONPATH=src python3 -m cr_tax_kb.cli ingest ley-2
PYTHONPATH=src python3 -m cr_tax_kb.cli ingest ley-2 --file ~/Downloads/codigo-trabajo.html --url "https://sinalevi.go.cr/ResultadosNormativa/Informacion?param1=8045&param2=151754&param3=1"
```

The ingester refuses a source whose title does not match the registry, and reports numbering gaps and duplicates as warnings in `norm.json`.

**4. Data files** for apps and vector databases: [data/index.json](data/index.json) (document manifest) and [data/chunks.jsonl](data/chunks.jsonl) (one citable section per line with metadata). Regenerate with `PYTHONPATH=src python3 -m cr_tax_kb.cli export`.

## How search works

BM25 over an in-memory SQLite FTS5 index, built at start from `corpus/`. Accents are folded and Spanish words are crudely stemmed. Body text is English with Spanish legal terms. Each section carries its own Spanish search terms in a hidden `<!-- es: ... -->` line (weighted highest), and each document's `keywords_es` adds a weaker document-level signal. Embedding search (to rank sections better across languages) is the next step; `data/chunks.jsonl` is ready to embed.

## Quality checks

```
python3 -m unittest discover -s tests
```

Checks frontmatter, source URLs, no em dashes, that `data/` matches the corpus, the MCP handshake, and the retrieval evals: [eval/questions.json](eval/questions.json) (right document) and [eval/sections.json](eval/sections.json) (right section). CI runs the same on every push.

The legal engine has its own benchmark in [benchmark/](benchmark/README.md): 62 labor, CCSS and tax questions. It measures retrieval recall, latency and tokens per answer against reading the whole law, and an end-to-end agent comparison (engine, model memory, pasted law text). Latest numbers: [benchmark/RESULTS.md](benchmark/RESULTS.md).

## Used by

Fact3, a web3 accounting service for Costa Rica: the app's tax engine and Claude sessions on the project read this repo.
