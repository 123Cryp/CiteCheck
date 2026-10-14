# CiteCheck

Bonded citation verification on GenLayer. A citer stakes GEN on a claim of the form "this source says X", quoting the exact passage from a pinned, immutable source. Anyone can challenge by matching the bond, optionally quoting a counter passage from the same source. Validators independently fetch the source, check in code that the quoted passages really appear on the page, and use an LLM only to judge whether the passage, read in context, supports the statement as worded. The winner takes both bonds.

CiteCheck verifies citation faithfulness, not whether the statement is true in the world.

## How it works

| Step | Who | What happens |
|---|---|---|
| Register | Citer | Posts statement, pinned source URL, exact quoted passage and a bond (at least 1 GEN). |
| Challenge window | Anyone except the citer | Matches the bond exactly to challenge, optionally with a counter passage from the same source. Window length is set at deployment. |
| Finalize | Anyone | Unchallenged claims return the bond to the citer after the window. |
| Resolve | Anyone | Leader and validators each fetch the page. Quote missing: MISQUOTED, decided in code with no LLM. Quote present: LLM returns SUPPORTED, UNSUPPORTED, CONTRADICTED or UNDETERMINED. |
| Payout | Contract | SUPPORTED pays the citer both bonds. MISQUOTED, UNSUPPORTED or CONTRADICTED pays the challenger. UNDETERMINED allows a retry after 1 hour, and after 3 undetermined attempts both bonds are refunded. |
| Withdraw | Winner | Pull payment of the credited balance. |

Validators must agree on the settlement outcome (citer wins, challenger wins, or undetermined), which is exactly what moves the money. Page bytes are never compared, because two independent fetches rarely match byte for byte.

## Accepted sources

| Form | Example |
|---|---|
| GitHub raw file at a full 40-character commit sha | `https://raw.githubusercontent.com/owner/repo/<sha>/path/file.md` |
| arXiv abstract with an explicit version | `https://arxiv.org/abs/2401.01234v2` |
| Wikipedia permanent link | `https://en.wikipedia.org/w/index.php?title=Coffee&oldid=1234567890` |

Branch links, unversioned arXiv links and normal Wikipedia article links are rejected because their content can change after registration.

## Layout

| Path | Purpose |
|---|---|
| `contracts/citecheck.py` | The Intelligent Contract, ready to paste into GenLayer Studio. |
| `frontend/index.html` | No-build hash-routed frontend (genlayer-js from a CDN). |
| `tests/` | Offline test suite with a self-written GenLayer SDK stub. No pip install needed. |
| `ARCHITECTURE.md` | State machine, economics, threat model, GenVM lessons. |
| `samples/source.md` | Fixed sample source for live testing through its commit-pinned raw URL. |

## Run the tests

```
python3 -m unittest discover -s tests -v
```

## Deploy

1. Paste `contracts/citecheck.py` into GenLayer Studio.
2. Deploy with one constructor argument: `challenge_window_seconds` (60 to 2592000). Use 172800 for production and 120 for a live test.
3. Put the deployed address in `CONTRACT_ADDRESS` at the top of the script in `frontend/index.html`.

## Live deployment (GenLayer Studio)

| Item | Value |
|---|---|
| Contract | `0x3f5127a943d3AD2C4500E8FbB7BA898237bF5FDC` |
| Explorer | https://explorer-studio.genlayer.com/address/0x3f5127a943d3AD2C4500E8FbB7BA898237bF5FDC |
| Challenge window | 172800 seconds (48 hours) |
| Pinned test source | `https://raw.githubusercontent.com/123Cryp/CiteCheck/a1b068fbf0766646689c78873b35bb0614a2ed21/samples/source.md` |

## Verified on live GenVM

| Path | Result |
|---|---|
| Supported claim, challenged | `UPHELD`, citer wins both bonds, reason quotes the fetched page |
| Unsupported claim, challenged | `REFUTED` with verdict `CONTRADICTED` |
| Fabricated quote, challenged | `REFUTED` with verdict `MISQUOTED`, decided in code without the LLM |
| Challenger counter passage | Found on the page in code, shown to the judge, claim refuted |
| Duplicate challenge | Rejected and refunded instead of reverting |
| Resolve without a challenge, or twice | Reverts |
| Withdraw | Exact balances paid out, contract balance equals remaining escrow |

The 48 hour unchallenged finalize path is covered by the offline suite and is exercised live once the window of the last open test claim has passed.

## Status

72 offline tests pass in CI. Live addresses and results are listed above.
