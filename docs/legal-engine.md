# Costa Rica legal data engine: design

Status: proposal, 2026-10-12. Scope: every primary and interpretive source Fact3 needs for labor, social security, tax, accounting, commercial and general administrative law in Costa Rica, stored so an AI can answer with exact, citable, dated text and never needs to scrape a website at question time.

## 1. What "extremely precise" requires

An answer is only as good as the text behind it. For legal work that means:

1. **Verbatim text at article level.** The unit a lawyer cites is the article (or transitorio, or inciso). Summaries are useful, but the answer must be able to quote the article itself.
2. **Exact lookup.** "Artículo 29 del Código de Trabajo" must return article 29, not the five articles that sound most similar.
3. **Time.** Laws are reformed. Every article needs the version it belongs to and the dates it was in force, so the engine can answer "what did the law say in 2024" when a client files late.
4. **Provenance.** Each article carries its source URL, the date it was retrieved, a hash of the source file, and the reform notes SCIJ prints under it ("Así reformado por...").
5. **Binding force.** A law, a decree, a DGT general resolution, a DGT oficio, a court ruling and a firm's blog post do not weigh the same. Every record says what it is.
6. **Refusal.** If the corpus does not contain it, the engine says so instead of letting the model fill the gap.

A plain vector database gives none of 2 to 6 by itself. That drives the architecture.

## 2. Git repo or vector database? Both, with different jobs

| Layer | Job | Where it lives |
| --- | --- | --- |
| **Source of truth** | Verbatim normalized texts, metadata, reform notes, versions | This Git repo, as JSONL and Markdown |
| **Serving index** | Fast exact lookup, keyword search, semantic search, filters by date and area | Built from the repo: SQLite file today, Postgres + pgvector in the app |
| **Explainers** | Plain-language guides that cite articles (`corpus/`) | This Git repo |

Why Git as the source of truth:

- **Diffs are the legal history.** When the Asamblea reforms an article, re-ingesting produces a one-line diff in `articles.jsonl`. `git log -p` on an article is its reform history. A database overwrites rows silently.
- **Review.** A change to the law store goes through a pull request and CI checks (article counts, numbering gaps, title match) before anything serves it.
- **Portable.** Any tool, model or vendor can read JSONL. The index can be rebuilt from scratch in seconds, so it is disposable.
- **Cheap.** Size estimate: about 120 norms, roughly 20,000 articles, under 50 MB of text. That is small for Git and tiny for any database.

Why an index on top:

- **Exact lookup** (norm + article + date) is a SQL query, not a similarity search.
- **Lexical search** (BM25 / Postgres full text with Spanish stemming) is the most precise retriever for legal terms such as "preaviso", "cesantía", "renta presuntiva".
- **Semantic search** (embeddings) catches paraphrased questions ("me pueden despedir estando embarazada") that share no words with the article.
- The engine runs both and merges them (reciprocal rank fusion), then returns the full article text with its citation.

Why not a dedicated vector database (Pinecone, Weaviate, etc.): at 20,000 to 60,000 vectors, pgvector or sqlite-vec are more than enough, keep everything in one place, and avoid a second vendor. Revisit only if the corpus grows by two orders of magnitude (for example full jurisprudence).

Recommended deployment:

1. **Now:** the MCP server in this repo builds an in-memory SQLite FTS5 index from the files at start. Zero infrastructure, works in Claude Code, Claude Desktop, Cursor.
2. **App:** a `build` step loads the same JSONL into Postgres (the app's database, or Supabase) with `tsvector` (Spanish config) and `pgvector` columns. The Fact3 app and an HTTP MCP endpoint query that.
3. **Embeddings:** computed at build time and stored next to each article, keyed by the article's content hash so unchanged articles are never re-embedded. Provider is an open decision.

## 3. Data model

```
norm            one law, decree, reglamento or resolution
  version       one consolidated text of that norm (SCIJ "versión"), with valid_from / valid_to
    unit        article, transitorio, or annex; verbatim text; reform notes; status
reference       unit -> unit or norm ("remite al artículo 8", "reformado por Ley 9343")
interpretation  ruling, oficio, dictamen or resolution that interprets units
explainer       corpus/ guide sections that cite units
```

Files in the repo:

```
laws/registry.json                    catalog of norms to ingest (curated, see section 5)
laws/<norm-id>/norm.json              metadata of the current version
laws/<norm-id>/articles.jsonl         one unit per line (current version)
laws/<norm-id>/text.md                human-readable rendering
```

Unit record (one line of `articles.jsonl`):

```json
{
  "id": "ley-2:art-29",
  "norm_id": "ley-2",
  "norm_title": "Código de Trabajo",
  "kind": "articulo",
  "number": "29",
  "heading": "",
  "path": ["Título Segundo ...", "Capítulo Cuarto ..."],
  "text": "verbatim article text",
  "notes": ["(Así reformado por ...)"],
  "status": "vigente",
  "area": "laboral",
  "rank": "ley",
  "version_date": "2026-05-12",
  "source_url": "https://sinalevi.go.cr/ResultadosNormativa/Informacion?param1=8045&param2=151754&param3=1",
  "retrieved_at": "2026-10-12",
  "source_sha256": "...",
  "text_sha256": "..."
}
```

Citation format everywhere: `ley-2:art-29` (norm id, unit). Explainers in `corpus/` link to units the same way, so a guide's claim can be checked against the article it summarizes.

Rank (binding force), highest first: `constitucion`, `tratado`, `ley`, `decreto` (reglamento ejecutivo), `resolucion-general` (DGT, CCSS, SUGEF), `jurisprudencia-vinculante` (Sala Constitucional), `jurisprudencia`, `dictamen-pgr` (binding on the administration that asked), `oficio` (informative only, art. 119 CNPT), `secondary`.

## 4. Versions and change tracking

- Each ingest records the SCIJ version date, the source hash and the per-article text hash.
- Git keeps every previous version. For point-in-time answers, the build step can load older versions from Git history into the index with `valid_from` / `valid_to`.
- A scheduled check (weekly) compares the SCIJ version of each registered norm with the stored one and opens a PR when something changed, listing which articles changed. Yearly items get a calendar reminder: minimum wages decree (December), income tax brackets decree (late in the year), CCSS base mínima contributiva.

## 5. Scope: what "everything" means

Norm ids are assigned at ingest; law numbers below are confirmed against the source title at ingest time (the ingester refuses a file whose title does not match).

**Labor (laboral)**
- Código de Trabajo, Ley 2 (includes the Reforma Procesal Laboral, Ley 9343, and riesgos del trabajo, Title IV)
- Ley de Protección al Trabajador, Ley 7983, and its reglamentos (ROP, FCL)
- Aguinaldo for private employees, Ley 2412
- Teletrabajo, Ley 9738, and reglamento
- Hostigamiento sexual en el empleo y la docencia, Ley 7476
- Igualdad de oportunidades para personas con discapacidad, Ley 7600
- Decreto de salarios mínimos (yearly)
- MTSS criteria (Dirección de Asuntos Jurídicos) as interpretation

**Social security (ccss)**
- Ley Constitutiva de la CCSS, Ley 17
- Reglamento del Seguro de Salud; Reglamento del Seguro de Invalidez, Vejez y Muerte
- Reglamento para la afiliación de los trabajadores independientes
- Reglamento del Seguro de Riesgos del Trabajo (INS)
- CCSS Junta Directiva agreements on base mínima contributiva and contribution scales

**Tax (tributario)**
- Código de Normas y Procedimientos Tributarios, Ley 4755, and Reglamento de Procedimiento Tributario
- Ley del Impuesto sobre la Renta, Ley 7092, and its reglamento
- Ley de Fortalecimiento de las Finanzas Públicas, Ley 9635 (IVA title, renta reforms, transitorios)
- Ley del Impuesto al Valor Agregado (Ley 6826 as reformed by Ley 9635) and Reglamento de la Ley del IVA
- Ley para Mejorar la Lucha contra el Fraude Fiscal, Ley 9416 (beneficiarios finales)
- Impuesto a las personas jurídicas, Ley 9428
- Régimen de Zonas Francas, Ley 7210, and reglamento
- Transfer pricing decree
- DGT general resolutions: comprobantes electrónicos (MH-DGT-RES-0027-2024), TRIBU-CR, deadlines
- Yearly decrees: income tax brackets, base amounts
- DGT oficios (informative), Tribunal Fiscal Administrativo rulings, Sala Primera tax rulings as interpretation

**Accounting (contable)**
- Ley de Regulación del Colegio de Contadores Públicos, Ley 1038, and reglamento
- Código de Comercio articles on accounting books and financial statements
- Legalización de libros (Registro Nacional / Hacienda rules)
- NIIF and NIIF para PYMES adoption: the Colegio's adoption circulars are ingestible; the IFRS standards themselves are copyrighted by the IFRS Foundation, so the engine stores references and Fact3's own summaries, not their verbatim text.

**Commercial and corporate (mercantil)**
- Código de Comercio, Ley 3284
- Ley 8262, Fortalecimiento de las PYMES, and reglamento (PYME registration)
- Ley 9699, responsabilidad de las personas jurídicas
- Ley 7786 and Ley 8204 (legitimación de capitales), SUGEF rules for virtual asset service providers

**General and administrative (general)**
- Constitución Política
- Código Civil, Ley 63
- Ley General de la Administración Pública, Ley 6227
- Código Procesal Contencioso-Administrativo, Ley 8508
- Protección al ciudadano del exceso de requisitos, Ley 8220
- Promoción de la Competencia y Defensa Efectiva del Consumidor, Ley 7472
- Protección de la persona frente al tratamiento de sus datos personales, Ley 8968
- Certificados, firmas digitales y documentos electrónicos, Ley 8454

**Interpretation layer** (phase 3): PGR dictámenes and opiniones jurídicas (SCIJ), Sala Constitucional, Sala Primera and Sala Segunda rulings (Nexus, Poder Judicial), Tribunal Fiscal Administrativo, DGT oficios. Stored with `rank`, date and the units they interpret; never mixed into the norm text.

## 6. Ingestion pipeline

1. **Acquire.** SCIJ consolidated text is the default source, because SCIJ prints reform notes under each article. Since 2026 SCIJ lives at `sinalevi.go.cr` (the old `pgrweb.go.cr/scij` links redirect there) and loads its text through two POST endpoints: `_CargarFicha` (version number, version date, article count) and `_CargarTextoCompleto` (the text, one fragment per unit, each followed by a "Ficha Artículo N" anchor). The ingester cuts units at those anchors, so SCIJ's own unit list decides the article count, and it checks that count against the ficha. Registry fields: `scij_nrm` (norm id, `param1`) and `scij_version` (version id, `param2`). La Gaceta, Hacienda, MTSS and CCSS publish what SCIJ lacks (resolutions, yearly decrees, circulars). The ingester also accepts a file saved from a browser (HTML or PDF), so any source can enter the pipeline.
2. **Snapshot.** The raw file is hashed (SHA-256). The hash and URL go into `norm.json`.
3. **Parse.** HTML or PDF to text lines, then split into units at "ARTÍCULO n" / "TRANSITORIO n" headings, tracking Libro / Título / Capítulo / Sección as the unit's path, and separating reform notes from the article text.
4. **Validate.** Title must match the registry; numbering gaps and duplicates are reported; zero-unit parses fail.
5. **Review and commit.** Diffs go through a PR. CI re-runs the checks.
6. **Build.** Index for MCP (now) and Postgres + pgvector (app).

Access constraint: the cloud environment used by Claude sessions cannot reach `sinalevi.go.cr`, `hacienda.go.cr` and most `.go.cr` hosts, so ingestion runs on Fact3's own machine for a short list of named norms, at least 5 seconds between requests. Neither `pgrweb.go.cr` nor `sinalevi.go.cr` publishes a robots.txt (checked 2026-10-12). Raw pages are cached in `laws/.cache/` (gitignored) and `ingest` reuses them unless `--refresh` is passed. Legal texts are public, but SCIJ's terms of use should be checked before running a scheduled refresh against it.

## 7. Contract for AI clients

MCP tools:

- `get_article(norm, article)`: exact verbatim text with notes, status, version and source.
- `search_law(query, area?, norm?)`: ranked units with citation ids.
- `list_norms(area?)`: what the engine covers, with version dates.
- Existing tools (`search_tax_kb`, `get_document`) for the explainers.

Rules served with the tools: quote the unit and cite its id; state the version date; say when a unit is derogado or the norm is not in the store; separate law from interpretation; leave final positions to a licensed professional.

## 8. Phases

1. **Store and ingester** (this PR): registry, article model, SCIJ/HTML/PDF parser, validation, search and MCP tools over units, tests on a synthetic fixture.
2. **First ingestion**: Código de Trabajo, CNPT, Ley 7092 and reglamento, Ley 9635, IVA and reglamento, Ley Constitutiva CCSS. Needs one of the access options in section 6.
3. **Rest of section 5**, explainers in `corpus/` relinked to units, weekly change check.
4. **Postgres + pgvector build** and hybrid ranking, once the embeddings provider is chosen.
5. **Interpretation layer** (PGR, courts, TFA, DGT oficios).

## 9. Decisions for Fact3

- Access route for ingestion (section 6).
- Embeddings provider and whether the app's Postgres hosts the index.
- Whether the repo should be renamed (for example `cr-legal-kb`) now that it covers more than tax.
