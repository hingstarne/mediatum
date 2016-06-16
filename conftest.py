# -*- coding: utf-8 -*-
"""
    :copyright: (c) 2015 by the mediaTUM authors
    :license: GPL3, see COPYING for details
"""

import logging
import os
import warnings
from pytest import skip
from utils.log import TraceLogger

TraceLogger.skip_trace_lines += ("pytest", )
# TraceLogger.stop_trace_at = tuple()


def pytest_addoption(parser):
    parser.addoption('--slow', action='store_true', default=False,
                     help='Also run slow tests')


def pytest_runtest_setup(item):
    """Skip tests if they are marked as slow and --slow is not given"""
    if getattr(item.obj, 'slow', None) and not item.config.getvalue('slow'):
        skip('slow tests not requested')


from core import config
from core.init import add_ustr_builtin, init_db_connector, load_system_types, load_types, connect_db, _set_current_init_state, init_app,\
    check_imports


# we are doing a 'basic_init()' here for testing that's a bit different from core.init_basic_init()
# maybe this can be converted to a new init state or replaced by basic_init()

config.initialize(config_filepath=os.path.join(config.basedir, "test_mediatum.cfg"))
add_ustr_builtin()
import utils.log
utils.log.initialize()
check_imports()
init_app()
init_db_connector()
load_system_types()
load_types()
connect_db()
from core import db
db.disable_session_for_test()
warnings.simplefilter("always")
_set_current_init_state("basic")

# Disable setting the user and ip for each version. This leads to some failures in tests and we don't need it there anyways.
# Versioning tests can enable this later.
from core.database.postgres import athana_continuum_plugin
athana_continuum_plugin.disabled = True

# global fixtures, do not import them again!
from core.test.fixtures import *

print logging.getLogger().level
