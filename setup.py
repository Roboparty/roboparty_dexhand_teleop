from glob import glob
import os
from pathlib import Path

from setuptools import find_packages, setup

package_name = "roboparty_dexhand_teleop"


def install_tree(source):
    entries = []
    for path in Path(source).rglob("*"):
        if path.is_file():
            destination = os.path.join("share", package_name, str(path.parent))
            entries.append((destination, [str(path)]))
    return entries

setup(
    name=package_name,
    version="0.1.1",
    packages=find_packages(exclude=["test"]),
    include_package_data=False,
    package_data={
        package_name: [
            "assets/rp_hand/*.yml",
            "assets/rp_hand/left/rp_hand_left.urdf",
            "assets/rp_hand/right/rp_hand_right.urdf",
        ]
    },
    data_files=[
        ("share/ament_index/resource_index/packages", [os.path.join("resource", package_name)]),
        (os.path.join("share", package_name),
         ["package.xml", "README.md", "CHANGELOG.md"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "docs"), glob("docs/*.md")),
    ] + install_tree("third_party"),
    install_requires=[
        "setuptools",
        "numpy",
        "PyYAML",
    ],
    zip_safe=True,
    maintainer="RoboParty",
    maintainer_email="ZhihaoLiu_hit@163.com",
    description=(
        "Maps canonical XR controller or hand-skeleton input to RP_Hand references."
    ),
    license="GPL-3.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "dexhand_teleop_bridge = roboparty_dexhand_teleop.dexhand_teleop_bridge:main",
        ],
    },
)
