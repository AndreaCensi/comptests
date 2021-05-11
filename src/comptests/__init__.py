__version__ = "7.1.2105111015"
__date__ = "2021-05-11T10:15:40.219697+00:00"

from zuper_commons.logs import ZLogger

logger = ZLogger(__name__)
logger.hello_module(name=__name__, filename=__file__, version=__version__, date=__date__)

from .registrar import *
from .comptests import *
from .results import *
