from .configuration import *
from .interfaces import *


def jobs_comptests(context):
    # configuration
    from conf_tools import GlobalConfig
    GlobalConfig.global_load_dir("example_package.configs")
    
    # mcdp_lang_tests
    from . import unittests
    
    # instantiation
    from comptests import jobs_registrar        
    jobs_registrar(context, get_example_package_config())
    