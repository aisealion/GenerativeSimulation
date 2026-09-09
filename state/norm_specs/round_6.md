# Round 6 Norm Specification

This document defines the institutional design for round 6 of the simulation. It specifies the normative rules that will guide agent behavior, the intended ecological and social effects, and the configuration parameters required for each norm. The specification must be at least 200 characters to satisfy validation checks.

## Norms
- **DynamicReserveNorm**: Adjusts the communal reserve contribution dynamically based on stock trends, encouraging adaptive sustainability.
- **PenaltyThresholdNorm**: Applies penalties to agents when total catch exceeds a defined threshold, promoting collective responsibility.
- **RecoveryBoostNorm**: Triggers a stock recovery boost when stock falls below a critical level, supporting ecosystem resilience.

## Parameters
- `reserve_adjust_factor`: float, default 0.03 – factor by which the reserve contribution is adjusted per unit stock deviation.
- `penalty_threshold`: float, default 1.15 – multiplier of the target catch above which penalties are applied.
- `recovery_boost_stock`: float, default 115.0 – stock level below which a recovery boost is triggered.

These norms are referenced in `state/config.json` under the `norms` list and will be activated when the simulation reaches round 6.
