"""Unit tests for the pure peak analysis layer."""

import array
import math

import pytest

import fia_peak
from fia_constants import Reject

import synthetic_peak


def make_trace(height=0.30, t_peak=32.0, shape=0.35, duration=70.0, hz=20.0,
               baseline=0.0):
    """Preallocated (t_buf, a_buf, n) of a synthetic log-normal FIA peak."""
    n = int(duration*hz)
    t_buf = array.array('f', bytes(4*n))
    a_buf = array.array('f', bytes(4*n))
    for i in range(n):
        t = i/hz
        t_buf[i] = t
        a_buf[i] = synthetic_peak.peak(
                t, height=height, t_peak=t_peak, shape=shape, baseline=baseline)
    return t_buf, a_buf, n


def const_trace(value, duration=70.0, hz=20.0):
    n = int(duration*hz)
    t_buf = array.array('f', bytes(4*n))
    a_buf = array.array('f', bytes(4*n))
    for i in range(n):
        t_buf[i] = i/hz
        a_buf[i] = value
    return t_buf, a_buf, n


# ---------------------------------------------------------------- absorbance

def test_absorbance_known_values():
    # A tenth of the blank is exactly 1.0 absorbance units.
    assert fia_peak.absorbance(3000.0, 30000.0) == pytest.approx(1.0)
    assert fia_peak.absorbance(30000.0, 30000.0) == pytest.approx(0.0)
    assert fia_peak.absorbance(15000.0, 30000.0) == pytest.approx(
            math.log10(2.0))


def test_absorbance_clamps_at_zero():
    # Brighter than the blank would be negative absorbance; clamp, matching
    # Colorimeter.absorbance.
    assert fia_peak.absorbance(40000.0, 30000.0) == 0.0


def test_absorbance_undefined_cases():
    assert fia_peak.absorbance(0.0, 30000.0) is None
    assert fia_peak.absorbance(-5.0, 30000.0) is None
    assert fia_peak.absorbance(1000.0, 0.0) is None
    assert fia_peak.absorbance(None, 30000.0) is None
    assert fia_peak.absorbance(1000.0, None) is None


def test_absorbance_roundtrip_through_to_raw():
    raw = synthetic_peak.to_raw(0.25, 30000.0)
    assert fia_peak.absorbance(raw, 30000.0) == pytest.approx(0.25)


# ----------------------------------------------------------------- mean, rsd

def test_mean_and_rsd_on_constant_buffer():
    buf = array.array('f', [100.0]*50)
    assert fia_peak.mean(buf, 50) == pytest.approx(100.0)
    assert fia_peak.rsd(buf, 50) == pytest.approx(0.0)


def test_rsd_known_spread():
    # [2,4,4,4,5,5,7,9]: mean 5, sample sd 2.13809, rsd 0.427618
    buf = array.array('f', [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
    assert fia_peak.mean(buf, 8) == pytest.approx(5.0)
    assert fia_peak.rsd(buf, 8) == pytest.approx(0.4276, abs=1e-4)


def test_rsd_undefined_cases():
    buf = array.array('f', [1.0, 2.0])
    assert fia_peak.rsd(buf, 0) is None
    assert fia_peak.rsd(buf, 1) is None       # needs two samples
    zeros = array.array('f', [0.0, 0.0, 0.0])
    assert fia_peak.rsd(zeros, 3) is None     # mean is zero
    assert fia_peak.mean(buf, 0) is None


def test_rsd_ignores_entries_beyond_n():
    # A partially filled buffer must not drag zeros into the statistics.
    buf = array.array('f', bytes(4*100))
    for i in range(10):
        buf[i] = 500.0
    assert fia_peak.rsd(buf, 10) == pytest.approx(0.0)
    assert fia_peak.mean(buf, 10) == pytest.approx(500.0)


# ------------------------------------------------------------------ find_peak

def test_find_peak_locates_synthetic_maximum():
    t_buf, a_buf, n = make_trace(height=0.30, t_peak=32.0)
    idx, t_peak, height = fia_peak.find_peak(t_buf, a_buf, n)
    assert t_peak == pytest.approx(32.0, abs=0.05)   # within one sample period
    assert height == pytest.approx(0.30, rel=0.01)
    assert 0 < idx < n


def test_find_peak_empty_trace():
    t_buf, a_buf, _ = const_trace(0.0)
    assert fia_peak.find_peak(t_buf, a_buf, 0) == (None, None, None)


def test_find_peak_is_global_not_window_restricted():
    # A peak at 60 s must be found, not clipped to the window edge -- that is
    # what makes the window check able to reject it.
    t_buf, a_buf, n = make_trace(t_peak=60.0)
    _, t_peak, _ = fia_peak.find_peak(t_buf, a_buf, n)
    assert t_peak > 50.0


# ---------------------------------------------------------------------- trapz

def test_trapz_constant_trace_is_analytic():
    # A flat 0.1 AU trace over a 30 s window integrates to exactly 3.0.
    t_buf, a_buf, n = const_trace(0.1)
    assert fia_peak.trapz(t_buf, a_buf, n, 20.0, 50.0) == pytest.approx(3.0)


def test_trapz_boundary_interpolation_makes_area_phase_insensitive():
    # Same underlying signal sampled on two different phases must give the same
    # area, which is only true if the window edges are interpolated.
    def area_with_offset(offset):
        hz = 20.0
        n = 1400
        t_buf = array.array('f', bytes(4*n))
        a_buf = array.array('f', bytes(4*n))
        for i in range(n):
            t = offset + i/hz
            t_buf[i] = t
            a_buf[i] = 0.1
        return fia_peak.trapz(t_buf, a_buf, n, 20.0, 50.0)

    assert area_with_offset(0.0) == pytest.approx(3.0)
    assert area_with_offset(0.023) == pytest.approx(3.0)
    assert area_with_offset(0.047) == pytest.approx(3.0)


def test_trapz_ramp_is_analytic():
    # A ramp a=t integrated over [20,50] is (50^2-20^2)/2 = 1050.
    hz = 20.0
    n = 1400
    t_buf = array.array('f', bytes(4*n))
    a_buf = array.array('f', bytes(4*n))
    for i in range(n):
        t = i/hz
        t_buf[i] = t
        a_buf[i] = t
    assert fia_peak.trapz(t_buf, a_buf, n, 20.0, 50.0) == pytest.approx(
            1050.0, rel=1e-4)


def test_trapz_undefined_cases():
    t_buf, a_buf, n = const_trace(0.1, duration=10.0)
    assert fia_peak.trapz(t_buf, a_buf, 1, 20.0, 50.0) is None    # n < 2
    assert fia_peak.trapz(t_buf, a_buf, n, 50.0, 20.0) is None    # hi <= lo
    # Trace ends at 10 s, entirely before the window.
    assert fia_peak.trapz(t_buf, a_buf, n, 20.0, 50.0) is None


# -------------------------------------------------------------------- analyze

def test_analyze_accepts_in_window_peak():
    t_buf, a_buf, n = make_trace(height=0.30, t_peak=32.0)
    result = fia_peak.analyze(t_buf, a_buf, n, 20.0, 50.0)
    assert result.reject == Reject.NONE
    assert result.is_ok
    assert result.height == pytest.approx(0.30, rel=0.01)
    assert result.t_peak == pytest.approx(32.0, abs=0.05)
    assert result.area > 0.0
    assert result.ratio == pytest.approx(result.height/result.area)
    assert result.n_samples == n


def test_analyze_rejects_early_peak():
    t_buf, a_buf, n = make_trace(t_peak=10.0, shape=0.2)
    result = fia_peak.analyze(t_buf, a_buf, n, 20.0, 50.0)
    assert result.reject == Reject.WINDOW_EARLY
    assert not result.is_ok
    # Height is still populated for diagnostics.
    assert result.height > 0.0


def test_analyze_rejects_late_peak():
    t_buf, a_buf, n = make_trace(t_peak=60.0, shape=0.2)
    result = fia_peak.analyze(t_buf, a_buf, n, 20.0, 50.0)
    assert result.reject == Reject.WINDOW_LATE
    assert not result.is_ok
    assert result.height > 0.0


def test_analyze_flat_trace_has_no_peak():
    t_buf, a_buf, n = const_trace(0.0)
    result = fia_peak.analyze(t_buf, a_buf, n, 20.0, 50.0)
    assert result.reject == Reject.NO_PEAK
    assert not result.is_ok


def test_analyze_empty_trace_has_no_peak():
    t_buf, a_buf, _ = const_trace(0.0)
    result = fia_peak.analyze(t_buf, a_buf, 0, 20.0, 50.0)
    assert result.reject == Reject.NO_PEAK
    assert result.height is None
    assert result.area is None


def test_analyze_reuses_supplied_result_object():
    t_buf, a_buf, n = make_trace()
    holder = fia_peak.PeakResult()
    result = fia_peak.analyze(t_buf, a_buf, n, 20.0, 50.0, result=holder)
    assert result is holder


def test_health_ratio_moves_with_peak_shape():
    # Height/area is the pump-wear and membrane-fouling signal: a broader peak
    # at the same height has more area, so a lower ratio.
    _, _, _ = make_trace()
    sharp = fia_peak.analyze(*make_trace(shape=0.25), t_lo=20.0, t_hi=50.0)
    broad = fia_peak.analyze(*make_trace(shape=0.50), t_lo=20.0, t_hi=50.0)
    assert sharp.ratio > broad.ratio
