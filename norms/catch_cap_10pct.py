"""
Round 1 Norm: 10% Catch Cap with 1kg Sustenance Floor

Implements the core constraint from the Round 1 adopted norm:
- Each fisher may take no more than 10% of the lake's current total weight per trip
- Must keep at least 1 kg for sustenance

This is a single norm that combines both the cap and the floor logic:
- The cap limits catch to 10% of stock_before
- The floor ensures at least 1 kg is kept (relevant when stock is very low)
- Excess is automatically returned (forfeited to the lake)
"""

from engine.norms.base import Norm, NormDecision


class CatchCap10PctNorm(Norm):
    """
    Enforces a 10% catch cap relative to current stock, with a 1kg minimum floor.

    Config parameters: None (uses fixed 10% and 1kg values per the adopted norm)

    Behavior:
    - Calculates limit as 10% of stock_before
    - If raw catch <= limit: allow full catch
    - If raw catch > limit: trim to limit, record violation with excess amount
    - Floor: If limit < 1kg, fisher may still keep 1kg (sustenance guarantee)
    """

    type_name = "catch_cap_10pct"

    # Fixed values from the adopted norm
    CAP_PERCENTAGE = 0.10  # 10%
    MINIMUM_KEEP_KG = 1.0  # 1 kg sustenance floor

    def describe(self, context, agent_id):
        """Tell the agent their current catch limit."""
        stock = context.stock_before
        cap = stock * self.CAP_PERCENTAGE
        effective_limit = max(cap, self.MINIMUM_KEEP_KG)

        if cap < self.MINIMUM_KEEP_KG:
            return (
                f"The lake holds {stock:.0f}kg. "
                f"You may keep up to {effective_limit:.0f}kg (the minimum sustenance amount)."
            )
        return (
            f"The lake holds {stock:.0f}kg. "
            f"You may keep up to {cap:.1f}kg (10% of the total)."
        )

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """
        Apply the 10% cap with 1kg floor.

        Args:
            context: HarvestContext with stock_before
            agent_id: The agent being evaluated
            raw_kg: Physics-computed catch
            proposed_kg: Previous norm's decision (or raw_kg)

        Returns:
            NormDecision with trimmed catch if over limit
        """
        stock = context.stock_before
        cap = stock * self.CAP_PERCENTAGE

        # Apply the floor: effective limit is at least 1kg
        effective_limit = max(cap, self.MINIMUM_KEEP_KG)

        if proposed_kg <= effective_limit:
            # Within limits - allow as-is
            return NormDecision.allow(proposed_kg)

        # Over the limit - trim and record violation
        excess = proposed_kg - effective_limit
        if cap < self.MINIMUM_KEEP_KG:
            note = (
                f"Your catch of {proposed_kg:.1f}kg exceeded the sustenance minimum. "
                f"You kept {effective_limit:.0f}kg."
            )
        else:
            note = (
                f"Your catch of {proposed_kg:.1f}kg exceeded the 10% limit ({cap:.1f}kg). "
                f"You kept {effective_limit:.1f}kg; {excess:.1f}kg was returned to the lake."
            )

        return NormDecision.violation(
            kept_kg=effective_limit,
            sanction="over_10pct_cap",
            note=note,
        )
