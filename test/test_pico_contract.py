from types import SimpleNamespace
import unittest

import numpy as np

from roboparty_dexhand_teleop.pico_contract import (
    FRAME_ID,
    canonical_hand_state,
    controller_trigger_grip,
    require_frame_id,
    source_stamp_ns,
)


def header(frame_id=FRAME_ID, sec=1, nanosec=2):
    return SimpleNamespace(
        frame_id=frame_id,
        stamp=SimpleNamespace(sec=sec, nanosec=nanosec),
    )


def pose(index):
    return SimpleNamespace(
        position=SimpleNamespace(x=float(index), y=0.0, z=1.0),
        orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
    )


class PicoContractTest(unittest.TestCase):
    def test_header_contract(self):
        message = SimpleNamespace(header=header())
        require_frame_id(message)
        self.assertEqual(source_stamp_ns(message), 1_000_000_002)
        with self.assertRaisesRegex(ValueError, "frame_id"):
            require_frame_id(SimpleNamespace(header=header("openxr")))

    def test_controller_contract(self):
        message = SimpleNamespace(axes=[0.25, 0.75, -1.0, 1.0])
        self.assertEqual(controller_trigger_grip(message), (0.25, 0.75))
        with self.assertRaisesRegex(ValueError, "axes"):
            controller_trigger_grip(SimpleNamespace(axes=[0.5]))
        with self.assertRaisesRegex(ValueError, "finite"):
            controller_trigger_grip(SimpleNamespace(axes=[np.nan, 0.5]))

    def test_hand_pose_contract(self):
        state = canonical_hand_state(SimpleNamespace(poses=[pose(i) for i in range(26)]))
        self.assertEqual(state.shape, (26, 7))
        np.testing.assert_array_equal(state[0], [0, 0, 1, 0, 0, 0, 1])
        self.assertIsNone(canonical_hand_state(SimpleNamespace(poses=[])))
        with self.assertRaisesRegex(ValueError, "26"):
            canonical_hand_state(SimpleNamespace(poses=[pose(i) for i in range(25)]))

    def test_hand_pose_rejects_invalid_quaternion(self):
        poses = [pose(i) for i in range(26)]
        poses[4].orientation.w = 0.0
        with self.assertRaisesRegex(ValueError, "zero quaternion"):
            canonical_hand_state(SimpleNamespace(poses=poses))


if __name__ == "__main__":
    unittest.main()
