# setup.py 1
from setuptools import find_packages, setup

setup(
    name="api",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "db = api_console:db",
            "dev = api_console:dev",
        ]
    },
    zip_safe=False,
)
