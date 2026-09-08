from dataclasses import dataclass
from engine.norms.base import Norm, NormDecision

CAP_KG = 10.0
DEPOSIT_KG = 2.0
FINE_RATE = 0.05  # 5% of total catch
FINE_MAX_KG = 2.0

class Round1Norm(Norm):
    type_name: str = "round_1"

    def describe(self, context, agent_id):
        return f"Catch cap {CAP_KG} kg per trip, deposit {DEPOSIT_KG} kg to communal reserve."

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        # Apply catch cap
        capped = min(raw_kg, CAP_KG)
        # Determine deposit availability
        if capped >= DEPOSIT_KG:
            kept = capped - DEPOSIT_KG
            # Record deposit for later aggregate
            context.round_scratch(self.key).setdefault("deposits", []).append(DEPOSIT_KG)
            return NormDecision.adjust(kept_kg=kept, note="deposit applied")
        else:
            # Not enough catch to cover deposit – fine path
            shortfall = DEPOSIT_KG - capped
            # Fine is 5% of the trip's total catch (raw_kg) capped at 2 kg
            fine = min(FINE_RATE * raw_kg, FINE_MAX_KG)
            # Record fine for later aggregate
            context.round_scratch(self.key).setdefault("fines", []).append(fine)
            # Agent keeps whatever they caught (no deposit) but note the violation
            return NormDecision.violation(kept_kg=capped, sanction="fine", note=f"missing deposit, fine {fine:.2f} kg")

    def on_round_end(self, context, round_results):
        # Update persistent communal reserve balance
        state = context.norm_state(self.key)
        reserve = state.get("reserve_kg", 0.0)
        deposits = sum(context.round_scratch(self.key).get("deposits", []))
        fines = sum(context.round_scratch(self.key).get("fines", []))
        state["reserve_kg"] = reserve + deposits + fines
        return None
