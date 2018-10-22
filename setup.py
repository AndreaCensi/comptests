import os

from setuptools import setup, find_packages


def get_version(filename):
    import ast
    version = None
    with open(filename) as f:
        for line in f:
            if line.startswith('__version__'):
                version = ast.parse(line).body[0].value.s
                break
        else:
            raise ValueError('No version found in %r.' % filename)
    if version is None:
        raise ValueError(filename)
    return version


version = get_version(filename='src/comptests/__init__.py')

description = """ Testing utilities for projects that use ConfTools for handling their configuration. """


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


long_description = read('README.md')

setup(name='comptests',
      author="Andrea Censi",
      author_email="censi@mit.edu",
      url='http://github.com/AndreaCensi/comptests',

      description=description,
      long_description=long_description,
      keywords="",
      license="",

      classifiers=[
          'Development Status :: 4 - Beta',
          # 'Intended Audience :: Developers',
          # 'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
          # 'Topic :: Software Development :: Quality Assurance',
          # 'Topic :: Software Development :: Documentation',
          # 'Topic :: Software Development :: Testing'
      ],

      version=version,
      download_url='http://github.com/AndreaCensi/comptests/tarball/%s' % version,

      entry_points={
          'console_scripts': [
              'comptests = comptests:main_comptests',
              'comptests-to-junit = comptests.comptest_to_junit:comptest_to_junit_main',
          ],
          #         'nose.plugins.0.10': [
          #             'xunitext = xunitext:XUnitExt'
          #             ]
      },
      package_dir={'': 'src'},
      packages=find_packages('src'),
      install_requires=[
          'PyContracts',
          'compmake>=3.5.29',
          'ConfTools',
          'quickapp',
          'junit_xml',
      ],
      tests_require=['nose'],
      )
