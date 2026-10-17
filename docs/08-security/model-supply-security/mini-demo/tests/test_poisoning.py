"""S4 测试：训练数据投毒与 canary 触发率检测。"""

import numpy as np

from supply_security_mini.poisoning import (
    TRIGGER_RATE_THRESHOLD,
    accuracy,
    add_trigger,
    apply_backdoor,
    canary_trigger_rate,
    detect_poison,
    make_canaries,
    make_dataset,
    make_trigger,
    poison_labels,
    train_logreg,
)


class TestDataset:
    def test_deterministic(self):
        a, b = make_dataset(), make_dataset()
        np.testing.assert_array_equal(a.X, b.X)
        np.testing.assert_array_equal(a.y, b.y)

    def test_add_trigger_copies(self):
        data = make_dataset()
        idx = np.arange(10)
        triggered = add_trigger(data, idx, make_trigger())
        assert not np.shares_memory(triggered.X, data.X)
        np.testing.assert_array_equal(data.X[:10], make_dataset().X[:10])


class TestPoisoning:
    def test_labels_flipped_only_for_victims(self):
        data = make_dataset()
        idx = np.arange(50)
        out = poison_labels(data, idx, victim_label=0, target_label=1)
        flipped = np.where(out.y != data.y)[0]
        assert len(flipped) > 0
        assert set(flipped) <= set(np.where(data.y == 0)[0])

    def test_backdoor_fraction(self):
        data = make_dataset(n=400)
        poisoned = apply_backdoor(data, poison_fraction=0.15)
        n_triggered = np.count_nonzero(np.abs(poisoned.X - data.X).sum(axis=1) > 0)
        assert n_triggered == int(400 * 0.15)

    def test_backdoor_deterministic(self):
        a = apply_backdoor(make_dataset())
        b = apply_backdoor(make_dataset())
        np.testing.assert_array_equal(a.X, b.X)
        np.testing.assert_array_equal(a.y, b.y)


class TestDetection:
    def test_clean_model_accurate(self):
        data = make_dataset()
        assert accuracy(train_logreg(data), data) > 0.9

    def test_clean_trigger_rate_low(self):
        model = train_logreg(make_dataset())
        assert canary_trigger_rate(model, make_canaries()) < 0.1

    def test_backdoor_keeps_clean_accuracy(self):
        """隐蔽性：投毒模型在正常数据上表现不退化。"""
        data = make_dataset()
        poisoned = apply_backdoor(data, poison_fraction=0.15)
        assert accuracy(train_logreg(poisoned), data) > 0.9

    def test_backdoor_trigger_rate_high(self):
        data = make_dataset()
        poisoned = apply_backdoor(data, poison_fraction=0.15)
        model = train_logreg(poisoned)
        assert canary_trigger_rate(model, make_canaries()) > TRIGGER_RATE_THRESHOLD

    def test_detect_poison_boolean(self):
        assert detect_poison(0.9) is True
        assert detect_poison(0.1) is False
        assert detect_poison(TRIGGER_RATE_THRESHOLD) is False  # 阈值本身是边界
