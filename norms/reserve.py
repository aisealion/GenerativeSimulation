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
        """Fisher is eligible unless stock is low and reserve is insufficient.
        Policy: when lake stock is below 6 kg, fishing is suspended until the
        communal reserve has at least 12 kg.
        """
        if context.stock_before < 6:
            state = self._balance_state(context)
            if state.get("balance_kg", 0.0) < 12.0:
                return False
        return True

def evaluate(self, context, agent_id, raw_kg, proposed_kg):
            """Deposit the policy‑specified amount into the communal reserve based on the current lake stock,
            enforce the deposit, and optionally withdraw to satisfy a shortfall threshold.
            The reserve balance is capped at 120 kg; excess beyond the cap is forfeited.
            """
            state = self._balance_state(context)
            # Determine deposit amount based on lake stock thresholds
            stock = context.stock_before
            if stock >= 12:
                deposit_amount = self.params.get('deposit_kg_12', 0.5)
            elif stock >= 8:
                deposit_amount = self.params.get('deposit_kg_8_12', 0.3)
            elif stock >= 6:
                deposit_amount = self.params.get('deposit_kg_6_8', 0.2)
            else:
                deposit_amount = 0.0
            # Ensure deposit does not exceed the proposed keep amount
            deposit = min(deposit_amount, proposed_kg)
            # Update reserve balance with the deposit
            balance = state.get("balance_kg", 0.0) + deposit
            if balance > 120.0:
                # Cap reached – excess beyond cap is forfeited
                state["balance_kg"] = 120.0
                # Any deposit above the cap is effectively lost
                deposit = max(0.0, 120.0 - state.get("balance_kg", 0.0))
            else:
                state["balance_kg"] = balance
            # Compute kept kilograms after deposit
            kept = max(0.0, proposed_kg - deposit)
            # Withdrawal handling for shortfall (unchanged logic)
            shortfall_thresh = self.params.get("shortfall_threshold_kg")
            max_withdraw = self.params.get("max_withdrawal_kg")
            if shortfall_thresh is not None and kept < shortfall_thresh:
                needed = shortfall_thresh - kept
                limit = max_withdraw if max_withdraw is not None else needed
                withdraw = min(needed, limit, state["balance_kg"])
                if withdraw > 0:
                    kept += withdraw
                    state["balance_kg"] -= withdraw
            note_parts = []
            if deposit > 0:
                note_parts.append(f"You deposited {deposit}kg into the communal reserve.")
            if shortfall_thresh is not None and kept > proposed_kg - deposit:
                note_parts.append(f"You withdrew {kept - (proposed_kg - deposit)}kg from the reserve.")
            note = " ".join(note_parts) if note_parts else None
            return NormDecision.adjust(kept_kg=kept, note=note)
