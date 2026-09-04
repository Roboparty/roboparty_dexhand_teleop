import unittest

import numpy as np

from roboparty_dexhand_teleop.hand_coordinates import (
    RP_HAND_BASIS,
    canonical_hand_to_rp_landmarks,
    quaternion_xyzw_to_matrix,
)


ROBOT_FROM_OPENXR = np.asarray(
    [[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32
)
UNITREE_FROM_ROBOT = np.asarray(
    [[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]], dtype=np.float32
)
RP_FROM_UNITREE = {
    "left": np.asarray(
        [[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]], dtype=np.float32
    ),
    "right": np.asarray(
        [[0.0, 0.0, -1.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0]], dtype=np.float32
    ),
}


def make_state(points, wrist_quaternion):
    state = np.zeros((26, 7), dtype=np.float32)
    state[:, 6] = 1.0
    state[0, :3] = points[0]
    state[0, 3:7] = wrist_quaternion
    state[2:, :3] = points[1:]
    return state


class HandCoordinatesTest(unittest.TestCase):
    def test_folded_basis_matches_gr00t_default_path(self):
        rng = np.random.default_rng(20260902)
        for side in ("left", "right"):
            expected_basis = RP_FROM_UNITREE[side] @ UNITREE_FROM_ROBOT @ ROBOT_FROM_OPENXR
            np.testing.assert_array_equal(RP_HAND_BASIS[side], expected_basis)
            for _ in range(100):
                points = rng.normal(size=(25, 3)).astype(np.float32)
                quaternion = rng.normal(size=4).astype(np.float32)
                quaternion /= np.linalg.norm(quaternion)
                state = make_state(points, quaternion)

                wrist_rotation = quaternion_xyzw_to_matrix(quaternion)
                robot_points = points @ ROBOT_FROM_OPENXR.T
                robot_wrist_rotation = (
                    ROBOT_FROM_OPENXR @ wrist_rotation @ ROBOT_FROM_OPENXR.T
                )
                robot_local = (robot_points - robot_points[0]) @ robot_wrist_rotation
                old_result = (
                    robot_local
                    @ UNITREE_FROM_ROBOT.T
                    @ RP_FROM_UNITREE[side].T
                )
                new_result = canonical_hand_to_rp_landmarks(state, side)
                np.testing.assert_allclose(new_result, old_result, atol=2e-6)

    def test_world_translation_and_wrist_rotation_are_removed(self):
        points = np.zeros((25, 3), dtype=np.float32)
        points[:, 0] = np.linspace(0.0, 0.24, 25)
        identity = make_state(points, [0.0, 0.0, 0.0, 1.0])

        angle = np.pi / 2.0
        quaternion = np.asarray([0.0, 0.0, np.sin(angle / 2.0), np.cos(angle / 2.0)])
        rotation = quaternion_xyzw_to_matrix(quaternion)
        moved_points = points @ rotation.T + np.asarray([1.2, -0.8, 0.4])
        moved = make_state(moved_points, quaternion)

        for side in ("left", "right"):
            np.testing.assert_allclose(
                canonical_hand_to_rp_landmarks(identity, side),
                canonical_hand_to_rp_landmarks(moved, side),
                atol=1e-6,
            )

    def test_canonical_palm_pose_is_not_a_dexpilot_landmark(self):
        points = np.zeros((25, 3), dtype=np.float32)
        points[:, 0] = np.linspace(0.0, 0.24, 25)
        baseline = make_state(points, [0.0, 0.0, 0.0, 1.0])
        moved_palm = baseline.copy()
        moved_palm[1, :3] = [20.0, -30.0, 40.0]

        for side in ("left", "right"):
            np.testing.assert_array_equal(
                canonical_hand_to_rp_landmarks(baseline, side),
                canonical_hand_to_rp_landmarks(moved_palm, side),
            )

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            canonical_hand_to_rp_landmarks(np.zeros((25, 7)), "left")
        with self.assertRaises(ValueError):
            canonical_hand_to_rp_landmarks(np.zeros((26, 7)), "middle")
        state = np.zeros((26, 7), dtype=np.float32)
        with self.assertRaises(ValueError):
            canonical_hand_to_rp_landmarks(state, "right")


if __name__ == "__main__":
    unittest.main()
