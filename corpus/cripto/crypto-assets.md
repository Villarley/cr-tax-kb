---
id: crypto-assets
title: Tax treatment of crypto assets in Costa Rica
topic: cripto
jurisdiction: CR
as_of: 2026-10-08
status: vigente (criterio no vinculante)
verified: secondary
keywords_es: criptomonedas, criptoactivos, activos virtuales, activo intangible, bitcoin, USDC, stablecoin, MH-DGT-OF-0460-2023, oficio DGT, ganancias de capital, impuesto sobre las utilidades, IVA comisiones exchange, remesas al exterior, BCCR moneda de curso legal, proyecto de ley 25.796, rentas del exterior, me pagan en cripto o USDC por mi trabajo, salario en cripto, qué impuesto aplica
sources:
  - label: EY, DGT issues ruling on tax treatment of crypto assets (MH-DGT-OF-0460-2023)
    url: https://www.ey.com/es_ce/technical/tax/tax-alerts/costa-rica-la-dgt-emite-un-oficio-relacionado-con-el-tratamiento
    type: secondary
    date: 2023-09-07
  - label: Delfino, government presents bills to tax foreign income (Bill 25.796)
    url: https://www.delfino.cr/2026/09/gobierno-presenta-dos-proyectos-para-gravar-rentas-del-exterior-y-recortar-exoneraciones
    type: secondary
    date: 2026-09
---

# Tax treatment of crypto assets in Costa Rica

## The DGT's position (oficio MH-DGT-OF-0460-2023)

Dated August 23, 2023. Because the Banco Central de Costa Rica does not recognize crypto as legal tender, the DGT treats it as **virtual assets, which are intangible assets** ("activos virtuales (activos intangibles)"). It is not money and not a foreign currency for tax purposes.

The oficio is an answer to a consultation, so under art. 119 CNPT it is **informative, not binding** (see [[authority-and-sources]]).

## Income tax

| Situation | Tax | Rate |
| --- | --- | --- |
| Gains from buying and selling crypto held as personal wealth (investor) | IRCGPC, capital gains | 15% on the gain (see [[renta-capital]]) |
| Returns from crypto investments (yield, staking-like returns) | IRCGPC, capital income | 15% |
| Crypto tied to a lucrative activity (trading business, a company's treasury used in its business) | ISU | Progressive or corporate rates (see [[renta-territoriality]]) |
| Commissions for organizing, verifying or exchanging virtual assets (exchanges, brokers, validators acting as a business) | ISU | Ordinary rates |

**Getting paid in crypto for work** is ordinary business income (ISU) valued in colones on the date received. The later sale or swap of that crypto is a second event that can produce a gain or loss, measured from the value at receipt.

## IVA

Services related to virtual assets, including buying and selling them, are subject to IVA, and so are the commissions on those services. The crypto itself is not a taxable "sale of goods" for the holder; the IVA lands on the service provider's fee.

## Territoriality

- A Costa Rica-resident provider of crypto services earns Costa Rican-source ISU income.
- A non-resident providing a crypto service to a Costa Rica resident, with direct effect in Costa Rica, triggers the impuesto sobre remesas al exterior (see [[remesas-exterior]]).
- **Open question for Fact3:** whether a gain realized on a foreign exchange by a resident investor is Costa Rican-source at all. The territorial principle suggests foreign gains are out of scope, but the DGT has not addressed it directly. Get a written legal opinion before selling crypto tax filings (already flagged in the MVP plan).

## Pending legislation (not law)

In September 2026 the government presented Bill **25.796** to tax foreign-source passive income and capital gains, plus a second bill to cut exemptions (Delfino). TRIBU-CR already has codes 119 to 124 for "rentas pasivas de fuente extranjera". Until the bill passes and its text is confirmed, treat foreign passive income and gains as untaxed under the territorial system, and keep the classification rules dated so they can switch on a given effective date.

## Practical rules for the Fact3 ledger

1. Value every crypto event in colones on its date: stablecoins at their USD value, then the BCCR CRC/USD rate for that day; other assets from a price feed.
2. Keep cost basis per lot so gains can be computed for the IRCGPC (15%) or the ISU.
3. Transfers between a client's own wallets and exchange accounts are not taxable events.
4. Swaps crypto to crypto are disposals (the DGT treats crypto as an asset, so a swap realizes a gain or loss).
5. Exchange and custody fees charged by a Costa Rican provider carry 13% IVA.
