# Changelog

## v1.1.0

Frontend usability milestone. The contract and its live deployment are unchanged.

| Area | Change |
|---|---|
| Pre-bond safety | Quote check in the browser using the contract's normalization, on the registration form and on claim pages (citer quote and counter passage). |
| Source pinning | Pin helper converts a GitHub file link and commit sha into the exact raw URL form the contract accepts. |
| Overview | Stats strip and status bar on the home page. |
| Sharing | Copy claim link and README status badge on every claim page. |
| Onboarding | Practice account for visitors without a browser wallet, with a funding request and removal button. |
| Code structure | Pure logic moved to `frontend/lib.js`, imported by the page. |
| Errors | Friendly messages for cancelled requests, insufficient funds and network failures. |
| Tests | 11 Node tests for `frontend/lib.js`, run in CI next to the 72 contract tests. Parity with the contract's `_pinned_source`, `_norm` and blocked-claim rules was checked on a shared corpus with no mismatches. |

## v1.0.0

First release: bonded citation verification contract, 72 offline tests, no-build frontend, live Studio deployment at `0x3f5127a943d3AD2C4500E8FbB7BA898237bF5FDC`.
