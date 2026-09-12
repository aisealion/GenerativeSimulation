import pytest

import norms as real_norms_package
import objects.handlers as real_object_handlers_package
from engine.norms.base import Norm
from engine.institution.registry import discover_subclasses, discover_handlers
from tests.institution.fixtures.subclass_ok.base import FakeBase as OkBase
from tests.institution.fixtures.subclass_collision.base import FakeBase as CollisionBase
import tests.institution.fixtures.subclass_ok as subclass_ok_pkg
import tests.institution.fixtures.subclass_collision as subclass_collision_pkg
import tests.institution.fixtures.handlers_ok as handlers_ok_pkg
import tests.institution.fixtures.handlers_missing_run as handlers_missing_run_pkg


def test_discover_subclasses_on_a_real_ships_empty_package():
    """norms/ ships with zero plugins by design (see norms/README.md) —
    discovery against a real, currently-empty package must return {},
    never raise."""
    assert discover_subclasses(real_norms_package, Norm, "type_name") == {}


def test_discover_handlers_on_a_real_ships_empty_package():
    """objects/handlers/ ships empty for the same reason norms/ does."""
    assert discover_handlers(real_object_handlers_package) == {}


def test_discover_subclasses_finds_every_matching_subclass():
    found = discover_subclasses(subclass_ok_pkg, OkBase, "key_name")
    assert set(found) == {"one", "two"}
    assert found["one"].__name__ == "One"
    assert found["two"].__name__ == "Two"


def test_discover_subclasses_never_returns_the_base_class_itself():
    found = discover_subclasses(subclass_ok_pkg, OkBase, "key_name")
    assert OkBase not in found.values()


def test_discover_subclasses_raises_on_key_collision():
    with pytest.raises(ValueError, match="already registered"):
        discover_subclasses(subclass_collision_pkg, CollisionBase, "key_name")


def test_discover_handlers_finds_every_run_function():
    found = discover_handlers(handlers_ok_pkg)
    assert set(found) == {"handler_one", "handler_two"}
    assert found["handler_one"](None) == "ran-one"
    assert found["handler_two"](None) == "ran-two"


def test_discover_handlers_raises_on_a_module_missing_run():
    with pytest.raises(ValueError, match="no callable"):
        discover_handlers(handlers_missing_run_pkg)
