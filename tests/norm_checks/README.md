# tests/norm_checks/

One subdirectory per round, `round_{N}/`, with two files from two
different authors:

- `norm_plan.json` — written by `norm-architect` (2026-09-24: semantic
  compilation only). Every atomic requirement the round's norm implies,
  classified as ROLE/ACTION/OBJECT/RULE/VISIBILITY/LIFECYCLE, each with an
  `agent_experience` block (what a fisher now knows, decides, may/may not
  do, remembers, observes) and `acceptance_tests` entries — given/when/
  expect *specifications*, never Python. norm-architect has no tools and
  no repository access beyond one conceptual doc; it cannot write a file
  path or an import, so it doesn't try to.
- `test_round_{N}.py` — written by `norm-engineer`, which translates every
  `acceptance_tests` entry from `norm_plan.json` into a real pytest
  function named `test_{requirement_id}_{scenario}`, asserting the plan's
  own frozen given/expect values literally, before writing any
  implementation code. `norm-engineer` reads `norm_plan.json` before
  writing any code (it's the concrete target it must satisfy) but cannot
  edit it — permission-denied by design, so the agent being judged against
  a spec can never adjust the spec to fit whatever it happens to build.

Write however many acceptance tests a requirement actually needs — never
just one. At minimum the compliant path, the non-compliant/penalty path
where the requirement implies one, and the boundary cases the norm's own
numbers imply (exactly at a threshold, just under it, just over it). The
Harness Validator (`validate_norm_plan()`) enforces structurally that
every ROLE/ACTION/RULE/VISIBILITY requirement has at least one
acceptance-test entry before norm-engineer's session ever starts.

Distinct from `tests/regression/`: that directory is a fixed, human-owned
suite neither `norm-architect` nor `norm-engineer` may ever edit or
weaken. This directory is the opposite — freshly authored every round,
and expected to start out failing red (nothing implementing the round's
norm exists yet) until `norm-engineer` makes it pass.

A requirement's acceptance tests passing is necessary, not sufficient,
for the round to be judged compliant. After a clean round, the harness
assembles a structured evidence package
(`_gather_norm_evidence()`, `state/norm_evidence/round_N.json`) — per
requirement, `norm-finalizer`'s independently verified claims plus each
acceptance test's own PASS/FAIL, plus a self-grading guardrail note (does
the generated test actually reference the plan's own literal given/expect
values, or did norm-engineer quietly loosen them?). `norm-auditor`
(a plain, tool-free completion call, not a separate test-writing agent)
then reviews norm.txt against `norm_plan.json` and that evidence package
together, specifically to catch under-enforcement a passing acceptance
test couldn't have caught on its own (a test that's technically green but
itself checks something weaker than the norm's own text demands).

A purely parametric round (writing only to `state/config.json`/
`state/fluents.json`) doesn't need a new test here — there's no new code
to cover; the Harness Validator only requires acceptance tests for
requirements that change a fisher's own experience. The orchestrator's
Self-Correction Gate (`norm_implementation_failing_tests_errors()` in
`engine/simulate.py`) runs `pytest tests/norm_checks/round_{N}/`
automatically every repair attempt, alongside `tests/regression/`,
feeding any failure's stack trace straight back to `norm-engineer` — this
is the mechanical part of the TDD loop, not something either agent needs
to invoke by hand.
