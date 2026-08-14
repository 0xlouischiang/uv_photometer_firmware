"""
Settings for the FIA cycle.

Defaults come from AMMONIA_FIA_SENSOR_DESIGN.md section 3.2. A missing or
malformed settings file yields working defaults plus a list of recorded errors,
rather than a crash -- matching how Configuration and Calibrations behave.

No file I/O here, so this runs on a host under pytest. FiaSettingsFile in
fia_hardware reads the JSON and hands the dict to from_dict.
"""

from fia_constants import Mode


class FiaSettings:
    """Validated FIA timings and thresholds."""

    DEFAULTS = {
            'mode'             : Mode.DUTY_CYCLE,
            'cycle_period_s'   : 900.0,
            'prime_s'          : 60.0,
            'baseline_s'       : 10.0,
            'baseline_rsd_max' : 0.003,
            'baseline_retries' : 2,
            'load_s'           : 15.0,
            'acquire_s'        : 70.0,
            'sample_hz'        : 20.0,
            'window_min_s'     : 20.0,
            'window_max_s'     : 50.0,
            'wash_threshold'   : 0.002,
            'wash_timeout_s'   : 120.0,
            'standard_every'   : 10,
            'standard_name'    : None,
            'calibration'      : None,
            }

    # (key, minimum, maximum). None means unbounded on that side.
    POSITIVE_FLOATS = (
            ('cycle_period_s'   , 0.0,  None),
            ('prime_s'          , 0.0,  None),
            ('baseline_s'       , 0.0,  None),
            ('baseline_rsd_max' , 0.0,  1.0),
            ('load_s'           , 0.0,  None),
            ('acquire_s'        , 0.0,  None),
            ('sample_hz'        , 0.0,  1000.0),
            ('window_min_s'     , 0.0,  None),
            ('window_max_s'     , 0.0,  None),
            ('wash_threshold'   , 0.0,  None),
            ('wash_timeout_s'   , 0.0,  None),
            )

    def __init__(self, **kwargs):
        self.errors = []
        for key, value in self.DEFAULTS.items():
            setattr(self, key, value)
        for key, value in kwargs.items():
            if key not in self.DEFAULTS:
                raise TypeError('unknown fia setting {}'.format(key))
            setattr(self, key, value)
        self.validate()

    @classmethod
    def from_dict(cls, data=None):
        """
        Build from a settings dict, ignoring unknown keys.

        The nested "peak_window_s": {"min":, "max":} form is accepted and
        flattened, matching the "range" convention in calibrations.json.
        """
        settings = cls()
        if data is None:
            return settings
        if not isinstance(data, dict):
            settings.errors.append('fia settings must be a dict')
            return settings

        for key in cls.DEFAULTS:
            if key in data:
                setattr(settings, key, data[key])

        window = data.get('peak_window_s', None)
        if window is not None:
            if isinstance(window, dict):
                if 'min' in window:
                    settings.window_min_s = window['min']
                if 'max' in window:
                    settings.window_max_s = window['max']
            else:
                settings.errors.append('peak_window_s must be a dict')

        for key in data:
            if key not in cls.DEFAULTS and key != 'peak_window_s':
                settings.errors.append('unknown fia setting {}'.format(key))

        settings.validate()
        return settings

    def validate(self):
        """
        Coerce and range-check every field, replacing bad values with defaults.

        Errors accumulate in self.errors so the caller can surface them; the
        object is always left usable.
        """
        self.errors = [e for e in self.errors]

        for key, low, high in self.POSITIVE_FLOATS:
            self._check_float(key, low, high)

        for key in ('baseline_retries', 'standard_every'):
            self._check_int(key, 0)

        if self.mode not in (Mode.CONTINUOUS, Mode.DUTY_CYCLE):
            self.errors.append('mode must be {} or {}'.format(
                Mode.CONTINUOUS, Mode.DUTY_CYCLE))
            self.mode = self.DEFAULTS['mode']

        if self.window_min_s >= self.window_max_s:
            self.errors.append('peak window min must be less than max')
            self.window_min_s = self.DEFAULTS['window_min_s']
            self.window_max_s = self.DEFAULTS['window_max_s']

        if self.window_max_s > self.acquire_s:
            self.errors.append('peak window max beyond acquire_s')

        if self.baseline_s*self.sample_hz < 2:
            self.errors.append('baseline_s too short for an rsd at sample_hz')

        return not self.errors

    def _check_float(self, key, low, high):
        raw = getattr(self, key)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            self.errors.append('{} must be a number'.format(key))
            setattr(self, key, self.DEFAULTS[key])
            return
        if low is not None and value <= low:
            self.errors.append('{} must be greater than {}'.format(key, low))
            value = self.DEFAULTS[key]
        if high is not None and value > high:
            self.errors.append('{} must not exceed {}'.format(key, high))
            value = self.DEFAULTS[key]
        setattr(self, key, value)

    def _check_int(self, key, low):
        raw = getattr(self, key)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            self.errors.append('{} must be an integer'.format(key))
            setattr(self, key, self.DEFAULTS[key])
            return
        if value < low:
            self.errors.append('{} must be at least {}'.format(key, low))
            value = self.DEFAULTS[key]
        setattr(self, key, value)

    @property
    def has_errors(self):
        return bool(self.errors)

    @property
    def sample_dt_s(self):
        return 1.0/self.sample_hz

    @property
    def sample_capacity(self):
        """Buffer size for one acquisition, with headroom for a late tick."""
        return int(self.acquire_s*self.sample_hz) + 8

    @property
    def baseline_capacity(self):
        return int(self.baseline_s*self.sample_hz) + 8

    @property
    def cycle_min_s(self):
        """
        Shortest possible cycle, excluding WASH.

        With the design doc defaults this is 155 s, which does not match the
        "130 s on per 15 min cycle" LED budget quoted in section 3.2. The
        sequencer reports measured LED on-time rather than assuming either
        number.
        """
        return self.prime_s + self.baseline_s + self.load_s + self.acquire_s
