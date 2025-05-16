__version__ = "7.3"
__date__ = ""

from zuper_commons.logs import ZLogger
from zuper_commons.logs import ZLoggerInterface

logger: ZLoggerInterface = ZLogger(__name__)
logger.hello_module(name=__name__, filename=__file__, version=__version__, date=__date__)

from .comptests import *
from .indices import *
from .registrar import *
from .results import *

logger.hello_module_finished(__name__)
