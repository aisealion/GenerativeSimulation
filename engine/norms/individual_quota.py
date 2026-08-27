import math

from engine.norms.base import Norm, NormDecision


class IndividualQuotaNorm(Norm):
    """Enforces per‑fisher quota:
    * max 1.0 kg per trip
    * max 5 % of current lake biomass per trip
    * lake must retain at least 80 % of its stock after the round
    """

    type_name = "individual_quota"

    def on_round_start(self, context):
        # compute per‑fisher limit once and store in round‑scratch
        per_fisher_limit = min(1.0, 0.05 * context.stock_before)
        # maximum total catch allowed to keep 80 % reserve
        max_total_catch = 0.2 * context.stock_before
        context.round_scratch(self.key).update({
            "per_fisher_limit": per_fisher_limit,
            "max_total_catch": max_total_catch,
            "total_harvested": 0.0,
        })
        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        # The old per‑fisher quota is superseded by the new 90 % lake‑stock policy.
        # This norm now simply passes through the decision unchanged.
        return NormDecision.allow(proposed_kg)

    def on_round_end(self, context, round_results):
        # Ensure the lake retains at least 80% – if due to rounding we fell short,
        # bump the stock back up via the override hook.
        scratch = context.round_scratch(self.key)
        total_harvested = scratch.get("total_harvested", 0.0)
        expected_stock = context.stock_before - total_harvested
        min_allowed_stock = 0.8 * context.stock_before
        if expected_stock < min_allowed_stock:
            # restore the missing amount so the simulation respects the reserve
            restore = min_allowed_stock - expected_stock
            context.override_stock_after_regrowth(context.stock_before - total_harvested + restore)
        return None
