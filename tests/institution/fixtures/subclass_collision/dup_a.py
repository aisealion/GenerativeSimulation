from tests.institution.fixtures.subclass_collision.base import FakeBase


class DupA(FakeBase):
    key_name = "dup"
