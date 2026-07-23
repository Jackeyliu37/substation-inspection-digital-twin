from glob import glob
import os

from setuptools import find_packages, setup


PACKAGE = "substation_gazebo"

setup(
    name=PACKAGE,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PACKAGE}"]),
        (f"share/{PACKAGE}", ["package.xml"]),
        (f"share/{PACKAGE}/config", glob("config/*.yaml")),
        (f"share/{PACKAGE}/maps", glob("maps/*")),
        (
            f"share/{PACKAGE}/config",
            ["../../../configs/meter_dataset_generation.yaml"],
        ),
        (f"share/{PACKAGE}/launch", glob("launch/*.launch.py")),
        (f"share/{PACKAGE}/worlds", glob("worlds/*.sdf")),
        (
            f"share/{PACKAGE}/models/inspection_robot",
            glob("models/inspection_robot/*"),
        ),
        (
            f"share/{PACKAGE}/models/synthetic_meter",
            glob("models/synthetic_meter/*"),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="jackeyliu37",
    maintainer_email="jackeyliu37@localhost",
    description="Headless Gazebo Harmonic substation simulation.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "scenario_manager = substation_gazebo.scenario_manager:main",
            "meter_dataset_generator = substation_gazebo.meter_dataset_generator:main",
            "meter_dataset_package = substation_gazebo.meter_dataset_package:main",
        ],
    },
)
