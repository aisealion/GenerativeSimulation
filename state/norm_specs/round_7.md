Policy: The community shall implement a sustainable harvesting limit that caps total fish extraction per round to 5% of the lake's current stock, ensuring long-term ecological balance.

Operationalization: At the start of each round, calculate 5% of the available stock (using the physics module's available_stock). The norm enforcement mechanism must prevent any agent's harvest action from causing the total harvested amount to exceed this cap. If the cap would be exceeded, the excess harvest is discarded and the agent receives a warning note. This rule supersedes individual agent quotas and must be applied before the stock regeneration step.

Rationale: Limiting total extraction preserves the lake's biomass, preventing collapse and promoting a stable fishery over many rounds.

Metrics: Verify that the sum of all agents' harvested kilograms each round does not exceed the computed 5% cap. Log any violations as norm violations.
