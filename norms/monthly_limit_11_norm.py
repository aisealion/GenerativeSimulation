"""
Round 11 norm implementing the policy from norm.txt.
Enforces per‑trip cap of 3 kg, mandatory personal keep of 1 kg, and a monthly community cap of 50 % of the lake stock at month start, capped at 10 kg.
Overage must be returned; failure results in a temporary loss of fishing privilege.
"""

from engine.norms.base import Norm, NormDecision


class MonthlyLimit11Norm(Norm):
    """Round 11 norm implementation.

    * Per‑trip: max 3 kg total catch, must retain at least 1 kg for personal use.
    * Monthly: community total harvestable catch may not exceed min(50 % of month‑start stock, 10 kg).
    * Over‑catch is allocated proportionally to agents; each must return its share before next month.
    * Agents who fail to return may be sanctioned (e.g., temporary loss of privilege).
    """

    type_name = "monthly_limit_11"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply per‑trip constraints and record catch for monthly accounting.

        Steps:
        1. Trim raw catch to the per‑trip cap of 3 kg.
        2. Ensure at least 1 kg is kept for personal use; the remainder is harvestable.
        3. Persist raw (trimmed) catch for later monthly cap enforcement.
        """
        note_parts = []
        # enforce per‑trip cap
        kept_total = raw_kg
        if kept_total > 3.0:
            kept_total = 3.0
            note_parts.append("trimmed to 3 kg per‑trip limit")

        # enforce mandatory personal keep
        if kept_total < 1.0:
            # cannot satisfy personal keep – violation, keep nothing
            note_parts.append("caught less than mandatory 1 kg personal keep")
            kept_kg = 0.0  # personal keep returned to lake (treated as violation)
            decision = NormDecision.violation(kept_kg=kept_kg, sanction="ban", note=", ".join(note_parts))
        else:
            kept_kg = 1.0  # personal keep retained by fisher
            # harvestable portion is kept_total - 1 kg (could be zero)
            decision = NormDecision.adjust(kept_kg=kept_kg, note=", ".join(note_parts) if note_parts else None)

        # record (trimmed) raw catch for monthly aggregation
        monthly = context.round_scratch(self.key)
        # store month‑start stock once per month
        if "month_start_stock" not in monthly:
            monthly["month_start_stock"] = context.stock_before
            monthly["monthly_total"] = 0.0
        # accumulate harvestable amount (trimmed total minus personal keep)
        harvestable = max(kept_total - 1.0, 0.0)
        monthly["monthly_total"] = monthly.get("monthly_total", 0.0) + harvestable
        # also keep per‑agent harvestable for proportional overage allocation
        catches = monthly.setdefault("catch_by_agent", {})
        catches[agent_id] = catches.get(agent_id, 0.0) + harvestable

        return decision

    def on_round_end(self, context, round_results):
        """Enforce monthly cap and record any required overage returns.

        The cap is the lower of 50 % of the month‑start stock and 10 kg.
        If total harvestable exceeds the cap, each agent must return a proportional share.
        The required return amounts are stored in the norm state under ``overage``.
        """
        monthly = context.round_scratch(self.key)
        if not monthly:
            return None
        month_start_stock = monthly.get("month_start_stock")
        if month_start_stock is None:
            return None
        total_harvest = monthly.get("monthly_total", 0.0)
        cap = min(0.5 * month_start_stock, 10.0)
        if total_harvest <= cap:
            return None
        overage = total_harvest - cap
        # proportional allocation based on each agent's harvestable contribution
        catches = monthly.get("catch_by_agent", {})
        state = context.norm_state(self.key)
        overage_alloc = state.setdefault("overage", {})
        for agent_id, agent_harvest in catches.items():
            if total_harvest > 0:
                share = (agent_harvest / total_harvest) * overage
                overage_alloc[agent_id] = {
                    "required_return_kg": round(share, 4),
                    "sanction": "monthly_overage",
                }
        return None
