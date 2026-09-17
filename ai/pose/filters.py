import math
import time

import numpy as np


class LowPassFilter:
    """Standard exponential smoothing low-pass filter."""

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.hat_x_prev: np.ndarray | None = None

    def filter(self, x: np.ndarray, alpha: float | None = None) -> np.ndarray:
        if alpha is None:
            alpha = self.alpha
        if self.hat_x_prev is None:
            self.hat_x_prev = x.copy()
            return x
        hat_x = alpha * x + (1.0 - alpha) * self.hat_x_prev
        self.hat_x_prev = hat_x
        return hat_x

    def reset(self):
        self.hat_x_prev = None


class OneEuroFilter:
    """
    One Euro Filter for real-time jitter reduction in pose estimation without lag.
    Reference: Casiez et al., CHI 2012.
    """

    def __init__(
        self,
        freq: float = 30.0,
        mincutoff: float = 1.0,
        beta: float = 0.007,
        dcutoff: float = 1.0,
    ):
        self.freq = freq
        self.mincutoff = mincutoff
        self.beta = beta
        self.dcutoff = dcutoff
        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.last_time: float | None = None

    def _alpha(self, cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x: np.ndarray, timestamp: float | None = None) -> np.ndarray:
        if timestamp is None:
            timestamp = time.time()

        if self.last_time is None:
            self.last_time = timestamp
            return x

        dt = max(1e-4, timestamp - self.last_time)
        self.last_time = timestamp

        # Estimate derivative
        if self.x_filter.hat_x_prev is None:
            dx = np.zeros_like(x)
        else:
            dx = (x - self.x_filter.hat_x_prev) / dt

        edx = self.dx_filter.filter(dx, self._alpha(self.dcutoff, dt))
        cutoff = self.mincutoff + self.beta * np.abs(edx)
        return self.x_filter.filter(x, self._alpha(cutoff, dt))

    def reset(self):
        self.x_filter.reset()
        self.dx_filter.reset()
        self.last_time = None
