import os

from conf_tools.utils import locate_files

__all__ = [
    'find_modules',
    'find_modules_main',
]


def find_modules_main(root):
    """ Finds the main modules (not '.' in the name) """
    is_main = lambda d: not '.' in d
    return list(filter(is_main, find_modules(root)))


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

    found = []
    for s in setups:
        # s = <d>/setup.py
        d = os.path.dirname(s)
        # <d>/src
        src = os.path.join(d, 'src')
        if os.path.exists(src):
            base = src
        else:
            base = d

        for i in locate_files(base, '__init__.py'):
            p = os.path.relpath(i, base)
            components = p.split('/')[:-1]  # remove __init__
            module = ".".join(components)
            found.append(module)
    if not found:
        msg = 'Could not find any module in \nroot = %s ' % root
        raise Exception(msg)
    return found
