# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Setup script for msticpy."""

import re
import setuptools


with open("README.md", "r") as fh:
    LONG_DESC = fh.read()

# pylint: disable=locally-disabled, invalid-name
with open("msticpy/_version.py", "r") as fd:
    v_match = re.search(r'^VERSION\s*=\s*[\'"]([^\'"]*)[\'"]', fd.read(), re.MULTILINE)
    __version__ = v_match.group(1) if v_match else "no version"
# pylint: enable=locally-disabled, invalid-name

with open("requirements.txt", "r") as fh:
    INSTALL_REQUIRES = fh.readlines()

with open("requirements-dev.txt", "r") as fh:
    INSTALL_DEV_REQUIRES = fh.readlines()

# Extras definitions
EXTRAS = {
    "dev": INSTALL_DEV_REQUIRES,
    "vt3": ["vt-py>=0.5.4", "vt-graph-api>=1.0.1", "nest_asyncio>=1.4.0"],
    "splunk": ["splunk-sdk>=1.6.0"],
}

setuptools.setup(
    name="msticpy",
    version=__version__,
    author="Ian Hellen",
    author_email="ianhelle@microsoft.com",
    description="MSTIC Security Tools",
    license="MIT License",
    long_description=LONG_DESC,
    long_description_content_type="text/markdown",
    url="https://github.com/microsoft/msticpy",
    project_urls={
        "Documentation": "https://msticpy.readthedocs.io",
        "Code": "https://github.com/microsoft/msticpy",
    },
    python_requires=">=3.6",
    packages=setuptools.find_packages(exclude=["tests", "tests.*", "*.tests.*"]),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
    ],
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS,
    keywords=[
        "security",
        "azure",
        "sentinel",
        "mstic",
        "cybersec",
        "infosec",
        "cyber",
        "cybersecurity",
    ],
    zip_safe=False,
    include_package_data=True,
)
