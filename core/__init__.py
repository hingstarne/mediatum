__version__ = "16.1dev0"

# set by core.database
db = None
# set by core.init.init_app()
app = None

# TODO: move to web.edit
editmodulepaths = [('', 'web/edit/modules')]

import utils.log
