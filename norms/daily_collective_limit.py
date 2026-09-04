"""Daily collective harvest limit with proportional surplus redistribution.

Implements:
- Individual per-trip cap (default 15 kg)
- Daily collective limit (default 200 kg)
- Proportional surplus redistribution
- Community pool tracking
- Deficit tracking for edge cases
"""

from engine.norms.base import Norm, NormDecision


class DailyCollectiveLimitNorm(Norm):
    type_name = "daily_collective_limit"

    def describe(self, context, agent_id):
        params = self._get_params()
        daily_limit = params["daily_limit_kg"]
        individual_cap = params["individual_cap_kg"]

        # Get current community pool total
        norm_state = context.norm_state(self.key)
        pool_total = norm_state.get("community_pool_kg", 0.0)

        # Get agent's deficit if any
        agent_deficit = self._get_agent_deficit(context, agent_id)

        parts = [
            f"You may keep at most {individual_cap} kg per trip.",
            f"The lake's total daily harvest cannot exceed {daily_limit} kg.",
            f"If the daily total exceeds {daily_limit} kg, surplus is returned proportionally to the community pool (currently {pool_total:.1f} kg total).",
        ]

        if agent_deficit > 0:
            parts.append(f"You currently owe {agent_deficit:.1f} kg to the community pool from previous rounds.")

        return " ".join(parts)

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply individual cap and record in round scratch for collective calculation."""
        params = self._get_params()
        individual_cap = params["individual_cap_kg"]

        # Apply individual cap first
        after_cap = min(proposed_kg, individual_cap)

        # Store this agent's contribution in round scratch for on_round_end
        scratch = context.round_scratch(self.key)
        agent_records = scratch.setdefault("agent_records", {})
        agent_records[agent_id] = {
            "after_cap": after_cap,
            "raw_kg": raw_kg,
            "proposed_kg": proposed_kg,
        }

        # For now, allow the capped amount; collective adjustment happens in on_round_end
        if after_cap < proposed_kg:
            return NormDecision.adjust(
                kept_kg=after_cap,
                note=f"Individual cap applied: {proposed_kg:.1f} kg → {after_cap:.1f} kg"
            )

        return NormDecision.allow(after_cap)

    def on_round_end(self, context, round_results):
        """Calculate surplus, redistribute proportionally, update pool and deficits."""
        params = self._get_params()
        daily_limit = params["daily_limit_kg"]

        scratch = context.round_scratch(self.key)
        agent_records = scratch.get("agent_records", {})

        if not agent_records:
            return

        # Calculate total after individual caps
        total_after_caps = sum(r["after_cap"] for r in agent_records.values())

        # Check if we're over the collective limit
        if total_after_caps <= daily_limit:
            # No surplus, everyone keeps what they have
            return

        # Calculate surplus
        surplus = total_after_caps - daily_limit

        # Calculate proportional redistribution
        norm_state = context.norm_state(self.key)
        pool_total = norm_state.get("community_pool_kg", 0.0)

        for agent_id, record in agent_records.items():
            after_cap = record["after_cap"]

            # Proportional share of surplus
            if total_after_caps > 0:
                proportional_share = (after_cap / total_after_caps) * surplus
            else:
                proportional_share = 0.0

            # Calculate final kept amount and any deficit
            if proportional_share >= after_cap:
                # Agent owes more than they have - they keep 0 and accrue deficit
                final_kept = 0.0
                deficit = proportional_share - after_cap
            else:
                final_kept = after_cap - proportional_share
                deficit = 0.0

            # Store the adjustment for this agent
            record["final_kept"] = final_kept
            record["surplus_returned"] = after_cap - final_kept
            record["deficit_accrued"] = deficit

            # Update agent's deficit in norm_state
            self._add_agent_deficit(context, agent_id, deficit)

            # Add to community pool
            pool_total += record["surplus_returned"]

        # Update community pool total
        norm_state["community_pool_kg"] = pool_total

        # Override round_results with final kept amounts
        for agent_id, record in agent_records.items():
            if "final_kept" in record and agent_id in round_results:
                old_kept = round_results[agent_id]["harvested_kg"]
                new_kept = record["final_kept"]
                if old_kept != new_kept:
                    round_results[agent_id]["harvested_kg"] = new_kept
                    round_results[agent_id]["note"] = (
                        f"Collective limit adjustment: {old_kept:.1f} kg → {new_kept:.1f} kg "
                        f"(returned {record['surplus_returned']:.1f} kg to community pool)"
                    )

    def _get_params(self):
        """Get parameters with defaults."""
        return {
            "daily_limit_kg": self.params.get("daily_limit_kg", 200),
            "individual_cap_kg": self.params.get("individual_cap_kg", 15),
        }

    def _get_agent_deficit(self, context, agent_id):
        """Get the current deficit for an agent."""
        norm_state = context.norm_state(self.key)
        deficits = norm_state.get("agent_deficits", {})
        return deficits.get(agent_id, 0.0)

    def _add_agent_deficit(self, context, agent_id, amount):
        """Add to an agent's deficit."""
        if amount <= 0:
            return
        norm_state = context.norm_state(self.key)
        deficits = norm_state.setdefault("agent_deficits", {})
        deficits[agent_id] = deficits.get(agent_id, 0.0) + amount
