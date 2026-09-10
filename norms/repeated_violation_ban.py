"""Repeated Violation Ban Norm: Bans fishers with repeated violations.

Policy: Repeated violations (the second or subsequent) result in a one-week
ban imposed by the council; the clerk records the ban in the ledger, issues
a written notice, holds the dock and boat key, and the rotating watch
prevents the banned fisher from launching the boat during the ban period.
"""

from engine.norms.base import Norm


class RepeatedViolationBanNorm(Norm):
    """Imposes a one-week ban on fishers with 2nd or subsequent violations.

    A fisher with 2+ violations is banned for 7 rounds (one week).
    During the ban, they are ineligible to fish.
    """

    type_name = "repeated_violation_ban"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Number of violations before ban (default: 2)
        self.violation_threshold = params.get("violation_threshold", 2)
        # Ban duration in rounds (default: 7 = one week)
        self.ban_duration_rounds = params.get("ban_duration_rounds", 7)

    def describe(self, context, agent_id):
        """Tell banned agents why they can't fish."""
        state = context.norm_state(self.key)
        ban_info = state.get(agent_id, {})
        if ban_info.get("banned_until_round", 0) > context.round_number:
            remaining = ban_info["banned_until_round"] - context.round_number
            return f"You are banned from fishing for {remaining} more round(s) due to repeated violations."
        return None

    def is_eligible(self, context, agent_id):
        """Check if agent is currently banned.

        Also ticks down the ban countdown if the agent is banned.
        """
        state = context.norm_state(self.key)
        ban_info = state.get(agent_id, {})
        banned_until = ban_info.get("banned_until_round", 0)

        if banned_until > context.round_number:
            # Still banned
            return False

        return True

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Check for repeated violations and impose ban if needed.

        This should run after violation_handler has recorded violations.
        We need to check the violation_handler's state to count violations.
        """
        state = context.norm_state(self.key)

        # Get violation count from violation_handler norm
        vh_state = context.norm_state("violation_handler")
        agent_violations = vh_state.get("violations", {}).get(agent_id, {})
        violation_count = agent_violations.get("count", 0)

        # Check if this agent should be banned
        if violation_count >= self.violation_threshold:
            ban_info = state.setdefault(agent_id, {})
            currently_banned_until = ban_info.get("banned_until_round", 0)

            # Only impose ban if not already banned
            if currently_banned_until <= context.round_number:
                # Impose one-week ban starting next round
                ban_start = context.round_number + 1
                ban_end = ban_start + self.ban_duration_rounds - 1
                ban_info["banned_until_round"] = ban_end
                ban_info["ban_start_round"] = ban_start
                ban_info["violation_count_at_ban"] = violation_count

                # Record in ledger
                ledger = state.setdefault("ledger", [])
                ledger.append({
                    "round": context.round_number,
                    "agent_id": agent_id,
                    "action": "ban_imposed",
                    "banned_from_round": ban_start,
                    "banned_until_round": ban_end,
                    "reason": f"Repeated violations (count: {violation_count})",
                })
