# Round 2 Norm Specification

This document defines the institutional design for round 2 of the simulation. It specifies the normative rules that will govern agent behavior, the intended ecological and social effects, and the configuration parameters required for each norm. The specification must be at least 200 characters to satisfy validation checks.

## Norms
- **ReserveNorm**: Caps the amount each agent may harvest based on a shared communal reserve, ensuring long‑term sustainability.
- **BanNorm**: Temporarily bans agents who exceed their harvest quota, promoting adherence to the reserve limits.
- **ReplenishNorm**: Triggers a lake‑stock replenishment event when total catch exceeds a high percentage of the current stock.

## Parameters
- `reserve_cap_ratio`: float, default 0.2 – maximum proportion of the communal reserve an individual agent may draw per round.
- `ban_duration_rounds`: int, default 2 – number of rounds an agent remains banned after a violation.
- `replenish_threshold`: float, default 0.75 – fraction of current stock harvested that triggers a replenishment.

These norms are referenced in `state/config.json` under the `norms` list and will be activated when the simulation reaches round 2.
