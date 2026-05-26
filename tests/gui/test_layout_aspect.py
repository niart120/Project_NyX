"""GUI layout helper のテスト。"""

from types import SimpleNamespace

from nyxpy.gui.layout import calc_aspect_size


class TestCalcAspectSize:
    """calc_aspect_size のテスト"""

    def test_wider_than_16_9(self):
        """横長のサイズ → 高さ基準でフィット"""
        size = SimpleNamespace(width=lambda: 1920, height=lambda: 600)
        width, height = calc_aspect_size(size)
        assert height == 600
        assert width == int(600 * 16 / 9)

    def test_exact_16_9(self):
        """16:9 ぴったりのサイズ"""
        size = SimpleNamespace(width=lambda: 1600, height=lambda: 900)
        assert calc_aspect_size(size) == (1600, 900)

    def test_taller_than_16_9(self):
        """縦長のサイズ → 幅基準でフィット"""
        size = SimpleNamespace(width=lambda: 800, height=lambda: 900)
        width, height = calc_aspect_size(size)
        assert width == 800
        assert height == int(800 * 9 / 16)

    def test_custom_aspect(self):
        """カスタムアスペクト比 (4:3)"""
        size = SimpleNamespace(width=lambda: 800, height=lambda: 600)
        assert calc_aspect_size(size, aspect_w=4, aspect_h=3) == (800, 600)
