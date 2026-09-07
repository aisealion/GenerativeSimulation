# Round 10 Norm Specification

**Policy**: Each fisher may take up to **12% of the lake’s current stock per trip**, capped at **15 kg**, and may not cumulatively take more than **30% of the lake’s stock in a calendar month**.

**Operationalization**:
- Before each departure, the fisher estimates the lake’s current stock (available as `context.stock_before`). The per‑trip limit is `min(0.12 * current_stock, 15.0)` kilograms.
- The fisher records the haul weight; the norm trims any excess to the per‑trip limit.
- A monthly communal ledger tracks total kilograms taken (`monthly_total`). The monthly cap is `0.30 * month_start_stock` where `month_start_stock` is the lake stock at the beginning of the calendar month (approximated here as `context.stock_before` for the first round of the month).
- If a fisher’s catch would cause `monthly_total` to exceed the monthly cap, the excess is removed from that fisher’s kept kilograms and a violation is recorded with sanction `monthly_limit_exceeded`.
- The remaining kept kilograms are returned to the fisher.
- No additional reserve or voting logic is implemented in this norm; those mechanisms are handled elsewhere in the simulation.
