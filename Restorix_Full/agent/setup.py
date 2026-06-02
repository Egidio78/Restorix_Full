from setuptools import setup, find_packages

setup(
    name="restorix-agent",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "boto3>=1.34.0",
        "paramiko>=3.4.0",
        "cryptography>=42.0.7",
        "pymysql>=1.1.0",
    ],
    entry_points={
        "console_scripts": [
            "restorix-agent=dbshield_agent.main:main",
        ],
    },
)
