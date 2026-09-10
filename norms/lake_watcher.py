"""Lake Watcher Norm: Manages rotating lake-watcher role, stock estimation,
and communal ledger archiving.

Policy: Before each trip the group meets to estimate the lake's current stock
via a designated lake-watcher who samples and scales or, if no watcher, by
consensus averaging. At trip end, the lake-watcher verifies each fisher's
ledger (total catch, reserve kept, net taken) and records violations.
"""

import random

from engine.norms.base import Norm, NormDecision
from roles.roles import assign_role, current_holder


class LakeWatcherNorm(Norm):
    """Manages the rotating lake-watcher role, stock estimation, and communal ledger.

    Each round, a designated lake-watcher is assigned who estimates the
    current stock. The watcher verifies catches, maintains the communal ledger
    with total catch, reserve kept, net taken, and records any violations and
    fines in the community fund.
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
            return f"You are the lake-watcher for this round. Estimate the stock, verify catches, and maintain the communal ledger."
        else:
            return f"{watcher_name} is the lake-watcher this round and will verify your catch and record it in the communal ledger."

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

        # Initialize community fund if not exists
        if "community_fund_kg" not in state:
            state["community_fund_kg"] = 0.0

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Lake watcher doesn't modify catches directly, just logs."""
        return NormDecision.allow(proposed_kg)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Record the catch in the communal ledger with verification details.

        Ledger format per round 3 requirements:
        - total_catch_kg: catch before any trimming
        - reserve_kept_kg: personal reserve maintained
        - net_taken_kg: actual harvested amount
        - verified_by: watcher name
        - violation: boolean
        - violation_type: "over_stock_limit", "reserve_shortfall", or null
        - fine_kg: fine amount if violation
        - excess_returned_kg: excess returned to lake
        """
        fluents = context.fluents
        agents = context.agents
        state = context.norm_state(self.key)

        watcher_id = current_holder(fluents, self.role_name, context.round_number)
        watcher_name = agents.get(watcher_id, {}).get("name", "unknown") if watcher_id else "consensus"

        # Get the reserve from mandatory_reserve norm
        reserve_state = context.norm_state("mandatory_reserve")
        agent_reserve = reserve_state.get(agent_id, {}).get("reserve_kg", 0.0)

        # Calculate total catch (before any trimming)
        # If there was a violation, raw_kg would be higher than harvested_kg
        # We need to reconstruct what they tried to take
        total_catch_kg = harvested_kg
        excess_kg = 0.0

        if decision.violated and decision.sanction == "over_stock_limit":
            # Try to extract excess from decision note
            # Note format: "Your catch of Xkg exceeds 12% of the estimated stock (Ykg). Excess of Zkg must be returned..."
            note = decision.note or ""
            if "Excess of " in note:
                try:
                    excess_str = note.split("Excess of ")[1].split("kg")[0]
                    excess_kg = float(excess_str)
                    total_catch_kg = harvested_kg + excess_kg
                except (IndexError, ValueError):
                    excess_kg = 0.0

        # Determine violation type
        violation_type = None
        if decision.violated:
            if decision.sanction == "over_stock_limit":
                violation_type = "over_stock_limit"
            elif decision.sanction == "reserve_shortfall":
                violation_type = "reserve_shortfall"

        # Get fine amount from violation_fine norm state (will be updated by violation_fine norm)
        fine_kg = 0.0
        fine_state = context.norm_state("violation_fine")
        if fine_state:
            for fine_record in fine_state.get("fines", []):
                if fine_record["round"] == context.round_number and fine_record["agent_id"] == agent_id:
                    fine_kg = fine_record["fine_kg"]
                    break

        # Record in the communal ledger
        ledger_entry = {
            "round": context.round_number,
            "agent_id": agent_id,
            "agent_name": agents.get(agent_id, {}).get("name", agent_id),
            "total_catch_kg": total_catch_kg,
            "reserve_kept_kg": agent_reserve,
            "net_taken_kg": harvested_kg,
            "verified_by": watcher_name,
            "watcher_id": watcher_id,
            "violation": decision.violated,
            "violation_type": violation_type,
            "fine_kg": fine_kg,
            "excess_returned_kg": excess_kg,
        }

        communal_ledger = state.setdefault("communal_ledger", [])
        communal_ledger.append(ledger_entry)

        # Also maintain backward-compatible catch_log
        log_entry = {
            "round": context.round_number,
            "agent_id": agent_id,
            "agent_name": agents.get(agent_id, {}).get("name", agent_id),
            "catch_kg": harvested_kg,
            "verified_by": watcher_name,
            "watcher_id": watcher_id,
            "excess_returned_kg": excess_kg,
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
            if r.get("participated", False) and r.get("violated", False)
        ]

        # Count fines from communal ledger
        communal_ledger = state.get("communal_ledger", [])
        round_fines = [
            entry for entry in communal_ledger
            if entry["round"] == context.round_number and entry["fine_kg"] > 0
        ]
        total_fines_this_round = sum(f["fine_kg"] for f in round_fines)

        # Record round summary
        round_summary = state.setdefault("round_summaries", [])
        round_summary.append({
            "round": context.round_number,
            "total_catch_kg": total_catch,
            "agent_count": len([r for r in round_results.values() if r.get("participated", False)]),
            "violation_count": len(violations),
            "fines_collected_kg": total_fines_this_round,
            "community_fund_total_kg": state.get("community_fund_kg", 0.0),
            "stock_estimate_kg": state.get("current_estimate_kg", context.stock_before),
        })

    def get_stock_estimate(self, context):
        """Get the current stock estimate for use by other norms."""
        state = context.norm_state(self.key)
        return state.get("current_estimate_kg", context.stock_before)

    def get_current_watcher(self, context):
        """Get the current watcher ID."""
        return current_holder(context.fluents, self.role_name, context.round_number)
