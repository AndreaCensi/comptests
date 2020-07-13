# -*- coding: utf-8 -*-
__version__ = '6.0.4'

from zuper_commons.logs import ZLogger

logger = ZLogger(__name__)

from .registrar import *
from .comptests import *
from .results import *
