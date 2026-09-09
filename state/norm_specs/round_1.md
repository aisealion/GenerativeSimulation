# Round 1 Norm Specification

This document defines the institutional design for round 1 of the simulation. It includes the set of normative rules, their intended effects, and the parameters required for each norm. The specification must be at least 200 characters to pass validation.

## Norms
- **SustainabilityNorm**: Ensures that total stock does not fall below a safety threshold.
- **EquityNorm**: Distributes harvested resources proportionally among agents based on prior contributions.

## Parameters
- `stock_threshold`: float, default 150.0 – minimum permissible stock.
- `equity_factor`: float, default 0.1 – weighting for equitable distribution.

The above norms are referenced in `state/config.json` under the `norms` list and will be activated during the simulation.
