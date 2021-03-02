__version__ = "7.1.2103021250"
__date__ = "2021-03-02T12:50:44.126344"

from zuper_commons.logs import ZLogger

logger = ZLogger(__name__)
logger.hello_module(name=__name__, filename=__file__, version=__version__, date=__date__)


from .registrar import *
from .comptests import *
from .results import *
