# Third-party components

The vendored `dex_retargeting` Python package is derived from Unitree's
`xr_teleoperate` project. Its MIT license is preserved in
`LICENSE.dex_retargeting`; the upstream Apache-2.0 project notice is preserved
in `LICENSE.xr_teleoperate`.

The RP_Hand retargeting URDFs are generated from the 2026-04-09 mechanical
model package supplied for RP_Hand. `tools/import_rp_hand_urdf.py` removes
rendering geometry, assigns the RP_Hand product names, and derives five virtual
fingertip frames from the distal surfaces of the supplied STL meshes. Mesh files
are not redistributed because this package only builds a kinematic model.

The source package documents its MJCF as the authoritative nonlinear coupling
model. Pinocchio consumes the source URDF's linear `mimic` approximation; the
importer preserves those coefficients without modification.

The upstream general-purpose URDF loader was removed. RP_Hand uses a fixed-base
kinematic URDF, which Pinocchio loads directly; mimic tags are read with the
Python standard library.
