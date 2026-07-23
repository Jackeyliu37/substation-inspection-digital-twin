from setuptools import find_packages, setup


PACKAGE = "substation_description"
DEVICES = "../../../configs/devices.yaml"

setup(
    name=PACKAGE,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PACKAGE}"]),
        (f"share/{PACKAGE}", ["package.xml"]),
        (f"share/{PACKAGE}/config", [DEVICES]),
        (f"share/{PACKAGE}/urdf", ["urdf/inspection_robot.urdf.xacro"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="jackeyliu37",
    maintainer_email="jackeyliu37@localhost",
    description="Stable robot and substation asset descriptions.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "asset_tf_broadcaster = substation_description.asset_tf_broadcaster:main",
        ],
    },
)
