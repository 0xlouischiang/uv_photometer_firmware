"""
Tests for FIA settings loading and validation.

The contract: a malformed settings file must still yield a usable object with
defaults, recording what was wrong. An analyser that refuses to boot because one
field is a typo is worse than one that runs the nominal cycle and complains.
"""

import json
import os

import pytest

from fia_constants import Mode
from fia_settings import FiaSettings


EXAMPLE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'examples', 'fia.json')


def test_defaults_match_the_design_doc():
    s = FiaSettings()
    assert s.prime_s == 60.0
    assert s.baseline_s == 10.0
    assert s.load_s == 15.0
    assert s.acquire_s == 70.0
    assert s.sample_hz == 20.0
    assert s.window_min_s == 20.0
    assert s.window_max_s == 50.0
    assert s.baseline_rsd_max == 0.003      # RSD < 0.3 %
    assert s.wash_threshold == 0.002
    assert s.standard_every == 10
    assert s.cycle_period_s == 900.0        # 15 min
    assert not s.has_errors


def test_shipped_example_file_is_valid():
    with open(EXAMPLE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    s = FiaSettings.from_dict(data)
    assert s.errors == []
    assert s.mode == Mode.DUTY_CYCLE
    assert s.calibration == 'NH3-N'
    assert s.window_min_s == 20.0
    assert s.window_max_s == 50.0


def test_nested_peak_window_is_flattened():
    # Matches the "range": {"min":, "max":} convention in calibrations.json.
    s = FiaSettings.from_dict({'peak_window_s': {'min': 15.0, 'max': 45.0}})
    assert s.window_min_s == 15.0
    assert s.window_max_s == 45.0
    assert s.errors == []


def test_missing_file_yields_defaults():
    assert FiaSettings.from_dict(None).prime_s == 60.0
    assert FiaSettings.from_dict().prime_s == 60.0


def test_non_dict_is_reported_not_raised():
    s = FiaSettings.from_dict([1, 2, 3])
    assert s.has_errors
    assert s.prime_s == 60.0        # still usable


def test_unknown_key_is_reported_but_harmless():
    s = FiaSettings.from_dict({'prime_s': 30.0, 'nonsense': 1})
    assert s.prime_s == 30.0
    assert any('nonsense' in e for e in s.errors)


def test_bad_numeric_falls_back_to_default():
    s = FiaSettings.from_dict({'prime_s': 'soon'})
    assert s.prime_s == 60.0
    assert s.has_errors


def test_negative_and_zero_durations_rejected():
    for value in (-1.0, 0.0):
        s = FiaSettings.from_dict({'acquire_s': value})
        assert s.acquire_s == 70.0
        assert s.has_errors


def test_inverted_window_is_reset():
    s = FiaSettings.from_dict({'peak_window_s': {'min': 50.0, 'max': 20.0}})
    assert s.window_min_s == 20.0
    assert s.window_max_s == 50.0
    assert any('min' in e for e in s.errors)


def test_window_beyond_acquisition_is_flagged():
    # A window that extends past the acquisition can never see its own peak.
    s = FiaSettings.from_dict({
        'acquire_s': 40.0,
        'peak_window_s': {'min': 20.0, 'max': 50.0},
        })
    assert any('beyond acquire_s' in e for e in s.errors)


def test_baseline_too_short_for_an_rsd_is_flagged():
    # Fewer than two samples cannot yield a standard deviation, so the 0.3 %
    # gate would silently never apply.
    s = FiaSettings.from_dict({'baseline_s': 0.01, 'sample_hz': 20.0})
    assert any('rsd' in e for e in s.errors)


def test_bad_mode_falls_back():
    s = FiaSettings.from_dict({'mode': 'whenever'})
    assert s.mode == Mode.DUTY_CYCLE
    assert s.has_errors


def test_valid_modes_accepted():
    assert FiaSettings.from_dict({'mode': 'continuous'}).mode == Mode.CONTINUOUS
    assert FiaSettings.from_dict({'mode': 'duty_cycle'}).mode == Mode.DUTY_CYCLE


def test_standard_every_zero_is_allowed():
    # Zero disables the interleave; it is not an error.
    s = FiaSettings.from_dict({'standard_every': 0})
    assert s.standard_every == 0
    assert not s.has_errors


def test_buffer_capacities_cover_the_acquisition():
    s = FiaSettings()
    assert s.sample_capacity >= s.acquire_s*s.sample_hz
    assert s.baseline_capacity >= s.baseline_s*s.sample_hz
    assert s.sample_dt_s == pytest.approx(0.05)


def test_cycle_min_s_exposes_the_design_doc_discrepancy():
    # Section 3.2 quotes "130 s on per 15 min cycle", but its own state timings
    # sum to 155 s before WASH even begins. Worth resolving against the LED
    # lifetime budget before hardware.
    assert FiaSettings().cycle_min_s == 155.0


def test_constructor_rejects_unknown_kwarg():
    with pytest.raises(TypeError):
        FiaSettings(not_a_setting=1)
