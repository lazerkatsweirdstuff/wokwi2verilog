from setuptools import setup, find_packages

setup(
    name="wokwi2verilog",
    version="1.0.0",
    author="Lazer Kat",
    description="Universal compiler for Wokwi C chips to Verilog",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/lazerkatsweirdstuff/wokwi2verilog",
    py_modules=["wokwi2verilog"],
    entry_points={
        "console_scripts": [
            "wokwi2verilog=wokwi2verilog:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)