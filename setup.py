import os
import sys

from setuptools import setup, find_packages


# Ensure we're using the correct Python version
if sys.version_info < (3, 8):
    sys.exit("Python >= 3.8 is required.")

setup(
    name="nekoconf",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.68.0,<2.0.0",
        "uvicorn>=0.15.0,<1.0.0",
        "pydantic>=1.8.0,<2.0.0",
        "pyyaml>=6.0",
        "websockets>=10.0,<12.0",
        "aiofiles>=0.8.0,<1.0.0",
        "jsonschema>=4.0.0; extra == 'schema'",
    ],
    entry_points={
        "console_scripts": [
            "nekoconf=nekoconf.cli:main",
        ],
    },
    python_requires=">=3.8",
    include_package_data=True,
    zip_safe=False,
    description="NekoConf - A cute configuration manager for your JSON and YAML configuration files",
    author="k3scat",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
