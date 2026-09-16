# Round 1 Institutional Design Specification

## Overview
Implemented the policy:
* Fisher records name, date, expected take before departing.
* Fisher logs actual catch on return.
* If catch >15 kg per trip, excess is returned to communal **reserve** and recorded in the **ledger**.
* If weekly total >30 kg, excess is similarly returned.
* A single failure to report or breach triggers a **5 kg penalty** deposited to the reserve and logged.
* The **keeper** role rotates weekly, enforces limits, records penalties, and posts ledger entries.
* Repeated violations (two within 30 days) cause a forfeited free trip, logged in the ledger.

## New Institutional Objects
* **reserve** – type `reserve.json`, holds a `balance` field (float, default 0). Allows deposits by all agents, no withdrawals.
* **ledger** – type `ledger.json`, holds an `entries` list. Supports `append` and `read` for all agents.

## Object Instances
```json
[
  {"id": "reserve", "type": "reserve"},
  {"id": "ledger", "type": "ledger"}
]
```

## New Role
* **keeper** – exclusive weekly role, description *"weekly keeper for enforcing limits"*. Assigned by `KeeperAssignmentRule`.

## New Rules (Level 3) attached to `harvest`
| Rule File | type_name | Purpose |
|-----------|-----------|---------|
| `actions/rules/harvest/excess_return_rule.py` | `excess_return_rule` | Handles per‑trip (>15 kg) and weekly (>30 kg) excess returns, updates reserve and ledger, tracks weekly totals and violation rounds. |
| `actions/rules/harvest/penalty_rule.py` | `penalty_rule` | On any breach or failure to report, deposits a 5 kg penalty to reserve and logs it. |
| `actions/rules/harvest/keeper_assignment_rule.py` | `keeper_assignment_rule` | Rotates the exclusive `keeper` role weekly and records the assignment. |
| `actions/rules/harvest/repeated_violation_rule.py` | `repeated_violation_rule` | Detects two violations within 30 days and logs a forfeited free‑trip entry in the ledger. |

## Configuration
Added the rules to `state/config.json` under `rules.harvest` so they are active each round.

## Prompts / Role Directives
Created `prompts/role_directives/keeper.md` with keeper perspective text.

## Verification
* All Python files compile (`python3 -m py_compile $(git ls-files "*.py")`).
* New norm‑check tests under `tests/norm_checks/` verify:
  * Ledger and reserve updates on excess returns.
  * Penalty deposits.
  * Keeper role rotation and directive existence.
  * Repeated‑violation forfeiture logging.
* All regression tests pass.

This file documents the full institutional change for round 1.
