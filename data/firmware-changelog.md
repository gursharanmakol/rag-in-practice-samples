# TechNova WH-1000 Firmware Changelog

## Version 3.2.1 — Released 2026-02-15

Bug fixes and stability improvements.

- Fixed an issue where ANC would occasionally produce a brief clicking sound when toggling between High and Low modes.
- Improved Bluetooth reconnection speed after the headphones exit sleep mode. Reconnection to the last paired device now takes approximately 2 seconds instead of 5.
- Resolved a bug where the battery level reported to connected devices via Bluetooth was sometimes 5–10% lower than the actual charge.
- Updated the USB-C charging controller to better support third-party cables that comply with the USB-C specification but were previously rejected.

## Version 3.1.0 — Released 2025-11-01

Performance improvements and new features.

- Added Bluetooth multipoint support: the WH-1000 can now maintain simultaneous connections with two devices. Audio playback automatically switches to the device that starts playing. Multipoint can be enabled in the TechNova app under Settings → Bluetooth → Multipoint.
- Improved ANC algorithm to reduce wind noise when using the headphones outdoors. The external microphones now apply a low-frequency filter that detects wind patterns and adjusts ANC processing accordingly.
- Fixed a Bluetooth stability issue where the headphones would disconnect from certain Android 14 devices after exactly 30 minutes of continuous playback. This was caused by a timeout handling error in the Bluetooth LE Audio stack.
- Improved audio latency in Bluetooth mode from 180ms to approximately 120ms, which reduces visible lip-sync delay when watching video content.

## Version 3.0.0 — Released 2025-08-20

Major release with new audio features.

- Introduced adaptive EQ: the WH-1000 now automatically adjusts equalization based on the fit and seal of the ear cushions. The internal microphones measure acoustic response and tune the frequency curve in real time. This feature can be disabled in the TechNova app if you prefer manual EQ control.
- Added support for LDAC high-resolution Bluetooth codec. When connected to a compatible source device, the WH-1000 can receive audio at up to 990 kbps, significantly improving audio quality over standard SBC or AAC codecs.
- Redesigned the touch controls on the right ear cup. Swipe gestures now control volume (up/down) and track navigation (forward/back). Double-tap plays or pauses. The previous single-tap gesture for pause has been removed to reduce accidental triggers.
- Increased maximum volume output by 3 dB. A new volume limiter option in the TechNova app allows users to cap output at the previous maximum if preferred.
- Fixed a rare issue where the headphones would not enter sleep mode after being idle for 15 minutes if ANC was left in Transparency mode.
