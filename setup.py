from setuptools import setup, find_packages
import os

def get_version(filename):
    import ast
    version = None
    with file(filename) as f:
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


description = """ Testing utilities for projects that use ConfTools 
for handling their configuration. """ 

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
            'comptests = comptests:main_comptests'
       ],
      #         'nose.plugins.0.10': [
      #             'xunitext = xunitext:XUnitExt'
      #             ]
      },
      package_dir={'':'src'},
      packages=find_packages('src'),
      install_requires=[
        'PyContracts', 
        'compmake', 
        'ConfTools', 
        'quickapp',
      ],
      tests_require=['nose'],
)

