# Composing recipes for one norm

Most real norms aren't one recipe — they're several, one per extracted
requirement. Extract every distinct requirement as an atomic
actor+verb+object first (main prompt, "Extract requirements"), classify
each independently, then compose. Two verb-phrases sharing one actor are
still two separate requirements — a role *existing* is different from a
*decision* that role later makes, which is different again from whatever
*responds* to that decision. Err toward over-splitting: a spurious extra
requirement collapses harmlessly during routing; a requirement never
extracted silently never gets implemented.

## Worked example

> For five rounds, one rotating inspector shall inspect harvest records
> and record violations in a communal ledger visible during voting.

Extraction and routing:

| Clause | Requirement | Recipe |
|---|---|---|
| "one rotating inspector" | The role exists and rotates | `new_role.md` (`exclusive: true`) |
| "shall inspect harvest records" | A new agent decision — inspecting is judgment, not arithmetic (`architecture.md`'s trigger-verb list) | `new_action.md` (Level 4 — needs a role grant/eligibility beyond generic) |
| "record violations in a communal ledger" | A persistent resource | `new_object.md` |
| "visible during voting" | Conditional visibility | `visibility_change.md` |
| "for five rounds" | Bounded duration on the inspection action's own configured behavior (or on the norm's overall activation) | `lifecycle_change.md` |

None of these five is optional because another one was built — a role
existing does not imply the inspection action was built; the ledger
existing does not imply violations actually get recorded into it. Each
row needs its own `owner` and `verification` in the final requirement
table.

## Ordering matters less than completeness

Build in whatever order is natural (usually: object → role → action, so
the action has something real to write into and someone real to hold the
role) but the **Final Self-Check**'s completeness re-walk must confirm
every clause above has a row, regardless of build order.
