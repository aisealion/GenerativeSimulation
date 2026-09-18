from engine.institution.rules import Rule
from roles.roles import set_fact

class ReserveMonitorRule(Rule):
    """Rule to monitor communal reserve balance and flag when below threshold."""
    type_name = "reserve_monitor_rule"

    def after_action(self, ctx, state):
        # Read current reserve balance
        try:
            balance = ctx.objects.read("communal_reserve", "balance_kg")
        except Exception:
            # If read not available, skip
            return None
        if balance < 70:
            # Set a public fact indicating reserve is low
            set_fact(ctx.state.get('fluents', []), "reserve_low", [], "community", ctx.round_number,
                    narration=f"Reserve balance {balance:.1f}kg below threshold; council may adjust policies.",
                    visibility="public")
        return None
