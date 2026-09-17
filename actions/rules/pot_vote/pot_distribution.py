from engine.institution.rules import Rule

class PotDistributionRule(Rule):
    """Applies the result of pot_vote to withdraw amounts from the communal pot and emit distribution events."""
    type_name = "pot_distribution"

    def after_action(self, ctx, round_record):
        # Assuming this rule is attached to pot_vote action.
        # round_record contains each agent's response in ctx.rules outputs.
        # Aggregate by averaging immediate and reserve kg proposals.
        total_immediate = 0.0
        total_reserve = 0.0
        count = 0
        for agent_id, resp in round_record.get("agents", {}).items():
            if not resp.get("participated", True):
                continue
            immediate = resp.get("immediate_kg")
            reserve = resp.get("reserve_kg")
            if immediate is None or reserve is None:
                continue
            total_immediate += immediate
            total_reserve += reserve
            count += 1
        if count == 0:
            return None
        avg_immediate = total_immediate / count
        avg_reserve = total_reserve / count
        # Withdraw from communal pot accordingly.
        pot_balance = ctx.objects.read("communal_pot", "balance_kg", viewer_agent_id=None)
        withdraw_immediate = min(avg_immediate, pot_balance)
        ctx.objects.withdraw(
            "communal_pot",
            "balance_kg",
            withdraw_immediate,
            by_agent_id=None,
            narration=f"Allocated {withdraw_immediate:.2f}kg to immediate community needs.",
        )
        remaining = pot_balance - withdraw_immediate
        withdraw_reserve = min(avg_reserve, remaining)
        ctx.objects.withdraw(
            "communal_pot",
            "balance_kg",
            withdraw_reserve,
            by_agent_id=None,
            narration=f"Allocated {withdraw_reserve:.2f}kg to reserve.",
        )
        # Withdraw remaining balance to empty the pot.
        remaining_after = ctx.objects.read("communal_pot", "balance_kg", viewer_agent_id=None)
        if remaining_after > 0:
            ctx.objects.withdraw(
                "communal_pot",
                "balance_kg",
                remaining_after,
                by_agent_id=None,
                narration=f"Remaining {remaining_after:.2f}kg cleared from pot after distribution.",
            )
        # Emit events for visibility.
        ctx.events.emit("pot_distribution", {"immediate_kg": withdraw_immediate, "reserve_kg": withdraw_reserve, "cleared_kg": remaining_after})
        return None
