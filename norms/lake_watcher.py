"""Lake Watcher Norm: Manages rotating lake-watcher role and stock estimation.

Policy: Before each trip the group meets to estimate the lake's current stock
via a designated lake-watcher who samples and scales or, if no watcher, by
consensus averaging.
"""

import random

from engine.norms.base import Norm, NormDecision
from roles.roles import assign_role, current_holder


class LakeWatcherNorm(Norm):
    """Manages the rotating lake-watcher role and stock estimation.

    Each round, a designated lake-watcher is assigned who estimates the
    current stock. The watcher also verifies catches and maintains the
    shared catch log.
    """

    type_name = "lake_watcher"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Role name for the lake watcher (default: "lake_watcher")
        self.role_name = params.get("role_name", "lake_watcher")

    def describe(self, context, agent_id):
        """Tell the agent who the current watcher is."""
        fluents = context.fluents
        watcher_id = current_holder(fluents, self.role_name, context.round_number)

        if watcher_id is None:
            return "No lake-watcher is currently assigned."

        agents = context.agents
        watcher_name = agents.get(watcher_id, {}).get("name", watcher_id)

        if agent_id == watcher_id:
            return f"You are the lake-watcher for this round. Estimate the stock and verify catches."
        else:
            return f"{watcher_name} is the lake-watcher this round and will verify your catch."

    def on_round_start(self, context):
        """Assign a lake-watcher for this round if none exists.

        If no watcher is assigned, rotate to the next alive fisher.
        The watcher "estimates" stock by using the actual physics stock value
        (representing their professional sampling/scaling).
        """
        fluents = context.fluents
        agents = context.agents
        runtime = context.runtime

        # Check if we already have a watcher for this round
        current_watcher = current_holder(fluents, self.role_name, context.round_number)

        if current_watcher is None:
            # Need to assign a new watcher - rotate among alive fishers
            alive_agents = [
                agent_id for agent_id in agents
                if agent_id not in runtime.get("dead_agents", [])
            ]

            if alive_agents:
                # Rotate: pick the next agent in sequence
                state = context.norm_state(self.key)
                last_watcher_idx = state.get("last_watcher_idx", -1)

                # Find the next alive agent
                next_idx = (last_watcher_idx + 1) % len(alive_agents)
                new_watcher = alive_agents[next_idx]

                # Assign the role (exclusive - only one watcher at a time)
                watcher_name = agents.get(new_watcher, {}).get("name", new_watcher)
                assign_role(
                    self.role_name, new_watcher, fluents, context.round_number,
                    exclusive=True,
                    narration=f"{watcher_name} has been designated as the lake-watcher for this round.",
                    visibility="public",
                )

                state["last_watcher_idx"] = next_idx
                state["current_watcher"] = new_watcher

        # Record the stock estimate (using actual stock as the estimate)
        state = context.norm_state(self.key)
        watcher_id = current_holder(fluents, self.role_name, context.round_number)

        if watcher_id:
            agents = context.agents
            watcher_name = agents.get(watcher_id, {}).get("name", watcher_id)
            stock_estimate = context.stock_before

            # Record the estimate
            estimates = state.setdefault("stock_estimates", [])
            estimates.append({
                "round": context.round_number,
                "watcher_id": watcher_id,
                "watcher_name": watcher_name,
                "stock_estimate_kg": stock_estimate,
            })
            state["current_estimate_kg"] = stock_estimate

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Lake watcher doesn't modify catches directly, just logs."""
        return NormDecision.allow(proposed_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Record the catch in the shared log with verification."""
        fluents = context.fluents
        agents = context.agents
        state = context.norm_state(self.key)

        watcher_id = current_holder(fluents, self.role_name, context.round_number)
        watcher_name = agents.get(watcher_id, {}).get("name", "unknown") if watcher_id else "consensus"

        # Calculate excess if there was a violation
        excess_kg = 0.0
        if decision.violated and decision.sanction == "over_stock_limit":
            # The excess is the difference between what they tried to keep and what was allowed
            # This is recorded in the decision note or we can infer from raw vs kept
            excess_kg = max(0.0, decision.note.split("exceeds")[0].split()[-2] if "exceeds" in (decision.note or "") else 0)
            # Actually, let's just use the raw catch minus what they kept if it was a violation
            if hasattr(context, '_last_raw_kg'):
                excess_kg = max(0.0, context._last_raw_kg - decision.kept_kg)

        # Record in the shared catch log
        log_entry = {
            "round": context.round_number,
            "agent_id": agent_id,
            "agent_name": agents.get(agent_id, {}).get("name", agent_id),
            "catch_kg": harvested_kg,
            "verified_by": watcher_name,
            "watcher_id": watcher_id,
            "excess_returned_kg": excess_kg if decision.violated else 0.0,
            "violation": decision.violated,
            "sanction": decision.sanction,
        }

        catch_log = state.setdefault("catch_log", [])
        catch_log.append(log_entry)

    def on_round_end(self, context, round_results):
        """Record round summary and prepare for next round's rotation."""
        state = context.norm_state(self.key)

        # Calculate total catches this round
        total_catch = sum(
            r["harvested_kg"] for r in round_results.values()
            if r.get("participated", False)
        )

        # Count violations
        violations = [
            r for r in round_results.values()
            if r.get("participated", False) and "violation" in str(r.get("note", "")).lower()
        ]

        # Record round summary
        round_summary = state.setdefault("round_summaries", [])
        round_summary.append({
            "round": context.round_number,
            "total_catch_kg": total_catch,
            "agent_count": len([r for r in round_results.values() if r.get("participated", False)]),
            "violation_count": len(violations),
            "stock_estimate_kg": state.get("current_estimate_kg", context.stock_before),
        })

    def get_stock_estimate(self, context):
        """Get the current stock estimate for use by other norms."""
        state = context.norm_state(self.key)
        return state.get("current_estimate_kg", context.stock_before)

    def get_current_watcher(self, context):
        """Get the current watcher ID."""
        return current_holder(context.fluents, self.role_name, context.round_number)
