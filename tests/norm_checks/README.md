# tests/norm_checks/

`norm-architect`-authored tests, written **before** any implementation
code exists for the round — one subdirectory per round:
`round_{N}/test_{short_description}.py`, covering the specific behavior
that round's norm requires. `norm-engineer` reads every test here before
writing any code (they're the concrete target it must satisfy) but cannot
edit this directory — permission-denied by design, so the agent being
judged against these tests can never adjust them to fit whatever it
happens to build.

Write however many test cases a requirement actually needs — never just
one. At minimum the compliant path, the non-compliant/penalty path where
the requirement implies one, and the boundary cases the norm's own
numbers imply (exactly at a threshold, just under it, just over it).

Distinct from `tests/regression/`: that directory is a fixed, human-owned
suite neither `norm-architect` nor `norm-engineer` may ever edit or
weaken. This directory is the opposite — freshly authored every round,
and expected to start out failing red (nothing implementing the round's
norm exists yet) until `norm-engineer` makes it pass.

Also distinct from `tests/norm_evaluation/`: that's `norm-auditor`'s own,
separately-authored suite, written *after* implementation exists,
specifically to catch what a pre-written test couldn't have anticipated
(the actual code's own logical omissions and under-enforcement) — a
requirement passing every test in this directory is necessary, not
sufficient, for the round to be judged compliant.

A purely parametric round (writing only to `state/config.json`/
`state/fluents.json`) doesn't need a new test here — there's no new code
to cover. The orchestrator's Self-Correction Gate
(`norm_implementation_failing_tests_errors()` in `engine/simulate.py`)
runs `pytest tests/norm_checks/round_{N}/` automatically every repair
attempt, alongside `tests/regression/`, feeding any failure's stack trace
straight back to `norm-engineer` — this is the mechanical part of the
TDD loop, not something either agent needs to invoke by hand.
