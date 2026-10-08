# Adding or updating knowledge

1. Find the right file under `corpus/<topic>/`, or create `corpus/<topic>/<id>.md`.
2. Frontmatter:

```yaml
---
id: iva-exports                 # stable, used in citations
title: IVA on exports of services and goods
topic: iva                      # general, iva, renta, cripto, facturacion, procedimiento, ccss
jurisdiction: CR
as_of: 2026-10-08               # last checked
effective_from: 2019-07-01      # optional
status: vigente                 # vigente, proyecto, propuesta, or a short note
verified: primary               # primary, official, secondary
keywords_es: exportación de servicios, exención IVA, ...
sources:
  - label: Ley 9635, arts. 4, 8 and 28
    url: https://...
    type: primary               # primary, official, secondary
    date: 2023-08               # optional
---
```

3. Add the fact as a self-contained `## ` section, citing the article or resolution number in the text.
4. Add the source to [SOURCES.md](SOURCES.md) and remove the gap if it is now filled.
5. Add a question to `eval/questions.json` that should retrieve the document.
6. Run `PYTHONPATH=src python3 -m cr_tax_kb.cli export` and `python3 -m unittest discover -s tests`.

When a rule changes (new year's brackets, a new resolution), update the section, bump `as_of`, and keep the old value in a short "Previous" line if clients may still file for that year.
