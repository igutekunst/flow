from setuptools import setup, find_packages

setup(
    name="flow-pubsub-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.0",
        "requests>=2.31.0",
        "websockets>=12.0",
    ],
    entry_points={
        "console_scripts": [
            "flow=flow_cli.main:cli",
        ],
    },
    python_requires=">=3.8",
) 
