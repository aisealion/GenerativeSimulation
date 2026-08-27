# lake_suspend — suspends fishing when lake stock is low and reserve insufficient.

from engine.norms.base import Norm


class LakeSuspendNorm(Norm):
    type_name = "lake_suspend"

    def is_eligible(self, context, agent_id):
        """Suspend fishing if the communal reserve holds less than 15 % of the lake stock.
        The lake stock is the current biomass before fishing this round.
        """
        reserve_state = context.norm_state("reserve")
        reserve_balance = reserve_state.get("balance_kg", 0.0)
        stock = context.stock_before
        # Minimum reserve is 15 % of the lake's current stock.
        if reserve_balance < 0.15 * stock:
            return False
        return True

    def describe(self, context, agent_id):
        if context.stock_before < 10.0:
            reserve_state = context.norm_state("reserve")
            reserve_balance = reserve_state.get("balance_kg", 0.0)
            stock = context.stock_before
            min_reserve = 0.15 * stock
            if reserve_balance < min_reserve:
                return f"Fishing is suspended; reserve must retain at least {int(min_reserve)} kg (15% of lake stock) before fishing resumes."
        return None
