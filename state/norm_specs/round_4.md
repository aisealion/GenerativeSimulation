# Round 4 Norm Specification

This document defines the institutional design for round 4 of the simulation. It outlines the normative rules that will guide agent behavior, the ecological and social objectives, and the configuration parameters required for each norm. The specification must be at least 200 characters to satisfy validation checks.

## Norms
- **DynamicCapNorm**: Dynamically adjusts individual harvest caps based on recent stock trends and community performance.
- **CommunityPenaltyNorm**: Applies penalties to agents collectively when the total catch exceeds a community target, encouraging cooperation.
- **ReserveBoostNorm**: Provides a temporary boost to the communal reserve when stock falls below a critical threshold, helping recovery.

## Parameters
- `cap_adjust_factor`: float, default 0.04 – adjustment factor for individual caps per unit of stock deviation.
- `penalty_rate`: float, default 0.12 – proportion of excess catch penalized during community penalties.
- `boost_threshold`: float, default 110.0 – stock level below which reserve boosts are triggered.

These norms are referenced in `state/config.json` under the `norms` list and will be activated when the simulation reaches round 4.
