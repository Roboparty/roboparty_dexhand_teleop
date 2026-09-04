import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from roboparty_dexhand_teleop.hand_retargeting import radians_to_counts, read_joint_limits


class HandRetargetingUtilitiesTest(unittest.TestCase):
    def test_radians_to_counts_clips_and_scales_each_joint(self):
        limits = np.asarray([[0.0, 1.0], [-1.0, 1.0]] + [[0.0, 2.0]] * 4)
        values = np.asarray([-1.0, 0.0, 1.0, 2.0, 3.0, 0.5])
        np.testing.assert_array_equal(
            radians_to_counts(values, limits),
            np.asarray([0, 5000, 5000, 10000, 10000, 2500], dtype=np.int32),
        )

    def test_joint_limits_come_from_urdf(self):
        # The thumb has two active joints, then index through pinky.
        document = (
            "<robot>"
            '<joint name="finger11" type="revolute"><limit lower="0" upper="1"/></joint>'
            '<joint name="finger12" type="revolute"><limit lower="0" upper="2"/></joint>'
            + "".join(
                f'<joint name="finger{i}1" type="revolute">'
                f'<limit lower="0" upper="{i + 1}"/></joint>'
                for i in range(2, 6)
            )
            + "</robot>"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hand.urdf"
            path.write_text(document, encoding="utf-8")
            limits = read_joint_limits(path)
        np.testing.assert_allclose(limits[:, 0], np.zeros(6))
        np.testing.assert_allclose(limits[:, 1], [1, 2, 3, 4, 5, 6])

    def test_packaged_models_use_current_rp_hand_kinematics(self):
        asset_root = (
            Path(__file__).resolve().parents[1]
            / "roboparty_dexhand_teleop"
            / "assets"
            / "rp_hand"
        )
        expected_mimics = {
            "finger13": ("finger12", 0.929, -0.015082),
            "finger22": ("finger21", 0.8847, 0.038265),
            "finger32": ("finger31", 0.8485, 0.035946),
            "finger42": ("finger41", 0.8321, 0.043170),
            "finger52": ("finger51", 0.7349, 0.035218),
        }

        for side in ("left", "right"):
            path = asset_root / side / f"rp_hand_{side}.urdf"
            root = ET.parse(path).getroot()
            self.assertEqual(root.get("name"), f"RP_Hand_{side.title()}")
            self.assertFalse(root.findall(".//visual"))
            self.assertFalse(root.findall(".//collision"))
            np.testing.assert_allclose(
                read_joint_limits(path)[:, 1],
                [1.75, 1.40, 1.40, 1.40, 1.40, 1.40],
            )

            joints = {joint.get("name"): joint for joint in root.findall("joint")}
            for joint_name, (driver, multiplier, offset) in expected_mimics.items():
                mimic = joints[joint_name].find("mimic")
                self.assertIsNotNone(mimic)
                self.assertEqual(mimic.get("joint"), driver)
                self.assertAlmostEqual(float(mimic.get("multiplier")), multiplier)
                self.assertAlmostEqual(float(mimic.get("offset")), offset)
            for index in range(1, 6):
                link_names = {link.get("name") for link in root.findall("link")}
                self.assertIn(f"finger{index}_tip", link_names)


if __name__ == "__main__":
    unittest.main()
