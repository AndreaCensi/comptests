__version__ = "6.0.2101041531"

from zuper_commons.logs import ZLogger

logger = ZLogger(__name__)

from .registrar import *
from .comptests import *
from .results import *
