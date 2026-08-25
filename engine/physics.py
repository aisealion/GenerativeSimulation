"""Fixed simulation physics — never editable by the norm-implementer,
regardless of what any norm asks for. Ported directly from Gupta et al.'s
CPR-game codebase (Codes/Gupta/CPRG_fishing, branch origin/hiromu/llm-norm,
ostrom3/Agent.py and Model.py), not this project's own design — a norm can
change caps, deposits, bans, and schedules (all implementer-owned, in
mechanisms/ and phases/), but the underlying catch equation, regrowth
rate, and survival economics below are the fixed rules of the world those
choices play out against, not something a community vote should be able
to rewrite.

Lives under engine/ specifically so it's outside the norm-implementer's
permission.edit allowlist (mechanisms/*, phases/*, prompts/*, plus a few
named files) by construction, the same way engine/simulate.py and
engine/llm_agents.py already are. The rate constants below live here for
the same reason the equations do, not in state/config.json (which the
norm-implementer can freely edit) — a fixed formula reading a
norm-implementer-editable rate is exactly as rewritable as the formula
itself would be.
"""

HARVEST_PRODUCTIVITY = 0.05  # catchability coefficient q in catch_from_effort()
GROWTH_RATE = 0.2  # logistic growth rate in apply_regrowth()
CARRYING_CAPACITY_KG = 300  # lake's ceiling, also its starting stock
CONSUMPTION_KG = 1.0  # fixed per-round cost every fisher owes just to get by


def catch_from_effort(effort, stock_kg):
    """Linear Schaefer-style catch equation (catch = effort x stock x
    catchability), matching Gupta et al.'s CPRAgent.harvest(). effort is
    the agent's own [0.0, 1.0] fishing-intensity choice; HARVEST_PRODUCTIVITY
    is their catchability coefficient q."""
    return effort * stock_kg * HARVEST_PRODUCTIVITY


def apply_regrowth(stock_kg):
    """Logistic growth on the leftover (post-harvest) stock — matches
    Gupta et al.'s CPRModel.step():
    ΔR = growth_rate * R * (1 - R/capacity), applied to what's left after
    harvest, not a flat per-round add. Growth slows as the stock nears
    carrying capacity and (unlike a flat add) can't outrun a depleted lake."""
    grown = stock_kg + GROWTH_RATE * stock_kg * (1 - stock_kg / CARRYING_CAPACITY_KG)
    return min(grown, CARRYING_CAPACITY_KG)


def apply_consumption(payoff, harvested_kg):
    """Running per-agent balance: this trip's catch in, the fixed
    consumption cost out — matches Gupta et al.'s CPRAgent.harvest():
    self.payoff += harvest_amount; self.payoff -= self.model.consumption.
    Unlike catch/regrowth this isn't about the lake at all — it's whether
    a fisher can keep feeding themselves from what they bring in."""
    return payoff + harvested_kg - CONSUMPTION_KG


def is_dead(payoff):
    """Matches Gupta et al.'s `if self.payoff < 0: self.dead = True` —
    permanent once true; nothing in this project ever resurrects an agent."""
    return payoff < 0


def alive_agent_ids(agents, runtime):
    """The agent_id iteration order every phase should use, not
    state["agents"] directly — excludes anyone in runtime["dead_agents"].
    One shared helper so death exclusion can't be forgotten by a phase
    rewrite the way a hand-rolled check per phase could be."""
    dead = set(runtime.get("dead_agents", []))
    return [agent_id for agent_id in agents if agent_id not in dead]
