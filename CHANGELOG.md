# Changelog

## Unreleased SD update after v2.2

- Eggcel: F1–F5 File/Actions/Range/Copy/Paste, Range→Go, fill down/right,
  formula-to-value conversion and one-step undo.
- XY, grouped column and pie charts; bounded iterative calculation, cancellation
  and local error recovery preserving the workbook.
- Source repository preparation: private data/build outputs excluded, preserved
  third-party notices, optional licensed audio and synthetic audio tests.

These application changes do not require a new UF2. The public/default build
omits supplied recordings; existing local audio files are preserved privately.

## Unreleased connectivity firmware fixes

- Cooperative Wi-Fi joins, correct station/AP switching, scan/password handling
  and retryable NTP failures.
- Bounded nonblocking HTTP server with reliable Esc cleanup, first-use settings,
  verified saves and script execution scope.
- BLE advertisement sizing, actual UART discovery/subscription, MTU-aware chat,
  timeouts and explicit controller cleanup.
- Detect unsupported Pico 2 W pairing; simulator now matches that limitation.
  Generic key persistence/passkey paths are tested only with an opt-in fixture.
- Added protocol and application regression checks. See
  [Connectivity](guides/Connectivity.md) for findings and outstanding native/TLS work.

These changes require a new UF2 on the device. The existing v2.2 binary has not
been rebuilt or replaced.

## Unreleased upstream service removal

- Remove the remaining FlipSocial and network notification clients from source
  and explicitly exclude their imports from firmware/simulator profiles.
- Remove upstream account/API settings, account-required decorator and service
  fixtures. Old account fields are ignored and dropped on the next successful
  settings save; Wi-Fi and unrelated preferences remain compatible.
- Verify the packaged SD settings template contains no retired account fields.
- Add a service-endpoint source check and old-card/home regression coverage.
  [Comms inventory and audit](guides/Comms.md) distinguishes retained local tools,
  the external NTP time source and outstanding hardware/security work.

A new UF2 is required; the existing v2.2 binary remains unchanged.

## v2.2

- PicoDESK groups Eggcel, PicoWord and PicoPaint separately from PicoLAB.
- Engineering calculator modes, Graph and Graph3D, with selected float32 ulab.
- Themed dark interface, calculator widget and Lorenz screensaver.
- Escape returns; Back and Del both erase before the cursor.
- Lean PicoCalc Pico 2 W firmware retaining essential connectivity/system tools.
