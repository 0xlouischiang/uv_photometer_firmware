"""
Peak analysis for the FIA cycle.

The analytical signal is peak height above the flowing reagent baseline. Height
is more precise, area tolerates pump flow drift better, so both are recorded and
their ratio serves as a health metric -- if it moves, pump tubing is worn or the
membrane is fouling. See AMMONIA_FIA_SENSOR_DESIGN.md section 3.2.

Imports `math` only, so this runs on a host under pytest as well as on device.
Quantification is deliberately not done here: the caller passes `height` to
`Calibrations.apply`, which keeps `ulab` on the device side.
"""

import math

from fia_constants import Reject


class PeakResult:
    """Outcome of one injection. __slots__ keeps it cheap to allocate."""

    __slots__ = (
            'height',
            'area',
            't_peak',
            'ratio',
            'reject',
            'n_samples',
            'is_standard',
            'late_samples',
            )

    def __init__(self):
        self.height = None
        self.area = None
        self.t_peak = None
        self.ratio = None
        self.reject = Reject.NO_PEAK
        self.n_samples = 0
        self.is_standard = False
        self.late_samples = 0

    @property
    def is_ok(self):
        return self.reject == Reject.NONE


def absorbance(raw, blank):
    """
    Absorbance from raw counts against a blank, clamped at zero.

    Matches Colorimeter.absorbance (src/colorimeter.py:242) but uses math.log10
    instead of ulab, and guards the non-positive cases the original does not.
    Returns None when the ratio is undefined.
    """
    if raw is None or blank is None:
        return None
    if raw <= 0.0 or blank <= 0.0:
        return None
    value = -math.log10(float(raw)/float(blank))
    return value if value > 0.0 else 0.0


def mean(buf, n):
    """Mean of the first n entries of buf. None when n is zero."""
    if n <= 0:
        return None
    total = 0.0
    for i in range(n):
        total += buf[i]
    return total/n


def rsd(buf, n):
    """
    Relative standard deviation (sd/mean) of the first n entries.

    Sample standard deviation (n-1 divisor). Returns None when n < 2 or the
    mean is zero, since the ratio is undefined there.
    """
    if n < 2:
        return None
    avg = mean(buf, n)
    if avg is None or avg == 0.0:
        return None
    total = 0.0
    for i in range(n):
        delta = buf[i] - avg
        total += delta*delta
    return math.sqrt(total/(n-1))/abs(avg)


def find_peak(t_buf, a_buf, n):
    """
    Locate the global maximum over the whole trace.

    Global, not window-restricted, on purpose. Searching only inside the
    acceptance window would return a window-edge value and report a bad
    injection as good -- the window check exists to catch exactly that.

    Returns (index, t_peak, height), or (None, None, None) if n is zero.
    """
    if n <= 0:
        return None, None, None
    idx = 0
    peak = a_buf[0]
    for i in range(1, n):
        if a_buf[i] > peak:
            peak = a_buf[i]
            idx = i
    return idx, t_buf[idx], peak


def _interp(t_buf, a_buf, i0, i1, t):
    """Linear interpolation of absorbance at time t between two samples."""
    t0 = t_buf[i0]
    t1 = t_buf[i1]
    if t1 == t0:
        return a_buf[i0]
    frac = (t - t0)/(t1 - t0)
    return a_buf[i0] + frac*(a_buf[i1] - a_buf[i0])


def trapz(t_buf, a_buf, n, t_lo, t_hi):
    """
    Trapezoid integral of absorbance over [t_lo, t_hi].

    The two boundary sub-intervals are linearly interpolated so the area does
    not depend on where samples happen to land relative to the window edges.
    Returns None if the trace does not span the window at all.
    """
    if n < 2 or t_hi <= t_lo:
        return None
    if t_buf[n-1] < t_lo or t_buf[0] > t_hi:
        return None

    area = 0.0
    for i in range(n-1):
        ta = t_buf[i]
        tb = t_buf[i+1]
        if tb <= t_lo or ta >= t_hi:
            continue
        aa = a_buf[i]
        ab = a_buf[i+1]
        # Clip this sub-interval to the window, interpolating at the edges.
        if ta < t_lo:
            aa = _interp(t_buf, a_buf, i, i+1, t_lo)
            ta = t_lo
        if tb > t_hi:
            ab = _interp(t_buf, a_buf, i, i+1, t_hi)
            tb = t_hi
        area += 0.5*(aa + ab)*(tb - ta)
    return area


def analyze(t_buf, a_buf, n, t_lo, t_hi, result=None):
    """
    Height, area, peak time, health ratio and acceptance for one injection.

    A peak maximum outside [t_lo, t_hi] is flagged rather than reported -- that
    single check catches air bubbles, valve failures and pump slip. Height and
    area are still filled in for diagnostics; the caller must check `reject`
    (or `is_ok`) before quantifying.

    Pass `result` to reuse a PeakResult instead of allocating one.
    """
    if result is None:
        result = PeakResult()
    result.n_samples = n

    idx, t_peak, height = find_peak(t_buf, a_buf, n)
    if idx is None:
        result.height = None
        result.area = None
        result.t_peak = None
        result.ratio = None
        result.reject = Reject.NO_PEAK
        return result

    result.height = height
    result.t_peak = t_peak
    result.area = trapz(t_buf, a_buf, n, t_lo, t_hi)

    if result.area is not None and result.area > 0.0:
        result.ratio = height/result.area
    else:
        result.ratio = None

    if height <= 0.0:
        result.reject = Reject.NO_PEAK
    elif t_peak < t_lo:
        result.reject = Reject.WINDOW_EARLY
    elif t_peak > t_hi:
        result.reject = Reject.WINDOW_LATE
    else:
        result.reject = Reject.NONE
    return result
