# setup.py

from setuptools import setup, find_packages

setup(
    name="pydmconverter",
    version="0.1",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "pydmconverter = pydmconverter.__main__:main",
        ]
    },
    install_requires=[],  # Add dependencies if needed
)
