import pathlib

def test_norm_9_policy():
    """Round 9 norm‑implementer should have written a policy capping each trip to 45 kg.
    The norm.txt file is the authoritative source written by the simulation after the round.
    """
    norm_path = pathlib.Path(__file__).parents[2] / "norm.txt"
    text = norm_path.read_text()
    assert "45 kg per trip" in text, f"Expected policy to mention '45 kg per trip' in {norm_path}"
