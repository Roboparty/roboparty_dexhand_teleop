#!/usr/bin/env python3
"""Import the RP_Hand kinematics from the supplied mechanical model package."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


SIDES = {
    "left": ("DH116S-L000-A1", "RP_Hand_Left"),
    "right": ("DH116S-R000-A1", "RP_Hand_Right"),
}
DISTAL_LINKS = ("finger14", "finger23", "finger33", "finger43", "finger53")
TIP_CAP_DEPTH_M = 0.0005


def _binary_stl_vertices(path: Path) -> set[tuple[float, float, float]]:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"invalid binary STL: {path}")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + triangle_count * 50
    if len(data) != expected_size:
        raise ValueError(f"expected a binary STL of {expected_size} bytes: {path}")

    vertices = set()
    for triangle in range(triangle_count):
        vertex_offset = 84 + triangle * 50 + 12
        for vertex in range(3):
            vertices.add(struct.unpack_from("<fff", data, vertex_offset + vertex * 12))
    return vertices


def _distal_tip_origin(mesh_path: Path) -> tuple[float, float, float]:
    vertices = _binary_stl_vertices(mesh_path)
    maximum_z = max(vertex[2] for vertex in vertices)
    cap = [vertex for vertex in vertices if vertex[2] >= maximum_z - TIP_CAP_DEPTH_M]
    if not cap:
        raise ValueError(f"could not locate distal cap in {mesh_path}")
    return tuple(sum(vertex[axis] for vertex in cap) / len(cap) for axis in range(3))


def _strip_rendering(root: ET.Element) -> None:
    for link in root.findall("link"):
        for tag in ("visual", "collision"):
            for child in list(link.findall(tag)):
                link.remove(child)


def _append_tip(root: ET.Element, index: int, parent_link: str, origin) -> None:
    tip_name = f"finger{index}_tip"
    ET.SubElement(root, "link", {"name": tip_name})
    joint = ET.SubElement(root, "joint", {"name": f"{tip_name}_joint", "type": "fixed"})
    ET.SubElement(
        joint,
        "origin",
        {"xyz": " ".join(f"{value:.9g}" for value in origin), "rpy": "0 0 0"},
    )
    ET.SubElement(joint, "parent", {"link": parent_link})
    ET.SubElement(joint, "child", {"link": tip_name})


def import_side(source_root: Path, destination_root: Path, side: str) -> Path:
    model_name, product_name = SIDES[side]
    model_root = source_root / model_name
    source_urdf = model_root / "urdf" / f"{model_name}.urdf"
    if not source_urdf.is_file():
        raise FileNotFoundError(source_urdf)

    tree = ET.parse(source_urdf)
    root = tree.getroot()
    root.set("name", product_name)
    _strip_rendering(root)

    for index, distal_link in enumerate(DISTAL_LINKS, start=1):
        mesh_path = model_root / "meshes" / f"{distal_link}_link.STL"
        _append_tip(root, index, f"{distal_link}_link", _distal_tip_origin(mesh_path))

    ET.indent(tree, space="  ")
    destination = destination_root / side / f"rp_hand_{side}.urdf"
    destination.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destination, encoding="utf-8", xml_declaration=True)
    with destination.open("a", encoding="utf-8") as stream:
        stream.write("\n")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    parser.add_argument(
        "--destination-root",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "roboparty_dexhand_teleop"
        / "assets"
        / "rp_hand",
    )
    args = parser.parse_args()

    for side in SIDES:
        destination = import_side(
            args.source_root.expanduser().resolve(),
            args.destination_root.expanduser().resolve(),
            side,
        )
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
