# Changelog

## Unreleased

- Clarify `bash`/`zsh` ROS environment setup in the operator SOP.

## 0.1.1 - 2026-09-04

- Isolate ROS bridge processes from incompatible user-site NumPy packages so
  Pinocchio-backed skeleton retargeting works with the system ROS binaries.

## 0.1.0 - 2026-09-04

- Add independent left/right controller and skeleton teleoperation bridges.
- Add RP_Hand DexPilot retargeting with the production URDF and joint limits.
- Add automatic recovery after temporary PICO hand-tracking gaps.
- Add the native Ubuntu 22.04 full-body and dexterous-hand operating SOP.
