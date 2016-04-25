import os
from os.path import dirname, join

from conf_tools.utils import locate_files

__all__ = [
    'find_modules',
    'find_modules_main',
]


def find_modules_main(root):
    """ Finds the main modules (not '.' in the name) """
    is_main = lambda d: not '.' in d
    return filter(is_main, find_modules(root))

def find_modules(root):
    """ 
        Looks for modules defined in packages that have the structure: ::
        
            dirname/setup.py
            dirname/src/
            dirname/src/module/__init__.py
            dirname/src/module/module2/__init__.py
            
        This will yield ['module', 'module.module2']
    """
    setups = locate_files(root, 'setup.py')
    for s in setups:
        # look for '__init__.py'
        base = join(dirname(s), 'src')
        for i in locate_files(base, '__init__.py'):
            p = os.path.relpath(i, base)
            components = p.split('/')[:-1]  # remove __init__
            module = ".".join(components)
            yield module
