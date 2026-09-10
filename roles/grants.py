"""Declarative role/fact shapes for engine.action_base.SimpleAgentAction's
role_grant()/institutional_fact() hooks, and the functions that apply them
onto roles.roles's own primitives (assign_role()/set_fact()). Kept separate
from roles.py itself (which stays the low-level fluent primitive layer) and
from engine/action_base.py (which stays limited to the Action/SimpleAgentAction
contract) — this is purely the thin convenience layer between the two.
"""
from dataclasses import dataclass, field

from roles.roles import assign_role, set_fact


@dataclass
class RoleGrant:
    """Describes a role fluent one agent's response should create/update.
    `exclusive=True` for a role only one agent holds at a time (a rotating
    recorder/steward) — see assign_role()'s own docstring for why this
    flag exists rather than expecting the caller to pass the right `args`
    itself. `exclusive=False` (default) for a role every agent can hold
    independently and simultaneously, like "fisher"."""

    role_name: str
    exclusive: bool = False
    args: list | None = None
    narration: str | None = None
    visibility: str = "public"
    event_type: str = "fact_initiated"


@dataclass
class InstitutionalFact:
    """Describes a non-role fact one agent's response should record — a
    ledger entry, a report, an object other agents can see. Unlike
    RoleGrant, `holder` isn't necessarily the acting agent: pass
    "community" for a fact that belongs to everyone rather than one
    fisher. `narration` is required (an un-narrated fact should just call
    roles.roles.set_fact() directly — this type exists specifically for
    the visible/memory-worthy case)."""

    fluent_name: str
    holder: str
    narration: str
    args: list = field(default_factory=list)
    visibility: str = "public"
    event_type: str = "fact_initiated"


def apply_role_grant(fluents, round_number, agent_id, grant):
    return assign_role(
        grant.role_name, agent_id, fluents, round_number,
        args=grant.args, exclusive=grant.exclusive,
        narration=grant.narration, visibility=grant.visibility,
        event_type=grant.event_type,
    )


def apply_institutional_fact(fluents, round_number, fact):
    return set_fact(
        fluents, fact.fluent_name, fact.args, fact.holder, round_number,
        narration=fact.narration, visibility=fact.visibility,
        event_type=fact.event_type,
    )
