__version__ = "7.1.2105121722"
__date__ = "2021-05-12T17:22:40.713154+00:00"

from zuper_commons.logs import ZLogger

logger = ZLogger(__name__)
logger.hello_module(name=__name__, filename=__file__, version=__version__, date=__date__)

from .registrar import *
from .comptests import *
from .results import *
from .indices import *
