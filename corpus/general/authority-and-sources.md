---
id: authority-and-sources
title: Legal hierarchy, binding force and where official texts live
topic: general
jurisdiction: CR
as_of: 2026-10-08
status: vigente
verified: secondary
keywords_es: jerarquía normativa, ley, reglamento, decreto ejecutivo, resolución de alcance general, oficio, consulta tributaria, artículo 119 CNPT, Código de Normas y Procedimientos Tributarios, SCIJ, La Gaceta, conservación de documentos, cuánto tiempo guardar facturas y registros contables, prescripción, cinco años
sources:
  - label: EY, DGT ruling on crypto assets (cites art. 119 CNPT on non-binding consultations)
    url: https://www.ey.com/es_ce/technical/tax/tax-alerts/costa-rica-la-dgt-emite-un-oficio-relacionado-con-el-tratamiento
    type: secondary
    date: 2023-09-07
  - label: Siempre al Día, withholding on non-residents (cites art. 109 CNPT, 5-year retention)
    url: https://siemprealdia.co/costa-rica/impuestos/retencion-a-no-domiciliados-en-costa-rica/
    type: secondary
    date: 2026
  - label: SCIJ (Sistema Costarricense de Información Jurídica), official consolidated texts
    url: https://pgrweb.go.cr/scij/
    type: primary
---

# Legal hierarchy, binding force and where official texts live

## Hierarchy of tax norms

Answer tax questions by citing the highest norm that settles them, in this order:

1. **Constitución Política** and international treaties (tax treaties are few for Costa Rica).
2. **Laws (leyes)** passed by the Asamblea Legislativa. The core ones for Fact3:
   - Ley 9635, Ley de Fortalecimiento de las Finanzas Públicas (2018). Título I is the Ley del Impuesto sobre el Valor Agregado (IVA). Título II reformed the Ley del Impuesto sobre la Renta.
   - Ley 7092, Ley del Impuesto sobre la Renta (as amended by Ley 9635).
   - Ley 4755, Código de Normas y Procedimientos Tributarios (CNPT): procedure, sanctions, consultations, record keeping.
   - Ley 17, Ley Constitutiva de la CCSS, plus CCSS regulations for social security.
3. **Reglamentos (decretos ejecutivos)**: Reglamento de la Ley del IVA, Reglamento de la Ley del Impuesto sobre la Renta, and yearly decrees that update brackets (for 2026, Decreto 45333-H).
4. **Resoluciones de alcance general** from the Dirección General de Tributación (DGT), numbered MH-DGT-RES-NNNN-YYYY (older ones DGT-R-NNN-YYYY). They bind taxpayers and the administration. Examples: MH-DGT-RES-0027-2024 (e-invoicing v4.4), MH-DGT-RES-0017-2023 (export-related IVA exemptions), MH-DGT-RES-0010-2026 (TRIBU-CR deadlines).
5. **Oficios / respuestas a consultas** (MH-DGT-OF-NNNN-YYYY): DGT answers to a specific taxpayer's question.

## Binding force of DGT consultations

Under article 119 of the CNPT, DGT answers to consultations of the general kind are **informative, not binding** ("tienen un carácter informativo"). Fact3 can rely on them as the administration's stated view (for example the crypto ruling MH-DGT-OF-0460-2023), but must flag them as non-binding in any client-facing advice and keep classification rules configurable.

## Record keeping

Article 109 of the CNPT requires keeping accounting records and their supporting documents for **5 years**. Fact3 should keep invoice XML, Hacienda responses, filing receipts and ledger sources for at least that long (the MVP plan already assumes 5 years of object storage).

## Where to get official texts

| Source | What | URL |
| --- | --- | --- |
| SCIJ (Procuraduría General) | Consolidated laws and decrees with reform history | https://pgrweb.go.cr/scij/ |
| Imprenta Nacional, La Gaceta | Official publication of laws, decrees, resolutions | https://www.imprentanacional.go.cr/ |
| Ministerio de Hacienda | Resolutions, TRIBU-CR guides, form codes, e-invoicing annexes | https://www.hacienda.go.cr/ |
| CCSS | Contribution scales and regulations for independent workers | https://www.ccss.sa.cr/ |

Note for maintainers: this container could not reach SCIJ or hacienda.go.cr directly (blocked by the network policy), so the first corpus relies on official PDFs reachable through other mirrors and on reputable secondary sources (Big Four alerts, specialist firms). Every chunk says which kind of source backs it.
