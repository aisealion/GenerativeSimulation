"""Weekly random audit with fishing rights suspension.

Implements:
- Random audit every N rounds
- Sample selection from agent population
- Violation detection via ledger review
- One-round fishing ban for violators
"""

import random

from engine.norms.base import Norm, NormDecision


class WeeklyAuditNorm(Norm):
    type_name = "weekly_audit"

    def describe(self, context, agent_id):
        norm_state = context.norm_state(self.key)
        parts = []

        # Check for pending ban
        pending_bans = norm_state.get("pending_bans", {})
        if agent_id in pending_bans and pending_bans[agent_id] > 0:
            parts.append(
                f"YOU ARE BANNED: You lost fishing rights for this round due to an audit violation. "
                f"You will be eligible to fish again next round."
            )

        # Report recent audit results
        audit_history = norm_state.get("audit_history", [])
        if audit_history:
            last_audit = audit_history[-1]
            audit_round = last_audit["round"]
            sanctioned = last_audit.get("sanctioned_agents", [])

            if context.round_number == audit_round + 1:
                # This is the round right after an audit
                if sanctioned:
                    parts.append(
                        f"AUDIT RESULTS (Round {audit_round}): Violations detected. "
                        f"Sanctioned agents (banned this round): {', '.join(sanctioned)}"
                    )
                else:
                    parts.append(
                        f"AUDIT RESULTS (Round {audit_round}): No violations detected. All agents compliant."
                    )

        # Announce upcoming audit
        params = self._get_params()
        frequency = params["audit_frequency_rounds"]
        rounds_until_audit = frequency - (context.round_number % frequency)

        if rounds_until_audit == 0:
            parts.append("AUDIT TODAY: A random audit will occur at the end of this round.")
        elif rounds_until_audit == 1:
            parts.append("AUDIT TOMORROW: A random audit will occur at the end of the next round.")
        elif rounds_until_audit <= 3:
            parts.append(f"Upcoming audit in {rounds_until_audit} rounds.")

        if parts:
            return " ".join(parts)
        return None

    def is_eligible(self, context, agent_id):
        """Check if agent is banned from fishing."""
        norm_state = context.norm_state(self.key)
        pending_bans = norm_state.get("pending_bans", {})

        if agent_id in pending_bans and pending_bans[agent_id] > 0:
            # Decrement ban counter
            pending_bans[agent_id] -= 1
            if pending_bans[agent_id] <= 0:
                del pending_bans[agent_id]
            return False

        return True

    def on_round_end(self, context, round_results):
        """Conduct audit if this is an audit round."""
        params = self._get_params()
        frequency = params["audit_frequency_rounds"]

        # Check if this is an audit round
        if context.round_number % frequency != 0:
            return

        # Find the dynamic_individual_cap norm to access its ledger
        ledger = self._get_ledger_from_cap_norm(context)
        if not ledger:
            return

        # Get agents to audit
        agent_ids = list(round_results.keys())
        sample_size = max(1, int(len(agent_ids) * params["audit_sample_rate"]))
        audited_agents = random.sample(agent_ids, min(sample_size, len(agent_ids)))

        # Check for violations
        sanctioned = []
        violations = []

        for agent_id in audited_agents:
            # Find this agent's entries in the ledger for the current week
            week_start = context.round_number - frequency + 1
            week_end = context.round_number

            agent_violations = []
            for entry in ledger:
                if entry["agent_id"] != agent_id:
                    continue
                if not (week_start <= entry["round"] <= week_end):
                    continue

                # Violation: raw catch > cap AND they tried to keep excess
                # (which means they didn't properly return)
                # Since the norm enforces returns automatically, a "violation"
                # in this context means the system detected they attempted to keep excess
                # We track this by checking if they returned the full excess amount
                raw_catch = entry["raw_catch"]
                cap_applied = entry["cap_applied"]
                returned = entry["returned"]

                if raw_catch > cap_applied:
                    expected_return = raw_catch - cap_applied
                    if returned < expected_return - 0.001:  # Small tolerance for floating point
                        agent_violations.append({
                            "round": entry["round"],
                            "raw_catch": raw_catch,
                            "cap": cap_applied,
                            "expected_return": expected_return,
                            "actual_returned": returned,
                        })

            if agent_violations:
                sanctioned.append(agent_id)
                violations.append({
                    "agent_id": agent_id,
                    "violations": agent_violations,
                })

        # Apply sanctions (one-round ban)
        norm_state = context.norm_state(self.key)
        pending_bans = norm_state.setdefault("pending_bans", {})

        for agent_id in sanctioned:
            pending_bans[agent_id] = params["sanction_duration_rounds"]

        # Record audit results
        audit_history = norm_state.setdefault("audit_history", [])
        audit_record = {
            "round": context.round_number,
            "audited_agents": audited_agents,
            "sanctioned_agents": sanctioned,
            "violations": violations,
            "total_agents": len(agent_ids),
        }
        audit_history.append(audit_record)

        # Trim history (keep last 10)
        if len(audit_history) > 10:
            norm_state["audit_history"] = audit_history[-10:]

    def _get_params(self):
        """Get parameters with defaults."""
        return {
            "audit_frequency_rounds": self.params.get("audit_frequency_rounds", 7),
            "audit_sample_rate": self.params.get("audit_sample_rate", 0.30),
            "sanction_duration_rounds": self.params.get("sanction_duration_rounds", 1),
        }

    def _get_ledger_from_cap_norm(self, context):
        """Find the dynamic_individual_cap norm and get its ledger."""
        # Look for the cap norm in config
        cap_norm_key = self._find_cap_norm_key(context)
        if not cap_norm_key:
            return []

        norm_state = context.norm_state(cap_norm_key)
        return norm_state.get("ledger", [])

    def _find_cap_norm_key(self, context):
        """Find the key for the dynamic_individual_cap norm in config."""
        norms_config = context.config.get("norms", [])
        for spec in norms_config:
            if spec.get("type") == "dynamic_individual_cap":
                return spec.get("id", "dynamic_individual_cap")
        return None
