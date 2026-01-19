from setuptools import setup, find_packages

setup(
    name="wokwi2verilog",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'wokwi2verilog=wokwi2verilog.cli:main',
        ],
    },
    python_requires='>=3.6',
)