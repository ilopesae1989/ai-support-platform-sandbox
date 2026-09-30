# F24.3H — Reviewer v2 local refinement and locked holdout

## Baseline observed
The first bounded development evaluation of `agent-reviewer-sbx:1` consumed exactly 24 inference attempts across F24.3G/R1/R2. One case (CR-DEV-001) has no validated review result because the first harness incorrectly required a `store` echo after HTTP 200. Of the other 23 validated results, 22 were admissible under Python policy and CR-DEV-006 was rejected with `evidence_reference_invalid`.

Across the 66 explicitly labeled criteria that were scoreable, 62 matched the delegated development labels and four differed. All four differences were concentrated in ambiguity handling: relative criticality, ambiguous identity, and unresolved external references. The development labels are not human-independent ground truth and the result is not a production quality certification.

## Change classification
This revision changes only the implementation instructions of the Reviewer. `communication-review-v1`, `ReviewRequest`, `ReviewResult`, `assess_review()`, the seven criteria, the v1 rubric, and all 24 development cases remain unchanged.

The v2 instructions add deterministic tie-break guidance for:
- evidence allowlisting before output, including an explicit ban on references to null context fields;
- relative or unmapped criticality descriptions -> inconclusive rather than an assumed concrete mapping;
- relational/generic identity descriptions when multiple identities are possible -> inconclusive;
- references to prior cases, interventions, messages, or conversations that are not in the current request -> inconclusive for criteria that depend on the missing referent;
- a final self-check that every evidence reference belongs to the finite allowlist for the current request.

The prompt intentionally does not contain development or holdout case IDs and does not quote their candidate strings.

## Locked holdout
`tests/review/data/communication_review_v1.holdout-r1.jsonl` contains 12 new synthetic cases. It is locked locally before any Foundry v2 creation or v2 inference. It was authored by the assistant under the user's delegated technical decision authority. It is not human-independent ground truth.

The holdout is for post-change regression/generalization checks. It must not be copied into the v2 prompt and its expected labels must never be sent to the Reviewer.

## Cloud sequencing
1. Complete this local microphase and preserve the v1 assets unchanged.
2. Create exactly one new Foundry version for `agent-reviewer-sbx`, using the same `gpt-5-mini-sbx` deployment, no tools, and the v2 instruction bytes.
3. Keep the response format/model/reasoning configuration unchanged for the first v2 comparison so the prompt is the primary changed variable.
4. Run a bounded targeted regression on the four development ambiguity/policy cases and then the locked holdout without retries.
5. Only after those measurements decide whether a stronger model, structured-output enforcement, another prompt revision, or production integration is justified.

Microsoft Foundry agent versions are immutable snapshots; a prompt change must therefore be saved as a new version rather than mutating version 1.
