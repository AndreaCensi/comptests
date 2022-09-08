__version__ = "7.3"
__date__ = ""

from zuper_commons.logs import ZLogger, ZLoggerInterface

logger: ZLoggerInterface = ZLogger(__name__)
logger.hello_module(name=__name__, filename=__file__, version=__version__, date=__date__)

from .registrar import *
from .comptests import *
from .results import *
from .indices import *

logger.hello_module_finished(__name__)
