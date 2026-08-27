# HarvestContext: everything a Norm needs for one round, built exactly once
# per round and shared by every hook call for that round (never rebuilt
# mid-round — see phases/harvest.py's run(), which builds one and threads it
# through the whole agent loop).

from dataclasses import dataclass, field

from mechanisms.stock_check import available_stock


@dataclass
class HarvestContext:
    config: dict
    fluents: list
    runtime: dict
    agents: dict
    round_number: int
    stock_before: float
    scratch: dict = field(default_factory=dict)
    stock_override_kg: float | None = field(default=None, init=False)

    @classmethod
    def from_state(cls, state):
        return cls(
            config=state["config"],
            fluents=state["fluents"],
            runtime=state["runtime"],
            agents=state["agents"],
            round_number=state["round_number"],
            stock_before=available_stock(state["runtime"]),
        )

    def norm_state(self, key):
        """Cross-round-persistent state for the norm with this key — a
        reserve balance, a ban countdown. Backed by runtime["norms"][key],
        written to state/runtime.json by the simulation exactly like
        runtime["payoff"]/runtime["dead_agents"] already are — never by the
        norm-implementer directly (state/runtime.json stays off its
        allowlist; only the plugin *code* it writes touches this dict, at
        simulation run time, same as always). One namespaced sub-dict per
        norm key — this is the concrete replacement for ad hoc top-level
        runtime keys like a past round's communal_reserve_kg/banned_agents."""
        return self.runtime.setdefault("norms", {}).setdefault(key, {})

    def round_scratch(self, key):
        """This-round-only state for the norm with this key (a running
        community catch tally, say). Lives only on this HarvestContext
        instance — never persisted. A fresh instance every round means this
        always starts empty; never store something here a norm needs to
        remember next round (use norm_state() for that)."""
        return self.scratch.setdefault(key, {})

    def override_stock_after_regrowth(self, stock_kg):
        """For a round-level rule that replaces the physics-computed
        post-regrowth stock outright (a "replenish the lake" trigger) — call
        from Norm.on_round_end(), after every agent's harvest this round is
        already settled. Last caller wins if two active norms both call
        this the same round (config order) — be deliberate about ordering
        if composing two such rules."""
        self.stock_override_kg = stock_kg
