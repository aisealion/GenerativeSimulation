# Recipe: new_action (Level 2 or 4)

A genuinely new agent decision that no existing action hosts. Read
`action-contract.md` in full before starting — it prices Level 2 vs.
Level 4 accurately; don't judge cost from memory.

Never edit a protected action to add this — always a new file alongside
existing ones (`architecture.md`).

| | |
|---|---|
| **Required** | `state/actions/{name}.json` — `name` matches the filename stem and the `state/institution.json` key. |
| **Required** | Register in `state/institution.json`: `"{name}": {"spec": "state/actions/{name}.json", "protected": false}`. |
| **Required** | `scheduling.gate`/`after`/`before` in the spec (never a `state/schedule.json` edit — it compiles automatically). |
| **Required** | `participation` policy in the spec. |
| **Required** | `prompt.template` in the spec (no separate prompt file for a normal action). |
| **Conditional** | `execution.handler: "generic_agent_decision"` + `prompt.fields`/`outputs.fields` — **Level 2**, if the action is only "ask one question, record the answer verbatim." No handler file. |
| **Conditional** | `actions/handlers/{name}.py` (`def run(ctx) -> round_record`) — **Level 4**, the moment a role grant, an institutional fact, custom eligibility, cross-agent aggregation, or any enforcement consequence is needed. Use `engine.institution.agent_loop.per_agent_decision()` for the loop unless the action needs more than one call per agent or none at all. |
| **Conditional** | `prompts/role_directives/{role}.md` if this action introduces or requires a new role — see `new_role.md`. |
| **Conditional** | An object type/instance if the action reads or writes a ledger/pool/permit — see `new_object.md`. |
| **Conditional** | A rule under `actions/rules/{name}/` if the action needs enforcement beyond recording the answer — see `new_rule.md`. |
| **Required** | `tests/norm_checks/` test calling `engine.institution.runtime.ActionRuntime.run_action(spec, state, round_number)`, covering **both** the compliant path and, where the requirement implies one, the non-compliance/enforcement path. |
| **Forbidden** | Editing `state/schedule.json` directly. Editing any protected action spec/handler, or one an earlier round already created. Pre-seeding new runtime state in `state/runtime.json`. |
| **Verify** | Action appears in the compiled schedule (a fresh read after your edits, or the orchestrator's own structural check). Participants resolve per the declared policy. `execution.handler` resolves (a real builtin, or a real `run` in the handler file). Prompt renders with the fields the design specifies. `tests/norm_checks/` passes both paths. |

If the requirement seems larger than one round's budget after actually
pricing it against `action-contract.md` — not before — that's exactly
the case for `engine/clarify_norm.py` to ask about scope, or for
implementing the smallest honest real piece, never for silently
implementing nothing.
