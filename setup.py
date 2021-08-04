from setuptools import setup, find_namespace_packages

setup(
    name="json-codec",
    version="0.0.1",
    author="Simple Machines",
    author_email="hello@simplemachines.com.au",
    description="JSON codecs for dataclasses.",
    license="Copyright 2021 Simple Machines Pty Ltd. All Rights Reserved",
    packages=find_namespace_packages("src"),
    package_dir={"": "src"},
    install_requires=[],
    test_suite="tests",
    extras_require={"testing": ["hypothesis", "pytest"]}
)
