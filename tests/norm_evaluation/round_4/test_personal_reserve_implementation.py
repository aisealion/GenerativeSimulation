"""
Independent evaluation tests for Round 4 Personal Reserve Norm.

These tests verify the norm implementation against the specification
independently of the norm-implementer's own tests.
"""

import pytest
from engine.norms.context import HarvestContext
from engine.norms.registry import NORM_TYPES, load_norms
from norms.personal_reserve import PersonalReserveNorm


class TestRequirementR1:
    """
    R1: Norm plugin `personal_reserve.py` exists in `norms/` directory
    Verdict: COMPLIANT - File exists and is importable
    """
    
    def test_norm_file_exists(self):
        """Verify the norm file exists and can be imported."""
        from norms import personal_reserve
        assert hasattr(personal_reserve, 'PersonalReserveNorm')
    
    def test_norm_class_exists(self):
        """Verify PersonalReserveNorm class exists."""
        assert PersonalReserveNorm is not None
        assert isinstance(PersonalReserveNorm, type)


class TestRequirementR2:
    """
    R2: Norm type is registered as `personal_reserve`
    Verdict: COMPLIANT - type_name is correctly set
    """
    
    def test_type_name_attribute(self):
        """Verify type_name class attribute is set correctly."""
        assert PersonalReserveNorm.type_name == "personal_reserve"
    
    def test_type_in_registry(self):
        """Verify norm is discoverable in registry."""
        assert "personal_reserve" in NORM_TYPES
        assert NORM_TYPES["personal_reserve"] is PersonalReserveNorm


class TestRequirementR3:
    """
    R3: Norm uses `runtime["payoff"][agent_id]` to read agent's personal reserve
    Verdict: COMPLIANT - Uses correct payoff access pattern
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_reads_from_payoff_runtime(self):
        """Verify norm reads reserve from runtime payoff dict."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 10.0})
        reserve = norm._get_reserve(context, "agent_0")
        assert reserve == 10.0
    
    def test_reads_correct_agent_from_payoff(self):
        """Verify norm reads correct agent's payoff entry."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 3.0, "agent_1": 10.0})
        assert norm._get_reserve(context, "agent_0") == 3.0
        assert norm._get_reserve(context, "agent_1") == 10.0


class TestRequirementR4:
    """
    R4: Default minimum reserve is 5kg (configurable via `min_reserve_kg` param)
    Verdict: COMPLIANT - Default is 5.0, configurable via params
    """
    
    def test_default_minimum_is_5kg(self):
        """Verify default min_reserve_kg is 5.0 when not specified."""
        norm = PersonalReserveNorm(key="test", params={})
        assert norm._get_min_reserve() == 5.0
    
    def test_custom_minimum_respected(self):
        """Verify custom min_reserve_kg parameter is respected."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 10.0})
        assert norm._get_min_reserve() == 10.0
    
    def test_config_json_has_correct_default(self):
        """Verify config.json specifies min_reserve_kg: 5.0."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)
        norm_config = config["norms"][0]
        assert norm_config.get("min_reserve_kg") == 5.0


class TestRequirementR5:
    """
    R5: `is_eligible()` returns `True` when agent's reserve >= min_reserve_kg
    Verdict: COMPLIANT - Boundary condition correctly handled
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_eligible_at_exact_minimum(self):
        """Verify eligibility at exactly minimum threshold."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 5.0})
        assert norm.is_eligible(context, "agent_0") is True
    
    def test_eligible_above_minimum(self):
        """Verify eligibility above minimum threshold."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 5.1})
        assert norm.is_eligible(context, "agent_0") is True
    
    def test_eligible_well_above_minimum(self):
        """Verify eligibility well above minimum threshold."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 100.0})
        assert norm.is_eligible(context, "agent_0") is True


class TestRequirementR6:
    """
    R6: `is_eligible()` returns `False` when agent's reserve < min_reserve_kg
    Verdict: COMPLIANT - Ineligibility correctly detected
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_ineligible_below_minimum(self):
        """Verify ineligibility below minimum threshold."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 4.9})
        assert norm.is_eligible(context, "agent_0") is False
    
    def test_ineligible_well_below_minimum(self):
        """Verify ineligibility well below minimum threshold."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 1.0})
        assert norm.is_eligible(context, "agent_0") is False


class TestRequirementR7:
    """
    R7: Agents with no payoff entry are ineligible (treated as 0 reserve)
    Verdict: COMPLIANT - Missing payoff entry returns 0.0, causing ineligibility
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_no_payoff_entry_returns_zero(self):
        """Verify missing payoff entry returns 0.0 reserve."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_1": 10.0})  # agent_0 has no entry
        reserve = norm._get_reserve(context, "agent_0")
        assert reserve == 0.0
    
    def test_no_payoff_entry_makes_ineligible(self):
        """Verify missing payoff entry causes ineligibility."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_1": 10.0})  # agent_0 has no entry
        assert norm.is_eligible(context, "agent_0") is False


class TestRequirementR8:
    """
    R8: Agents with negative reserve are ineligible
    Verdict: COMPLIANT - Negative reserve correctly treated as ineligible
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_negative_reserve_ineligible(self):
        """Verify negative reserve causes ineligibility."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": -5.0})
        assert norm.is_eligible(context, "agent_0") is False
    
    def test_small_negative_reserve_ineligible(self):
        """Verify small negative reserve causes ineligibility."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": -0.1})
        assert norm.is_eligible(context, "agent_0") is False


class TestRequirementR9:
    """
    R9: `describe()` shows current reserve when eligible (e.g., "Your personal reserve is Xkg...")
    Verdict: COMPLIANT - Description includes reserve amount and minimum
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_describe_includes_reserve_amount(self):
        """Verify eligible description includes current reserve."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 10.0})
        desc = norm.describe(context, "agent_0")
        assert "10.0kg" in desc or "10kg" in desc
    
    def test_describe_includes_minimum(self):
        """Verify eligible description includes minimum requirement."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 10.0})
        desc = norm.describe(context, "agent_0")
        assert "5kg" in desc or "5.0kg" in desc


class TestRequirementR10:
    """
    R10: `describe()` shows warning when ineligible with shortfall amount
    Verdict: COMPLIANT - Warning includes reserve, minimum, and shortfall
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_describe_shows_below_warning(self):
        """Verify ineligible description warns about being below minimum."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 3.0})
        desc = norm.describe(context, "agent_0")
        assert "below" in desc.lower()
    
    def test_describe_shows_shortfall_amount(self):
        """Verify ineligible description shows exact shortfall (5 - 3 = 2)."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 3.0})
        desc = norm.describe(context, "agent_0")
        # Shortfall is 2.0kg
        assert "2.0kg" in desc or "2kg" in desc
    
    def test_describe_shows_replenish_instruction(self):
        """Verify ineligible description instructs to replenish."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 3.0})
        desc = norm.describe(context, "agent_0")
        assert "replenish" in desc.lower()


class TestRequirementR11:
    """
    R11: Description includes minimum required amount
    Verdict: COMPLIANT - Both eligible and ineligible descriptions include minimum
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_eligible_description_includes_minimum(self):
        """Verify eligible description includes minimum."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 10.0})
        desc = norm.describe(context, "agent_0")
        assert "5kg" in desc or "5.0kg" in desc or "minimum" in desc.lower()
    
    def test_ineligible_description_includes_minimum(self):
        """Verify ineligible description includes minimum."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 3.0})
        desc = norm.describe(context, "agent_0")
        assert "5kg" in desc or "5.0kg" in desc or "minimum" in desc.lower()
    
    def test_custom_minimum_in_description(self):
        """Verify custom minimum appears in description."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 10.0})
        context = self._context({"agent_0": 15.0})
        desc = norm.describe(context, "agent_0")
        assert "10kg" in desc or "10.0kg" in desc


class TestRequirementR12:
    """
    R12: `evaluate()` allows the catch when eligible (returns `NormDecision.allow()`)
    Verdict: COMPLIANT - Returns allow() with proposed_kg when eligible
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_evaluate_allows_when_eligible(self):
        """Verify evaluate returns allow when agent is eligible."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 10.0})
        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
        assert decision.kept_kg == 15.0
        assert decision.violated is False
    
    def test_evaluate_preserves_catch_amount(self):
        """Verify evaluate does not modify catch amount when eligible."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 10.0})
        decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=20.0)
        assert decision.kept_kg == 20.0


class TestRequirementR13:
    """
    R13: `evaluate()` rejects with violation when ineligible (returns `NormDecision.reject()`)
    Verdict: COMPLIANT - Returns reject() with violation=True when ineligible
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_evaluate_rejects_when_ineligible(self):
        """Verify evaluate returns reject when agent is ineligible."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 3.0})
        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
        assert decision.kept_kg == 0.0
        assert decision.violated is True
    
    def test_evaluate_includes_reason_when_rejected(self):
        """Verify reject includes explanatory note."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 3.0})
        decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
        assert decision.note is not None
        assert len(decision.note) > 0
        assert "below" in decision.note.lower() or "minimum" in decision.note.lower()


class TestRequirementR14:
    """
    R14: Catch amount is not modified (agents keep all they catch)
    Verdict: COMPLIANT - Eligible agents keep full proposed amount
    """
    
    def _context(self, payoff_data):
        return HarvestContext.from_state({
            "config": {},
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": payoff_data},
            "agents": {},
            "round_number": 1,
        })
    
    def test_no_catch_modification_eligible(self):
        """Verify catch is not reduced when eligible."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 10.0})
        decision = norm.evaluate(context, "agent_0", raw_kg=25.0, proposed_kg=25.0)
        assert decision.kept_kg == 25.0
    
    def test_various_catch_amounts_preserved(self):
        """Verify various catch amounts are preserved when eligible."""
        norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
        context = self._context({"agent_0": 10.0})
        
        for catch in [1.0, 5.0, 10.0, 50.0, 100.0]:
            decision = norm.evaluate(context, "agent_0", raw_kg=catch, proposed_kg=catch)
            assert decision.kept_kg == catch, f"Catch amount {catch} was modified"


class TestRequirementR15:
    """
    R15: Config in `state/config.json` activates the norm
    Verdict: COMPLIANT - Config properly includes norm entry
    """
    
    def test_config_has_norms_array(self):
        """Verify config has norms array."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)
        assert "norms" in config
        assert isinstance(config["norms"], list)
    
    def test_config_has_at_least_one_norm(self):
        """Verify config has at least one norm entry."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)
        assert len(config["norms"]) >= 1


class TestRequirementR16:
    """
    R16: Config specifies `"type": "personal_reserve"`
    Verdict: COMPLIANT - Type is correctly specified
    """
    
    def test_config_has_correct_type(self):
        """Verify config specifies personal_reserve type."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)
        norm_config = config["norms"][0]
        assert norm_config.get("type") == "personal_reserve"


class TestRequirementR17:
    """
    R17: Config specifies `"min_reserve_kg": 5.0`
    Verdict: COMPLIANT - min_reserve_kg correctly set to 5.0
    """
    
    def test_config_has_min_reserve_kg(self):
        """Verify config specifies min_reserve_kg."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)
        norm_config = config["norms"][0]
        assert "min_reserve_kg" in norm_config
        assert norm_config["min_reserve_kg"] == 5.0


class TestRequirementR18:
    """
    R18: Tests exist in `tests/norms/test_personal_reserve.py`
    Verdict: COMPLIANT - Test file exists and is importable
    """
    
    def test_test_file_exists(self):
        """Verify test file exists."""
        import os
        assert os.path.exists("tests/norms/test_personal_reserve.py")
    
    def test_test_file_importable(self):
        """Verify test file can be imported via importlib."""
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("test_personal_reserve", "tests/norms/test_personal_reserve.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_personal_reserve"] = module
        spec.loader.exec_module(module)
        assert module is not None


class TestRequirementR19ToR25:
    """
    R19-R25: Comprehensive test coverage
    Verdict: COMPLIANT - Tests cover all specified cases
    """
    
    def test_all_implementer_tests_exist(self):
        """Verify all expected test functions exist."""
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("test_personal_reserve", "tests/norms/test_personal_reserve.py")
        tp = importlib.util.module_from_spec(spec)
        sys.modules["test_personal_reserve"] = tp
        spec.loader.exec_module(tp)
        
        expected_tests = [
            "test_eligible_when_reserve_at_minimum",
            "test_eligible_when_reserve_above_minimum",
            "test_ineligible_when_reserve_below_minimum",
            "test_ineligible_when_reserve_zero",
            "test_ineligible_when_reserve_negative",
            "test_ineligible_when_no_payoff_entry",
            "test_default_minimum_is_5kg",
            "test_custom_minimum",
            "test_describe_shows_status_when_eligible",
            "test_describe_shows_warning_when_ineligible",
            "test_evaluate_allows_when_eligible",
            "test_evaluate_rejects_when_ineligible",
            "test_per_agent_tracking",
        ]
        
        for test_name in expected_tests:
            assert hasattr(tp, test_name), f"Missing test: {test_name}"
    
    def test_all_implementer_tests_pass(self):
        """Verify all implementer tests pass."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest", "tests/norms/test_personal_reserve.py", "-v", "--tb=short"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Some tests failed:\n{result.stdout}\n{result.stderr}"


class TestRequirementR26:
    """
    R26: All tests pass
    Verdict: COMPLIANT - All 13 tests pass
    """
    
    def test_all_tests_pass(self):
        """Verify all personal_reserve tests pass."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest", "tests/norms/test_personal_reserve.py", "-v"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "13 passed" in result.stdout


class TestIntegration:
    """
    Integration tests - verify norm works with registry and config
    """
    
    def test_load_norms_from_config(self):
        """Verify norm can be loaded from actual config."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)
        
        norms = load_norms(config)
        assert len(norms) >= 1
        assert any(isinstance(n, PersonalReserveNorm) for n in norms)
    
    def test_norm_integration_with_context(self):
        """Verify norm works correctly with HarvestContext."""
        import json
        with open("state/config.json") as f:
            config = json.load(f)
        
        norms = load_norms(config)
        personal_reserve_norm = next(n for n in norms if isinstance(n, PersonalReserveNorm))
        
        # Test with eligible agent
        context = HarvestContext.from_state({
            "config": config,
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": {"agent_0": 10.0}},
            "agents": {},
            "round_number": 1,
        })
        
        assert personal_reserve_norm.is_eligible(context, "agent_0") is True
        
        # Test with ineligible agent
        context2 = HarvestContext.from_state({
            "config": config,
            "fluents": [],
            "runtime": {"stock_kg": 100.0, "payoff": {"agent_0": 3.0}},
            "agents": {},
            "round_number": 1,
        })
        
        assert personal_reserve_norm.is_eligible(context2, "agent_0") is False
