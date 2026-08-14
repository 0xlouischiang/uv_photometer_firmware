"""
Synthetic FIA signal for host tests.

An FIA peak is asymmetric -- sharp rise, long tail -- because convection smears
the plug into a paraboloid before radial diffusion partly re-homogenises it
(design doc section 1). A symmetric Gaussian would not exercise the analysis
honestly, so the model here is log-normal in t.

Signal is fed to the sequencer as raw counts through the same absorbance path
the real sensor uses, rather than as absorbance directly.
"""

import math
import random


def peak(t, height=0.30, t_peak=32.0, shape=0.35, baseline=0.0):
    """
    Absorbance of a log-normal FIA peak at time t.

    height  -- peak absorbance above baseline
    t_peak  -- time of the maximum, seconds after injection
    shape   -- log-space width; larger is broader with a longer tail
    """
    if t <= 0.0:
        return baseline
    z = math.log(t/t_peak)/shape
    return baseline + height*math.exp(-0.5*z*z)


def to_raw(a, blank):
    """
    Raw counts that would produce absorbance `a` against `blank`.

    Inverts fia_peak.absorbance so tests drive the sequencer with counts.
    """
    return blank*(10.0**(-a))


class Noise:
    """Seeded multiplicative noise, for the baseline stability tests."""

    def __init__(self, rsd=0.0, seed=1234):
        self.rsd = rsd
        self._rand = random.Random(seed)

    def apply(self, value):
        if not self.rsd:
            return value
        return value*(1.0 + self._rand.gauss(0.0, self.rsd))


class ScriptedReader:
    """
    Stands in for the AS7331, driven by the fake clock.

    Returns (raw_signal, raw_reference, overflow). Absorbance is zero until the
    sequencer stamps t0, then follows the synthetic peak. Where t0 comes from
    matters: the reader asks the sequencer, so the signal is aligned to the same
    timing origin the analysis uses.
    """

    def __init__(self, clock, blank=30000.0, height=0.30, t_peak=32.0,
                 shape=0.35, baseline_a=0.0, noise=None, reference=None,
                 wash_tail_a=0.0):
        self.clock = clock
        self.blank = blank
        self.height = height
        self.t_peak = t_peak
        self.shape = shape
        self.baseline_a = baseline_a
        self.noise = noise or Noise(0.0)
        self.reference = reference
        self.wash_tail_a = wash_tail_a

        self.sequencer = None
        self.overflow = False
        self.raise_error = None
        self.call_count = 0

    def absorbance_at(self, elapsed_s):
        if elapsed_s is None:
            return self.baseline_a
        return peak(
                elapsed_s,
                height=self.height,
                t_peak=self.t_peak,
                shape=self.shape,
                baseline=self.baseline_a,
                )

    def __call__(self):
        self.call_count += 1
        if self.raise_error is not None:
            raise self.raise_error

        import fia_constants
        state = self.sequencer.state if self.sequencer is not None else None

        if state == fia_constants.State.WASH:
            # WASH holds until absorbance falls below threshold. wash_tail_a
            # lets a test keep it pinned high to exercise the timeout.
            a = self.wash_tail_a
        elif state in (fia_constants.State.ACQUIRE, fia_constants.State.ANALYZE):
            elapsed = (self.clock.now_ns() - self.sequencer.t0_ns)/1e9
            a = self.absorbance_at(elapsed)
        else:
            a = self.baseline_a

        raw = self.noise.apply(to_raw(a, self.blank))
        return raw, self.reference, self.overflow
