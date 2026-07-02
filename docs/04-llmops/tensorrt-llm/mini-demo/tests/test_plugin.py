"""Tests for the plugin registry and mock plugins."""
import numpy as np

from tensorrt_llm_mini.plugin import GELUPlugin, LookupPlugin, PluginRegistry


def test_plugin_registry_lists_plugins():
    assert "GELUPlugin" in PluginRegistry.list_plugins()
    assert "LookupPlugin" in PluginRegistry.list_plugins()


def test_gelu_plugin_forward():
    plugin = GELUPlugin()
    x = np.array([-1.0, 0.0, 1.0], dtype=np.float32)
    out = plugin.forward([x])
    assert len(out) == 1
    assert out[0].shape == x.shape
    # GELU(0) should be approximately 0.
    assert np.isclose(out[0][1], 0.0, atol=1e-5)


def test_lookup_plugin_forward():
    plugin = LookupPlugin()
    token_ids = np.array([[0, 2, 1]], dtype=np.int64)
    table = np.arange(12, dtype=np.float32).reshape(4, 3)
    out = plugin.forward([token_ids, table])
    assert len(out) == 1
    assert out[0].shape == (1, 3, 3)
    # row 0 = [0,1,2], row 2 = [6,7,8], row 1 = [3,4,5]
    expected = np.array([[[0, 1, 2], [6, 7, 8], [3, 4, 5]]], dtype=np.float32)
    np.testing.assert_array_equal(out[0], expected)
