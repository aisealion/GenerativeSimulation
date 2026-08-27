# lake_suspend — suspends fishing when lake stock is low and reserve insufficient.

from engine.norms.base import Norm


class LakeSuspendNorm(Norm):
    type_name = "lake_suspend"

    def is_eligible(self, context, agent_id):
        """Suspend fishing if the communal reserve holds less than 50 % of total biomass (stock + reserve)."""
        reserve_state = context.norm_state("reserve")
        reserve_balance = reserve_state.get("balance_kg", 0.0)
        total_biomass = context.stock_before + reserve_balance
        # Minimum reserve is half of total biomass.
        if reserve_balance < 0.5 * total_biomass:
            return False
        return True

    def describe(self, context, agent_id):
        if context.stock_before < 10.0:
            reserve_state = context.norm_state("reserve")
            reserve_balance = reserve_state.get("balance_kg", 0.0)
            total_biomass = context.stock_before + reserve_balance
            min_reserve = 0.5 * total_biomass
            if reserve_balance < min_reserve:
                return f"Fishing is suspended; reserve must retain at least {int(min_reserve)} kg (50% of total biomass) before fishing resumes."
        return None
