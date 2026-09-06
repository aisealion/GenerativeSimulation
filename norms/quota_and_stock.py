from dataclasses import dataclass

from engine.norms.base import Norm, NormDecision


class QuotaAndStockNorm(Norm):
    """Enforces the round‑1 policy.

    * Max 6 kg per trip – excess is discarded (or could be returned to a pool).
    * Fisher who exceeds the quota more than twice is suspended for a week (7 rounds).
    * Lake stock must stay ≥ 240 kg – if it falls below, all fishing is halted until recovered.
    """

    type_name = "quota_and_stock"

    # keys used in the per‑norm persistent state dict
    EXCESS_COUNT = "excess_count"
    SUSPENDED_UNTIL = "suspended_until"
    GLOBAL_SUSPEND = "global_suspend"

    def is_eligible(self, context, agent_id):
        """Skip agents that are under an individual suspension or a global stock suspension."""
        state = context.norm_state(self.key)
        # individual suspension
        suspended_until = state.get(self.SUSPENDED_UNTIL, 0)
        if context.round_number <= suspended_until:
            return False
        # global lake‑stock suspension
        if state.get(self.GLOBAL_SUSPEND, False):
            return False
        return True

    def on_round_start(self, context):
        """Set a global suspension when stock is below the threshold."""
        state = context.norm_state(self.key)
        if context.stock_before < 240:
            state[self.GLOBAL_SUSPEND] = True
        else:
            # clear global flag when stock has recovered
            state[self.GLOBAL_SUSPEND] = False
        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Clamp catch to 6 kg and track quota violations.

        Returns a NormDecision with the kept amount and an optional note.
        """
        state = context.norm_state(self.key)
        # ensure per‑agent counter exists
        excess_counts = state.setdefault(self.EXCESS_COUNT, {})
        count = excess_counts.get(agent_id, 0)

        if raw_kg > 6:
            # excess is discarded – keep only the quota amount
            kept = 6.0
            excess = raw_kg - kept
            count += 1
            excess_counts[agent_id] = count
            note = f"Quota exceeded by {excess:.1f} kg; kept 6 kg (violation {count})."
            # suspend after more than two violations
            if count > 2:
                state[self.SUSPENDED_UNTIL] = context.round_number + 7
                note += " Suspension for 1 week applied."
            return NormDecision.adjust(kept, note=note)
        # within quota – keep whatever previous norm decided
        return NormDecision.allow(proposed_kg)

    def on_round_end(self, context, round_results):
        """Clear the global suspension if stock has recovered after regrowth."""
        state = context.norm_state(self.key)
        # post‑regrowth stock is stored in the context after end_round processing
        if context.stock_override_kg is not None:
            # if another norm forced a stock value we respect that
            final_stock = context.stock_override_kg
        else:
            # stock after regrowth is available via context.stock_before for next round,
            # but we can look at the runtime record just created.
            # The HarvestPhase stores the post‑regrowth stock in runtime["stock_kg"].
            final_stock = context.runtime.get("stock_kg")
        if final_stock is not None and final_stock >= 240:
            # lift global suspension
            state[self.GLOBAL_SUSPEND] = False
        return None
