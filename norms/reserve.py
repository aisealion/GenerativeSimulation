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
        excess = raw_kg - proposed_kg
        if excess > 0:
            # Deposit any excess (catch trimmed by earlier caps) into the reserve
            state["balance_kg"] += excess
            return NormDecision.allow(proposed_kg)

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
        # No excess or withdrawal needed; allow the proposed amount
        return NormDecision.allow(proposed_kg)

    def on_round_end(self, context, round_results):
        """Add 10% of the total harvested kg for the day to the reserve.

        This implements the policy that 10% of the daily harvest is set aside
        for future generations.
        """
        total_harvested = sum(r.get("harvested_kg", 0.0) for r in round_results.values())
        deposit = 0.1 * total_harvested
        if deposit:
            state = self._balance_state(context)
            state["balance_kg"] += deposit

