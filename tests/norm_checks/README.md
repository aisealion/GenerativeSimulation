# tests/norm_checks/

Implementer-authored unit tests, one file per round that touches
`mechanisms/*.py` or `phases/*.py` (a structural or `new_phase` change) —
covering the specific behavior that round's norm asked for.

Distinct from `tests/regression/`: that directory is a fixed, human-owned
suite the norm-implementer must never edit or weaken. This directory is
the opposite — it's the norm-implementer's own, and it's expected to keep
growing. Naming convention: `test_round_{N}_{short_description}.py`, so a
later round can tell which test came from which norm without checking git
blame.

A purely parametric round (templates 1–5, writing only to
`state/config.json`/`state/fluents.json`) doesn't need a new test here —
there's no new code to cover. Run the whole directory with
`pytest tests/norm_checks/`, alongside `tests/regression/`, before
reporting a round done.
