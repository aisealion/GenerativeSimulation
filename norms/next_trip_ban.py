"""Next Trip Ban Norm: Implements one-round ban for violations.

Policy: Non-compliance results in the fisher sitting out the next trip.
"""

from engine.norms.base import Norm


class NextTripBanNorm(Norm):
    """Imposes a one-round ban on fishers who violated rules.

    Checks for violations from percent_stock_cap and reserve_verification,
    and bans the agent for the next round only.
    """

    type_name = "next_trip_ban"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Norm keys to check for violations
        self.stock_cap_key = params.get("stock_cap_key", "percent_stock_cap")
        self.reserve_verification_key = params.get("reserve_verification_key", "reserve_verification")

    def describe(self, context, agent_id):
        """Tell banned agents why they can't fish."""
        state = context.norm_state(self.key)
        ban_info = state.get(agent_id, {})

        if ban_info.get("banned_this_round", False):
            reason = ban_info.get("reason", "violation")
            return f"You are sitting out this trip due to a previous {reason}."

        return None

    def is_eligible(self, context, agent_id):
        """Check if agent is banned for this round.

        Called once per agent per round. Returns False if banned.
        """
        state = context.norm_state(self.key)
        ban_info = state.get(agent_id, {})

        if ban_info.get("banned_this_round", False):
            # Ban is being served this round - clear it after this check
            # (ban only lasts one round)
            return False

        return True

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Check for violations and impose ban for next round.

        This runs after all norms have evaluated. We check if this agent
        had a violation that should result in a next-trip ban.
        """
        state = context.norm_state(self.key)

        # Check if this agent had a qualifying violation
        qualifying_sanctions = ("over_stock_limit", "reserve_shortfall")

        if decision.violated and decision.sanction in qualifying_sanctions:
            # Impose ban for next round
            ban_info = state.setdefault(agent_id, {})
            ban_info["banned_next_round"] = True
            ban_info["reason"] = decision.sanction
            ban_info["violation_round"] = context.round_number

            # Record in ledger
            ledger = state.setdefault("ban_ledger", [])
            ledger.append({
                "round": context.round_number,
                "agent_id": agent_id,
                "violation": decision.sanction,
                "ban_starts": context.round_number + 1,
                "note": decision.note,
            })

    def on_round_end(self, context, round_results):
        """Activate bans for the next round and clear served bans."""
        state = context.norm_state(self.key)

        # For each agent, move "banned_next_round" to "banned_this_round"
        # and clear old bans
        for agent_id in list(state.keys()):
            if agent_id in ("ban_ledger",):
                continue

            ban_info = state[agent_id]

            # Clear ban that was served this round
            if ban_info.get("banned_this_round", False):
                ban_info["banned_this_round"] = False

            # Activate ban for next round
            if ban_info.get("banned_next_round", False):
                ban_info["banned_this_round"] = True
                ban_info["banned_next_round"] = False
