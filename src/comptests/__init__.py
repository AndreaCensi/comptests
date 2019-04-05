# -*- coding: utf-8 -*-
__version__ = '1.4.34'


import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from .registrar import *
from .comptests import *
from .results import *
