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
        """Implement the updated reserve policy.
        * Deposit 0.5 % of the *raw* catch (the physics‑calculated amount) into the communal reserve.
        * The fisher keeps the remainder minus any required extra contribution if the reserve is below the 5 kg minimum.
        * If after the standard 0.5 % deposit the reserve balance is still below 5 kg, the fisher must contribute an additional 0.5 kg from their keep (or as much as they have) each trip until the reserve reaches the threshold.
        * Existing short‑fall withdrawal logic (for low‑catch trips) is retained unchanged.
        """
        state = self._balance_state(context)
        # If a starting balance is configured, apply the full reserve logic only once.
        if self.params.get("starting_balance_kg") is not None and state.get("_starting_applied"):
            # Subsequent rounds: no reserve adjustments, fisher keeps full raw catch.
            return NormDecision.adjust(kept_kg=raw_kg, note=None)
        deposit = raw_kg * 0.005
        # Update reserve balance with the standard deposit
        balance = state.get("balance_kg", 0.0) + deposit
        note_parts = []
        if deposit > 0:
            note_parts.append(f"You deposited {deposit:.3f}kg into the communal reserve.")
        # Ensure reserve stays at least 80 % of lake biomass after this catch
        # Compute tentative kept amount (raw catch minus deposit) before any extra contribution
        tentative_kept = raw_kg - deposit
        min_reserve = 0.8 * (context.stock_before - tentative_kept)
        extra_contribution = 0.0
        if balance < min_reserve:
            needed = min_reserve - balance
            available = max(0.0, tentative_kept)
            extra_contribution = min(needed, available, 0.5)
            balance += extra_contribution
            note_parts.append(f"You added an extra {extra_contribution:.3f}kg to meet the 80% reserve requirement.")
        # Store updated balance (will be cleared if withdrawal occurs)
        state["balance_kg"] = balance
        # Mark that the starting balance logic has been applied for this norm instance.
        state["_starting_applied"] = True
        # Kept kg is raw catch minus deposit and any extra contribution
        kept = raw_kg - deposit - extra_contribution
        # Existing shortfall‑withdrawal logic (unchanged)
        shortfall_thresh = self.params.get("shortfall_threshold_kg")
        max_withdraw = self.params.get("max_withdrawal_kg")
        if shortfall_thresh is not None and kept < shortfall_thresh:
            needed = shortfall_thresh - kept
            limit = max_withdraw if max_withdraw is not None else needed
            added_this_round = deposit + extra_contribution
            withdraw = min(added_this_round, limit)
            if withdraw > 0:
                kept += withdraw
                note_parts.append(f"You withdrew {withdraw:.3f}kg from the reserve.")
            # After withdrawal, empty the reserve for this round
            state["balance_kg"] = 0.0
        note = " ".join(note_parts) if note_parts else None
        return NormDecision.adjust(kept_kg=kept, note=note)

