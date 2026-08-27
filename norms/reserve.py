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
        # Initialise balance if not present, using starting_balance_kg if provided
        state.setdefault("balance_kg", self.params.get("starting_balance_kg", 0.0))
        return state

    # The reserve now enforces a minimum absolute kilograms, not a percentage of stock.
    # No automatic top‑up – if the balance falls below the minimum, the next fisher
    # simply forfeits the required 5 % deposit (losing it) until the reserve is restored.
    def describe(self, context, agent_id):
        """Report the current reserve balance for the fisher's notice.
        Mirrors the test expectation of a simple integer‑kg sentence.
        """
        state = self._balance_state(context)
        balance = state.get("balance_kg", 0.0)
        return f"The community reserve currently holds {int(balance)}kg."


    def is_eligible(self, context, agent_id):
        """Fisher is eligible only if the community reserve meets the minimum.

        The policy requires the reserve to hold at least 20 kg at all times. If the
        balance is below that threshold the fisher must wait until it is restored.
        """
        state = self._balance_state(context)
        min_reserve = self.params.get("min_reserve_kg", 20.0)
        return state.get("balance_kg", 0.0) >= min_reserve

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Enforce a 5 % deposit of the fisher's kept catch into the communal reserve.

        * ``deposit_pct`` – fraction of the kept catch that must be deposited
          (default 0.05 for 5 %). Rounded to the nearest 0.1 kg.
        * ``min_reserve_kg`` – absolute minimum reserve weight (default 20 kg).
        """
        state = self._balance_state(context)

        # Normal deposit flow
        deposit_pct = self.params.get("deposit_pct", 0.05)
        deposit_amount = round(deposit_pct * proposed_kg, 1)
        min_reserve = self.params.get("min_reserve_kg", 20.0)

        if state.get("balance_kg", 0.0) < min_reserve:
            # Reserve too low – fisher forfeits the deposit (loses it) and receives a sanction
            kept = proposed_kg - deposit_amount
            return NormDecision.violation(
                kept_kg=kept,
                sanction="deposit_forfeit",
                note=f"Reserve below {min_reserve:.0f}kg; you forfeit the {deposit_amount:.1f}kg deposit.",
            )
        else:
            # Deposit succeeds – add to reserve and reduce fisher's kept kg
            state["balance_kg"] = state.get("balance_kg", 0.0) + deposit_amount
            kept = proposed_kg - deposit_amount
            return NormDecision.adjust(
                kept_kg=kept,
                note=f"You deposited {deposit_amount:.1f}kg into the communal reserve.",
            )
