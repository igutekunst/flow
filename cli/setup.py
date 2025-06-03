from setuptools import setup, find_packages

# Read the README file for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="flow-pubsub-cli",
    version="0.2.0",
    author="SuperCortex Flow",
    author_email="isaac@supercortex.io",
    description="A command-line client for SuperCortex Flow - a privacy-preserving, decentralized pub/sub messaging system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/igutekunst/flow",
    project_urls={
        "Bug Tracker": "https://github.com/igutekunst/flow/issues",
        "PyPI": "https://pypi.org/project/flow-pubsub-cli/",
        "Documentation": "https://github.com/igutekunst/flow#readme",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications",
        "Topic :: System :: Distributed Computing",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet",
        "Topic :: Security :: Cryptography",
    ],
    license="MIT",
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
    keywords=[
        "pubsub",
        "messaging",
        "decentralized",
        "privacy",
        "cli",
        "websockets",
        "cryptography",
        "distributed-systems",
    ],
) 
