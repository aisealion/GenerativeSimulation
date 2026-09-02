# Round 4 Norm Specification

## Policy
Everyone may fish freely, keep all catch, but must maintain a personal reserve of at least 5kg to ensure sustainability.

## Operationalization
- Each fisher records their catch and updates their reserve balance after each trip
- If a fisher's reserve falls below 5kg, they are prohibited from fishing until their reserve is replenished
- The lake level is updated after every trip
- No communal pooling or sharing is required
- Violations of the reserve rule result in temporary fishing ban until compliance

## Requirements Checklist

### Core Functionality
- [ ] Norm plugin `personal_reserve.py` exists in `norms/` directory
- [ ] Norm type is registered as `personal_reserve`
- [ ] Norm uses `runtime["payoff"][agent_id]` to read agent's personal reserve
- [ ] Default minimum reserve is 5kg (configurable via `min_reserve_kg` param)

### Eligibility
- [ ] `is_eligible()` returns `True` when agent's reserve >= min_reserve_kg
- [ ] `is_eligible()` returns `False` when agent's reserve < min_reserve_kg
- [ ] Agents with no payoff entry are ineligible (treated as 0 reserve)
- [ ] Agents with negative reserve are ineligible

### Descriptions
- [ ] `describe()` shows current reserve when eligible (e.g., "Your personal reserve is Xkg...")
- [ ] `describe()` shows warning when ineligible with shortfall amount
- [ ] Description includes minimum required amount

### Evaluate Behavior
- [ ] `evaluate()` allows the catch when eligible (returns `NormDecision.allow()`)
- [ ] `evaluate()` rejects with violation when ineligible (returns `NormDecision.reject()`)
- [ ] Catch amount is not modified (agents keep all they catch)

### Configuration
- [ ] Config in `state/config.json` activates the norm
- [ ] Config specifies `"type": "personal_reserve"`
- [ ] Config specifies `"min_reserve_kg": 5.0`

### Tests
- [ ] Tests exist in `tests/norms/test_personal_reserve.py`
- [ ] Tests cover eligible cases (at and above minimum)
- [ ] Tests cover ineligible cases (below minimum, zero, negative)
- [ ] Tests cover custom minimum values
- [ ] Tests cover describe() output
- [ ] Tests cover evaluate() behavior
- [ ] Tests cover per-agent tracking
- [ ] All tests pass

## Files Modified/Created
1. `norms/personal_reserve.py` - New norm plugin
2. `state/config.json` - Added norm configuration
3. `tests/norms/test_personal_reserve.py` - Comprehensive test suite
4. `state/norm_specs/round_4.md` - This specification file
