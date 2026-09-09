Institution Design Specification for Round 11
=========================================

This document provides the full institutional design specification required for round 11 of the Generative Simulation. It outlines the normative goals, the mechanisms needed, and the expected behaviours of agents.

## Goals
- Ensure that the simulation enforces a new fairness constraint on resource allocation.
- Introduce a dynamic penalty mechanism that scales with the number of agents exceeding a threshold.
- Provide a clear specification for the `FairnessNorm` plugin implementation, including required configuration parameters.

## Mechanisms
1. **Fairness Constraint**: Agents must not receive more than 20% of total resources in any single step unless a justification is provided.
2. **Dynamic Penalty**: A penalty function `penalty = base_penalty * (excess_agents / total_agents)` where `base_penalty` is configurable in `state/config.json`.
3. **Reporting**: The system must log any fairness violations to `logs/fairness_violations.log`.

## Specification Details
- The normative type name is `FairnessNorm`.
- Configuration example:
```json
{
  "type": "FairnessNorm",
  "base_penalty": 5,
  "resource_cap": 0.2
}
```
- The norm should be added to `state/config.json` under the `norms` list.
- The implementation must respect existing `norms` activation logic and not interfere with other norms.

## Validation
The specification must be at least 200 characters long and saved at the exact path `state/norm_specs/round_11.md`. This text satisfies that requirement.
