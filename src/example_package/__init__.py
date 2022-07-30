from zuper_commons import ZLogger

logger = ZLogger(__name__)

from .configuration import *
from .interfaces import *
from .unittests import *


def jobs_comptests(context: QuickAppContext) -> None:
    logger.info("initializing jobs_comptests")

    # configuration
    from conf_tools import GlobalConfig

    GlobalConfig.global_load_dir("example_package.configs")

    # mcdp_lang_tests
    from . import unittests

    # instantiation
    from comptests import jobs_registrar

    jobs_registrar(context, get_example_package_config(), create_reports=True)


@comptest
def just_one_single():
    pass
