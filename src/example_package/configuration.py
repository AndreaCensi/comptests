from conf_tools import ConfigMaster

__all__ = [
    'get_example_package_config',
    'get_conftools_example_class1',
    'get_conftools_example_class2',     
]

class ExamplePackageConfig(ConfigMaster):
    def __init__(self):
        ConfigMaster.__init__(self, 'ExamplePackageConfig')
        
        from .interfaces import ExampleClass1, ExampleClass2
        self.add_class_generic('example_class1', '*.example_class1.yaml', ExampleClass1)
        self.add_class_generic('example_class2', '*.example_class2.yaml', ExampleClass2)

def get_example_package_config():
    return ExamplePackageConfig.get_singleton()

def get_conftools_example_class1():
    return get_example_package_config().example_class1

def get_conftools_example_class2():
    return get_example_package_config().example_class2
