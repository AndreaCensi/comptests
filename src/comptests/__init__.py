__version__ = "6.1.2101041551"

from zuper_commons.logs import ZLogger

logger = ZLogger(__name__)

from .registrar import *
from .comptests import *
from .results import *
