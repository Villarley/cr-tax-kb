---
id: tribu-cr
title: TRIBU-CR platform and declaration codes
topic: procedimiento
jurisdiction: CR
as_of: 2026-10-08
status: vigente
effective_from: 2025-10-06
verified: official
keywords_es: TRIBU-CR, ATV, OVi, oficina virtual, códigos de declaraciones, formulario 150, 101, 102, 104, 105, 153, 140, 270, D-104, D-101, D-151, D-270 mensual, MH-DGT-RES-0010-2026, declaraciones acumuladas, plazos, Hacienda Digital
sources:
  - label: Hacienda, consolidated new codification of declarations in TRIBU-CR
    url: https://www.hacienda.go.cr/docs/a_1NuevaCodificacionDeDeclaracionesEnTRIBU-CR-Consolidado_PP_PJ_PF.pdf
    type: official
  - label: Siempre al Día, changes in declarations with TRIBU-CR (cites MH-DGT-RES-0010-2026)
    url: https://siemprealdia.co/costa-rica/impuestos/cambios-en-declaraciones-tributarias-con-tribu-cr/
    type: secondary
    date: 2026
  - label: El Observador, TRIBU-CR starts October 6
    url: https://observador.cr/tribu-cr-arranca-el-6-de-octubre-datos-importantes-para-los-contribuyentes/
    type: secondary
---

# TRIBU-CR platform and declaration codes

## What it is
<!-- es: qué es TRIBU-CR, reemplazó ATV, Oficina Virtual OVi, 6 de octubre de 2025, sin API para declarar -->

TRIBU-CR is Hacienda's integrated tax platform. It went live on **October 6, 2025**, replacing ATV, TRAVI and DeclaraWeb; returns are filed only there, through the Oficina Virtual (OVi). There is no public filing API: in the Fact3 MVP the accountant files drafts by hand.

Declarations moved from "D-xxx" codes to three-digit codes. Old D-numbers can be ambiguous (for example the old informative D-151 is now 270, while the new 151 is an agricultural IVA return), so always use the new code.

## Codes Fact3 clients will use
<!-- es: códigos de formularios en TRIBU-CR, equivalencias con los antiguos D-104 D-101 D-151 D-105, 150 101 102 270 -->

| New | Old | Name | Frequency |
| --- | --- | --- | --- |
| 150 | D-104 | IVA, general (IVA01) | Monthly, by the 15th |
| 153 | D-105 | IVA, simplified regime | Quarterly |
| 155 | D-102 | IVA perceived on cross-border digital services (card issuers) | Daily |
| 157 | new | IVA, special regime for used goods | Monthly |
| 101 | D-101 | ISU, individual (annual income tax) | Annual |
| 102 | D-101 | ISU, legal entity | Annual |
| 104 / 105 | D-105 | ISU, simplified regime, individual / legal entity | Quarterly |
| 110 / 111 | D-162 | Capital gains and losses, individual / legal entity | Monthly |
| 113 / 114 | D-149 | Rentas de capital mobiliario | Monthly |
| 116 / 117 | D-125 | Rentas de capital inmobiliario | Monthly |
| 119 to 124 | new | Foreign-source passive income (see [[renta-capital]]) | Monthly |
| 137 / 138 | D-103 | Withholding on salaries | Monthly |
| 140 / 141 | D-103 | Withholding on remittances abroad | Monthly |
| 169 | D-195 | Impuesto a las personas jurídicas | Annual |
| 270 | D-151 | Summary of clients, suppliers and expenses without electronic invoice | Monthly from 2027 |
| 272 | D-195 | Inactive legal entities | Annual |
| 273 | new | Transfer pricing (informative) | Annual |

Other IVA codes: 151 and 152 (agricultural regime, four-monthly and annual), 154 (card withholding of IVA), 156 and 158 (IVA collected by registered cross-border digital intermediaries and providers).

## Deadline adjustments (MH-DGT-RES-0010-2026)
<!-- es: prórrogas y plazos de TRIBU-CR, declaraciones atrasadas o acumuladas de 2026 hasta el 25 de enero de 2027, declaración 270 mensual desde 2027, MH-DGT-RES-0010-2026 -->

Published March 20, 2026 (Alcance 30, La Gaceta 55):

- Declaration 270 for period 2025: due within the first 25 calendar days of June 2026 (June 25, 2026) without art. 83 CNPT sanctions.
- Monthly 2026 declarations can be filed in accumulated form up to **January 25, 2027**. Confirm which declarations this covers before relying on it.
- From 2027, declaration 270 becomes **monthly**, due in the first 25 days of the following month.

## Known issues
<!-- es: problemas de TRIBU-CR, fallas de migración, comprobante de presentación -->

TRIBU-CR had migration problems in its first months. Budget accountant time for manual fixes and keep the filing receipt for every return.
