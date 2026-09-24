# tests/norm_checks/

One subdirectory per round, `round_{N}/`, with two files from two
different authors:

- `norm_plan.json` — written by `norm-architect` (2026-09-24: semantic
  compilation only). Every atomic requirement the round's norm implies,
  classified as ROLE/ACTION/OBJECT/RULE/VISIBILITY/LIFECYCLE, each with an
  `agent_experience` block (what a fisher now knows, decides, may/may not
  do, remembers, observes). norm-architect has no tools and no repository
  access beyond one conceptual doc; it cannot write a file path, an
  import, or a test scenario, so it doesn't try to.
- `test_round_{N}.py` — written by `norm-engineer`, which decides what
  each requirement needs tested (grounded in that requirement's own
  `agent_experience` block) and writes a real pytest function named
  `test_{requirement_id}_{scenario}` for it, before writing any
  implementation code. `norm-engineer` reads `norm_plan.json` before
  writing any code (it's the concrete target it must satisfy) but cannot
  edit it — permission-denied by design, so the agent being judged against
  a plan can never adjust the plan to fit whatever it happens to build.

Write however many tests a requirement actually needs — never just one.
At minimum the compliant path, the non-compliant/penalty path where the
requirement implies one, and the boundary cases the norm's own numbers
imply (exactly at a threshold, just under it, just over it).

2026-09-24 (same day, second change): norm-architect originally also
proposed acceptance-test SPECIFICATIONS (given/when/expect) here, with the
Harness Validator (`validate_norm_plan()`) requiring at least one per
ROLE/ACTION/RULE/VISIBILITY requirement before norm-engineer's session
ever started. Dropped after a real run showed this discarding whole
rounds outright — DeepSeek-R1 didn't reliably converge on covering every
flagged gap even across the validator's one bounded retry pass (see round
1 and round 2 of `sim/run-20260924-005713`: both discarded here, before
norm-engineer ever ran). norm-engineer now owns deciding scenarios
entirely, and the validator no longer checks for their presence.

Distinct from `tests/regression/`: that directory is a fixed, human-owned
suite neither `norm-architect` nor `norm-engineer` may ever edit or
weaken. This directory is the opposite — freshly authored every round,
and expected to start out failing red (nothing implementing the round's
norm exists yet) until `norm-engineer` makes it pass.

A requirement's tests passing is necessary, not sufficient, for the round
to be judged compliant. After a clean round, the harness assembles a
structured evidence package (`_gather_norm_evidence()`,
`state/norm_evidence/round_N.json`) — per requirement,
`norm-finalizer`'s independently verified claims plus each test's own
PASS/FAIL. `norm-auditor` (a plain, tool-free completion call, not a
separate test-writing agent) then reviews norm.txt against
`norm_plan.json` and that evidence package together, specifically to
catch under-enforcement a passing test couldn't have caught on its own (a
test that's technically green but itself checks something weaker than the
norm's own text demands) — this is now the *only* backstop against a
self-authored test that's too weak, since norm-engineer both picks the
scenarios and writes the assertions.

A purely parametric round (writing only to `state/config.json`/
`state/fluents.json`) doesn't need a new test here — there's no new code
to cover. The orchestrator's Self-Correction Gate
(`norm_implementation_failing_tests_errors()` in `engine/simulate.py`)
runs `pytest tests/norm_checks/round_{N}/` automatically every repair
attempt, alongside `tests/regression/`, feeding any failure's stack trace
straight back to `norm-engineer` — this is the mechanical part of the TDD
loop, not something either agent needs to invoke by hand.
