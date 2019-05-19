#!/usr/bin/env python
# -*- coding: utf-8 -*-
 
from setuptools import setup, find_packages
import ishell

setup(
    name = "irods-shell",
    version = ishell.__version__,
    packages = find_packages(),
    author = "Valentin Niess",
    author_email = "valentin.niess@gmail.com",
    description = "Irods in a nutSHELL",
    long_description = open("README.md").read(),
    long_description_content_type = "text/markdown",
    include_package_data = True,
    url = "https://github.com/niess/ishell",
    classifiers = (
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ),
    install_requires = ("python-irodsclient>=0.7.0"),
    entry_points = {
        "console_scripts" : ("iinit=ishell.iinit:main",
                             "ishell=ishell.ishell:main")
    }
)
