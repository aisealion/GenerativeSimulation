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
| **Required** | `prompt.template` in the spec — **`"prompt"` is a TOP-LEVEL key of the spec, a sibling of `"execution"`, never nested inside it** (no separate prompt file for a normal action). `render_action()` only ever looks at the spec's own top-level `"prompt"` key. See the worked example below. |
| **Required** | The literal JSON example inside `prompt.template`'s own `"Respond with ONLY this JSON object..."` line must use DOUBLE braces (`{{"field": ...}}`), never single ones — the template gets passed through Python's `str.format()`, which treats a single `{`/`}` as a substitution field to fill in, not literal text, and raises `KeyError` on one it doesn't recognize. Anywhere else in the template that names an actual field to substitute (e.g. `{stock_kg}`) uses single braces, exactly as normal. |
| **Conditional** | `execution.handler: "generic_agent_decision"` — **Level 2**, if the action is only "ask one question, record the answer verbatim." No handler file. `prompt.fields` is a DICT of `{field_name: {"literal": ...} \| {"from": "state", "path": "runtime.stock_kg"} \| {"from": "object", "object_id": ..., "field": ...}}` entries — values to compute and inject into the template's own `{field_name}` placeholders, never a list of field-name strings, and `{}` (empty dict) if the template needs no injected context at all. `outputs.fields`, if present, is likewise a DICT `{response_key: record_key}` renaming specific keys from the agent's own JSON response — omit it entirely to record the response verbatim, never a list. |
| **Conditional** | `actions/handlers/{name}.py` (`def run(ctx) -> round_record`) — **Level 4**, the moment a role grant, an institutional fact, custom eligibility, cross-agent aggregation, or any enforcement consequence is needed. Use `engine.institution.agent_loop.per_agent_decision()` for the loop unless the action needs more than one call per agent or none at all. `ctx`'s attributes are a fixed, closed list — see `action-contract.md`'s Level 4 section before writing any `ctx.*` usage. |
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

## Worked example — a Level 2 `state/actions/{name}.json`, exact shape

```json
{
  "name": "record_catch",
  "description": "each fisher records total catch on the shared ledger",
  "protected": false,
  "scheduling": {"gate": "true", "after": null, "before": null},
  "participation": {"policy": "all_alive_fishers"},
  "roles": {"actor_role": "fisher"},
  "prompt": {
    "fields": {
      "stock_kg": {"from": "state", "path": "runtime.stock_kg"}
    },
    "template": "The lake currently holds about {stock_kg:.0f}kg. Record your catch total and sign the ledger.\n\nRespond with ONLY this JSON object, nothing else:\n{{\"harvested_kg\": <your catch total>, \"signature\": \"<your signature>\"}}\n"
  },
  "execution": {
    "handler": "generic_agent_decision"
  }
}
```

Note `"prompt"` sitting at the same level as `"execution"`, `"roles"`,
`"participation"` — not inside any of them — the doubled `{{`/`}}` around
the literal JSON example inside `template` (vs. the single `{stock_kg}`
just before it, which IS meant to be substituted), and `prompt.fields` as
a DICT (here injecting one computed value, `stock_kg`) rather than a list
— an action whose template needs no injected context at all still needs
this key, just as `{}`. `outputs.fields` is omitted here entirely, so the
agent's own response (`{"harvested_kg": ..., "signature": ...}`) is
recorded verbatim, unrenamed.
