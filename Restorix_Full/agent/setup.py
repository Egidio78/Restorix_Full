from setuptools import setup, find_packages

setup(
    name="dbshield-agent",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "boto3>=1.34.0",
        "paramiko>=3.4.0",
        "cryptography>=42.0.7",
    ],
    entry_points={
        "console_scripts": [
            "dbshield-agent=dbshield_agent.main:main",
        ],
    },
)
