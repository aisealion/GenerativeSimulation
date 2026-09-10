"""Reserve Verification Norm: Verifies 1kg reserve with lake-watcher.

Policy: The fisher's 1 kg reserve is weighed by the watcher before departure
and logged as "Reserve kept: 1 kg – verified by [watcher]"; any shortfall
forces the fisher to sit out the next trip.
"""

from engine.norms.base import Norm, NormDecision
from roles.roles import current_holder


class ReserveVerificationNorm(Norm):
    """Verifies each fisher's 1kg reserve with the lake-watcher.

    Works alongside the mandatory_reserve norm to add watcher verification.
    Shortfall triggers a violation that results in sitting out the next trip.
    """

    type_name = "reserve_verification"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Required reserve in kg (default: 1.0)
        self.reserve_kg = params.get("reserve_kg", 1.0)
        # Key of the lake_watcher norm to get watcher from
        self.watcher_norm_key = params.get("watcher_norm_key", "lake_watcher")
        # Key of the mandatory_reserve norm to check reserve status
        self.reserve_norm_key = params.get("reserve_norm_key", "mandatory_reserve")

    def describe(self, context, agent_id):
        """Tell the agent about reserve verification."""
        fluents = context.fluents
        watcher_id = current_holder(fluents, "lake_watcher", context.round_number)
        agents = context.agents

        if watcher_id:
            watcher_name = agents.get(watcher_id, {}).get("name", "the watcher")
            return f"Your {self.reserve_kg:.0f}kg reserve will be verified by {watcher_name} before departure."
        else:
            return f"Your {self.reserve_kg:.0f}kg reserve must be maintained."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Check reserve status - doesn't modify catch, just verifies.

        The actual reserve enforcement is handled by mandatory_reserve.
        This norm adds the verification layer and tracks shortfalls.
        """
        # Get reserve status from mandatory_reserve norm
        reserve_state = context.norm_state(self.reserve_norm_key)
        agent_reserve = reserve_state.get(agent_id, {}).get("reserve_kg", 0.0)

        # Get current watcher
        fluents = context.fluents
        watcher_id = current_holder(fluents, "lake_watcher", context.round_number)
        agents = context.agents
        watcher_name = agents.get(watcher_id, {}).get("name", "the watcher") if watcher_id else "consensus"

        state = context.norm_state(self.key)
        verifications = state.setdefault("verifications", [])

        # Check for shortfall
        if agent_reserve < self.reserve_kg:
            # Reserve shortfall - violation that triggers next-trip ban
            verifications.append({
                "round": context.round_number,
                "agent_id": agent_id,
                "reserve_kg": agent_reserve,
                "required_kg": self.reserve_kg,
                "verified_by": watcher_name,
                "passed": False,
            })

            # Track shortfall for next_trip_ban
            shortfalls = state.setdefault("shortfalls", [])
            shortfalls.append({
                "round": context.round_number,
                "agent_id": agent_id,
                "reason": "reserve_shortfall",
            })

            return NormDecision.violation(
                kept_kg=proposed_kg,
                sanction="reserve_shortfall",
                note=f"Reserve verification FAILED: you have only {agent_reserve:.1f}kg reserve (required: {self.reserve_kg:.0f}kg). You must sit out the next trip."
            )

        # Reserve verified
        verifications.append({
            "round": context.round_number,
            "agent_id": agent_id,
            "reserve_kg": agent_reserve,
            "required_kg": self.reserve_kg,
            "verified_by": watcher_name,
            "passed": True,
        })

        # Return note about successful verification (non-violation)
        return NormDecision.adjust(
            kept_kg=proposed_kg,
            note=f"Reserve kept: {self.reserve_kg:.0f}kg – verified by {watcher_name}."
        )

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Record verification result."""
        # Verification already recorded in evaluate
        pass
