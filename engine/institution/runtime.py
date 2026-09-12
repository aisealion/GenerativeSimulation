# ActionRuntime: the one thing engine/simulate.py calls per action per
# round, replacing the old `action_module.ACTION.run(state)`. Resolves an
# ActionSpec's execution.handler to either a builtin (Level 2, zero code)
# or a discovered actions/handlers/{name}.py function (Level 3/4, or one of
# the 5 protected actions ported 1:1), calls it, and finishes the
# round-record bookkeeping every handler used to have to do for itself.

import importlib

from engine.institution import builtin_handlers
from engine.institution.context import ActionContext


def resolve_handler(handler_name):
    """A builtin (an attribute of engine.institution.builtin_handlers)
    takes precedence by name; otherwise `handler_name` is a filename stem
    under actions/handlers/. Raises immediately, with a clear message, if
    neither resolves — the same fail-fast posture engine/norms/registry.py
    already has for an unknown norm type."""
    builtin = getattr(builtin_handlers, handler_name, None)
    if callable(builtin):
        return builtin
    try:
        module = importlib.import_module(f"actions.handlers.{handler_name}")
    except ModuleNotFoundError as exc:
        raise ValueError(
            f"execution.handler {handler_name!r} is neither a builtin "
            f"(engine.institution.builtin_handlers) nor actions/handlers/{handler_name}.py"
        ) from exc
    handler = getattr(module, "run", None)
    if not callable(handler):
        raise ValueError(f"actions/handlers/{handler_name}.py has no callable run(ctx) function")
    return handler


def resolve_memory_writes(handler_name):
    """A handler module's optional `memory_writes(state, round_record)`
    function, or a no-op if it has none — mirrors resolve_handler()'s
    builtin-first lookup (a builtin like generic_agent_decision never
    contributes memory writes on its own; the institutional side effect
    worth remembering, if any, belongs to a custom handler that actually
    knows what happened)."""
    if hasattr(builtin_handlers, handler_name):
        return lambda state, record: []
    try:
        module = importlib.import_module(f"actions.handlers.{handler_name}")
    except ModuleNotFoundError:
        return lambda state, record: []
    return getattr(module, "memory_writes", lambda state, record: [])


class ActionRuntime:
    @staticmethod
    def run_action(spec, state, round_number):
        """Builds the ActionContext, dispatches to the resolved handler,
        and appends the result to state["runtime"]["rounds"] — a handler
        returns the round_record's own content (whatever
        SimpleAgentAction.run()'s fixed section or a custom Action.run()
        used to build); "round"/"action" are filled in here if the handler
        didn't already set them, so a handler never has to repeat that
        boilerplate."""
        ctx = ActionContext.build(spec, state, round_number)
        handler = resolve_handler(spec["execution"]["handler"])
        round_record = handler(ctx)
        round_record.setdefault("round", round_number)
        round_record.setdefault("action", spec["name"])

        runtime = state["runtime"]
        runtime["round"] = round_number
        runtime["rounds"].append(round_record)
        return round_record
