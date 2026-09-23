# Round 3 Spec

This is the spec for Round 3 of the institutional simulation, which describes the institutional arrangements for the fishery management system.

## Overview

In Round 3, a new council is introduced to oversee the fishery management system. The actions of fishers and the council are regulated by a series of rules and procedures to ensure proper management of fish stocks, reporting, and compliance.

## Actions

This round defines the following actions that agents may take:

- `record_catch`: Fishers record total catch weight at the dock.
- `select_witness`: Fishers select a neutral community member to witness the hand-over of excess fish.
- `submit_log`: Fishers submit the log to the weekly council for approval.

## Roles

- `council`: Council composed of senior, trusted fishers elected by majority vote at weekly meeting, serving one season with vacancies filled by quick vote if member misses half a season.

## Rules  

### R1: Council reviews the log each week against the scale reading taken at the weekly meeting.

This rule ensures that when fishers submit logs to the council, the council reviews them against the recorded scale readings to verify accuracy. This helps maintain the integrity of the reporting system.

### R2: If the logged returned weight does not equal the excess, council confiscates missing portion and levies a fee.

This rule enforces that when reported weights do not match scale readings, the council is authorized to confiscate any remaining portion and impose a financial penalty.

### R3: Council conducts monthly random spot-checks to verify returned amounts.

This rule mandates that the council conducts random monthly spot-checks to verify that reported fish returns match actual quantities.

### R4: If a fisher refuses to deliver missing fish, council confiscates 100% and records it in communal inventory.

This rule ensures that when a fisher refuses to deliver fish that was found missing, the council confiscates 100% of that portion and records it in the communal inventory.

## Objects  

### R5: Refrigerated communal bin for storing fees and confiscated fish, used for community events or sold at market.

This creates a communal storage bin for fees and confiscated fish that can be used for community events or sold at market.