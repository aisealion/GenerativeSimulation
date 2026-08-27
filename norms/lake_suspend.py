# lake_suspend — suspends fishing when lake stock is low and reserve insufficient.

from engine.norms.base import Norm


class LakeSuspendNorm(Norm):
    type_name = "lake_suspend"

    def is_eligible(self, context, agent_id):
        """If lake stock is below 10 kg and reserve balance is under 15 kg,
        prohibit fishing for all agents.
        """
        if context.stock_before < 10.0:
            # Reserve norm stores its balance under its key, default "reserve"
            reserve_state = context.norm_state("reserve")
            balance = reserve_state.get("balance_kg", 0.0)
            if balance < 15.0:
                return False
        return True

    def describe(self, context, agent_id):
        if context.stock_before < 10.0:
            reserve_state = context.norm_state("reserve")
            if reserve_state.get("balance_kg", 0.0) < 15.0:
                return "Fishing is currently suspended due to low lake stock; the community reserve must reach at least 15 kg before fishing resumes."
        return None
