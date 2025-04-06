import os
import sys

from setuptools import find_packages, setup

# Ensure we're using the correct Python version
if sys.version_info < (3, 8):
    sys.exit("Python >= 3.8 is required.")

# Let setuptools handle the version and requirements from pyproject.toml
setup(
    packages=find_packages(include=["nekoconf", "nekoconf.*"]),
    include_package_data=True,
    package_dir={"nekoconf": "nekoconf"},
    package_data={
        "nekoconf": ["static/**/*"],
    },
    zip_safe=False,
)
