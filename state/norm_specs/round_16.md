# Norm Specification – Round 16

**Policy**
Each fisher may keep up to 5 kg per trip; any excess is deposited into a communal pool. At the end of each month the pool distributes 3 kg to fishers whose reserve is below 20 kg, starting with the lowest reserves, then splits any remaining fish equally among all fishers. Fishers with reserves below 10 kg must deposit an additional 1 kg into the pool before their next trip, or a 1 kg penalty is automatically deducted on the following catch.

**Operationalization**
1. After each trip the fisher records the amount kept (≤ 5 kg) and any excess, which is added to the communal pool ledger.
2. The ledger keeper (dock clerk or designated record‑keeper) checks each fisher’s reserve_kg. If reserve_kg < 10 kg, the keeper requires the fisher to deposit an extra 1 kg into the pool before the next trip.
3. If the extra deposit is missing, the keeper sets a `penalty_due` flag for that fisher.
4. On the next trip, before applying the 5 kg keep limit, the system automatically subtracts 1 kg from the fisher’s allowed catch if `penalty_due` is true, then clears the flag.
5. The fisher’s reserve_kg is updated by adding the kept catch and any allocation from the pool, and subtracting any penalty applied on the next catch.
6. The communal_pool_kg variable tracks the total kilograms in the shared container; it is increased by any excess from each trip and decreased by allocations during the monthly meeting.
7. At month‑end the ledger tallies communal_pool_kg and:
   a) allocates 3 kg to each qualifying fisher (reserve_kg < 20 kg) in order of lowest reserves until the pool is exhausted, reducing communal_pool_kg accordingly;
   b) if any fish remain, splits the remainder equally among all fishers and adds the share to each reserve_kg, bringing communal_pool_kg to zero.
