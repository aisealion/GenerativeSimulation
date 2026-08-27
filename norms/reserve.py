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
        # Deposit any excess catch into the reserve
        excess = raw_kg - proposed_kg
        if excess > 0:
            state["balance_kg"] += excess
            return NormDecision.allow(proposed_kg)

        # Minimum catch per policy (default 1kg)
        min_catch = self.params.get("min_catch_kg", 1)
        if proposed_kg < min_catch and state["balance_kg"] > 0:
            # Determine maximum withdrawal allowed per trip
            max_withdrawal = self.params.get("max_withdrawal_kg", state["balance_kg"])
            needed = min_catch - proposed_kg
            withdrawal = min(needed, max_withdrawal, state["balance_kg"])
            if withdrawal > 0:
                state["balance_kg"] -= withdrawal
                return NormDecision.adjust(
                    kept_kg=proposed_kg + withdrawal,
                    note=f"You drew {withdrawal:.0f}kg from the community reserve to meet the minimum catch.",
                )
        return NormDecision.allow(proposed_kg)
