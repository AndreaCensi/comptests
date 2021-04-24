__version__ = "7.1.2104241741"
__date__ = "2021-04-24T17:41:52.727146"

from zuper_commons.logs import ZLogger

logger = ZLogger(__name__)
logger.hello_module(name=__name__, filename=__file__, version=__version__, date=__date__)


from .registrar import *
from .comptests import *
from .results import *
