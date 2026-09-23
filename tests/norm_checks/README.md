# tests/norm_checks/

`norm-architect`-authored tests, written **before** any implementation
code exists for the round — one subdirectory per round, one file:
`round_{N}/test_round_{N}.py`, covering every requirement that round's
norm implies. `norm-engineer` reads it before writing any code (it's the
concrete target it must satisfy) but cannot edit this directory —
permission-denied by design, so the agent being judged against this test
file can never adjust it to fit whatever it happens to build.

Write however many test cases a requirement actually needs — never just
one. At minimum the compliant path, the non-compliant/penalty path where
the requirement implies one, and the boundary cases the norm's own
numbers imply (exactly at a threshold, just under it, just over it).

Distinct from `tests/regression/`: that directory is a fixed, human-owned
suite neither `norm-architect` nor `norm-engineer` may ever edit or
weaken. This directory is the opposite — freshly authored every round,
and expected to start out failing red (nothing implementing the round's
norm exists yet) until `norm-engineer` makes it pass.

A requirement passing every test here is necessary, not sufficient, for
the round to be judged compliant — `norm-auditor` (2026-09-23: a plain,
tool-free completion call, not a separate test-writing agent) still
cross-references the raw norm.txt text against the actual code directly,
specifically to catch under-enforcement a pre-written test couldn't have
anticipated (code that's technically present and passes this suite, but
implements the requirement more weakly than the norm's own text demands).

A purely parametric round (writing only to `state/config.json`/
`state/fluents.json`) doesn't need a new test here — there's no new code
to cover. The orchestrator's Self-Correction Gate
(`norm_implementation_failing_tests_errors()` in `engine/simulate.py`)
runs `pytest tests/norm_checks/round_{N}/` automatically every repair
attempt, alongside `tests/regression/`, feeding any failure's stack trace
straight back to `norm-engineer` — this is the mechanical part of the
TDD loop, not something either agent needs to invoke by hand.
