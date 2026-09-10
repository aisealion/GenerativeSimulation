"""Excess Redistribution Norm: Redistributes excess catch from violators.

Policy: Excess catch from non-compliant fishers is redistributed by a quick
vote of compliant fishers after each trip, giving each an equal share.

Implementation note: We use deterministic equal split instead of vote,
as the voting infrastructure for per-trip resource allocation doesn't exist.
"""

from engine.norms.base import Norm, NormDecision


class ExcessRedistributionNorm(Norm):
    """Redistributes excess from violators equally among compliant fishers.

    At the end of each round, calculates total excess from violations,
    then splits it equally among all compliant (non-violating) agents
    by adding to their payoff.
    """

    type_name = "excess_redistribution"

    def __init__(self, key, params):
        super().__init__(key, params)
        # Key of percent_stock_cap norm to get violation data from
        self.stock_cap_key = params.get("stock_cap_key", "percent_stock_cap")

    def describe(self, context, agent_id):
        """Inform agents about redistribution if applicable."""
        state = context.norm_state(self.key)

        # Check if there was a redistribution this round
        last_redistribution = state.get("last_redistribution", {})
        if last_redistribution.get("round") == context.round_number:
            share = last_redistribution.get("share_per_compliant_agent", 0.0)
            if share > 0:
                return f"Excess catch was redistributed; compliant fishers received {share:.2f}kg each."

        return None

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        """This norm doesn't modify individual catches during evaluation."""
        return NormDecision.allow(proposed_kg)

    def on_round_end(self, context, round_results):
        """Redistribute excess from violators to compliant fishers.

        Called after all agents have settled. Calculates total excess,
        identifies compliant agents, and redistributes equally.
        """
        # Get violation data from percent_stock_cap norm
        stock_cap_state = context.norm_state(self.stock_cap_key)
        violations = stock_cap_state.get("violations", [])

        # Filter to this round's violations
        this_round_violations = [
            v for v in violations
            if v.get("round") == context.round_number
        ]

        if not this_round_violations:
            # No violations this round, nothing to redistribute
            return

        # Calculate total excess
        total_excess = sum(
            v.get("excess_kg", 0.0) for v in this_round_violations
        )

        if total_excess <= 0:
            return

        # Identify violating agents
        violating_agents = set(v.get("agent_id") for v in this_round_violations)

        # Identify compliant agents (participated and not violating)
        compliant_agents = [
            agent_id for agent_id, result in round_results.items()
            if result.get("participated", False) and agent_id not in violating_agents
        ]

        if not compliant_agents:
            # No compliant agents to redistribute to
            # Excess goes back to the lake (not distributed)
            state = context.norm_state(self.key)
            state["last_redistribution"] = {
                "round": context.round_number,
                "total_excess_kg": total_excess,
                "compliant_count": 0,
                "share_per_compliant_agent": 0.0,
                "redistributed_kg": 0.0,
                "returned_to_lake_kg": total_excess,
            }
            return

        # Calculate equal share
        share_per_agent = total_excess / len(compliant_agents)

        # Add share to each compliant agent's payoff
        runtime = context.runtime
        payoff = runtime.setdefault("payoff", {})

        for agent_id in compliant_agents:
            current_payoff = payoff.get(agent_id, 0.0)
            payoff[agent_id] = current_payoff + share_per_agent

        # Record the redistribution
        state = context.norm_state(self.key)
        redistributions = state.setdefault("redistributions", [])
        redistributions.append({
            "round": context.round_number,
            "total_excess_kg": total_excess,
            "compliant_count": len(compliant_agents),
            "violating_agents": list(violating_agents),
            "share_per_compliant_agent": share_per_agent,
            "total_redistributed_kg": total_excess,
        })

        state["last_redistribution"] = {
            "round": context.round_number,
            "total_excess_kg": total_excess,
            "compliant_count": len(compliant_agents),
            "share_per_compliant_agent": share_per_agent,
            "redistributed_kg": total_excess,
            "returned_to_lake_kg": 0.0,
        }

        # Track agent receipts
        agent_receipts = state.setdefault("agent_receipts", {})
        for agent_id in compliant_agents:
            if agent_id not in agent_receipts:
                agent_receipts[agent_id] = 0.0
            agent_receipts[agent_id] += share_per_agent
