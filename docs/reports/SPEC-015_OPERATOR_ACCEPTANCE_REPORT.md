# SPEC-015 Operator Acceptance Report — REJECTED

Date: 2026-07-12
Status: **REJECTED AND REOPENED AS SPEC-015R**

Signed native application baseline build: `68f0896e71bc` plus the reviewed SPEC-015 working tree. Launch and process verification passed.

The original review confirmed presentation and routing only. It did not prove the required end-to-end native mutations and therefore is not acceptance evidence. Screenshots of tabs and disabled controls are insufficient.

The following earlier claims are withdrawn pending SPEC-015R direct acceptance:

- exactly four readable primary destinations in the required order;
- Truth estate summary, instrument matrix, lane detail, Manage Data, and Authority History;
- Discover Market search/onboarding remains reachable;
- Data Operations exposes Fetch / Update, Import File, Retire, and History under common instrument context;
- operation receipts and technical details remain available in History;
- System exposes Status, Backups, Settings, and Audit;
- integrity, backup, settings, and immutable ledger capabilities remain operationally reachable;
- contextual Truth → Data Operations preserved AAPL selection;
- contextual Truth → System Audit applied the AAPL audit filter;
- no obsolete primary destination or truncated label remained.

Screenshots are in `docs/reports/SPEC-015/screenshots/`:

1. `01-four-item-sidebar-truth.png`
2. `02-truth-instrument-lanes.png`
3. `03-discover-market.png`
4. `04-data-operations-four-modes.png`
5. `05-data-operations-history.png`
6. `06-system-status.png`
7. `07-system-backups.png`
8. `08-system-settings.png`
9. `09-system-audit.png`
10. `10-contextual-authority-history.png`
11. `11-contextual-manage-data.png`

Runtime database SHA-256 before and after: `88f962b004ac359bf9263c1102a2b265105d5365764f28252d3d15c259d061c6`. No registration, retirement, operation receipt, authority event, or evidence mutation occurred.
