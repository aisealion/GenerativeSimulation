"""Dynamic individual cap with violation penalties and minimum floor.

Implements Round 4 norms:
- Dynamic cap: 15 kg standard, 10 kg when stock < 100 kg
- 1 kg minimum self-sustenance floor
- 1 kg penalty to communal pool on violation
- Personal limit reduction (-5 kg) for next trip on violation
- Shared logbook for audit trail
- Excess returned to lake
"""

from engine.norms.base import Norm, NormDecision


class DynamicCapWithPenaltyNorm(Norm):
    type_name = "dynamic_cap_with_penalty"

    def describe(self, context, agent_id):
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        # Get current standard cap
        current_cap = self._get_current_cap(context)
        is_emergency = current_cap == params["emergency_cap_kg"]

        parts = []

        # Describe current cap situation
        if is_emergency:
            parts.append(
                f"EMERGENCY CAP ACTIVE: Lake stock is below {params['emergency_threshold_kg']} kg. "
                f"You may keep at most {params['emergency_cap_kg']} kg per trip (normally {params['standard_cap_kg']} kg). "
                f"The standard cap will resume when stock recovers to {params['emergency_threshold_kg']} kg or more."
            )
        else:
            parts.append(
                f"Standard cap: You may keep at most {params['standard_cap_kg']} kg per trip. "
                f"Current lake stock is healthy ({context.stock_before:.1f} kg)."
            )

        # Check for personal limit penalty
        personal_limits = norm_state.get("personal_limits", {})
        if agent_id in personal_limits:
            penalty_info = personal_limits[agent_id]
            reduced_limit = penalty_info.get("reduced_limit", current_cap)
            parts.append(
                f"PENALTY ACTIVE: Due to a previous violation, your personal limit for this trip is {reduced_limit} kg. "
                f"After this trip, your limit will reset if you comply."
            )

        # Describe minimum floor
        parts.append(f"Self-sustenance minimum: You must keep at least {params['min_keep_kg']} kg per trip.")

        # Describe violation penalty
        parts.append(
            f"Violation penalty: If you exceed your limit, excess goes to the lake and you pay "
            f"{params['violation_penalty_kg']} kg to the communal pool."
        )

        # Show communal pool total
        communal_pool = norm_state.get("communal_pool_kg", 0)
        parts.append(f"Communal pool total: {communal_pool:.1f} kg (from all violations).")

        # Add recent logbook entries
        logbook = self._get_logbook(context)
        if logbook:
            agent_entries = [e for e in logbook if e["agent_id"] == agent_id]
            recent = [e for e in agent_entries if e["round"] >= context.round_number - 2]
            if recent:
                parts.append("Your recent logbook entries:")
                for entry in recent[-3:]:
                    penalty_str = f", penalty {entry['penalty']:.1f}kg" if entry['penalty'] > 0 else ""
                    violation_str = " (VIOLATION)" if entry['violated'] else ""
                    parts.append(
                        f"  Round {entry['round']}: caught {entry['raw_catch']:.1f}kg, "
                        f"limit {entry['personal_limit']:.1f}kg, kept {entry['kept']:.1f}kg, "
                        f"returned {entry['returned']:.1f}kg{penalty_str}{violation_str}"
                    )

        return " ".join(parts)

    def on_round_start(self, context):
        """Determine which cap applies this round and clean up expired penalties."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        # Determine current standard cap based on stock
        if context.stock_before < params["emergency_threshold_kg"]:
            current_cap = params["emergency_cap_kg"]
        else:
            current_cap = params["standard_cap_kg"]

        # Track previous cap for recovery detection
        previous_cap = norm_state.get("current_cap")
        norm_state["current_cap"] = current_cap
        norm_state["previous_cap"] = previous_cap
        norm_state["stock_at_round_start"] = context.stock_before

        # Track recovery/emergency announcements
        if previous_cap is not None:
            if previous_cap == params["emergency_cap_kg"] and current_cap == params["standard_cap_kg"]:
                norm_state["recovery_announcement"] = True
                norm_state["emergency_announcement"] = False
            elif previous_cap == params["standard_cap_kg"] and current_cap == params["emergency_cap_kg"]:
                norm_state["recovery_announcement"] = False
                norm_state["emergency_announcement"] = True
            else:
                norm_state["recovery_announcement"] = False
                norm_state["emergency_announcement"] = False

        # Monthly review (every 30 rounds)
        if context.round_number % 30 == 0:
            norm_state["monthly_review"] = {
                "round": context.round_number,
                "stock": context.stock_before,
                "cap_applied": current_cap,
            }

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply personal limit, cap, violation penalty, and minimum floor."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        # Get the applicable limit (standard cap or personal reduced limit)
        personal_limit = self._get_personal_limit(context, agent_id)

        # Step 1: Apply the limit (cap)
        after_cap = min(proposed_kg, personal_limit)
        returned_to_lake = proposed_kg - after_cap

        # Step 2: Check for violation (did they exceed their limit?)
        violated = proposed_kg > personal_limit
        penalty = 0.0

        if violated:
            # Assess 1 kg penalty to communal pool
            penalty = params["violation_penalty_kg"]
            after_penalty = max(0, after_cap - penalty)
        else:
            after_penalty = after_cap

        # Step 3: Apply minimum floor
        final_kept = max(after_penalty, params["min_keep_kg"])

        # If floor was applied and it increased the amount, we need to adjust
        # But we can't give more than they had after cap
        if final_kept > after_cap:
            final_kept = after_cap

        # Ensure we don't give more than they actually caught
        final_kept = min(final_kept, raw_kg)

        # Record in logbook
        self._add_logbook_entry(
            context, agent_id, raw_kg, personal_limit, final_kept,
            returned_to_lake, penalty, violated
        )

        # Store in scratch for on_round_end processing
        scratch = context.round_scratch(self.key)
        agent_records = scratch.setdefault("agent_records", {})
        agent_records[agent_id] = {
            "raw_kg": raw_kg,
            "proposed_kg": proposed_kg,
            "personal_limit": personal_limit,
            "after_cap": after_cap,
            "returned_to_lake": returned_to_lake,
            "penalty": penalty,
            "after_penalty": after_penalty,
            "final_kept": final_kept,
            "violated": violated,
        }

        # Build note
        notes = []
        if personal_limit < self._get_current_cap(context):
            notes.append(f"Personal limit {personal_limit}kg applied")
        if returned_to_lake > 0:
            notes.append(f"{returned_to_lake:.1f}kg returned to lake")
        if penalty > 0:
            notes.append(f"{penalty:.1f}kg penalty to communal pool")
        if violated:
            notes.append("VIOLATION recorded")

        note = "; ".join(notes) if notes else None

        if violated:
            return NormDecision.violation(kept_kg=final_kept, sanction="limit_reduction", note=note)

        if penalty > 0 or returned_to_lake > 0:
            return NormDecision.adjust(kept_kg=final_kept, note=note)

        return NormDecision.allow(final_kept)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Set up personal limit reduction for next trip if violation occurred."""
        scratch = context.round_scratch(self.key)
        agent_records = scratch.get("agent_records", {})
        record = agent_records.get(agent_id, {})

        if record.get("violated", False):
            # Set up penalty for next trip
            params = self._get_params()
            norm_state = context.norm_state(self.key)
            personal_limits = norm_state.setdefault("personal_limits", {})

            current_cap = self._get_current_cap(context)
            reduced_limit = max(
                params["min_keep_kg"],
                current_cap - params["limit_reduction_kg"]
            )

            personal_limits[agent_id] = {
                "reduced_limit": reduced_limit,
                "set_in_round": context.round_number,
            }
        else:
            # Clear any existing penalty (compliant trip)
            norm_state = context.norm_state(self.key)
            personal_limits = norm_state.get("personal_limits", {})
            if agent_id in personal_limits:
                del personal_limits[agent_id]

    def on_round_end(self, context, round_results):
        """Return excess to lake and update communal pool."""
        scratch = context.round_scratch(self.key)
        agent_records = scratch.get("agent_records", {})

        if not agent_records:
            return

        # Calculate totals
        total_returned = sum(r["returned_to_lake"] for r in agent_records.values())
        total_penalties = sum(r["penalty"] for r in agent_records.values())

        norm_state = context.norm_state(self.key)

        # Update communal pool with penalties
        if total_penalties > 0:
            current_pool = norm_state.get("communal_pool_kg", 0)
            norm_state["communal_pool_kg"] = current_pool + total_penalties

        # Return excess to lake
        if total_returned > 0:
            current_stock = context.stock_before
            total_harvested = sum(
                round_results.get(aid, {}).get("harvested_kg", 0)
                for aid in agent_records
            )
            stock_after_harvest = current_stock - total_harvested
            new_stock = stock_after_harvest + total_returned

            context.override_stock_after_regrowth(new_stock)

            norm_state["last_round_returned"] = total_returned
            norm_state["total_returned_to_lake"] = norm_state.get("total_returned_to_lake", 0.0) + total_returned

        # Clean up expired personal limits (they expire after one round)
        personal_limits = norm_state.get("personal_limits", {})
        agents_to_remove = []
        for aid, info in personal_limits.items():
            set_round = info.get("set_in_round", 0)
            # If the limit was set in a previous round, it should have been used this round
            # and on_agent_settled would have cleared it if compliant
            # If still present, agent didn't fish this round, keep it for next time
            if aid not in agent_records and context.round_number > set_round + 1:
                # Penalty expired (agent didn't fish for a round)
                agents_to_remove.append(aid)

        for aid in agents_to_remove:
            del personal_limits[aid]

    def _get_params(self):
        """Get parameters with defaults."""
        return {
            "standard_cap_kg": self.params.get("standard_cap_kg", 15),
            "emergency_cap_kg": self.params.get("emergency_cap_kg", 10),
            "emergency_threshold_kg": self.params.get("emergency_threshold_kg", 100),
            "min_keep_kg": self.params.get("min_keep_kg", 1),
            "violation_penalty_kg": self.params.get("violation_penalty_kg", 1),
            "limit_reduction_kg": self.params.get("limit_reduction_kg", 5),
        }

    def _get_current_cap(self, context):
        """Get the standard cap applicable for this round."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        current_cap = norm_state.get("current_cap")
        if current_cap is None:
            if context.stock_before < params["emergency_threshold_kg"]:
                current_cap = params["emergency_cap_kg"]
            else:
                current_cap = params["standard_cap_kg"]

        return current_cap

    def _get_personal_limit(self, context, agent_id):
        """Get the applicable limit for this agent (standard or reduced)."""
        current_cap = self._get_current_cap(context)
        norm_state = context.norm_state(self.key)
        personal_limits = norm_state.get("personal_limits", {})

        if agent_id in personal_limits:
            return personal_limits[agent_id].get("reduced_limit", current_cap)

        return current_cap

    def _get_logbook(self, context):
        """Get the shared logbook."""
        norm_state = context.norm_state(self.key)
        return norm_state.get("logbook", [])

    def _add_logbook_entry(self, context, agent_id, raw_catch, personal_limit,
                           kept, returned, penalty, violated):
        """Add an entry to the shared logbook."""
        norm_state = context.norm_state(self.key)
        logbook = norm_state.setdefault("logbook", [])

        entry = {
            "round": context.round_number,
            "agent_id": agent_id,
            "raw_catch": raw_catch,
            "standard_cap": self._get_current_cap(context),
            "personal_limit": personal_limit,
            "kept": kept,
            "returned": returned,
            "penalty": penalty,
            "violated": violated,
        }

        logbook.append(entry)

        # Trim old entries (keep last 100 for memory efficiency)
        if len(logbook) > 100:
            norm_state["logbook"] = logbook[-100:]
