# Communication Reviewer v3 development plan

## Accepted baseline

Reviewer v2 was evaluated in F24.3J-R1 with 16 real sequential inference calls:
4 targeted development regressions plus 12 cases from the locked holdout-r1.
All 16 responses were validated and admissible. Across 44 explicit labels,
38 matched and 6 differed. No explicit fail label was observed as pass.
The strict development candidate gate did not pass, and no production-quality
claim was made.

The six differences were confined to ambiguity/inconclusive boundaries:
- unresolved external or anaphoric references were sometimes classified pass;
- contradictory event facts were sometimes classified pass when the candidate
  merely described the contradiction;
- a relative criticality without a defined corporate mapping was classified
  fail instead of inconclusive.

## v3 change scope

The versioned criteria remain `communication-review-v1`; `src/review/contracts.py`,
`src/review/policy.py`, the v1 rubric, Reviewer v1, Reviewer v2, and their
historical evaluation data remain unchanged.

Reviewer v3 changes only the cognitive instructions. It makes precedence
explicit:
1. ambiguity is resolved before pass/fail;
2. contradictory `event_type` and `status_summary` force
   `event_consistency=inconclusive`;
3. unresolved external/anaphoric references force inconclusive for criteria
   whose meaning depends on the missing antecedent;
4. relative criticality without an explicit mapping is inconclusive, while a
   determinate unsupported corporate level remains fail;
5. fail requires a sufficiently determined proposition and an observable
   violation; pass requires enough current evidence to resolve the criterion.

The same model (`gpt-5-mini-sbx`), reasoning effort, response format, tools,
runtime, and Python policy must remain unchanged when v3 is created so the
comparison isolates the prompt.

## Fresh holdout-r2

`communication_review_v1.holdout-r2.jsonl` contains 12 new synthetic cases and
35 explicit criterion labels. It is locked locally before any Reviewer v3 cloud
creation or v3 inference. The rows and expected labels are never sent to the
Reviewer as expectations.

This holdout is assistant-authored under the user's technical delegation. It is
not human-independent ground truth and is not a production certification set.
holdout-r1 is considered consumed for v2 evaluation and must not be reused as a
fresh acceptance set for v3.

## Decision after v3 evaluation

After creating Reviewer v3, first run a small targeted regression over the
known ambiguity families, then run holdout-r2 unchanged. Do not tune v3 between
those two measurements. A semantic mismatch is evaluation evidence and must not
be retried to manufacture agreement. Transport or adapter ambiguity remains
fail-closed.

Only after those results should the project decide whether to proceed to F24.4
sandbox integration, create another prompt version, or test a different model
as a separate variable. Independent validation is still required before any
production-quality claim.
