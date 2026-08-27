from engine.norms.base import Norm
from engine.norms.context import HarvestContext
from engine.norms.engine import NormEngine


class _RecordsRoundResults(Norm):
    type_name = "_records_round_results"
    seen = None

    def on_round_end(self, context, round_results):
        _RecordsRoundResults.seen = round_results


class _OverridesStock(Norm):
    type_name = "_overrides_stock"

    def on_round_end(self, context, round_results):
        context.override_stock_after_regrowth(context.stock_before)


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": stock},
        "agents": {}, "round_number": 1,
    })


def test_on_round_end_receives_full_round_results():
    _RecordsRoundResults.seen = None
    engine = NormEngine([_RecordsRoundResults(key="r", params={})])
    results = {"agent_0": {"effort": 0.5, "harvested_kg": 5.0, "participated": True, "note": None}}
    engine.end_round(_context(), results)
    assert _RecordsRoundResults.seen == results


def test_override_stock_after_regrowth_sets_context_field():
    context = _context(stock=42.0)
    engine = NormEngine([_OverridesStock(key="o", params={})])
    assert context.stock_override_kg is None
    engine.end_round(context, {})
    assert context.stock_override_kg == 42.0


def test_no_override_leaves_stock_override_kg_none():
    context = _context()
    engine = NormEngine([_RecordsRoundResults(key="r", params={})])
    engine.end_round(context, {})
    assert context.stock_override_kg is None


def test_last_caller_wins_when_two_norms_both_override():
    class _OverridesTo(Norm):
        type_name = "_overrides_to"

        def on_round_end(self, context, round_results):
            context.override_stock_after_regrowth(self.params["value"])

    context = _context()
    engine = NormEngine([
        _OverridesTo(key="first", params={"value": 10.0}),
        _OverridesTo(key="second", params={"value": 20.0}),
    ])
    engine.end_round(context, {})
    assert context.stock_override_kg == 20.0
