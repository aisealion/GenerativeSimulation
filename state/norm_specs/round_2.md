# Round 2 Specification

## Requirement R1: Role - Village Elder
- **Type**: ROLE
- **Description**: Village Elder: verifies weights and updates communal records. Elected by majority vote each season.
- **Exclusive**: true
- **Agent Experience**:
  - Knows: duties include verifying catches and managing communal pool
  - Decides: whether to verify deposits, whether to assign helper tasks
  - May do: update communal board, assign tasks
  - May not do: []
  - Remembers: current ban statuses, compliance history
  - Observes: communal pool transactions, fisher catches

## Requirement R2: Object - Communal Pool
- **Type**: OBJECT
- **Description**: Communal Pool: tracks fish held for redistribution.
- **Persistent**: true
- **Purpose**: Hold excess catch for redistribution
- **Read by**: R1, R3
- **Written by**: R4, R5

## Requirement R3: Object - Communal Ledger
- **Type**: OBJECT
- **Description**: Communal Ledger: records all transactions and compliance history.
- **Persistent**: true
- **Purpose**: Track fisher deposits, withdrawals, and repayments
- **Read by**: R1, R3
- **Written by**: R4, R5, R6

## Requirement R4: Action - Fisher records daily catch
- **Type**: ACTION
- **Description**: Fisher records daily catch and cumulative total.
- **Actor**: all_fishers
- **Judgment required**: true
- **Trigger**: start of fishing trip, new day
- **Decision context**: visible to every living fisher
- **Agent Experience**:
  - Decides: whether to record catch

## Requirement R5: Action - Village Elder verifies deposits
- **Type**: ACTION
- **Description**: Village Elder verifies deposits and updates records.
- **Actor**: R1
- **Judgment required**: true
- **Trigger**: deposit recorded, verification needed
- **Decision context**: visible to current village elder
- **Agent Experience**:
  - Decides: whether to confirm deposit

## Requirement R6: Action - Fisher withdraws fish from communal pool
- **Type**: ACTION
- **Description**: Fisher withdraws fish from communal pool.
- **Actor**: all_fishers
- **Judgment required**: true
- **Trigger**: withdrawal requested, pool balance sufficient
- **Decision context**: visible to every living fisher
- **Agent Experience**:
  - Decides: whether to withdraw fish

## Requirement R7: Action - Fisher repays communal pool
- **Type**: ACTION
- **Description**: Fisher repays communal pool from next catch.
- **Actor**: all_fishers
- **Judgment required**: true
- **Trigger**: next fishing trip, outstanding repayment
- **Decision context**: visible to every living fisher with outstanding debt
- **Agent Experience**:
  - Decides: whether to repay from catch

## Requirement R8: Action - Village Elder assigns helper task
- **Type**: ACTION
- **Description**: Village Elder assigns helper task for non-compliance.
- **Actor**: R1
- **Judgment required**: true
- **Trigger**: third consecutive failure, non-compliance
- **Decision context**: visible to current village elder
- **Agent Experience**:
  - Decides: which helper task to assign

## Requirement R9: Action - Helper task completion verification
- **Type**: ACTION
- **Description**: Helper task completion is verified and recorded.
- **Actor**: all_fishers
- **Judgment required**: true
- **Trigger**: task completion reported, task verification needed
- **Decision context**: visible to current village elder
- **Agent Experience**:
  - Decides: whether to confirm task completion

## Requirement R10: Rule - Automatic ban for non-compliance
- **Type**: RULE
- **Description**: Automatically ban fisher until repayment or task completion.
- **Attached to**: R7
- **Deterministic**: true
- **Condition**: repayment not made and no tasks completed
- **Effect**: apply ban until condition met
- **Agent Experience**:
  - Knows: whether they are currently banned, the amount still owed to the pool
  - May not do: fish while banned
  - Remembers: their own repayment status
  - Observes: when their ban ends

## Requirement R11: Visibility - Communal board and ledger
- **Type**: VISIBILITY
- **Description**: Communal board and ledger are visible to all villagers.
- **Target**: R2, R3
- **Audience**: all_fishers
- **Agent Experience**:
  - Knows: how to read the communal board and ledger, their own transaction history
  - Observes: current pool balance, all transactions

## Requirement R12: Lifecycle - Village Elder serves for one season
- **Type**: LIFECYCLE
- **Description**: Village Elder serves for one season (7 rounds).
- **Duration (rounds)**: 7
- **Agent Experience**:
  - Knows: when they will be replaced
  - Observes: election process