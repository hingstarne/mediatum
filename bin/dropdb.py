# -*- coding: utf-8 -*-
"""
    :copyright: (c) 2014 by the mediaTUM authors
    :license: GPL3, see COPYING for details
"""

from __future__ import division, absolute_import, print_function

import logging
from core.init import basic_init
basic_init()

logg = logging.getLogger(__name__)

from core import db

logg.info("dropping mediaTUM db...")
db.drop_all()