from setuptools import find_packages, setup

PACKAGE = "substation_digital_twin"

setup(
    name=PACKAGE,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PACKAGE}"]),
        (f"share/{PACKAGE}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="jackeyliu37",
    maintainer_email="jackeyliu37@localhost",
    description="Semantic asset state owner.",
    license="Apache-2.0",
    tests_require=["pytest"],
)
