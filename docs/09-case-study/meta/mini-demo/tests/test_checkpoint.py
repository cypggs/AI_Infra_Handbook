"""Tests for the checkpoint boundary helper."""

import pytest

from meta_mini.checkpoint import is_checkpoint_step


def test_multiples_are_checkpoint_steps():
    assert is_checkpoint_step(100, 100) is True
    assert is_checkpoint_step(200, 100) is True
    assert is_checkpoint_step(1000, 200) is True


def test_non_multiples_are_not():
    assert is_checkpoint_step(99, 100) is False
    assert is_checkpoint_step(150, 200) is False


def test_every_step_when_interval_one():
    assert is_checkpoint_step(1, 1) is True
    assert is_checkpoint_step(7, 1) is True


def test_invalid_interval():
    with pytest.raises(ValueError):
        is_checkpoint_step(100, 0)
