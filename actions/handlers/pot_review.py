from engine.institution.rules import Rule

class PotReviewHandler:
    """Custom handler for pot_review action. Currently a placeholder that just emits an event.
    In a full implementation it would coordinate with the vote outcome.
    """
    def run(self, ctx):
        # Read pot balance
        pot_balance = ctx.objects.read("communal_pot", "balance_kg", viewer_agent_id=ctx.agent_id) if hasattr(ctx, 'agent_id') else ctx.objects.read("communal_pot", "balance_kg", viewer_agent_id=None)
        ctx.events.emit(
            "pot_review",
            {
                "elder_id": ctx.agent_id if hasattr(ctx, 'agent_id') else None,
                "balance_kg": pot_balance,
                "note": "Elder ready to distribute pot.",
            },
        )
        return {"pot_balance": pot_balance, "status": "ready"}
