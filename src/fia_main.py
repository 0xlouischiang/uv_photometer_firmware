"""
Entry point for the FIA analyser.

Additive on purpose: code.py still boots the cuvette photometer, and nothing
here runs unless it is asked for. To commission the FIA build, either

    import fia_main; fia_main.main()

from the REPL, or copy this over code.py on the CIRCUITPY drive.

It is deliberately not driven from Colorimeter.run(). That loop sleeps 100 ms
and calls gc.collect() every pass, which is exactly the jitter the design doc
names as the dominant method risk, and 10 Hz cannot carry a 20 Hz acquisition.

No fluidics hardware exists yet, so the actuator backend here is the logging
stub. Swapping in a real backend means implementing one method -- see
ActuatorBackend in fia_actuators.
"""

import gc
import time

import fia_actuators
import fia_hardware
import fia_sequencer
from calibrations import Calibrations
from calibrations import CalibrationsError
from configuration import Configuration
from configuration import ConfigurationError
from fia_constants import FAULT_TO_STR
from fia_constants import REJECT_TO_STR
from fia_constants import STATE_TO_STR
from fia_constants import State
from light_sensor import LightSensor
from light_sensor import LightSensorIOError


def load_settings():
    """FIA settings from fia.json, falling back to defaults."""
    settings_file = fia_hardware.FiaSettingsFile()
    try:
        settings_file.load()
    except fia_hardware.FiaSettingsError as error:
        print('fia settings: {}'.format(error))
    if settings_file.has_errors:
        while settings_file.has_errors:
            print('fia settings: {}'.format(settings_file.pop_error()))
    return settings_file.settings


def load_calibrations():
    calibrations = Calibrations()
    try:
        calibrations.load()
    except CalibrationsError as error:
        print('calibrations: {}'.format(error))
        return None
    while calibrations.has_errors:
        print('calibrations: {}'.format(calibrations.pop_error()))
    return calibrations


def build_reader(settings):
    """
    The signal sensor, plus a reference sensor if one is present.

    A second AS7331 needs a distinct I2C address, which LightSensor cannot
    currently express -- its constructor builds its own bus and passes no
    address. Adding `i2c=None, address=None` parameters (both defaulting to
    today's behaviour) is the minimal additive change; whether the vendor
    iorodeo_as7331 driver accepts an address is unverified, since the library is
    not vendored in this repo. Until then this runs single-beam.
    """
    light_sensor = LightSensor()
    reader = fia_hardware.SensorReader(light_sensor)

    configuration = Configuration()
    try:
        configuration.load()
    except ConfigurationError as error:
        print('configuration: {}'.format(error))
    else:
        reader.configure(
                gain=configuration.gain,
                integration_time=configuration.integration_time,
                )
    return reader


def report(result, calibrations, settings):
    """Print one injection. Stands in for logging until an SD card exists."""
    if result is None:
        return
    parts = ['h={:.4f}'.format(result.height if result.height else 0.0)]
    if result.area is not None:
        parts.append('area={:.3f}'.format(result.area))
    if result.ratio is not None:
        parts.append('h/a={:.4f}'.format(result.ratio))
    if result.t_peak is not None:
        parts.append('t={:.1f}s'.format(result.t_peak))
    parts.append('n={}'.format(result.n_samples))
    if result.late_samples:
        parts.append('late={}'.format(result.late_samples))
    if result.is_standard:
        parts.append('STANDARD')

    if result.is_ok and calibrations is not None:
        value = fia_hardware.quantify_result(
                calibrations, settings.calibration, result)
        if value is not None:
            units = calibrations.units(settings.calibration) or ''
            parts.append('=> {:.3f} {}'.format(value, units))
        else:
            parts.append('=> out of calibrated range')
    else:
        parts.append('REJECTED: {}'.format(REJECT_TO_STR[result.reject]))

    print(' '.join(parts))


def main(loop_forever=True):
    settings = load_settings()
    calibrations = load_calibrations()

    try:
        reader = build_reader(settings)
    except LightSensorIOError as error:
        print('missing sensor? {}'.format(error))
        return

    backend = fia_actuators.LoggingBackend(now_ns=time.monotonic_ns)
    actuators = fia_actuators.ActuatorSet(backend)

    sequencer = fia_sequencer.FiaSequencer(
            reader,
            actuators,
            settings,
            on_result=lambda r: report(r, calibrations, settings),
            )

    print('fia: {} mode, {:.0f} Hz, window [{:.0f}, {:.0f}] s'.format(
        settings.mode, settings.sample_hz,
        settings.window_min_s, settings.window_max_s))
    print('fia: actuators are a logging stub, no fluidics driven')

    gc.collect()
    sequencer.start()

    state = sequencer.state
    while True:
        # No sleep: the sequencer paces itself off the monotonic clock, and the
        # acquisition needs every tick it can get. Sampling blocks on the
        # sensor's integration time anyway.
        new_state = sequencer.update()
        if new_state != state:
            print('fia: {}'.format(STATE_TO_STR[new_state]))
            state = new_state
        if new_state == State.FAULT:
            print('fia: FAULT {}'.format(FAULT_TO_STR[sequencer.fault_reason]))
            if not loop_forever:
                return
            # Hold in fault rather than retrying blindly: the fault conditions
            # are a dead pump, a leak or a missing sensor, none of which clear
            # on their own.
            return


if __name__ == '__main__':
    main()
