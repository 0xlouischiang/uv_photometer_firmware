"""
Device-side adapters for the FIA cycle.

This is the only FIA module that touches hardware, so it is the only one that
cannot be imported on a host. Everything with logic in it lives in the pure core
(fia_peak, fia_actuators, fia_settings, fia_sequencer) and is tested there.

Three things live here:
  - SensorReader, which presents LightSensor in the form the sequencer wants
  - FiaSettingsFile, which loads fia.json using the existing settings machinery
  - quantify(), which passes peak height to the existing Calibrations.apply,
    keeping ulab on this side of the boundary
"""

import constants
import fia_constants
from calibrations import CalibrationsError
from fia_sequencer import SensorError
from light_sensor import LightSensorIOError
from json_settings_file import JsonSettingsFile

from fia_settings import FiaSettings

# fia_constants mirrors this rather than importing constants, since importing
# constants would pull in board and break host testing. Catch any divergence.
assert fia_constants.CHANNEL_UVC == constants.CHANNEL_UVC


FIA_FILE = 'fia.json'


class FiaSettingsError(Exception):
    pass


class FiaSettingsFile(JsonSettingsFile):
    """
    Loads fia.json from the filesystem root, like configuration.json.

    A missing file is not an error -- JsonSettingsFile.load skips it -- and
    FiaSettings then supplies defaults throughout, so an unconfigured device
    still runs the design doc's nominal cycle.
    """

    FILE_TYPE = 'fia'
    FILE_NAME = FIA_FILE
    LOAD_ERROR_EXCEPTION = FiaSettingsError

    def __init__(self):
        super().__init__()
        self.settings = FiaSettings()

    def check(self):
        self.settings = FiaSettings.from_dict(self.data)
        if self.settings.has_errors:
            self.error_dict['fia'] = list(self.settings.errors)


class SensorReader:
    """
    Presents the AS7331 in the form FiaSequencer expects.

    Returns (raw_signal, raw_reference, overflow). raw_reference is None on a
    single-beam build, in which case the sequencer falls back to plain
    absorbance against the stored blank.

    Overflow is reported rather than raised: an overflow invalidates one
    injection, not the instrument, so the cycle finishes and the result carries
    a flag. A genuine IO error does raise, as SensorError, and faults the cycle.
    """

    def __init__(self, light_sensor, reference_sensor=None,
                 channel=fia_constants.CHANNEL_UVC):
        self.light_sensor = light_sensor
        self.reference_sensor = reference_sensor
        self.channel = channel

    def configure(self, settings=None, gain=None, integration_time=None):
        """
        Apply gain and integration time to both sensors.

        Integration time must stay short. 32 or 64 ms keeps 15-30 Hz, which is
        ample for a peak with a 10 s rise; the long integration times alias the
        peak (design doc section 3.2).
        """
        for sensor in self._sensors():
            if gain is not None:
                sensor.gain = gain
            if integration_time is not None:
                sensor.integration_time = integration_time

    def _sensors(self):
        if self.reference_sensor is None:
            return (self.light_sensor,)
        return (self.light_sensor, self.reference_sensor)

    @property
    def max_counts(self):
        return self.light_sensor.max_counts

    def __call__(self):
        try:
            values = self.light_sensor.raw_values
            raw = values[self.channel]
            overflow = raw >= self.light_sensor.max_counts

            reference = None
            if self.reference_sensor is not None:
                ref_values = self.reference_sensor.raw_values
                reference = ref_values[self.channel]
                overflow = overflow or (
                        reference >= self.reference_sensor.max_counts)
        except LightSensorIOError as error:
            raise SensorError(error)
        except OSError as error:
            # An I2C transaction failing mid-cycle surfaces as OSError, not as
            # the driver's own exception type.
            raise SensorError(error)
        return raw, reference, overflow


def quantify(calibrations, name, height):
    """
    Concentration from peak height, via the existing calibration machinery.

    The pure core deliberately stops at peak height so that ulab.numpy.polyval
    stays on the device side. A quadratic FIA fit is fit_type "polynomial" with
    three coefficients, highest-order first -- no schema change was needed.

    Returns None if the calibration is missing, the height is outside the fitted
    range, or the fit type is unsupported.
    """
    if height is None or name is None:
        return None
    if name not in calibrations.data:
        return None
    try:
        return calibrations.apply(name, height)
    except CalibrationsError:
        return None


def quantify_result(calibrations, name, result):
    """
    Concentration for a PeakResult, or None if the result was flagged.

    Refuses to quantify a rejected result. A peak outside the acceptance window
    means an air bubble, a valve failure or pump slip, and reporting a number
    from it would be worse than reporting nothing.
    """
    if result is None or not result.is_ok:
        return None
    return quantify(calibrations, name, result.height)
