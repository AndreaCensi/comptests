from conf_tools import ConfigMaster
import os
from conf_tools import GlobalConfig

class ExampleClass1():
    def __init__(self, param1):
        self.param1 = param1


class ExampleClass2():
    def __init__(self, param1):
        self.param1 = param1


class ExamplePackageConfig(ConfigMaster):
    def __init__(self):
        ConfigMaster.__init__(self, 'ExamplePackageConfig')
        self.add_class('example_class1', '*.example_class1.yaml', ExampleClass1)
        self.add_class('example_class2', '*.example_class2.yaml', ExampleClass2)


def get_example_package_config():
    return ExamplePackageConfig.get_singleton()


def get_conftools_example_class1():
    return get_example_package_config().example_class1


def get_conftools_example_class2():
    return get_example_package_config().example_class2


def jobs_comptests(context):
    from . import unittests
    from comptests import jobs_registrar

    configs = []
    from pkg_resources import resource_filename  # @UnresolvedImport
    configs.append(resource_filename("example_package", "configs"))
    

    for d in configs:
        d = os.path.abspath(d)
        if not os.path.exists(d):
            raise ValueError('directory does not exist: %r' % d)
        
        GlobalConfig.global_load_dir(d) 
        
    jobs_registrar(context, get_example_package_config())
    