import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cabbie-jmp", # Replace with your own username
    version="0.0.1",
    author="RW Hooper",
    author_email="rwhooper@example.com",
    description="Cloud Application Builder",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jmpdmnky/cabbie",
    packages=setuptools.find_packages(),
    license="Proprietary and Confidential",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)