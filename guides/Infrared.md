# Infrared: excluded from this release

GungOS does not ship Infrared in the Comms menu or frozen firmware. The IR
application, high-level remote library and `ir_rx`/`ir_tx` protocol modules
have been removed. Existing user remote files on SD are left alone.

PicoCalc has no built-in IR emitter or receiver. Contributors with appropriate
external hardware can recover the earlier implementation from Git history.
An extension needs explicit hardware configuration, safe GPIO ownership and
physical transmit/receive tests. GP2–GP5 are PSRAM data lines; the earlier
inherited pin list must not be restored unchanged.

Generic GPIO/PWM/timer simulator fixtures and false board capability flags
remain; neither makes IR support available in this release.
