# Round 1 Institutional Specification

This document outlines the institutional design and rule implementations for Round 1 of the fishery simulation, based on the norm plan.

## Overview

This institutional framework implements governance structures for a local fishery community to manage fishing rights, enforce compliance, and ensure sustainable resource use through community-based management.

## Roles Implemented

### Fisher (fisher)
- Eligibility to act as a fisher in the community
- Participates in daily fishing activities and record-keeping

### Lake Guard (lake_guard)  
- Chosen by rotating draw from volunteers
- Responsible for checking compliance with catch limits
- Enforces fishing rights sanctions when needed

## Actions Implemented

### `register_catch`
- Villagers record fish caught in a shared ledger each fishing day
- Fishers record their daily catch in the shared ledger

### `sign_logbook`
- Villagers sign the logbook each fishing day  
- Fishers sign the logbook after recording catches

### `choose_guard`
- Lake guard is chosen by rotating draw from volunteers
- Community selects the next lake guard through a draw process

### `check_compliance` 
- Lake guard checks daily logbook entries for limit compliance
- Guard identifies fishers who exceed catch limits

### `harvest`
- Core fishing activity that is regulated by the compliance system

## Objects Implemented

### Shared Ledger (`shared_ledger`)
- Shared ledger for recording fish catches
- Maintains daily catch records and weekly summaries
- Tracks community service assignments

## Rules Implemented

### `fishing_rights_sanction` (Requirement R11)
- Fishers who fail to return excess fish lose fishing rights for one week
- Community service is required before fishing rights are restored
- Enforcement mechanism tracks sanctions and prevents fishing during ban period

### `weekly_tally` (Requirement R7) 
- Ledger is tallied weekly to identify the fisher with the lowest catch
- Lowest catch fisher is identified for community service assignment

## Enforcement Mechanisms

The system enforces:
1. Compliance through daily logging and check-ins
2. Sanctions for non-compliance (one-week fishing ban + community service) 
3. Weekly identification of lowest catch fisher
4. Community service assignment for lowest catch fisher
5. Random draw resolution for tied service assignments

## Community Processes

### Guard Schedule and Protocol (Requirement R12)
- Community publishes guard schedule and enforcement protocol monthly
- Ensures transparency in guard rotation and enforcement procedures

### Pledge Signing (Requirement R13)
- All fishers sign a pledge to abstain from fishing first two weeks of March
- Demonstrates commitment to community conservation measures

## Norm Compliance

This institution implements the norm requirements for sustainable fishery management, including:
- Daily logging and tracking of catches
- Weekly compliance checks  
- Enforcement through sanctions and community service
- Transparent governance with rotating guard responsibility