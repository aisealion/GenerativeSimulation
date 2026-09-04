"""Deficit penalty norm: 10% forfeiture for agents with outstanding deficits.

Implements:
- 10% penalty on next trip's haul for agents with uncleared deficits
- Penalty continues until deficit is cleared
- Forfeited amount goes to community pool
"""

from engine.norms.base import Norm, NormDecision


class DeficitPenaltyNorm(Norm):
    type_name = "deficit_penalty"

    def describe(self, context, agent_id):
        deficit = self._get_deficit(context, agent_id)
        if deficit > 0:
            return (
                f"You have an outstanding deficit of {deficit:.1f} kg owed to the community pool. "
                f"10% of this trip's catch will be forfeited until the deficit is cleared."
            )
        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply 10% penalty if agent has a deficit."""
        deficit = self._get_deficit(context, agent_id)

        if deficit <= 0:
            return NormDecision.allow(proposed_kg)

        params = self._get_params()
        penalty_rate = params["penalty_rate"]

        # Calculate penalty (10% of the proposed amount)
        penalty_amount = min(proposed_kg * penalty_rate, deficit)

        # Ensure we don't forfeit more than the agent has
        penalty_amount = min(penalty_amount, proposed_kg)

        if penalty_amount <= 0:
            return NormDecision.allow(proposed_kg)

        # Reduce the kept amount
        new_kept = proposed_kg - penalty_amount

        # Reduce the deficit
        self._reduce_deficit(context, agent_id, penalty_amount)

        # Add forfeited amount to community pool
        self._add_to_community_pool(context, penalty_amount)

        new_deficit = self._get_deficit(context, agent_id)

        if new_deficit <= 0:
            note = (
                f"Deficit penalty applied: {penalty_amount:.1f} kg forfeited to community pool. "
                f"Your deficit is now cleared."
            )
        else:
            note = (
                f"Deficit penalty applied: {penalty_amount:.1f} kg forfeited to community pool. "
                f"Remaining deficit: {new_deficit:.1f} kg."
            )

        return NormDecision.adjust(kept_kg=new_kept, note=note)

    def _get_params(self):
        """Get parameters with defaults."""
        return {
            "penalty_rate": self.params.get("penalty_rate", 0.10),
        }

    def _get_deficit(self, context, agent_id):
        """Get the current deficit for an agent from the daily_collective_limit norm state."""
        # Deficits are stored in the daily_collective_limit norm's state
        # We access it via the key that norm uses
        daily_limit_key = self._find_daily_limit_key(context)
        if not daily_limit_key:
            return 0.0

        norm_state = context.norm_state(daily_limit_key)
        deficits = norm_state.get("agent_deficits", {})
        return deficits.get(agent_id, 0.0)

    def _reduce_deficit(self, context, agent_id, amount):
        """Reduce an agent's deficit by the given amount."""
        daily_limit_key = self._find_daily_limit_key(context)
        if not daily_limit_key:
            return

        norm_state = context.norm_state(daily_limit_key)
        deficits = norm_state.setdefault("agent_deficits", {})
        current = deficits.get(agent_id, 0.0)
        new_amount = max(0.0, current - amount)

        if new_amount > 0:
            deficits[agent_id] = new_amount
        else:
            # Remove the deficit entry if cleared
            deficits.pop(agent_id, None)

    def _add_to_community_pool(self, context, amount):
        """Add forfeited amount to the community pool."""
        daily_limit_key = self._find_daily_limit_key(context)
        if not daily_limit_key:
            return

        norm_state = context.norm_state(daily_limit_key)
        current = norm_state.get("community_pool_kg", 0.0)
        norm_state["community_pool_kg"] = current + amount

    def _find_daily_limit_key(self, context):
        """Find the key for the daily_collective_limit norm in config."""
        norms_config = context.config.get("norms", [])
        for spec in norms_config:
            if spec.get("type") == "daily_collective_limit":
                return spec.get("id", "daily_collective_limit")
        return None
