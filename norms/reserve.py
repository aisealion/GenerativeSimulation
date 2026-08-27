# reserve — a shared community reserve, fed by whatever an earlier norm in
# config order withheld from an agent this round (deposit), which
# low-catchers can draw from to top up a short trip (withdraw). Persistent
# balance lives at context.norm_state(key)["balance_kg"].
#
# Config:
#     {
#       "type": "reserve",
#       "id": "reserve",
#       "shortfall_threshold_kg": 5,   # below this kept_kg, eligible to withdraw
#       "max_withdrawal_kg": 4,        # per-trip withdrawal ceiling
#       "starting_balance_kg": 0       # only read the first round this norm's
#                                       # persistent state is empty; never
#                                       # resets an existing balance later
#     }
#
# Place this norm *after* any cap-type norm (e.g. catch_limit) in
# state["config"]["norms"] — evaluate() deposits raw_kg - proposed_kg, i.e.
# whatever's been trimmed off by every norm that already ran this call. If
# nothing ran before it, that's 0 and there's nothing to deposit that round
# for that agent, which is correct — but a misordering silently deposits
# nothing rather than raising an error, so get the order right.

from engine.norms.base import Norm, NormDecision


class ReserveNorm(Norm):
    type_name = "reserve"

    def _balance_state(self, context):
        state = context.norm_state(self.key)
        state.setdefault("balance_kg", self.params.get("starting_balance_kg", 0.0))
        return state

    def describe(self, context, agent_id):
        balance = self._balance_state(context)["balance_kg"]
        return f"The community reserve currently holds {balance:.0f}kg."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        state = self._balance_state(context)
        # 5% contribution to the communal reserve each trip (default)
        contribution_pct = self.params.get("contribution_pct", 0.05)
        contribution = raw_kg * contribution_pct
        max_allowed_keep = raw_kg - contribution
        # If agent keeps more than allowed, they failed to set aside required 5%
        if proposed_kg > max_allowed_keep:
            # entire catch (including what would have been contribution) goes to reserve
            state["balance_kg"] += raw_kg
            return NormDecision.allow(0.0, note="Failed to set aside required 5% contribution; entire catch forfeited.")
        # Otherwise, add the mandatory contribution to the reserve
        state["balance_kg"] += contribution

        # Withdrawal allowed only when lake stock drops below a threshold (default 110kg)
        stock_threshold = self.params.get("withdrawal_stock_threshold", 110)
        # Optional approval flag (e.g., majority vote) – defaults to True for now
        withdrawal_approved = self.params.get("withdrawal_approved", True)
        if context.stock_before < stock_threshold and withdrawal_approved:
            threshold = self.params.get("shortfall_threshold_kg")
            if threshold is not None and proposed_kg < threshold and state["balance_kg"] > 0:
                max_withdrawal = self.params.get("max_withdrawal_kg", state["balance_kg"])
                withdrawal = min(threshold - proposed_kg, max_withdrawal, state["balance_kg"])
                if withdrawal > 0:
                    state["balance_kg"] -= withdrawal
                    return NormDecision.adjust(
                        kept_kg=proposed_kg + withdrawal,
                        note=f"You drew {withdrawal:.0f}kg from the community reserve to top up a short trip.",
                    )
        return NormDecision.allow(proposed_kg)
