# Round 19 Norm Specification

**Policy**
- Each fisher may take up to **2 kg** per trip.
- The fisher must **keep at least 1 kg** for personal consumption.
- The **community portion** of the month’s harvest may not exceed **30 % of the lake’s stock at the start of the month**, with an absolute cap of **3 kg**.

**Operationalization**
1. **Trip‑level accounting**
   - The recorder logs a **personal quota of 1 kg** for the fisher.
   - The remaining catch (up to 1 kg) is recorded as the **community portion** for that trip.
2. **Monthly aggregation**
   - The recorder sums all community portions for the month.
   - If the summed community portion exceeds the **30 % stock cap** *or* the **3 kg absolute cap** (whichever is lower), the excess is **rejected** and not added to the community pool.
   - If the 30 % stock cap is **less than 1 kg**, the community portion for each trip is limited to that remaining amount, while the fisher still keeps the full 1 kg personal quota.
3. **Trip‑limit enforcement**
   - If a fisher catches **more than 2 kg** on a single trip, the excess above 2 kg is **automatically added to the community pool** and the fisher **forfeits their personal quota** for that trip.
4. **Violations & sanctions**
   - Violating the **per‑trip 2 kg limit** or exceeding the **monthly community cap** triggers a **one‑month fishing ban** recorded in the **ban ledger**.
5. **Recorder role**
   - The recorder role **rotates monthly** in alphabetical order.
   - The **current recorder** for this round is **Rina**.
   - All fishers must consult the **ban ledger** at the monthly opening meeting before any trip.
6. **Community pool state**
   - The community pool is stored in the simulation’s state variable **`community_pool`** and is updated each month by the recorder based on recorded excess catch.

**Implementation Notes**
- The norm should be added to `norms/` as a subclass of `engine.norms.base.Norm` with `type_name = "round_19"`.
- Use `HarvestContext.norm_state` to persist the community pool (`community_pool_kg`).
- Use `HarvestContext.round_scratch` to track per‑fisher monthly community contributions.
- Enforce per‑trip caps in `evaluate`, and apply monthly caps in `on_round_end`.
- Record sanctions via `NormDecision.violation` with a sanction identifier such as `"trip_limit_exceeded"` or `"monthly_cap_exceeded"`.
- Update the ban ledger (presumed to be part of the simulation state) when a sanction occurs.

---
*Prepared for round 19 of the simulation as dictated by `norm.txt`.*