from google_mini.topology import Torus3D


def test_size_is_product_of_dims():
    assert Torus3D((4, 4, 4)).size == 64
    assert Torus3D((2, 3, 5)).size == 30


def test_neighbors_are_six_with_wraparound():
    t = Torus3D((4, 4, 4))
    nbrs = t.neighbors(0, 0, 0)
    assert len(nbrs) == 6
    # 角节点 (0,0,0) 的 +x 邻居是 1，-x 邻居因环绕而是 3（kx-1）
    assert (1, 0, 0) in nbrs
    assert (3, 0, 0) in nbrs
    assert (0, 3, 0) in nbrs
    assert (0, 0, 3) in nbrs


def test_index_xyz_roundtrip():
    t = Torus3D((3, 4, 5))
    for x in range(3):
        for y in range(4):
            for z in range(5):
                idx = t.to_index(x, y, z)
                assert t.to_xyz(idx) == (x, y, z)


def test_fail_heal_healthy_count():
    t = Torus3D((4, 4, 4))
    assert t.healthy_count() == 64
    t.fail(7)
    t.fail(10)
    assert t.healthy_count() == 62
    assert t.is_failed(7) and not t.is_failed(8)
    t.heal(7)
    assert t.healthy_count() == 63
    assert not t.is_failed(7)
