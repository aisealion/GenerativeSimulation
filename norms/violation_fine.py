"""Violation Fine Norm: Imposes 2% fine for violations.

Policy: Violations trigger a fine equal to 2% of the lake's stock at the
moment of the infraction, paid to the community by the lake-watcher.
"""

from engine.norms.base import Norm, NormDecision
from roles.roles import current_holder


class ViolationFineNorm(Norm):
    """Calculates and records fines for violations.

    Listens for violations from percent_stock_cap (over_stock_limit) and
    reserve_verification (reserve_shortfall). Calculates fine as 2% of
    lake stock at infraction time and records it in the community fund.
    """

    type_name = "violation_fine"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Fine percentage as a decimal (default: 0.02 = 2%)
        self.fine_percent = params.get("fine_percent", 0.02)
        # Key of the lake_watcher norm to get watcher from
        self.watcher_norm_key = params.get("watcher_norm_key", "lake_watcher")

    def describe(self, context, agent_id):
        """Tell the agent about the violation fine policy."""
        stock = context.stock_before
        fine_kg = stock * self.fine_percent
        return f"Violations incur a fine of {self.fine_percent*100:.0f}% of lake stock ({fine_kg:.1f}kg this round), collected for the community fund."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """This norm doesn't modify catches, only records fines post-violation."""
        return NormDecision.allow(proposed_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Record fine for any violations detected."""
        if not decision.violated:
            return

        # Only fine specific violation types
        if decision.sanction not in ("over_stock_limit", "reserve_shortfall"):
            return

        # Calculate fine: 2% of stock at trip start
        stock_at_infraction = context.stock_before
        fine_kg = stock_at_infraction * self.fine_percent

        # Get current watcher
        fluents = context.fluents
        agents = context.agents
        watcher_id = current_holder(fluents, "lake_watcher", context.round_number)
        watcher_name = agents.get(watcher_id, {}).get("name", "the watcher") if watcher_id else "consensus"

        # Record the fine
        state = context.norm_state(self.key)
        fines = state.setdefault("fines", [])
        fine_record = {
            "round": context.round_number,
            "agent_id": agent_id,
            "agent_name": agents.get(agent_id, {}).get("name", agent_id),
            "violation_type": decision.sanction,
            "stock_kg_at_infraction": stock_at_infraction,
            "fine_kg": fine_kg,
            "collected_by": watcher_name,
            "watcher_id": watcher_id,
        }
        fines.append(fine_record)

        # Update total fines collected
        total_fines = state.get("total_fines_collected_kg", 0.0)
        state["total_fines_collected_kg"] = total_fines + fine_kg

        # Also update the community fund in lake_watcher's state
        watcher_state = context.norm_state(self.watcher_norm_key)
        community_fund = watcher_state.get("community_fund_kg", 0.0)
        watcher_state["community_fund_kg"] = community_fund + fine_kg

        # Update this agent's ledger entry with fine information
        communal_ledger = watcher_state.setdefault("communal_ledger", [])
        # Find the entry for this agent in this round
        for entry in communal_ledger:
            if entry["round"] == context.round_number and entry["agent_id"] == agent_id:
                entry["fine_kg"] = fine_kg
                entry["violation"] = True
                entry["violation_type"] = decision.sanction
                break

    def on_round_end(self, context, round_results):
        """Record round summary of fines."""
        state = context.norm_state(self.key)

        # Count fines this round
        round_fines = [
            f for f in state.get("fines", [])
            if f["round"] == context.round_number
        ]

        if round_fines:
            total_fine_kg = sum(f["fine_kg"] for f in round_fines)
            state["last_round_fine_total_kg"] = total_fine_kg
            state["last_round_violation_count"] = len(round_fines)
