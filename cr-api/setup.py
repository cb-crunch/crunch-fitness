#!/usr/bin/env python
# coding: utf-8

from setuptools import setup, find_packages

import os
thisdir = os.path.abspath(os.path.dirname(__file__))


setup(
    name='cr.api',
    version='1.0',
    description="Crunch API",
    author=u'Crunch.io',
    author_email='dev@crunch.io',
    license='Proprietary',
    install_requires=['CherryPy',
                      'cr.db',
                      'webtest',
                      'numpy'
                      ],
    tests_require=[],
    packages=find_packages(exclude=['ez_setup']),
    namespace_packages=['cr'],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'cr.api = cr.api.server:run',
        ]
    }
)
