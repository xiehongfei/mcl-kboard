"""Tests for force mapping and key/force alignment helpers."""

from __future__ import annotations

import math

from mcl_kboard.force import (
    AdaptiveHardScale,
    AdaptiveNoiseFloor,
    ForceRing,
    ForceSample,
    PeakGate,
    map_amplitude_to_velocity,
    velocity_to_gain,
    velocity_to_layer,
)


def test_map_amplitude_basic():
    v0 = map_amplitude_to_velocity(0.01, noise_floor=0.02, a_hard=0.3, gamma=1.0)
    assert v0 == 0.0
    v1 = map_amplitude_to_velocity(0.3, noise_floor=0.02, a_hard=0.3, gamma=1.0)
    assert math.isclose(v1, 1.0, rel_tol=1e-6)
    vmid = map_amplitude_to_velocity(0.16, noise_floor=0.02, a_hard=0.3, sensitivity=1.0, gamma=1.0)
    assert 0.4 < vmid < 0.6


def test_gamma_softens_curve():
    args = dict(noise_floor=0.0, a_hard=1.0, sensitivity=1.0)
    linear = map_amplitude_to_velocity(0.25, gamma=1.0, **args)
    soft = map_amplitude_to_velocity(0.25, gamma=0.5, **args)
    assert soft > linear


def test_velocity_layer_and_gain():
    assert velocity_to_layer(0.1) == "soft"
    assert velocity_to_layer(0.5) == "mid"
    assert velocity_to_layer(0.9) == "hard"
    g = velocity_to_gain(0.5, 0.2, 1.0)
    assert math.isclose(g, 0.6)


def test_force_ring_window():
    ring = ForceRing()
    ring.push(ForceSample(1.0, 0.1))
    ring.push(ForceSample(1.01, 0.4))
    ring.push(ForceSample(1.05, 0.2))
    assert ring.max_in_window(1.0, 0.03) == 0.4
    assert ring.max_in_window(1.04, 0.01) == 0.2


def test_force_ring_max_since_index():
    ring = ForceRing()
    ring.push(ForceSample(1.0, 0.9))
    start = len(ring)
    ring.push(ForceSample(1.01, 0.1))
    ring.push(ForceSample(1.02, 0.4))
    assert ring.max_since_index(start) == 0.4


def test_adaptive_noise_floor():
    nf = AdaptiveNoiseFloor(window=50, percentile=0.2, min_floor=0.01)
    for _ in range(40):
        nf.update(0.02)
    nf.update(0.5)
    assert 0.01 <= nf.floor < 0.1


def test_adaptive_hard_scale():
    h = AdaptiveHardScale(initial=0.1)
    for p in (0.05, 0.08, 0.2, 0.15, 0.18, 0.09, 0.22, 0.11):
        h.observe(p)
    assert 0.05 < h.a_hard < 0.5


def test_peak_gate_debounce():
    gate = PeakGate(min_spacing_s=0.05)
    assert gate.accept(0.0, 0.2, 0.05)
    assert not gate.accept(0.01, 0.21, 0.05)
    assert gate.accept(0.1, 0.3, 0.05)
