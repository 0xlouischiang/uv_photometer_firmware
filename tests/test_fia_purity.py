"""
Guards the boundary that makes the FIA core testable.

src/constants.py imports board and iorodeo_as7331 at module scope, so anything
importing constants -- colorimeter, calibrations, configuration,
json_settings_file, light_sensor -- cannot be imported on a host. The FIA core
must therefore stay clear of all of it.

These tests fail the moment someone adds a convenience import that breaks that,
which is the point: the failure arrives at the commit, not weeks later when the
whole suite has quietly become undiscoverable.
"""

import importlib
import sys

import pytest


CORE_MODULES = (
        'fia_constants',
        'fia_peak',
        'fia_actuators',
        'fia_settings',
        'fia_sequencer',
        )

FORBIDDEN = (
        'board',
        'ulab',
        'iorodeo_as7331',
        'constants',
        'busio',
        'digitalio',
        'analogio',
        'displayio',
        'keypad',
        )


@pytest.fixture
def blocked_platform_modules():
    """
    Make every platform module raise ImportError, then restore.

    None in sys.modules is the documented way to force an ImportError, so this
    catches a lazy `import board` inside a function too, not just module scope.
    """
    saved = {}
    for name in FORBIDDEN:
        saved[name] = sys.modules.get(name, '__absent__')
        sys.modules[name] = None
    for name in CORE_MODULES:
        sys.modules.pop(name, None)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value == '__absent__':
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
        for name in CORE_MODULES:
            sys.modules.pop(name, None)
        for name in CORE_MODULES:
            importlib.import_module(name)


@pytest.mark.parametrize('name', CORE_MODULES)
def test_core_module_imports_without_platform_modules(
        name, blocked_platform_modules):
    module = importlib.import_module(name)
    assert module is not None


def test_whole_core_imports_together_without_platform_modules(
        blocked_platform_modules):
    for name in CORE_MODULES:
        importlib.import_module(name)


def test_forbidden_modules_are_genuinely_blocked(blocked_platform_modules):
    # Confirms the fixture actually blocks, so the tests above are not vacuous.
    with pytest.raises(ImportError):
        importlib.import_module('board')


def test_core_declares_no_platform_imports_in_source():
    """
    Belt and braces: scan the source text.

    The import-time tests above only catch what executes. A platform import
    inside a rarely taken branch would slip past them, so check the text too.
    """
    import os
    src_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
    offenders = []
    for name in CORE_MODULES:
        path = os.path.join(src_dir, name + '.py')
        with open(path, 'r', encoding='utf-8') as f:
            for lineno, line in enumerate(f, start=1):
                stripped = line.strip()
                if not (stripped.startswith('import ')
                        or stripped.startswith('from ')):
                    continue
                for forbidden in FORBIDDEN:
                    if (stripped.startswith('import ' + forbidden)
                            or stripped.startswith('from ' + forbidden)):
                        offenders.append(
                                '{}:{}: {}'.format(name, lineno, stripped))
    assert not offenders, 'platform imports in the FIA core: ' + str(offenders)


def test_core_uses_math_not_ulab():
    # ulab.numpy.log10 and ulab arrays are the specific things that would drag
    # the core onto the device. Confirm the stdlib equivalents are in use.
    import array

    import fia_peak
    import fia_sequencer

    assert fia_peak.absorbance(3000.0, 30000.0) == pytest.approx(1.0)
    assert isinstance(array.array('f', [1.0]), array.array)
    assert fia_sequencer.array is array
