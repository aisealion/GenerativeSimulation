# communal_reserve — a mandatory percentage deposit from each fisher's catch
# into a communal reserve, with lake replenishment triggered when stock falls
# below a threshold.
#
# Config:
#     {
#       "type": "communal_reserve",
#       "id": "communal_reserve",
#       "deposit_pct": 0.10,               # percentage of kept catch to deposit
#       "replenish_threshold_kg": 100,     # stock level below which reserve is used
#       "starting_balance_kg": 0           # initial reserve balance (first round only)
#     }
#
# This norm should be placed AFTER catch_limit and reserve in the norms list,
# as it operates on the final kept amount after those norms have processed.
# It deducts the deposit percentage from the fisher's final payoff and adds it
# to the communal reserve balance. At round end, if stock < threshold, the
# reserve is used to replenish the lake.

from engine.norms.base import Norm, NormDecision


class CommunalReserveNorm(Norm):
    type_name = "communal_reserve"

    def _reserve_state(self, context):
        state = context.norm_state(self.key)
        state.setdefault("balance_kg", self.params.get("starting_balance_kg", 0.0))
        return state

    def describe(self, context, agent_id):
        deposit_pct = self.params.get("deposit_pct", 0.10)
        balance = self._reserve_state(context)["balance_kg"]
        pct_display = int(deposit_pct * 100)
        return f"You must deposit {pct_display}% of your catch into the communal reserve (currently {balance:.0f}kg)."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        deposit_pct = self.params.get("deposit_pct", 0.10)
        deposit_amount = proposed_kg * deposit_pct
        final_kept = proposed_kg - deposit_amount

        # Add deposit to reserve balance
        state = self._reserve_state(context)
        state["balance_kg"] += deposit_amount

        # Track that this agent made their deposit (for compliance checking)
        if "deposits" not in state:
            state["deposits"] = {}
        state["deposits"][agent_id] = deposit_amount

        note = f"You deposited {deposit_amount:.1f}kg ({int(deposit_pct * 100)}%) into the communal reserve."
        return NormDecision.adjust(kept_kg=final_kept, note=note)

    def on_round_end(self, context, round_results):
        """Check if lake needs replenishment and apply if necessary."""
        threshold = self.params.get("replenish_threshold_kg", 100)
        stock = context.stock_before  # Stock at start of round

        if stock < threshold:
            state = self._reserve_state(context)
            balance = state.get("balance_kg", 0.0)

            if balance > 0:
                # Replenish the lake from the reserve
                # New stock = current stock + reserve balance
                new_stock = stock + balance
                context.override_stock_after_regrowth(new_stock)
                state["balance_kg"] = 0.0
                state["last_replenishment_kg"] = balance
                state["last_replenishment_round"] = context.round_number

        # Clear deposits tracking for next round
        state = self._reserve_state(context)
        if "deposits" in state:
            state["deposits_this_round"] = state["deposits"]
            state["deposits"] = {}
