import unittest

import numpy as np

from roboparty_dexhand_teleop.hand_command import HandCommandSelector, controller_to_counts


class ControllerMappingTest(unittest.TestCase):
    def test_trigger_and_grip_use_stronger_per_axis_target(self):
        result = controller_to_counts(
            0.5,
            0.75,
            [0.8, 0, 0, 0, 0, 0],
            [0.8, 1, 1, 1, 1, 1],
            [0.8, 0.8, 0.8, 0, 0, 0],
        )
        np.testing.assert_array_equal(result, [8000, 6000, 6000, 5000, 5000, 5000])

    def test_deadzone_and_scale(self):
        result = controller_to_counts(
            0.04,
            1.0,
            [0] * 6,
            [1] * 6,
            [1] * 6,
            scale=0.4,
            enable_grip=False,
        )
        np.testing.assert_array_equal(result, [0] * 6)


class HandCommandSelectorTest(unittest.TestCase):
    def test_switch_blends_from_last_command(self):
        selector = HandCommandSelector("controller", transition_ms=300.0)
        controller = np.zeros(6)
        skeleton = np.full(6, 6000)
        np.testing.assert_array_equal(
            selector.select(0, {"controller": controller, "skeleton": skeleton}),
            controller,
        )
        selector.request("skeleton")
        np.testing.assert_array_equal(
            selector.select(100, {"controller": controller, "skeleton": skeleton}),
            controller,
        )
        np.testing.assert_array_equal(
            selector.select(150_000_100, {"controller": controller, "skeleton": skeleton}),
            np.full(6, 3000),
        )
        np.testing.assert_array_equal(
            selector.select(300_000_100, {"controller": controller, "skeleton": skeleton}),
            skeleton,
        )
        self.assertEqual(selector.active_mode, "skeleton")

    def test_unavailable_requested_source_holds_without_switching(self):
        selector = HandCommandSelector("controller")
        selector.select(0, {"controller": np.ones(6), "skeleton": None})
        selector.request("skeleton")
        self.assertIsNone(selector.select(1, {"controller": np.ones(6), "skeleton": None}))
        self.assertEqual(selector.active_mode, "controller")


if __name__ == "__main__":
    unittest.main()
