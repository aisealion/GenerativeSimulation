from __future__ import annotations
from typing import Any
from engine.institution.rules import Rule


class TermLifecycleRule(Rule):
    """
    Village Elder serves for one season (7 rounds).
    """

    def on_agent_settled(self, ctx, **kwargs):
        # This rule activates when an agent has been assigned a role for the season
        agent_id = ctx.agent_id
        if ctx.agent_id == "village_elder":
            # Track when the role will expire
            # This may need additional logic to manage rotations
            pass