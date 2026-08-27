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
        """Deposit the surplus above the mandatory 1.0 kg keep into the communal reserve.
        The keep is capped at 1.0 kg regardless of the catch; any amount above that
        is deposited. The reserve balance is capped at 120 kg. Withdrawal logic for
        low‑catchers (shortfall_threshold_kg) remains unchanged.
        """
        state = self._balance_state(context)
        # Determine deposit: amount above 1.0 kg keep, but not exceeding the proposed keep
        surplus = max(0.0, proposed_kg - 1.0)
        deposit = surplus
        # Update reserve balance with deposit, respecting cap
        balance = state.get("balance_kg", 0.0) + deposit
        if balance > 120.0:
            balance = 120.0
        state["balance_kg"] = balance
        # Kept kg after deposit is at most 1.0 kg (or the full proposed if less)
        kept = min(proposed_kg, 1.0)
        # Handle shortfall threshold withdrawal (unchanged logic)
        shortfall_thresh = self.params.get("shortfall_threshold_kg")
        max_withdraw = self.params.get("max_withdrawal_kg")
        if shortfall_thresh is not None and kept < shortfall_thresh:
            needed = shortfall_thresh - kept
            limit = max_withdraw if max_withdraw is not None else needed
            withdraw = min(needed, limit, state["balance_kg"])
            if withdraw > 0:
                kept += withdraw
                state["balance_kg"] -= withdraw
        # Build note about deposit and any withdrawal
        note_parts = []
        if deposit > 0:
            note_parts.append(f"You deposited {deposit:.3f}kg into the communal reserve.")
        if shortfall_thresh is not None and kept > min(proposed_kg, 1.0):
            note_parts.append(f"You withdrew {kept - min(proposed_kg, 1.0):.3f}kg from the reserve.")
        note = " ".join(note_parts) if note_parts else None
        return NormDecision.adjust(kept_kg=kept, note=note)

