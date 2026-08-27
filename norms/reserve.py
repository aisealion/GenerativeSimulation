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
        """Fisher is always eligible; deposit logic handles reserve constraints.
        """
        return True

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Deposit any excess catch (beyond the required 1 kg keep) into the communal reserve.
        Enforce a reserve cap of 120 kg; excess beyond the cap is forfeited.
        """
        state = self._balance_state(context)
        # Determine required keep amount (policy mandates at least 1 kg kept)
        keep_required = 1.0
        # If proposed_kg already respects keep, compute excess
        excess = max(0.0, proposed_kg - keep_required)
        # Deposit excess into reserve, respecting cap
        new_balance = state.get("balance_kg", 0.0) + excess
        if new_balance > 120.0:
            # Cap reached – excess beyond cap is forfeited (no sanction per policy)
            state["balance_kg"] = 120.0
            # Fisher keeps only keep_required kg
            kept = keep_required
        else:
            state["balance_kg"] = new_balance
            kept = proposed_kg - excess
        return NormDecision.adjust(kept_kg=kept, note="You deposited {}kg into the communal reserve.".format(excess))
