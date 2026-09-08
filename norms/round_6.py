from dataclasses import dataclass
from engine.norms.base import Norm, NormDecision

# Constants for Round 6 policy
CAP_KG = 5.0                     # Maximum catch per trip (kg)
DEPOSIT_PCT = 0.30               # 30 % of caught weight goes to communal reserve
RESERVE_MIN_PCT = 0.30           # Reserve must hold at least 30 % of lake biomass
BAN_TRIGGER_PCT = 0.35           # Ban triggers when reserve falls below 35 % of biomass
BAN_INCREASE_KG = 5.0            # Additional deposits needed to lift a ban
PENALTY_KG = 1.0                 # Penalty added to reserve for missed deposit


class Round6Norm(Norm):
    type_name: str = "round_6"

    def describe(self, context, agent_id):
        """Human‑readable description shown to the fisher."""
        return (
            f"Cap {CAP_KG} kg per trip, deposit {int(DEPOSIT_PCT*100)}% of catch. "
            f"Reserve must stay ≥ {int(RESERVE_MIN_PCT*100)}% of lake stock; "
            f"ban triggers below {int(BAN_TRIGGER_PCT*100)}%"
        )

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply the cap, compute the required deposit and handle violations.

        * If the capped catch is enough to cover the 30 % deposit, the fisher keeps the
          remainder and the deposit amount is recorded for end‑of‑round aggregation.
        * If the catch is too small to meet the deposit requirement, the fisher loses
          the right to keep any fish this trip (kept_kg = 0) and a 1 kg penalty is
          added to the communal reserve.
        """
        # Enforce the per‑trip cap.
        capped = min(raw_kg, CAP_KG)
        required_deposit = DEPOSIT_PCT * capped

        if capped >= required_deposit:
            # Normal case – deposit the required portion.
            deposit = required_deposit
            kept = capped - deposit
            context.round_scratch(self.key).setdefault("deposits", []).append(deposit)
            # No penalty for this fisher.
            context.round_scratch(self.key).setdefault("penalties", []).append(0.0)
            return NormDecision.adjust(kept_kg=kept, note="deposit applied")
        else:
            # Not enough catch to satisfy the deposit rule.
            # Fisher keeps nothing this trip; a fixed penalty is added to the reserve.
            context.round_scratch(self.key).setdefault("deposits", []).append(0.0)
            context.round_scratch(self.key).setdefault("penalties", []).append(PENALTY_KG)
            return NormDecision.violation(
                kept_kg=0.0,
                sanction="no_fishing",
                note=f"insufficient catch for 30% deposit, {PENALTY_KG} kg penalty added to reserve",
            )

    def on_round_end(self, context, round_results):
        """Update the communal reserve and manage the temporary ban status.

        The reserve is increased by all recorded deposits and any penalties incurred.
        If the reserve falls below the ban trigger level (35 % of current stock), a
        ban becomes active. The ban is lifted once the reserve reaches either the
        trigger level again or has grown by ``BAN_INCREASE_KG`` relative to the
        reserve size when the ban started.
        """
        state = context.norm_state(self.key)
        reserve = state.get("reserve_kg", 0.0)

        # Aggregate deposits and penalties for this round.
        deposits = sum(context.round_scratch(self.key).get("deposits", []))
        penalties = sum(context.round_scratch(self.key).get("penalties", []))
        new_reserve = reserve + deposits + penalties
        state["reserve_kg"] = new_reserve

        # Evaluate ban conditions.
        ban_active = state.get("ban_active", False)
        stock = context.stock_before  # lake biomass at start of the round
        trigger_level = BAN_TRIGGER_PCT * stock

        if not ban_active:
            if new_reserve < trigger_level:
                # Ban starts now.
                state["ban_active"] = True
                state["ban_start_reserve"] = new_reserve
        else:
            # Ban is already active – check if it can be lifted.
            start_reserve = state.get("ban_start_reserve", 0.0)
            lift_by_increase = start_reserve + BAN_INCREASE_KG
            if new_reserve >= trigger_level or new_reserve >= lift_by_increase:
                # Ban ends.
                state["ban_active"] = False
                state.pop("ban_start_reserve", None)
        return None
