from setuptools import setup

with open("README.md") as f:
    long_description = f.read()

setup(
    name="lcal",
    version="1",
    description="A simple tui calendar with timezone support and all the essentials!",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Law Chun Man",
    author_email="lawchunman1@proton.me",
    python_requires=">=3.9",
    packages=["lcal"],
    entry_points={
        'console_scripts': [
            'lcal = lcal.__main__:main',
        ],
    },
)
