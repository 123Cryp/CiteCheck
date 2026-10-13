# CiteCheck architecture

## Scope

CiteCheck settles one narrow question: does a pinned, immutable source say what the citer says it says. It does not judge whether the statement is true in the world, and it does not rank sources. Citing your own pinned file is allowed and is judged on faithfulness only.

## State machine

```
register_claim --> OPEN --(window passes, no challenge)--> finalize_unchallenged --> ACCEPTED
                     |
                challenge_claim (equal bond, optional counter passage, before window ends)
                     v
                 CHALLENGED --resolve_challenge--> UPHELD     (outcome CITER: SUPPORTED)
                     |                        \--> REFUTED    (outcome CHALLENGER: MISQUOTED / UNSUPPORTED / CONTRADICTED)
                     |                        \--> CHALLENGED (outcome NONE, retry after 1 hour)
                     |                        \--> VOID       (outcome NONE for the 3rd time, both bonds refunded)
                     \--abandon_unresolved (7 days after challenge)--> VOID
```

## Pinned sources

| Form | Why it is immutable |
|---|---|
| `raw.githubusercontent.com/<owner>/<repo>/<40 hex sha>/<path>` | Content addressed by commit. |
| `arxiv.org/abs/<id>v<n>` | Versioned arXiv records are never edited in place. |
| `<lang>.wikipedia.org/w/index.php?[title=…&]oldid=<n>` | A revision id always renders that revision. |

Everything else is rejected at registration: branch refs, query strings other than the Wikipedia form, fragments, userinfo, `..` path segments, look-alike hosts, and URLs over 300 characters. Without pinning, a citer could edit the page after a challenge and turn a losing claim into a winning one.

## Verdicts and outcomes

| Verdict | Decided by | Outcome |
|---|---|---|
| MISQUOTED | Code: passage not on a page of at least 200 characters | CHALLENGER |
| SUPPORTED | LLM | CITER |
| CONTRADICTED | LLM | CHALLENGER |
| UNSUPPORTED | LLM | CHALLENGER |
| UNDETERMINED | Fetch failed, page under 200 characters without the passage (likely an error page), judge unavailable or unparseable, or the judge said it cannot tell | NONE |

Matching normalizes whitespace, non-breaking spaces, typographic quotes and dashes, and is case insensitive. A judge answer cannot rescue a passage that is not on the page.

## Consensus design

`resolve_challenge` calls `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` positionally. Both closures are built by module-level factories and capture only plain strings, never the contract. The leader runs the full derivation and returns a JSON string. Each validator runs the same derivation independently, with its own fetch and its own LLM call, and agrees only if its outcome bucket (CITER, CHALLENGER, NONE) equals the leader's.

Comparing outcome buckets instead of raw labels follows the rule that validators must bind the settlement-driving decision. UNSUPPORTED versus CONTRADICTED moves the same money, so disagreement there should not fail consensus. A leader that reports NONE while validators reach a decision is rejected, so a leader cannot force a retry or a void. Reason text, excerpt, counter status and page digest are leader attested and never compared, because they legitimately differ between fetches.

Every error inside the nondet block is caught inside it and becomes an UNDETERMINED result, so a failed fetch never crashes the transaction.

## Judge prompt hardening

| Measure | Purpose |
|---|---|
| Statement, quoted passage, source context and counter excerpt each sit in their own `<<<NAME … NAME>>>` block | Clear data boundaries |
| `<<<` and `>>>` are stripped from all untrusted text | Blocks cannot be closed early |
| Labels are `CC_SUPPORTS`, `CC_NOT_SUPPORTED`, `CC_CONTRADICTS`, `CC_UNCLEAR`, and any `cc_` in untrusted text is rewritten to `cc-` | Literal label injection from a page or statement cannot produce a valid label |
| Statements containing `< > { }` or backticks, `cc_`, "system prompt", or "ignore all/previous/prior/the above" are rejected at registration | Removes the cheapest injection shapes from citer-controlled text |
| The prompt states that instruction-like content counts against the citer | Semantic injection backfires |
| Output is a closed enum, and anything else becomes UNDETERMINED | Junk cannot settle money |

## Economics

| Rule | Value |
|---|---|
| Minimum bond | 1 GEN. Use whole GEN, since Studio's value field rejects decimals |
| Challenger bond | Must equal the citer bond exactly |
| Self challenge | Rejected for the same address |
| Winner receives | Both bonds, credited to a pull balance |
| Fees | None, so there is no privileged address or owner |
| Challenge window | Constructor argument, 60 seconds to 30 days |
| Undetermined retries | 3 attempts at least 1 hour apart, then both bonds are refunded |
| Abandon timeout | 7 days after the challenge, then anyone can refund both bonds |

Invariant checked after every step of a 1500-step randomized test: contract balance equals escrowed plus owed, and total GEN in equals balance plus total paid out.

## Refund instead of revert

GEN attached to a payable call that reverts stays in the contract with no record of the sender. So `register_claim` and `challenge_claim` contain no `raise` at all. Invalid input credits the attached value to the sender's withdrawable balance and returns a string starting with `REJECTED:`. A test enforces that no `raise` appears in any payable method.

## Threat model

| Threat | Mitigation |
|---|---|
| Citer edits the source after being challenged | Only pinned, immutable source forms are accepted. |
| Citer quotes text that is not on the page | MISQUOTED is decided in code. |
| Transient error page wrongly read as a misquote | Pages under 200 characters without the passage are UNDETERMINED. |
| Quote taken out of context | 1500 characters of context on each side, plus the challenger's optional counter passage, which is checked in code and shown with its own context. |
| Prompt injection | See the hardening table. |
| Leader lies | Every validator re-derives independently. A different outcome bucket fails consensus. |
| Short outage voids a valid challenge | Retries are at least 1 hour apart, and VOID needs 3 undetermined attempts. |
| Funds stuck after repeated consensus failure | `abandon_unresolved` after 7 days refunds both sides. Anyone can call it. |
| Citer challenges from a second wallet to block real challengers | The claim is still resolved by consensus. If it is unfaithful, the citer's main address gets the refuted mark. |
| Reputation farming with trivial unchallenged claims | Accepted-unchallenged and upheld-under-challenge are counted separately. Reputation is informational and gates nothing. |
| Duplicate spam | An identical open claim (normalized statement, URL, quote) is rejected. |
| Reentrancy on payout | Balance is zeroed before the transfer is emitted. |

## Known limitations

| Limitation | Note |
|---|---|
| GitHub ref ambiguity | A branch literally named as a 40-hex string could shadow a commit sha on raw.githubusercontent.com. Use the sha from the commit page. |
| Wikipedia templates | Templates transcluded into an old revision render in their current form. Article body text is fixed. |
| Pages that need JavaScript | GenVM fetches plain page text. Raw GitHub files are the most reliable source form. |
| Borderline judgments | Validators can split on outcome. The transaction then fails consensus and can be retried, and abandon is the final backstop. |
| No sybil resistance | Bonds are the only barrier. |

## GenVM rules applied

| Topic | Rule applied |
|---|---|
| Header | `# v0.2.16`, then the pinned `Depends` line, then code. No comments or docstrings, which can break Studio schema loading. |
| Imports | `dataclass` imported explicitly after `from genlayer import *`. |
| Storage | Fields declared as class annotations with sized types (`u256`, `str`, `Address`, `TreeMap`, `DynArray`). No `bool` or plain `int` fields. Containers are never assigned in `__init__`. Records are `@allow_storage @dataclass`. |
| Sender and time | `gl.message.sender_address` and `datetime.datetime.now()`. |
| Nondet | `run_nondet_unsafe` called positionally. Module-level closures. Leader result read from `.calldata` of `gl.vm.Return`. `exec_prompt(..., response_format="json")` output accepted as a dict or a string. |
| Payout | `emit_transfer(value=...)` with no trigger argument for wallets. |
| Payable | `@gl.public.write.payable` on both value-carrying methods, and no reverts inside them. |
| Views | Return JSON strings to avoid map decoding differences in genlayer-js. The list view is paginated. |
| Evidence | Raw text sources, because JS-rendered pages return navigation chrome only. |
