"""
A manually advanced monotonic clock.

Injected into FiaSequencer in place of time.monotonic_ns so a 15-minute cycle
runs in milliseconds of wall time, and so tests control exactly when each
transition is observed.
"""

NS_PER_S = 1000000000


class FakeClock:

    def __init__(self, start_ns=0):
        self.t_ns = int(start_ns)

    def now_ns(self):
        return self.t_ns

    @property
    def now_s(self):
        return self.t_ns/NS_PER_S

    def advance(self, dt_s):
        self.t_ns += int(dt_s*NS_PER_S)
        return self.t_ns

    def advance_ms(self, dt_ms):
        self.t_ns += int(dt_ms)*1000000
        return self.t_ns

    def advance_ns(self, dt_ns):
        self.t_ns += int(dt_ns)
        return self.t_ns
