# Sources and gaps

As of 2026-10-08. "Read" means the content was fetched and summarized for this corpus; "cited" means only referenced.

## Primary and official

| Source | Status | Used in |
| --- | --- | --- |
| [Ley 9635](https://www.uned.ac.cr/ejecutiva/images/direccion-financiera/leyes_decretos/ley_9635.pdf) (UNED mirror), IVA arts. 1, 4, 8, 10, 11, 27, 28, 35 to 43; Renta art. 1 | Read (partial: text cut at Renta art. 15) | iva-general, iva-exports, regimen-simplificado, renta-territoriality |
| [Hacienda, TRIBU-CR declaration codes](https://www.hacienda.go.cr/docs/a_1NuevaCodificacionDeDeclaracionesEnTRIBU-CR-Consolidado_PP_PJ_PF.pdf) | Read | tribu-cr, renta-capital, remesas-exterior |
| [Reglamento de la Ley del IVA](https://uned.cr/ejecutiva/direccionfinanciera/images/direccion-financiera/leyes_decretos/reglamento_iva.pdf) | Cited | iva-general |

## Secondary (read)

- EY: [2026 brackets, Decreto 45333-H](https://www.ey.com/es_ce/technical/tax/tax-alerts/costa-rica-ministerio-de-hacienda-establecio-los-tramos-del-impuesto-sobre-la-renta-para-el-periodo-fiscal-2026), [crypto oficio MH-DGT-OF-0460-2023](https://www.ey.com/es_ce/technical/tax/tax-alerts/costa-rica-la-dgt-emite-un-oficio-relacionado-con-el-tratamiento), [export-related exemptions MH-DGT-RES-0017-2023](https://www.ey.com/es_ce/technical/tax/tax-alerts/costa-rica-la-dgt-emite-resolucion-sobre-servicios-relacionados), [CCSS reduced BMC](https://www.ey.com/es_ce/technical/tax/tax-alerts/costa-rica-se-aprueba-reduccion-de-la-base-minima-contributibutiva-a-la-ccss)
- Deloitte: [comprobante 4.4, five changes](https://www.deloitte.com/latam/es/services/tax/perspectives/cr-comprobante-electronico-4-4-cinco-cambios-relevantes.html)
- Siempre al Día: [withholding on non-residents](https://siemprealdia.co/costa-rica/impuestos/retencion-a-no-domiciliados-en-costa-rica/), [TRIBU-CR declaration changes](https://siemprealdia.co/costa-rica/impuestos/cambios-en-declaraciones-tributarias-con-tribu-cr/)
- El Observador: [capital gains](https://observador.cr/ganancias-de-capital-como-tributan/)
- Abogado Tributario: [CCSS scale for independents 2026](https://abogadotributario.cr/blog/el-costo-de-ser-trabajador-independiente-en-costa-rica/)

## Legal texts (laws/)

Verbatim norms are tracked in [laws/registry.json](laws/registry.json) and ingested with `cli ingest`. Phase 2 (first ingestion): Código de Trabajo, Ley 7983, Ley Constitutiva de la CCSS, CNPT and its reglamento, Ley 7092 and its reglamento, Ley 9635, Ley del IVA and its reglamento. None stored yet: SCIJ and the `.go.cr` sites are not reachable from the cloud environment (see docs/legal-engine.md, section 6).

## Gaps to fill next (in priority order)

1. **Primary texts from SCIJ** (blocked from the cloud container): Ley 7092 consolidated (art. 23 corporate 30% rate, partial payments, chapter XI capital income rates and exemptions, art. 59 remittances), CNPT arts. 109 and 119, Reglamento del IVA.
2. **Decreto 45333-H** text, to confirm the 2026 brackets (the 0% individual threshold jump looks large).
3. **MH-DGT-RES-0027-2024** and its annexes: document types, mensaje receptor deadline, CABYS, REP conditions, QR status.
4. **MH-DGT-RES-0010-2026**: exact scope of the January 25, 2027 accumulated filing.
5. **CCSS**: official contribution scale for independents and current BMC.
6. **Régimen simplificado** regulation: eligible activities and limits.
7. **Bill 25.796** text and status, and the legal basis of TRIBU-CR codes 119 to 124.
8. **Crypto**: any DGT oficios after 2023, and the written legal opinion Fact3 plans to get.
9. **Accounting**: NIIF para PYMES adoption by the Colegio de Contadores Públicos, books required for personas jurídicas (legalización de libros).
