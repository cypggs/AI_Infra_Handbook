"""Tests for the SDC validation helper."""

from meta_mini.sdc import is_validation_step


def test_disabled_never_validates():
    for step in (1, 50, 100, 999):
        assert is_validation_step(step, 0) is False


def test_multiples_validate():
    assert is_validation_step(100, 100) is True
    assert is_validation_step(50, 50) is True
    assert is_validation_step(99, 100) is False


def test_more_frequent_than_checkpoint():
    # validation every 50, checkpoint every 100 -> validation catches SDC first
    assert is_validation_step(50, 50) is True
    assert is_validation_step(100, 50) is True
