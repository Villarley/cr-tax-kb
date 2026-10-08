---
id: facturacion-electronica-v44
title: Electronic invoicing version 4.4
topic: facturacion
jurisdiction: CR
as_of: 2026-10-08
status: vigente
effective_from: 2025-09-01
verified: secondary
keywords_es: factura electrónica, comprobantes electrónicos, versión 4.4, MH-DGT-RES-0027-2024, tiquete electrónico, nota de crédito, nota de débito, factura electrónica de compra, factura electrónica de exportación, recibo electrónico de pago, REP, mensaje receptor, aceptación, clave numérica 50 dígitos, CABYS, medios de pago SINPE Móvil, descuentos, código QR, XML firmado, obligatoria desde setiembre 2025, compra de servicios a empresa extranjera, software extranjero
sources:
  - label: Deloitte, five relevant changes in comprobante 4.4
    url: https://www.deloitte.com/latam/es/services/tax/perspectives/cr-comprobante-electronico-4-4-cinco-cambios-relevantes.html
    type: secondary
  - label: KPMG, technical provisions for electronic vouchers (MH-DGT-RES-0027-2024)
    url: https://kpmg.com/cr/es/home/tendencias/2024/11/newsflash-noviembre-2024-4.html
    type: secondary
    date: 2024-11
  - label: Sovos, Costa Rica e-invoicing rules
    url: https://sovos.com/es/iva/reglas-fiscales/factura-electronica-costa-rica/
    type: secondary
  - label: Siempre al Día, QR code in v4.4 suspended
    url: https://siemprealdia.co/costa-rica/impuestos/suspension-codigo-qr-en-la-factura-electronica-4-4/
    type: secondary
---

# Electronic invoicing version 4.4

## Legal basis and dates

- Resolution **MH-DGT-RES-0027-2024** ("Disposiciones técnicas de los comprobantes electrónicos para efectos tributarios"), published November 2024 with its "Anexos y Estructuras" document.
- Mandatory from **September 1, 2025**. The original June 1, 2025 date was extended by the DGT (announcement of February 11, 2025).

## Document types (comprobantes)

- Factura electrónica (sale to an identified buyer)
- Tiquete electrónico (sale to a final consumer without a tax ID)
- Nota de crédito and nota de débito electrónicas (corrections)
- **Factura electrónica de compra** (the buyer issues it: purchases from simplified-regime sellers, and since 4.4 also services and intangibles bought from foreign providers without Costa Rican domicile, including the IVA)
- **Factura electrónica de exportación** (sales to foreign buyers, see [[iva-exports]])
- **Recibo electrónico de pago** (new in 4.4, see below)
- Mensaje receptor (the buyer's acceptance, partial acceptance or rejection of a received invoice)

Each document is a signed XML with a **50-digit numeric key** (clave), sent to Hacienda when issued; Hacienda answers with an acceptance or rejection message. Records are kept 5 years.

## The five main changes in 4.4 (Deloitte)

1. **Payment methods:** new fields and codes to report digital payments such as SINPE Móvil and other platforms, so Hacienda can trace them.
2. **Combos and packages:** the seller must break down items bundled into a package.
3. **Discounts:** ten discount type codes (loyalty, volume, seasonal, promotional, commercial, other, and more) instead of a free-text description.
4. **Purchase invoice extended:** factura electrónica de compra now covers services and intangibles bought from foreign providers, with the import IVA included. Not for tangible goods that go through customs.
5. **Recibo electrónico de pago (REP):** for credit sales by independent professionals and small and medium businesses (not large taxpayers). It lets them pay the IVA when the customer pays rather than when invoicing (credit sales up to 90 days).

## Other points to confirm in the annexes

- **CABYS** codes (Catálogo de Bienes y Servicios) are required per line item and determine the IVA rate; Fact3 should map client services to CABYS codes.
- The **QR code** foreseen in 4.4 was reported as suspended (Siempre al Día). Check current status before generating one.
- The deadline for the buyer's mensaje receptor and its effect on the IVA credit: confirm in the resolution text (the automation spec already flags this for the accountant).

## Relevance to Fact3

- Freelancers paid by foreign clients issue **export invoices**; GrantFox-style companies receive **regular invoices** from local contractors and issue export invoices to foreign funders.
- Buying foreign SaaS or services: issue a factura electrónica de compra (reverse charge IVA) so the cost is deductible and the IVA is accounted for.
- The MVP uses an existing provider API (Alegra, GTI, Factura Profesional candidates) that handles XML signing and the Hacienda API.
