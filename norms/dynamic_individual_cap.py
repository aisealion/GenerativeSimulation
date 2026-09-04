"""Dynamic individual cap based on lake reserves.

Implements:
- Standard 15 kg cap when reserves >= 20 kg
- Emergency 10 kg cap when reserves < 20 kg
- Excess returned to lake (regenerates stock)
- Shared ledger for audit trail
"""

from engine.norms.base import Norm, NormDecision


class DynamicIndividualCapNorm(Norm):
    type_name = "dynamic_individual_cap"

    def describe(self, context, agent_id):
        params = self._get_params()
        standard_cap = params["standard_cap_kg"]
        emergency_cap = params["emergency_cap_kg"]
        threshold = params["emergency_threshold_kg"]

        # Determine current cap
        current_cap = self._get_current_cap(context)
        is_emergency = current_cap == emergency_cap

        parts = []

        if is_emergency:
            parts.append(
                f"EMERGENCY CAP ACTIVE: Lake reserves are below {threshold} kg. "
                f"You may keep at most {emergency_cap} kg per trip (normally {standard_cap} kg). "
                f"The standard cap will resume when reserves recover to {threshold} kg or more."
            )
        else:
            parts.append(
                f"You may keep at most {standard_cap} kg per trip. "
                f"Current lake reserves are healthy ({context.stock_before:.1f} kg)."
            )

        # Add recent ledger entries
        ledger = self._get_ledger(context)
        if ledger:
            recent = [e for e in ledger if e["round"] >= context.round_number - 2]
            if recent:
                parts.append("Recent ledger entries:")
                for entry in recent[-3:]:  # Show last 3
                    parts.append(
                        f"  Round {entry['round']}: {entry['agent_id']} caught {entry['raw_catch']:.1f}kg, "
                        f"kept {entry['kept']:.1f}kg, returned {entry['returned']:.1f}kg"
                    )

        return " ".join(parts)

    def on_round_start(self, context):
        """Determine which cap applies this round and track history."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        # Determine current cap based on reserves
        if context.stock_before < params["emergency_threshold_kg"]:
            current_cap = params["emergency_cap_kg"]
        else:
            current_cap = params["standard_cap_kg"]

        # Track previous cap for recovery detection
        previous_cap = norm_state.get("current_cap")

        # Update state
        norm_state["current_cap"] = current_cap
        norm_state["previous_cap"] = previous_cap
        norm_state["reserves_at_round_start"] = context.stock_before

        # Track if this is a recovery or emergency activation
        if previous_cap is not None:
            if previous_cap == params["emergency_cap_kg"] and current_cap == params["standard_cap_kg"]:
                norm_state["recovery_announcement"] = True
            elif previous_cap == params["standard_cap_kg"] and current_cap == params["emergency_cap_kg"]:
                norm_state["emergency_announcement"] = True
            else:
                norm_state["recovery_announcement"] = False
                norm_state["emergency_announcement"] = False

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply the appropriate cap and record in ledger."""
        params = self._get_params()
        current_cap = self._get_current_cap(context)

        # Apply the cap
        after_cap = min(proposed_kg, current_cap)
        returned = proposed_kg - after_cap

        # Record in ledger
        self._add_ledger_entry(context, agent_id, raw_kg, after_cap, returned, current_cap)

        # Store in scratch for on_round_end stock replenishment
        scratch = context.round_scratch(self.key)
        agent_records = scratch.setdefault("agent_records", {})
        agent_records[agent_id] = {
            "raw_kg": raw_kg,
            "proposed_kg": proposed_kg,
            "after_cap": after_cap,
            "returned": returned,
            "cap_applied": current_cap,
        }

        if after_cap < proposed_kg:
            return NormDecision.adjust(
                kept_kg=after_cap,
                note=f"Individual cap ({current_cap} kg) applied: {proposed_kg:.1f} kg → {after_cap:.1f} kg, {returned:.1f} kg returned to lake"
            )

        return NormDecision.allow(after_cap)

    def on_round_end(self, context, round_results):
        """Return excess to lake stock."""
        scratch = context.round_scratch(self.key)
        agent_records = scratch.get("agent_records", {})

        if not agent_records:
            return

        # Calculate total returned to lake
        total_returned = sum(r["returned"] for r in agent_records.values())

        if total_returned > 0:
            # Replenish lake stock: current stock - harvested + returned
            # Note: The physics system has already deducted harvested amounts
            # We need to add the returned amount back to stock
            current_stock = context.stock_before

            # Calculate what stock would be after all harvesting
            total_harvested = sum(round_results.get(aid, {}).get("harvested_kg", 0) for aid in agent_records)
            stock_after_harvest = current_stock - total_harvested

            # Add returned fish back
            new_stock = stock_after_harvest + total_returned

            # Override the stock
            context.override_stock_after_regrowth(new_stock)

            # Record in norm state
            norm_state = context.norm_state(self.key)
            norm_state["last_round_returned"] = total_returned
            norm_state["total_returned_to_lake"] = norm_state.get("total_returned_to_lake", 0.0) + total_returned

    def _get_params(self):
        """Get parameters with defaults."""
        return {
            "standard_cap_kg": self.params.get("standard_cap_kg", 15),
            "emergency_cap_kg": self.params.get("emergency_cap_kg", 10),
            "emergency_threshold_kg": self.params.get("emergency_threshold_kg", 20),
        }

    def _get_current_cap(self, context):
        """Get the cap applicable for this round."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        # Use stored cap from on_round_start, or calculate if not set
        current_cap = norm_state.get("current_cap")
        if current_cap is None:
            if context.stock_before < params["emergency_threshold_kg"]:
                current_cap = params["emergency_cap_kg"]
            else:
                current_cap = params["standard_cap_kg"]

        return current_cap

    def _get_ledger(self, context):
        """Get the shared ledger."""
        norm_state = context.norm_state(self.key)
        return norm_state.get("ledger", [])

    def _add_ledger_entry(self, context, agent_id, raw_catch, kept, returned, cap_applied):
        """Add an entry to the shared ledger."""
        norm_state = context.norm_state(self.key)
        ledger = norm_state.setdefault("ledger", [])

        entry = {
            "round": context.round_number,
            "agent_id": agent_id,
            "raw_catch": raw_catch,
            "kept": kept,
            "returned": returned,
            "cap_applied": cap_applied,
        }

        ledger.append(entry)

        # Trim old entries (keep last 50 for memory efficiency)
        if len(ledger) > 50:
            norm_state["ledger"] = ledger[-50:]
