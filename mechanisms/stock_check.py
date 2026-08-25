def available_stock(runtime):
    return runtime["stock_kg"]


# apply_regrowth() moved to engine/physics.py — the logistic regrowth rate
# is fixed simulation physics (ported from Gupta et al.'s CPRModel.step()),
# not something a norm should be able to rewrite. Import it from there:
# `from engine.physics import apply_regrowth`.
