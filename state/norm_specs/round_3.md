# Round 3 Norm Specification

This document defines the institutional design for round 3 of the simulation. It outlines the normative rules that will guide agent behavior, the ecological and social objectives, and the configuration parameters required for each norm. The specification must be at least 200 characters to satisfy validation checks.

## Norms
- **DynamicIndividualCapNorm**: Adjusts each agent's harvest cap dynamically based on recent stock trends, encouraging adaptive sustainability.
- **WeeklyAuditNorm**: Conducts a weekly audit of total catches, applying penalties for deviations from community targets.
- **ReserveBoostNorm**: Allows a temporary increase in communal reserve contributions when stock falls below a critical threshold.

## Parameters
- `cap_adjustment_factor`: float, default 0.05 – incremental adjustment to individual caps per stock deviation unit.
- `audit_penalty_rate`: float, default 0.1 – proportion of excess catch penalized during weekly audits.
- `reserve_boost_threshold`: float, default 120.0 – stock level below which reserve boosts are triggered.

These norms are referenced in `state/config.json` under the `norms` list and will be activated when the simulation reaches round 3.
