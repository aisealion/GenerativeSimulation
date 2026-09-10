"""Lake Watcher Norm: Manages rotating lake-watcher role, stock estimation,
and communal ledger archiving.

Policy: Kai (the designated lake-watcher) estimates stock before each trip,
verifies each fisher's catch and reserve, records entries in the communal
ledger including deposits to the communal reserve, and logs any violations.
"""

import random

from engine.norms.base import Norm, NormDecision
from roles.roles import assign_role, current_holder


class LakeWatcherNorm(Norm):
    """Manages the rotating lake-watcher role, stock estimation, and communal ledger.

    Each round, a designated lake-watcher (Kai) is assigned who estimates the
    current stock. The watcher verifies catches, maintains the communal ledger
    with catch amounts, deposit status, personal reserve status, and records
    any violations.
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
            return f"You are Kai, the lake-watcher for this round. You estimate the stock, verify catches, maintain the communal ledger, and manage the communal reserve."
        else:
            return f"{watcher_name} (Kai) is the lake-watcher this round and will verify your catch, record it in the communal ledger, and manage any deposits to the communal reserve."

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
                    narration=f"{watcher_name} has been designated as Kai, the lake-watcher for this round.",
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
        """Record the catch in the communal ledger with verification details.

        Ledger format for round 4:
        - round: round number
        - agent_id: fisher identifier
        - agent_name: fisher name
        - catch_kg: actual harvested amount
        - deposit_kg: amount deposited to communal reserve
        - deposit_status: boolean indicating if deposit was made
        - personal_reserve_kept: boolean indicating if 1kg reserve maintained
        - verified_by: watcher name (Kai)
        - watcher_id: watcher agent id
        - violation: boolean
        - violation_type: "over_cap_without_deposit" or null
        """
        fluents = context.fluents
        agents = context.agents
        state = context.norm_state(self.key)

        watcher_id = current_holder(fluents, self.role_name, context.round_number)
        watcher_name = agents.get(watcher_id, {}).get("name", "Kai") if watcher_id else "Kai"

        # Get the reserve from mandatory_reserve norm
        reserve_state = context.norm_state("mandatory_reserve")
        agent_reserve = reserve_state.get(agent_id, {}).get("reserve_kg", 0.0)
        personal_reserve_kept = agent_reserve >= 1.0

        # Determine violation type for round 4
        violation_type = None
        if decision.violated:
            if decision.sanction == "over_cap":
                violation_type = "over_cap_without_deposit"

        # Get deposit info from communal_reserve norm state
        deposit_kg = 0.0
        deposit_status = False
        communal_reserve_state = context.norm_state("communal_reserve")
        if communal_reserve_state:
            # Check if there's a deposit record for this agent this round
            for deposit_record in communal_reserve_state.get("deposits", []):
                if deposit_record["round"] == context.round_number and deposit_record["agent_id"] == agent_id:
                    deposit_kg = deposit_record["deposit_kg"]
                    deposit_status = deposit_kg > 0
                    break

        # Record in the communal ledger
        ledger_entry = {
            "round": context.round_number,
            "agent_id": agent_id,
            "agent_name": agents.get(agent_id, {}).get("name", agent_id),
            "catch_kg": harvested_kg,
            "deposit_kg": deposit_kg,
            "deposit_status": deposit_status,
            "personal_reserve_kept": personal_reserve_kept,
            "verified_by": watcher_name,
            "watcher_id": watcher_id,
            "violation": decision.violated,
            "violation_type": violation_type,
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
            "deposit_kg": deposit_kg,
            "violation": decision.violated,
            "sanction": decision.sanction,
        }
        catch_log = state.setdefault("catch_log", [])
        catch_log.append(log_entry)

        # Track deposit history separately
        if deposit_status:
            deposit_history = state.setdefault("deposit_history", [])
            deposit_history.append({
                "round": context.round_number,
                "agent_id": agent_id,
                "agent_name": agents.get(agent_id, {}).get("name", agent_id),
                "deposit_kg": deposit_kg,
                "recorded_by": watcher_name,
            })

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

        # Count deposits from communal ledger
        communal_ledger = state.get("communal_ledger", [])
        round_deposits = [
            entry for entry in communal_ledger
            if entry["round"] == context.round_number and entry["deposit_kg"] > 0
        ]
        total_deposits_this_round = sum(d["deposit_kg"] for d in round_deposits)

        # Get reserve balance from communal_reserve
        communal_reserve_state = context.norm_state("communal_reserve")
        reserve_balance = 0.0
        if communal_reserve_state:
            reserve_balance = communal_reserve_state.get("reserve_balance_kg", 0.0)

        # Record round summary
        round_summary = state.setdefault("round_summaries", [])
        round_summary.append({
            "round": context.round_number,
            "total_catch_kg": total_catch,
            "agent_count": len([r for r in round_results.values() if r.get("participated", False)]),
            "violation_count": len(violations),
            "total_deposits_kg": total_deposits_this_round,
            "reserve_balance_kg": reserve_balance,
            "stock_estimate_kg": state.get("current_estimate_kg", context.stock_before),
        })

    def get_stock_estimate(self, context):
        """Get the current stock estimate for use by other norms."""
        state = context.norm_state(self.key)
        return state.get("current_estimate_kg", context.stock_before)

    def get_current_watcher(self, context):
        """Get the current watcher ID."""
        return current_holder(context.fluents, self.role_name, context.round_number)
