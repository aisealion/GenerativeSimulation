from dataclasses import dataclass
from engine.norms.base import Norm, NormDecision

BASE_QUOTA_PCT = 0.18  # 18% of current stock
DEPOSIT_PCT = 0.05    # 5% of catch goes to communal reserve
OVERQUOTA_MULT = 0.9  # multiplier per consecutive over‑quota trip
SUSPEND_AFTER = 3     # consecutive over‑quota trips before suspension

class Round4Norm(Norm):
    type_name: str = "round_4"

    def describe(self, context, agent_id):
        # Provide a concise description shown to the fisher.
        return (
            f"Quota: {int(BASE_QUOTA_PCT*100)}% of lake stock, "
            f"deposit {int(DEPOSIT_PCT*100)}% of catch. "
            "Over‑quota trips reduce next quota by 10% each, three in a row → suspension."
        )

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        # Persistent per‑agent state for this norm.
        state = context.norm_state(self.key)
        agent_state = state.setdefault(agent_id, {"streak": 0, "suspended": False})

        # If the fisher is suspended, they get nothing this trip.
        if agent_state.get("suspended"):
            # Record a zero deposit (nothing to add).
            context.round_scratch(self.key).setdefault("deposits", []).append(0.0)
            return NormDecision.violation(
                kept_kg=0.0,
                sanction="suspended",
                note="suspended for one trip",
            )

        # Base quota based on current stock.
        base_quota = BASE_QUOTA_PCT * context.stock_before
        # Adjust for any consecutive over‑quota streak.
        adjusted_quota = base_quota * (OVERQUOTA_MULT ** agent_state.get("streak", 0))

        # Deposit 5% of the raw catch regardless of quota outcome.
        deposit = DEPOSIT_PCT * raw_kg
        context.round_scratch(self.key).setdefault("deposits", []).append(deposit)

        if raw_kg > adjusted_quota:
            # Over‑quota: keep only the adjusted quota.
            kept = adjusted_quota
            # Mark this fisher as over‑quota for end‑of‑round processing.
            context.round_scratch(self.key).setdefault("over_quota", []).append(agent_id)
            return NormDecision.adjust(
                kept_kg=kept,
                note=f"over‑quota, quota {adjusted_quota:.2f} kg, deposit {deposit:.2f} kg",
            )
        else:
            # Within quota: keep full catch.
            kept = raw_kg
            # Reset streak for this fisher – handled in on_round_end.
            return NormDecision.adjust(
                kept_kg=kept,
                note=f"within quota, deposit {deposit:.2f} kg",
            )

    def on_round_end(self, context, round_results):
        # Update persistent communal reserve.
        state = context.norm_state(self.key)
        reserve = state.get("reserve_kg", 0.0)
        deposits = sum(context.round_scratch(self.key).get("deposits", []))
        state["reserve_kg"] = reserve + deposits

        # Determine which agents were over‑quota this round.
        over_agents = set(context.round_scratch(self.key).get("over_quota", []))
        all_agents = set(round_results.keys())

        for agent_id in all_agents:
            agent_state = state.setdefault(agent_id, {"streak": 0, "suspended": False})
            if agent_id in over_agents:
                # Increment streak.
                agent_state["streak"] = agent_state.get("streak", 0) + 1
                # Apply suspension if streak reaches the threshold.
                if agent_state["streak"] >= SUSPEND_AFTER:
                    agent_state["suspended"] = True
            else:
                # Reset streak and clear any suspension flag.
                agent_state["streak"] = 0
                agent_state["suspended"] = False
        return None
