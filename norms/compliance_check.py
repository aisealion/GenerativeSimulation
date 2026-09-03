# compliance_check — verifies that fishers made their required deposit into the
# communal reserve, and applies a reduced quota penalty for non-compliance.
#
# Config:
#     {
#       "type": "compliance_check",
#       "id": "compliance_check",
#       "deposit_norm_id": "communal_reserve",  # which norm tracks deposits
#       "reduced_pct": 0.06,                    # reduced catch limit (6%)
#       "normal_pct": 0.12,                     # normal catch limit (12%)
#       "trigger_sanction": "missed_deposit"    # sanction to emit on violation
#     }
#
# This norm should be placed AFTER communal_reserve in the norms list so it
# can check the deposit tracking from that norm. It maintains persistent state
# about which agents were non-compliant, and modifies the effective catch limit
# for those agents in subsequent rounds.

from engine.norms.base import Norm, NormDecision


class ComplianceCheckNorm(Norm):
    type_name = "compliance_check"

    def _compliance_state(self, context, agent_id):
        state = context.norm_state(self.key)
        return state.setdefault(agent_id, {"compliant_last_round": True, "using_reduced_quota": False})

    def describe(self, context, agent_id):
        state = self._compliance_state(context, agent_id)
        if state["using_reduced_quota"]:
            reduced_pct = self.params.get("reduced_pct", 0.06)
            return f"You missed your deposit last round. Your catch limit is reduced to {int(reduced_pct * 100)}% this round."
        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        state = self._compliance_state(context, agent_id)

        if state["using_reduced_quota"]:
            # Apply reduced quota (6% of stock)
            reduced_pct = self.params.get("reduced_pct", 0.06)
            stock = context.stock_before
            reduced_limit = reduced_pct * stock

            if proposed_kg > reduced_limit:
                trigger = self.params.get("trigger_sanction", "missed_deposit")
                return NormDecision.violation(
                    kept_kg=reduced_limit,
                    sanction=trigger,
                    note=f"Your catch exceeded the reduced {int(reduced_pct * 100)}% limit ({reduced_limit:.1f}kg) due to missed deposit."
                )

        return NormDecision.allow(proposed_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Check if this agent made their deposit this round."""
        deposit_norm_id = self.params.get("deposit_norm_id", "communal_reserve")

        # Get deposit tracking from the communal_reserve norm
        reserve_state = context.norm_state(deposit_norm_id)
        deposits_this_round = reserve_state.get("deposits_this_round", {})

        made_deposit = agent_id in deposits_this_round and deposits_this_round[agent_id] > 0

        state = self._compliance_state(context, agent_id)
        state["compliant_last_round"] = made_deposit

        # If they made a deposit this round, clear the reduced quota flag
        if made_deposit:
            state["using_reduced_quota"] = False

    def on_round_end(self, context, round_results):
        """After processing all agents, mark non-compliant agents for reduced quota next round."""
        deposit_norm_id = self.params.get("deposit_norm_id", "communal_reserve")
        reserve_state = context.norm_state(deposit_norm_id)
        deposits_this_round = reserve_state.get("deposits_this_round", {})

        for agent_id in round_results:
            state = self._compliance_state(context, agent_id)
            made_deposit = agent_id in deposits_this_round and deposits_this_round[agent_id] > 0

            # Update compliance status
            state["compliant_last_round"] = made_deposit

            if not made_deposit:
                # Mark for reduced quota next round
                state["using_reduced_quota"] = True
