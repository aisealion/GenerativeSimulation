"""Sustenance cap with communal obligations and weekly reviews.

Implements Round 5 norms:
- Fixed 12 kg per-trip cap
- 1 kg minimum self-sustenance floor
- Communal obligations when violating cap (excess becomes obligation)
- Two-trip window to satisfy obligations
- Automatic 10% deduction per trip toward obligations
- Weekly community council reviews (every 7 rounds)
- Excess returned to lake (replenishes stock)
- Communal pool for obligation fee payments
"""

from engine.norms.base import Norm, NormDecision


class SustenanceCapWithObligationNorm(Norm):
    type_name = "sustenance_cap_with_obligation"

    def describe(self, context, agent_id):
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        parts = []

        # Describe the cap and minimum
        parts.append(
            f"You may keep at most {params['cap_kg']} kg per trip, "
            f"with a minimum of {params['min_keep_kg']} kg for self-sustenance."
        )

        # Check for outstanding obligations
        obligations = norm_state.get("obligations", {})
        if agent_id in obligations:
            obl = obligations[agent_id]
            parts.append(
                f"COMMUNAL OBLIGATION: You owe {obl['amount']:.1f} kg from a previous violation. "
                f"You have {obl['trips_remaining']} trip(s) remaining to satisfy this obligation "
                f"through catch deductions or payment."
            )

        # Show communal pool total
        communal_pool = norm_state.get("communal_pool_kg", 0)
        parts.append(f"Communal pool total: {communal_pool:.1f} kg (from obligation payments).")

        # Weekly review announcement
        last_review = norm_state.get("last_review_round", 0)
        if last_review > 0 and context.round_number - last_review < 2:
            parts.append(
                f"Weekly community council review occurred in round {last_review}. "
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
                    obl_str = f", obligation {entry['obligation_accrued']:.1f}kg" if entry['obligation_accrued'] > 0 else ""
                    violation_str = " (VIOLATION)" if entry['violation'] else ""
                    parts.append(
                        f"  Round {entry['round']}: caught {entry['raw_catch']:.1f}kg, "
                        f"deducted {entry['obligation_deducted']:.1f}kg, kept {entry['kept']:.1f}kg, "
                        f"returned {entry['returned_to_lake']:.1f}kg{obl_str}{violation_str}"
                    )

        return " ".join(parts)

    def on_round_start(self, context):
        """Check for weekly review and clean up expired obligations."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        # Weekly review check (every 7 rounds)
        if context.round_number % params["review_frequency_rounds"] == 0:
            norm_state["last_review_round"] = context.round_number
            norm_state["weekly_review_occurred"] = True
        else:
            norm_state["weekly_review_occurred"] = False

        # Decrement trips_remaining for all obligations
        obligations = norm_state.get("obligations", {})
        for agent_id, obl in list(obligations.items()):
            obl["trips_remaining"] -= 1

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """Apply obligation deduction, then 12kg cap, then 1kg floor."""
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        # Step 1: Apply obligation deduction first
        obligation_deducted = 0.0
        obligations = norm_state.get("obligations", {})

        if agent_id in obligations:
            obl = obligations[agent_id]
            # Deduct up to 10% of raw catch or the obligation amount, whichever is smaller
            max_deduction = raw_kg * params["auto_deduction_rate"]
            obligation_deducted = min(max_deduction, obl["amount"])

            # Update the obligation
            obl["amount"] -= obligation_deducted
            if obl["amount"] <= 0:
                # Obligation fully satisfied
                del obligations[agent_id]

        # Remaining after obligation deduction
        after_obligation = proposed_kg - obligation_deducted

        # Step 2: Apply the 12kg cap
        after_cap = min(after_obligation, params["cap_kg"])
        returned_to_lake = after_obligation - after_cap

        # Step 3: Check for violation (did they exceed the cap?)
        violated = after_obligation > params["cap_kg"]

        # Step 4: Apply minimum floor
        final_kept = max(after_cap, params["min_keep_kg"])

        # Ensure we don't give more than they actually caught
        final_kept = min(final_kept, raw_kg)

        # Ensure we don't give more than they had after cap
        if final_kept > after_cap:
            final_kept = after_cap

        # Track obligation accrued (will be set in on_agent_settled if violation)
        obligation_accrued = 0.0

        # Record in ledger
        self._add_ledger_entry(
            context, agent_id, raw_kg, obligation_deducted, final_kept,
            returned_to_lake, obligation_accrued, violated
        )

        # Store in scratch for on_agent_settled and on_round_end processing
        scratch = context.round_scratch(self.key)
        agent_records = scratch.setdefault("agent_records", {})
        agent_records[agent_id] = {
            "raw_kg": raw_kg,
            "proposed_kg": proposed_kg,
            "obligation_deducted": obligation_deducted,
            "after_obligation": after_obligation,
            "after_cap": after_cap,
            "returned_to_lake": returned_to_lake,
            "final_kept": final_kept,
            "violated": violated,
            "obligation_accrued": obligation_accrued,  # Will be updated in on_agent_settled
        }

        # Build note
        notes = []
        if obligation_deducted > 0:
            notes.append(f"{obligation_deducted:.1f}kg deducted for communal obligation")
        if returned_to_lake > 0:
            notes.append(f"{returned_to_lake:.1f}kg returned to lake")
        if violated:
            notes.append("VIOLATION: 12kg cap exceeded")

        note = "; ".join(notes) if notes else None

        if violated:
            return NormDecision.violation(kept_kg=final_kept, sanction="communal_obligation", note=note)

        if obligation_deducted > 0 or returned_to_lake > 0:
            return NormDecision.adjust(kept_kg=final_kept, note=note)

        return NormDecision.allow(final_kept)

    def on_agent_settled(self, context, agent_id, decision, harvested_kg):
        """Track violations and create/update communal obligations."""
        scratch = context.round_scratch(self.key)
        agent_records = scratch.get("agent_records", {})
        record = agent_records.get(agent_id, {})

        if record.get("violated", False):
            # Create a new obligation for the excess
            params = self._get_params()
            norm_state = context.norm_state(self.key)
            obligations = norm_state.setdefault("obligations", {})

            # Excess = amount over the cap
            excess = record["after_obligation"] - params["cap_kg"]

            if agent_id in obligations:
                # Add to existing obligation (shouldn't normally happen, but handle it)
                obligations[agent_id]["amount"] += excess
                # Reset trips remaining
                obligations[agent_id]["trips_remaining"] = params["obligation_trips"]
            else:
                # Create new obligation
                obligations[agent_id] = {
                    "amount": excess,
                    "trips_remaining": params["obligation_trips"],
                    "created_round": context.round_number,
                }

            # Update the record
            record["obligation_accrued"] = excess

    def on_round_end(self, context, round_results):
        """Return excess to lake, force-pay expired obligations, update communal pool."""
        scratch = context.round_scratch(self.key)
        agent_records = scratch.get("agent_records", {})
        params = self._get_params()
        norm_state = context.norm_state(self.key)

        if not agent_records:
            return

        # Calculate totals
        total_returned = sum(r["returned_to_lake"] for r in agent_records.values())
        total_deducted = sum(r["obligation_deducted"] for r in agent_records.values())

        # Update communal pool with deductions
        if total_deducted > 0:
            current_pool = norm_state.get("communal_pool_kg", 0)
            norm_state["communal_pool_kg"] = current_pool + total_deducted

        # Handle expired obligations (force-pay any remaining after 2 trips)
        obligations = norm_state.get("obligations", {})
        total_forced_payment = 0.0

        for agent_id, obl in list(obligations.items()):
            if obl["trips_remaining"] <= 0 and obl["amount"] > 0:
                # Force-pay the remaining obligation
                remaining = obl["amount"]
                total_forced_payment += remaining

                # Deduct from the agent's harvested amount for this round
                if agent_id in round_results:
                    round_results[agent_id]["harvested_kg"] = max(
                        0, round_results[agent_id]["harvested_kg"] - remaining
                    )
                    # Add a note about forced payment
                    existing_note = round_results[agent_id].get("note", "")
                    forced_note = f"Forced payment of {remaining:.1f}kg for expired communal obligation"
                    round_results[agent_id]["note"] = (
                        f"{existing_note}; {forced_note}" if existing_note else forced_note
                    )

                # Clear the obligation
                del obligations[agent_id]

        # Add forced payments to communal pool
        if total_forced_payment > 0:
            current_pool = norm_state.get("communal_pool_kg", 0)
            norm_state["communal_pool_kg"] = current_pool + total_forced_payment

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

    def _get_params(self):
        """Get parameters with defaults."""
        return {
            "cap_kg": self.params.get("cap_kg", 12),
            "min_keep_kg": self.params.get("min_keep_kg", 1),
            "obligation_trips": self.params.get("obligation_trips", 2),
            "auto_deduction_rate": self.params.get("auto_deduction_rate", 0.10),
            "review_frequency_rounds": self.params.get("review_frequency_rounds", 7),
        }

    def _get_ledger(self, context):
        """Get the shared ledger."""
        norm_state = context.norm_state(self.key)
        return norm_state.get("ledger", [])

    def _add_ledger_entry(self, context, agent_id, raw_catch, obligation_deducted,
                          kept, returned_to_lake, obligation_accrued, violation):
        """Add an entry to the shared ledger."""
        norm_state = context.norm_state(self.key)
        ledger = norm_state.setdefault("ledger", [])

        entry = {
            "round": context.round_number,
            "agent_id": agent_id,
            "raw_catch": raw_catch,
            "obligation_deducted": obligation_deducted,
            "kept": kept,
            "returned_to_lake": returned_to_lake,
            "obligation_accrued": obligation_accrued,
            "violation": violation,
        }

        ledger.append(entry)

        # Trim old entries (keep last 100 for memory efficiency)
        if len(ledger) > 100:
            norm_state["ledger"] = ledger[-100:]
