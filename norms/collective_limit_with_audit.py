"""Collective harvest limit with monthly audits and forfeiture penalties.

Implements Round 6 norms:
- Fixed 18 kg per-trip individual cap
- 220 kg daily collective harvest limit with hard cutoff
- All excess (individual and collective) goes to community pool
- Monthly community council audits (every 30 rounds)
- 5 kg forfeiture penalty for non-compliance
- Shared ledger for transparency
"""

from engine.norms.base import Norm, NormDecision


class CollectiveLimitWithAuditNorm(Norm):
    type_name = "collective_limit_with_audit"

    def describe(self, context, agent_id):
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        parts = []

        # Describe the caps
        parts.append(
            f"You may keep at most {params['individual_cap_kg']} kg per trip. "
            f"The lake's total daily harvest cannot exceed {params['daily_limit_kg']} kg."
        )

        # Show community pool total
        community_pool = norm_state.get("community_pool_kg", 0)
        parts.append(f"Community pool total: {community_pool:.1f} kg.")

        # Check for pending penalties
        pending_penalties = self._get_pending_penalties(context, agent_id)
        if pending_penalties > 0:
            parts.append(
                f"PENDING PENALTY: You have {pending_penalties} forfeiture penalty(s) pending. "
                f"{params['forfeiture_amount_kg']} kg will be deducted from your next trip(s)."
            )

        # Show daily limit status
        scratch = context.round_scratch(self.key)
        daily_total = scratch.get("daily_total", 0)
        limit_reached = scratch.get("limit_reached", False)
        if limit_reached:
            parts.append(
                f"WARNING: The daily collective limit of {params['daily_limit_kg']} kg "
                f"has been reached. Subsequent catches this round will be returned to the pool."
            )
        else:
            remaining = params["daily_limit_kg"] - daily_total
            parts.append(f"Daily collective limit remaining: {remaining:.1f} kg.")

        # Monthly audit announcement
        last_audit = norm_state.get("last_audit_round", 0)
        if last_audit > 0 and context.round_number - last_audit < 2:
            parts.append(
                f"Monthly community council audit occurred in round {last_audit}. "
                "The shared ledger was reviewed for violations."
            )

        # Add recent ledger entries
        ledger = self._get_ledger(context)
        if ledger:
            agent_entries = [e for e in ledger if e["agent_id"] == agent_id]
            recent = [e for e in agent_entries if e["round"] >= context.round_number - 2]
            if recent:
                parts.append("Your recent ledger entries:")
                for entry in recent[-3:]:
                    violation_str = " (VIOLATION)" if entry.get("violation", False) else ""
                    parts.append(
                        f"  Round {entry['round']}: caught {entry['raw_catch']:.1f}kg, "
                        f"forfeiture {entry.get('forfeiture_applied', 0):.1f}kg, "
                        f"kept {entry['final_kept']:.1f}kg, "
                        f"pool deposit {entry.get('pool_deposit', 0):.1f}kg{violation_str}"
                    )

        return " ".join(parts)

    def on_round_start(self, context):
        """Reset daily totals and check for monthly audit."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)
        scratch = context.round_scratch(self.key)

        # Reset daily tracking
        scratch["daily_total"] = 0.0
        scratch["limit_reached"] = False
        scratch["agent_records"] = {}

        # Monthly audit check (every 30 rounds)
        if context.round_number % params["audit_frequency_rounds"] == 0:
            norm_state["last_audit_round"] = context.round_number
            norm_state["monthly_audit_occurred"] = True
            self._conduct_audit(context)
        else:
            norm_state["monthly_audit_occurred"] = False

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply forfeiture penalty, individual cap, and track in ledger."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)
        scratch = context.round_scratch(self.key)

        # Check if daily limit already reached
        if scratch.get("limit_reached", False):
            # Entire catch goes to pool
            self._add_ledger_entry(
                context, agent_id, raw_kg, 0.0, 0.0, 0.0, 0.0, raw_kg, True,
                "Daily collective limit already reached"
            )
            return NormDecision.adjust(
                kept_kg=0.0,
                note=f"Daily collective limit of {params['daily_limit_kg']} kg reached. "
                     f"Entire catch of {raw_kg:.1f} kg returned to community pool."
            )

        # Step 1: Apply forfeiture penalty if any
        forfeiture_applied = 0.0
        pending_penalties = self._get_pending_penalties(context, agent_id)

        if pending_penalties > 0:
            forfeiture_amount = params["forfeiture_amount_kg"]
            # Apply one penalty (or partial if catch is smaller)
            forfeiture_applied = min(forfeiture_amount, proposed_kg)
            # Remove one penalty from queue
            self._remove_penalty(context, agent_id)

        # Remaining after forfeiture
        after_forfeiture = proposed_kg - forfeiture_applied

        # Step 2: Apply individual cap
        after_cap = min(after_forfeiture, params["individual_cap_kg"])
        individual_excess = after_forfeiture - after_cap

        # Check for individual cap violation
        individual_violation = after_forfeiture > params["individual_cap_kg"]

        # Track in scratch for collective limit check in on_agent_settled
        agent_records = scratch.setdefault("agent_records", {})
        agent_records[agent_id] = {
            "raw_kg": raw_kg,
            "proposed_kg": proposed_kg,
            "forfeiture_applied": forfeiture_applied,
            "after_forfeiture": after_forfeiture,
            "after_cap": after_cap,
            "individual_excess": individual_excess,
            "individual_violation": individual_violation,
            "final_kept": after_cap,  # May be adjusted in on_agent_settled
            "pool_deposit": forfeiture_applied + individual_excess,
            "collective_excess": 0.0,
            "collective_violation": False,
        }

        # Build note
        notes = []
        if forfeiture_applied > 0:
            notes.append(f"{forfeiture_applied:.1f}kg forfeiture penalty applied")
        if individual_excess > 0:
            notes.append(f"{individual_excess:.1f}kg individual excess to pool")
        if individual_violation:
            notes.append(f"Individual cap of {params['individual_cap_kg']}kg exceeded")

        note = "; ".join(notes) if notes else None

        # Temporarily allow the capped amount; collective adjustment happens later
        return NormDecision.adjust(kept_kg=after_cap, note=note)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Check collective limit and apply cutoff if exceeded."""
        params = self._get_params()
        scratch = context.round_scratch(self.key)
        agent_records = scratch.get("agent_records", {})

        if agent_id not in agent_records:
            return

        record = agent_records[agent_id]

        # Check if limit already reached before this agent
        if scratch.get("limit_reached", False):
            # Entire catch goes to pool
            record["final_kept"] = 0.0
            record["collective_excess"] = record["after_cap"]
            record["collective_violation"] = True
            record["pool_deposit"] += record["after_cap"]
            return

        # Check if adding this agent would exceed collective limit
        daily_total = scratch.get("daily_total", 0)
        projected_total = daily_total + record["after_cap"]

        if projected_total > params["daily_limit_kg"]:
            # Collective limit exceeded - this agent gets cutoff
            scratch["limit_reached"] = True
            record["collective_violation"] = True

            # If partial contribution is possible
            if daily_total < params["daily_limit_kg"]:
                allowed_amount = params["daily_limit_kg"] - daily_total
                record["final_kept"] = allowed_amount
                record["collective_excess"] = record["after_cap"] - allowed_amount
                record["pool_deposit"] += record["collective_excess"]
                scratch["daily_total"] = params["daily_limit_kg"]
            else:
                # Limit already at max, agent gets nothing
                record["final_kept"] = 0.0
                record["collective_excess"] = record["after_cap"]
                record["pool_deposit"] += record["collective_excess"]
        else:
            # Within limit
            record["final_kept"] = record["after_cap"]
            scratch["daily_total"] = projected_total

            # Check if we hit the limit exactly
            if projected_total >= params["daily_limit_kg"]:
                scratch["limit_reached"] = True

    def on_round_end(self, context, round_results):
        """Update community pool, finalize ledger entries."""
        scratch = context.round_scratch(self.key)
        agent_records = scratch.get("agent_records", {})
        norm_state = context.norm_state(self.key)

        if not agent_records:
            return

        # Calculate total pool deposits
        total_pool_deposit = 0.0

        for agent_id, record in agent_records.items():
            pool_deposit = record.get("pool_deposit", 0.0)
            total_pool_deposit += pool_deposit

            # Determine final violations
            violation = record.get("individual_violation", False) or record.get("collective_violation", False)

            # Update the ledger entry with final amounts
            self._update_ledger_entry(
                context, agent_id,
                record.get("forfeiture_applied", 0.0),
                record.get("after_cap", 0.0),
                record.get("final_kept", 0.0),
                pool_deposit,
                violation
            )

            # Update round_results with final kept amount
            if agent_id in round_results:
                old_kept = round_results[agent_id]["harvested_kg"]
                new_kept = record.get("final_kept", 0.0)
                if old_kept != new_kept:
                    round_results[agent_id]["harvested_kg"] = new_kept
                    existing_note = round_results[agent_id].get("note", "")
                    collective_note = f"Collective limit adjustment: {old_kept:.1f} kg -> {new_kept:.1f} kg"
                    round_results[agent_id]["note"] = (
                        f"{existing_note}; {collective_note}" if existing_note else collective_note
                    )

        # Update community pool
        if total_pool_deposit > 0:
            current_pool = norm_state.get("community_pool_kg", 0)
            norm_state["community_pool_kg"] = current_pool + total_pool_deposit
            norm_state["last_round_pool_deposit"] = total_pool_deposit

    def _conduct_audit(self, context):
        """Conduct monthly audit and queue penalties for violators."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)
        ledger = self._get_ledger(context)

        # Find all violations since last audit
        last_audit_round = norm_state.get("last_audit_round", 0)
        audit_frequency = params["audit_frequency_rounds"]
        start_round = max(0, last_audit_round - audit_frequency)

        violations_by_agent = {}

        for entry in ledger:
            if entry["round"] > start_round and entry.get("violation", False):
                agent_id = entry["agent_id"]
                if agent_id not in violations_by_agent:
                    violations_by_agent[agent_id] = 0
                violations_by_agent[agent_id] += 1

        # Queue penalties for each violation
        pending_penalties = norm_state.setdefault("pending_penalties", {})

        for agent_id, violation_count in violations_by_agent.items():
            if agent_id not in pending_penalties:
                pending_penalties[agent_id] = 0
            pending_penalties[agent_id] += violation_count

        # Store audit results
        norm_state["last_audit_violations"] = violations_by_agent
        norm_state["last_audit_penalties_queued"] = sum(violations_by_agent.values())

    def _get_pending_penalties(self, context, agent_id):
        """Get number of pending penalties for an agent."""
        norm_state = context.norm_state(self.key)
        pending_penalties = norm_state.get("pending_penalties", {})
        return pending_penalties.get(agent_id, 0)

    def _remove_penalty(self, context, agent_id):
        """Remove one pending penalty for an agent."""
        norm_state = context.norm_state(self.key)
        pending_penalties = norm_state.setdefault("pending_penalties", {})

        if agent_id in pending_penalties and pending_penalties[agent_id] > 0:
            pending_penalties[agent_id] -= 1
            if pending_penalties[agent_id] == 0:
                del pending_penalties[agent_id]

    def _get_params(self):
        """Get parameters with defaults."""
        return {
            "individual_cap_kg": self.params.get("individual_cap_kg", 18),
            "daily_limit_kg": self.params.get("daily_limit_kg", 220),
            "audit_frequency_rounds": self.params.get("audit_frequency_rounds", 30),
            "forfeiture_amount_kg": self.params.get("forfeiture_amount_kg", 5),
        }

    def _get_ledger(self, context):
        """Get the shared ledger."""
        norm_state = context.norm_state(self.key)
        return norm_state.get("ledger", [])

    def _add_ledger_entry(self, context, agent_id, raw_catch, forfeiture_applied,
                          after_cap, after_collective, final_kept, pool_deposit,
                          violation, note=""):
        """Add an entry to the shared ledger."""
        norm_state = context.norm_state(self.key)
        ledger = norm_state.setdefault("ledger", [])

        entry = {
            "round": context.round_number,
            "agent_id": agent_id,
            "raw_catch": raw_catch,
            "forfeiture_applied": forfeiture_applied,
            "after_cap": after_cap,
            "after_collective": after_collective,
            "final_kept": final_kept,
            "pool_deposit": pool_deposit,
            "violation": violation,
            "note": note,
        }

        ledger.append(entry)

        # Trim old entries (keep last 200 for memory efficiency)
        if len(ledger) > 200:
            norm_state["ledger"] = ledger[-200:]

    def _update_ledger_entry(self, context, agent_id, forfeiture_applied,
                             after_cap, final_kept, pool_deposit, violation):
        """Update the most recent ledger entry for this agent with final amounts."""
        norm_state = context.norm_state(self.key)
        ledger = norm_state.get("ledger", [])

        # Find the most recent entry for this agent in current round
        for entry in reversed(ledger):
            if entry["agent_id"] == agent_id and entry["round"] == context.round_number:
                entry["forfeiture_applied"] = forfeiture_applied
                entry["after_cap"] = after_cap
                entry["final_kept"] = final_kept
                entry["pool_deposit"] = pool_deposit
                entry["violation"] = violation
                break
