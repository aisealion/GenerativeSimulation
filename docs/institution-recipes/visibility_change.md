# Recipe: visibility_change

Who sees what, and when, changes — a ledger becomes world-readable, a
sanction becomes private, a role's own record becomes visible during a
specific action (e.g. voting).

| | |
|---|---|
| **Required** | For an institutional object: edit `state/object_types/{type}.json`'s `visibility` block (per-field, `{"who": "ALL"/"NONE"/"ROLE:<name>"}`). |
| **Required** | For a fact (a sanction, a status): the `visibility` argument to `set_fact()`/`end_fact()` (`"public"` or `"agent_only"`) at the point it's written — not something edited after the fact. |
| **Required** | For a one-off occurrence: the `Visibility` passed to `ctx.events.emit(...)` (`GLOBAL`/`PARTICIPANTS`/`ROLE_HOLDERS`/`AGENT`/`AGENT_SET`). |
| **Conditional** | If visibility should depend on *when* (e.g. "visible during voting, hidden otherwise"), that's the consuming action's own `prompt.fields` resolving it conditionally — not a change to the object/fact's own static visibility. |
| **Forbidden** | Defaulting a new sanction/obligation fact to `"agent_only"` without a reason — this project's adopted norms consistently specify public ledgers/monitors; silence should default to public unless the norm specifically calls for privacy. |
| **Verify** | `ObjectRuntime.read(..., viewer_agent_id=...)` returns `None` for a viewer the design says shouldn't see it, and the real value for one who should. `roles.roles.visible_facts()`/`render_notices()` reflects the intended audience for a fact-based visibility change. |
