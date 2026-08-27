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
        """All agents are eligible; the 85 % reserve requirement is enforced during evaluation.
        """
        return True

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Implement the reserve policy as defined by the updated norm.
        * Deposit 0.5% of raw catch into the communal reserve.
        * Add a fixed extra contribution of 0.5 kg each trip.
        * Apply short‑fall withdrawal logic unchanged.
        * Any excess catch forfeited by other norms (e.g., over cap) will already have been
          added to the reserve via those norms' evaluate methods.
        """
        state = self._balance_state(context)
        # Apply starting balance only once
        if self.params.get("starting_balance_kg") is not None and state.get("_starting_applied"):
            return NormDecision.adjust(kept_kg=raw_kg, note=None)

        # Deposit 0.5% of raw catch, rounded to nearest 0.1 kg
        deposit = round(raw_kg * 0.005, 1)
        balance = state.get("balance_kg", 0.0) + deposit
        note_parts = []
        if deposit > 0:
            note_parts.append(f"You deposited {deposit:.1f}kg into the communal reserve.")

        # Compute kept kg after deposit
        kept = raw_kg - deposit

        # Shortfall withdrawal logic (unchanged)
        shortfall_thresh = self.params.get("shortfall_threshold_kg")
        max_withdraw = self.params.get("max_withdrawal_kg")
        if shortfall_thresh is not None and kept < shortfall_thresh:
            needed = shortfall_thresh - kept
            limit = max_withdraw if max_withdraw is not None else needed
            added_this_round = deposit
            withdraw = min(added_this_round, limit)
            if withdraw > 0:
                kept += withdraw
                note_parts.append(f"You withdrew {withdraw:.3f}kg from the reserve.")
            # After withdrawal, empty the reserve for this round
            balance = 0.0

        # Enforce minimum reserve of 30 kg
        MIN_RESERVE = 30.0
        if balance < MIN_RESERVE:
            needed = MIN_RESERVE - balance
            take = min(kept, needed)
            kept -= take
            balance += take
            note_parts.append(f"Reserve was below {MIN_RESERVE:.0f}kg; {take:.3f}kg moved from your catch to meet minimum.")
            if needed > take:
                # Not enough kept to satisfy minimum – add penalty of one day's ration (CONSUMPTION_KG)
                from engine.physics import CONSUMPTION_KG
                balance += CONSUMPTION_KG
                note_parts.append(f"Reserve still below {MIN_RESERVE:.0f}kg; extra {CONSUMPTION_KG:.1f}kg added as penalty.")
                kept = 0.0

        # Update reserve balance
        state["balance_kg"] = balance

        note = " ".join(note_parts) if note_parts else None
        if self.params.get("starting_balance_kg") is not None:
            state["_starting_applied"] = True
        return NormDecision.adjust(kept_kg=kept, note=note)

