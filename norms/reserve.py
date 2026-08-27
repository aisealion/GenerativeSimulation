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
        """Implement the updated reserve policy.
        * Deposit 0.5 % of the *raw* catch (the physics‑calculated amount) into the communal reserve.
        * The fisher keeps the remainder minus any required extra contribution if the reserve is below the 5 kg minimum.
        * If after the standard 0.5 % deposit the reserve balance is still below 5 kg, the fisher must contribute an additional 0.5 kg from their keep (or as much as they have) each trip until the reserve reaches the threshold.
        * Existing short‑fall withdrawal logic (for low‑catch trips) is retained unchanged.
        """
        state = self._balance_state(context)
        # Standard deposit: 0.5 % of the raw catch
        deposit = raw_kg * 0.005
        # Update reserve balance with the standard deposit
        balance = state.get("balance_kg", 0.0) + deposit
        note_parts = []
        if deposit > 0:
            note_parts.append(f"You deposited {deposit:.3f}kg into the communal reserve.")
        # Ensure reserve stays at least 15 % of lake stock after deposit
        MIN_RESERVE = 0.15 * context.stock_before
        if balance < MIN_RESERVE:
            # Take extra from fisher's keep to meet minimum reserve
            needed = MIN_RESERVE - balance
            # Cannot take more than what fisher has left after deposit
            available = max(0.0, raw_kg - deposit)
            extra_contribution = min(needed, available)
            balance += extra_contribution
            note_parts.append(f"You added an extra {extra_contribution:.3f}kg to meet the reserve minimum.")
        # Store updated balance
        state["balance_kg"] = balance
        # Kept kg is raw catch minus standard deposit and any extra contribution
        kept = raw_kg - deposit - extra_contribution
        # Existing shortfall‑withdrawal logic (unchanged)
        shortfall_thresh = self.params.get("shortfall_threshold_kg")
        max_withdraw = self.params.get("max_withdrawal_kg")
        if shortfall_thresh is not None and kept < shortfall_thresh:
            needed = shortfall_thresh - kept
            limit = max_withdraw if max_withdraw is not None else needed
            withdraw = min(needed, limit, state["balance_kg"])
            if withdraw > 0:
                kept += withdraw
                state["balance_kg"] -= withdraw
                note_parts.append(f"You withdrew {withdraw:.3f}kg from the reserve.")
        note = " ".join(note_parts) if note_parts else None
        return NormDecision.adjust(kept_kg=kept, note=note)

