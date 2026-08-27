# stock_reserve_fisher_limit — enforce community reserve percentage and per‑fisher trip cap.
#
# Config (one entry in state["config"]["norms"]):
# {
#   "type": "stock_reserve_fisher_limit",
#   "id": "stock_reserve_fisher_limit",   # optional, defaults to "type"
#   "reserve_pct": 0.35,                    # fraction of stock_before to keep in reserve
#   "fisher_pct": 0.07                      # fraction of *remaining* stock (after reserve) each fisher may catch per trip
# }
#
# This norm tracks a persistent reserve balance (kg) via context.norm_state().
# At the start of each evaluation it ensures the reserve is at least the target
# percentage of the current lake stock. If the reserve is under‑funded, the norm
# withdraws fish from the agent's proposed catch to top it up. After the reserve
# is satisfied, the norm caps the agent's keep at fisher_pct of the remaining
# stock. Any excess fish is deposited back into the reserve and the fisher loses
# that portion of their allowance (the norm returns an `adjust` decision with a
# note explaining the action).

from engine.norms.base import Norm, NormDecision


class StockReserveFisherLimitNorm(Norm):
    type_name = "stock_reserve_fisher_limit"

    def _state(self, context):
        """Return the per‑norm persistent dict, ensuring a default balance.
        """
        state = context.norm_state(self.key)
        state.setdefault("reserve_kg", 0.0)
        return state

    def describe(self, context, agent_id):
        # Optional: describe current reserve and per‑fisher limit.
        st = self._state(context)
        reserve = st["reserve_kg"]
        target = self.params.get("reserve_pct", 0.35) * context.stock_before
        remaining = context.stock_before - reserve
        fisher_limit = self.params.get("fisher_pct", 0.07) * max(0.0, remaining)
        return (
            f"Reserve: {reserve:.0f}/{target:.0f}kg. "
            f"Your trip cap: {fisher_limit:.0f}kg."
        )

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        # Ensure reserve meets the required percentage.
        reserve_pct = self.params.get("reserve_pct", 0.35)
        fisher_pct = self.params.get("fisher_pct", 0.07)
        stock_before = context.stock_before
        target_reserve = reserve_pct * stock_before

        st = self._state(context)
        reserve = st["reserve_kg"]
        # If reserve is below target, take from this agent's proposed catch.
        if reserve < target_reserve and proposed_kg > 0:
            needed = target_reserve - reserve
            take = min(needed, proposed_kg)
            reserve += take
            proposed_kg -= take
            st["reserve_kg"] = reserve
            # Note the withdrawal for transparency.
            note = f"{take:.0f}kg taken from your catch to replenish the community reserve."
            # Continue to enforce fisher limit on the reduced amount.
        else:
            note = None

        # Compute remaining stock after the (updated) reserve.
        remaining_stock = max(0.0, stock_before - reserve)
        fisher_limit = fisher_pct * remaining_stock

        if proposed_kg <= fisher_limit:
            # No further adjustment needed.
            return NormDecision.allow(proposed_kg) if note is None else NormDecision.adjust(proposed_kg, note=note)

        # Exceeds fisher limit – excess goes back into reserve.
        excess = proposed_kg - fisher_limit
        reserve += excess
        st["reserve_kg"] = reserve
        adjusted_note = (
            f"{excess:.0f}kg exceeds your per‑trip cap of {fisher_limit:.0f}kg; "
            f"the excess is returned to the community reserve."
        )
        # Combine with any earlier note.
        if note:
            adjusted_note = note + " " + adjusted_note
        return NormDecision.adjust(fisher_limit, note=adjusted_note)
