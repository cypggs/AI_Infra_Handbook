import pytest

from feature_store_mini.entity import Entity


def test_entity_fields():
    e = Entity("user", "user_id", "app user")
    assert e.name == "user"
    assert e.join_key == "user_id"
    assert e.description == "app user"


def test_entity_description_default():
    e = Entity("item", "item_id")
    assert e.description == ""


def test_entity_is_frozen():
    e = Entity("user", "user_id")
    with pytest.raises(AttributeError):
        e.name = "other"


def test_entity_hashable_usable_as_dict_key():
    e = Entity("user", "user_id")
    d = {e: 1}
    assert d[Entity("user", "user_id")] == 1


def test_entity_rejects_empty_fields():
    with pytest.raises(ValueError):
        Entity("", "user_id")
    with pytest.raises(ValueError):
        Entity("user", "")


def test_key_of_extracts_join_key():
    e = Entity("user", "user_id")
    assert e.key_of({"user_id": 42, "x": 1}) == "42"


def test_key_of_missing_join_key():
    e = Entity("user", "user_id")
    with pytest.raises(KeyError):
        e.key_of({"x": 1})
