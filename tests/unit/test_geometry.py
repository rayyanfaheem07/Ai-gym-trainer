import pytest

from ai.geometry.angles import calculate_angle_2d, calculate_angle_3d
from ai.geometry.metrics import calculate_symmetry_index


def test_calculate_angle_2d_right_angle():
    a = (0.0, 1.0)
    b = (0.0, 0.0)
    c = (1.0, 0.0)
    angle = calculate_angle_2d(a, b, c)
    assert pytest.approx(angle, 0.1) == 90.0


def test_calculate_angle_2d_straight_line():
    a = (0.0, 1.0)
    b = (0.0, 0.0)
    c = (0.0, -1.0)
    angle = calculate_angle_2d(a, b, c)
    assert pytest.approx(angle, 0.1) == 180.0


def test_calculate_angle_3d():
    a = (1.0, 0.0, 0.0)
    b = (0.0, 0.0, 0.0)
    c = (0.0, 1.0, 0.0)
    angle = calculate_angle_3d(a, b, c)
    assert pytest.approx(angle, 0.1) == 90.0


def test_symmetry_index():
    assert calculate_symmetry_index(100.0, 100.0) == 100.0
    assert calculate_symmetry_index(80.0, 100.0) < 100.0
