from setuptools import setup, find_packages

setup(
    name="supercortex-flow",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "websockets>=12.0",
        "aiohttp>=3.8.0",
    ],
    python_requires=">=3.8",
) 