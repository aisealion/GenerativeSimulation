"""Monthly Stock Suspension Norm: Community-wide suspension when stock is low.

Policy: Monthly stock is measured by a random net haul at a fixed spot;
the council averages weight per fish, extrapolates to the whole lake, and
if the estimate is <200kg the council announces a one-week suspension
effective the next day.
"""

from engine.norms.base import Norm


class MonthlyStockSuspensionNorm(Norm):
    """Implements monthly stock measurement and community suspension.

    Every 30 rounds (monthly), checks if stock < 200kg.
    If so, all fishers are banned for 7 rounds (one week) starting next round.
    """

    type_name = "monthly_stock_suspension"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Stock threshold in kg (default: 200kg)
        self.threshold_kg = params.get("threshold_kg", 200.0)
        # Measurement interval in rounds (default: 30 = monthly)
        self.measurement_interval = params.get("measurement_interval_rounds", 30)
        # Suspension duration in rounds (default: 7 = one week)
        self.suspension_duration = params.get("suspension_duration_rounds", 7)

    def describe(self, context, agent_id):
        """Tell agents about any active community suspension."""
        state = context.norm_state(self.key)
        suspension_end = state.get("suspension_end_round", 0)

        if suspension_end > context.round_number:
            remaining = suspension_end - context.round_number
            return f"Community fishing suspension in effect for {remaining} more round(s) due to low stock."

        # Also warn if a measurement is coming
        last_check = state.get("last_measurement_round", 0)
        next_check = last_check + self.measurement_interval
        rounds_until_check = next_check - context.round_number

        if 0 < rounds_until_check <= 5:
            return f"Monthly stock measurement in {rounds_until_check} round(s)."

        return None

    def is_eligible(self, context, agent_id):
        """Check if community suspension is active."""
        state = context.norm_state(self.key)
        suspension_end = state.get("suspension_end_round", 0)

        if suspension_end > context.round_number:
            # Community suspension is active
            return False

        return True

    def on_round_start(self, context):
        """Perform monthly stock measurement if it's time."""
        state = context.norm_state(self.key)

        # Initialize if first round
        if "last_measurement_round" not in state:
            state["last_measurement_round"] = 0
            state["suspension_end_round"] = 0
            state["measurement_history"] = []

        last_check = state["last_measurement_round"]
        next_check = last_check + self.measurement_interval

        # Check if it's time for monthly measurement
        if context.round_number >= next_check:
            # Perform measurement
            current_stock = context.stock_before
            below_threshold = current_stock < self.threshold_kg

            # Record measurement
            measurement = {
                "round": context.round_number,
                "stock_kg": current_stock,
                "threshold_kg": self.threshold_kg,
                "below_threshold": below_threshold,
            }
            state["measurement_history"].append(measurement)
            state["last_measurement_round"] = context.round_number

            # If below threshold, announce suspension effective next round
            if below_threshold:
                suspension_start = context.round_number + 1
                suspension_end = suspension_start + self.suspension_duration - 1
                state["suspension_end_round"] = suspension_end
                measurement["suspension_imposed"] = True
                measurement["suspension_start_round"] = suspension_start
                measurement["suspension_end_round"] = suspension_end

    def on_round_end(self, context, round_results):
        """Record round results for the ledger."""
        state = context.norm_state(self.key)

        # Track total community catch this round
        total_catch = sum(
            r["harvested_kg"] for r in round_results.values()
            if r.get("participated", False)
        )

        ledger = state.setdefault("round_ledger", [])
        ledger.append({
            "round": context.round_number,
            "total_catch_kg": total_catch,
            "stock_before": context.stock_before,
            "suspension_active": state.get("suspension_end_round", 0) > context.round_number,
        })
