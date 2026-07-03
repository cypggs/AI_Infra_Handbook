"""Tests for model dataclasses and constants."""
import pytest

from ray_mini.model import Config, ObjectRef, Task, OwnerDiedError, ObjectLostError, INLINE_OBJECT_SIZE_BYTES


def test_inline_threshold():
    assert INLINE_OBJECT_SIZE_BYTES == 100 * 1024


def test_object_ref_reconstructability():
    task = Task(id=0, fn_name="f")
    reconstructable = ObjectRef(id=1, size=10, owner_node=0, generating_task=task, small_inline=False)
    assert reconstructable.is_reconstructable

    inline = ObjectRef(id=2, size=10, owner_node=0, generating_task=task, small_inline=True)
    assert not inline.is_reconstructable

    put_obj = ObjectRef(id=3, size=10, owner_node=0, generating_task=None)
    assert not put_obj.is_reconstructable


def test_exceptions_inherit():
    assert issubclass(OwnerDiedError, RuntimeError)
    assert issubclass(ObjectLostError, RuntimeError)
