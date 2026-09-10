"""Percent Stock Cap Norm: Enforces a percentage-based catch limit.

Policy: No fisher may take more than 10% of the lake's current stock per trip.
The 10% limit is calculated from the stock estimate provided by the lake-watcher.
"""

from engine.norms.base import Norm, NormDecision


class PercentStockCapNorm(Norm):
    """Enforces a percentage-based catch limit relative to estimated stock.

    If the proposed catch exceeds the percentage limit of the current stock
    estimate, it is trimmed and marked as a violation.
    """

    type_name = "percent_stock_cap"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Percentage limit as a decimal (default: 0.10 = 10%)
        self.percent_limit = params.get("percent_limit", 0.10)
        # Key of the lake_watcher norm to get stock estimate from
        self.watcher_norm_key = params.get("watcher_norm_key", "lake_watcher")

    def describe(self, context, agent_id):
        """Tell the agent about the percentage-based catch limit."""
        # Get stock estimate from lake_watcher norm
        watcher_state = context.norm_state(self.watcher_norm_key)
        stock_estimate = watcher_state.get("current_estimate_kg", context.stock_before)

        limit_kg = stock_estimate * self.percent_limit
        return f"You may take no more than {self.percent_limit*100:.0f}% of the estimated stock ({limit_kg:.1f}kg this round)."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Trim catch to the percentage limit if it exceeds it."""
        # Get stock estimate from lake_watcher norm
        watcher_state = context.norm_state(self.watcher_norm_key)
        stock_estimate = watcher_state.get("current_estimate_kg", context.stock_before)

        # Calculate the limit based on stock estimate
        limit_kg = stock_estimate * self.percent_limit

        if proposed_kg <= limit_kg:
            return NormDecision.allow(proposed_kg)

        # Exceeds percentage limit - trim and mark as violation
        excess = proposed_kg - limit_kg
        return NormDecision.violation(
            kept_kg=limit_kg,
            sanction="over_stock_limit",
            note=f"Your catch of {proposed_kg:.1f}kg exceeds {self.percent_limit*100:.0f}% of the estimated stock ({limit_kg:.1f}kg). Excess of {excess:.1f}kg must be returned before your next trip."
        )

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Record violation details for redistribution tracking."""
        if not decision.violated or decision.sanction != "over_stock_limit":
            return

        state = context.norm_state(self.key)

        # Get stock estimate for recording
        watcher_state = context.norm_state(self.watcher_norm_key)
        stock_estimate = watcher_state.get("current_estimate_kg", context.stock_before)
        limit_kg = stock_estimate * self.percent_limit

        # Record the violation for redistribution calculations
        violations = state.setdefault("violations", [])
        violations.append({
            "round": context.round_number,
            "agent_id": agent_id,
            "attempted_kg": harvested_kg + (decision.note.split("Excess of ")[1].split("kg")[0] if "Excess of " in (decision.note or "") else 0),
            "allowed_kg": harvested_kg,
            "excess_kg": harvested_kg - limit_kg if harvested_kg > limit_kg else 0,
            "stock_estimate_kg": stock_estimate,
        })

        # Track total excess for redistribution
        total_excess = state.get("total_excess_this_round", 0.0)
        excess_this_violation = max(0.0, harvested_kg - limit_kg) if harvested_kg > limit_kg else 0.0
        state["total_excess_this_round"] = total_excess + excess_this_violation
