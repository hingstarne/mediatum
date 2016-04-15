#!/usr/bin/env ipython2
# -*- coding: utf-8 -*-
'''
Created on 06.06.2013
@author: stenzel

***************
mediatumipython
***************

mediaTUM command line based on many great IPython features and some extensions.

Run it
======

Command line, from the mediaTUM base directory::

    ipython -i bin/mediatumipython.py


In a IPython Notebook cell::

    %run bin/mediatumipython.py


Basics
======

* shell-like "filesystem" browsing for the mediaTUM node tree
* IPython prompt shows the current node
* the current node can be accessed with `cnode`, the previous node with `lastnode`


Commands
========

Commands are implemented as IPython magic functions. You can omit the leading % most of the time.
For more information on each magic function, use `%<magic>?`, for example `%check_login?`

Initialization
--------------

* `%init full` - init everything, needed for some commands.
    At startup, only important stuff is initialized (database, basic data types ...) automatically.
    Plugins are loaded only in 'full' mode.


Change current node
-------------------

* `%cd <nid>` - change current node by ID
* `%cd -` - change to previous node
* `%child <child name>` - change to named child of current node (alias ch)


Display info for current node
-----------------------------

* `%list_all` - list current node info for all categories: parents, children, attributes, files (alias l)
* `%list_attributes` - (alias la)
* `%list_children` - (alias lc)
* `%list_parents` - (alias lp)
* `%list_files` - (alias lf)
* `%list_rights` - (alias lr)


Set `limit_number_of_info_lines = <n>` to display only the first <n> lines of a category.


Change the tree
---------------

* `%link <nid>` - add node with <nid> as child to current node
* `%remove <nid>` - remove child with <nid> from current node


SQL shortcuts
-------------

See `ipython-sql documentation <https://pypi.python.org/pypi/ipython-sql>`_ for more info.

* `%sql` - run any sql statement (provided by ipython-sql)
* `%select` - run a select statement
* `%insert` - run a insert statement
* `%update` - run a update statement
* `%delete` - run a delete statement


User Management
---------------

%check_login <login_name> - check if user is able to login with given password. Returns the user object even if authentication fails.
%password <login_name> - set user password


Misc information
----------------

* `%citeproc` - show citeproc mappings


Maintenance
^^^^^^^^^^^

* `%postprocess <nid>` - run postprocessing on current node or <nid>, if given
* `%checkmask [--fix] [--all] [--allmasks]` - run integrity checks on masks, see %checkmask? for details
* `%purge_nodes`: delete nodes that are not connected to the root node in any way ("unreachable nodes")


SQLAlchemy
==========

The `q` function can be used to query the database:


Node queries
------------

.. code-block:: python

    # count collections
    q(Collection).count()

    # get a node named test, fails if none or more than one result found
    q(Data).filter_by(name="test").one()

    # get a node named test, fails if more than one result found, returns None if none found
    q(Data).filter_by(name="test").scalar()

    # get the first document
    q(Document).first()

    # get all content children of Collection #993321
    q(Collection).get(993321).content_children # returns NodeAppenderQuery
    q(Collection).get(993321).content_children.all() # returns list

    # get all masks of Metadatatype #816859
    q(Metadatatype).get(816859).masks.all()

    # attribute access
    q(Data).get(816859)["description"]
    q(Data).get(816859).a.description

    # find all image nodes that are archived
    q(Image).filter(Image.sys.archive_type != None).count()

'''
from __future__ import division, absolute_import, print_function
from collections import OrderedDict
from functools import wraps
import getpass
from itertools import islice, chain
import logging
import os.path
import sys
import tempfile
import warnings
from sqlalchemy import sql
from sqlalchemy.orm.exc import NoResultFound
import humanize

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.init as initmodule
from utils.compat import *

# log settings #

# set this to INFO for SQL statement echo, DEBUG for even more info from SQLAlchemy
SQLALCHEMY_LOGGING = logging.WARN
SQL_LOGGING = logging.WARN
ROOT_LOGLEVEL = logging.INFO
LOG_FILEPATH = os.path.join(tempfile.gettempdir(), "mediatumipython.log")

# / log settings #

initmodule.basic_init(ROOT_LOGLEVEL, log_filepath=LOG_FILEPATH, use_logstash=False)
initmodule.register_workflow()

from core.database.postgres.node import t_noderelation
from core.database.postgres import alchemyext
import core.database.postgres.connector

# change this to True in your IPython notebook after running mediatumipython.py
IPYTHON_NOTEBOOK = False

core.database.postgres.connector.DEBUG_SHOW_TRACE = False
core.database.postgres.connector.DEBUG = True
core.database.postgres.SLOW_QUERY_SECONDS = 3600

# use default connection specified by mediatum config for ipython-sql magic
SQLMAGICS_CONNECTION_FACTORY = lambda: core.db.connectstr
# TODO: changing the connection string should be possible for the postgres connector, too


from core.users import get_guest_user
try:
    guest_user = get_guest_user()
except:
    guest_user = None

# we don't want to raise warnings for missing node classes, just stub them and be silent
_core_init_loglevel = logging.getLogger("core.init").level
logging.getLogger("core.init").setLevel(logging.ERROR)
initmodule.check_undefined_nodeclasses(stub_undefined_nodetypes=True)
logging.getLogger("core.init").setLevel(_core_init_loglevel)

from core import db, Node, File
from core import User, UserGroup, AuthenticatorInfo
from core import AccessRule, AccessRuleset, NodeToAccessRule, NodeToAccessRuleset
from core import Fts, Setting

q = core.db.query
s = core.db.session

# load types for interactive querying
from contenttypes import Audio, Content, Directory, Collection, Container, Collections, Home, Document, Image, Imagestream, \
    Project, Video, Data
from core.systemtypes import Mappings, Metadatatypes, Root, Searchmasks
from schema.schema import Metadatatype, Maskitem, Mask, Metafield
from schema.mapping import Mapping, MappingField
from workflow.workflow import Workflow, Workflows
from core.database.postgres.permission import NodeToAccessRule, NodeToAccessRuleset, EffectiveNodeToAccessRuleset
from core.oauth import OAuthUserCredentials

from sqlalchemy.exc import SQLAlchemyError

# set user-defined log levels later to avoid log spam in startup phase
logging.getLogger("sqlalchemy.engine").setLevel(SQLALCHEMY_LOGGING)
# setting this to logging.DEBUG show all DB statements
logging.getLogger("sqllog").setLevel(SQL_LOGGING)

logg = logging.getLogger(__name__)

global last_inserted_node
last_inserted_node_id = None
global cnode
# root can be None for uninitialized / corrupt databases. We allow this.
root = cnode = q(Root).scalar()
global lastnode
lastnode = root

global limit_number_of_info_lines
limit_number_of_info_lines = None

# IPython magic

from IPython.core.magic import Magics, magics_class, line_magic, needs_local_scope
from IPython.core.magic_arguments import argument, magic_arguments,\
    parse_argstring, defaults


def exec_sqlfunc(func):
    return alchemyext.exec_sqlfunc(s, func)


def reachable_node_ids():
    return q(t_noderelation.c.cid).filter(t_noderelation.c.nid == 1).union_all(sql.select([sql.expression.literal(1)]))


def delete_unreachable_nodes(synchronize_session='fetch'):
    reachable_nodes_sq = reachable_node_ids().subquery()
    s.execute(t_noderelation.delete(~t_noderelation.c.nid.in_(reachable_nodes_sq)))
    s.execute(t_noderelation.delete(~t_noderelation.c.cid.in_(reachable_nodes_sq)))
    q(File).filter(~File.nid.in_(reachable_nodes_sq)).delete(synchronize_session)
    return q(Node).filter(~Node.id.in_(reachable_nodes_sq)).delete(synchronize_session)


def unreachable_nodes():
    reachable_node_sq = reachable_node_ids().subquery()
    return q(Node).filter(~Node.id.in_(reachable_node_sq))


def inversion_label(invert):
    return u"(-)" if invert else u""


def blocking_label(blocking):
    return u"(blocking)" if blocking else u""


def inherited_label(inherited):
    return u"(inherited)" if inherited else u""


def format_access_ruleset_assoc(ra, inherited):
    r = ra.ruleset

    return u"{}{}{} {}".format(inversion_label(ra.invert), blocking_label(ra.blocking), inherited_label(inherited), r.name)


def format_access_rule_assoc(ra):
    r = ra.rule
    group_names = r.group_names
    if group_names is not None:
        group_names_or_ids = [n or str(r.group_ids[i]) for i, n in enumerate(r.group_names)]
    else:
        group_names_or_ids = []

    return u"{}{} groups:{} {} subnets:{} {} dateranges:{} {}".format(inversion_label(ra.invert), blocking_label(ra.blocking),
                                                                      inversion_label(r.invert_group), ", ".join(group_names_or_ids) or "-",
                                                                      inversion_label(r.invert_subnet), r.subnets or "-",
                                                                      inversion_label(r.invert_date), r.dateranges or "-")


def make_info_producer_access_rules(ruletype):
    def _info_producer(node):
        rule_assocs = node.access_rule_assocs.filter_by(ruletype=ruletype).all()
        own_ruleset_assocs = node.access_ruleset_assocs.filter_by(ruletype=ruletype).all()
        effective_ruleset_assocs = node.effective_access_ruleset_assocs.filter(
            EffectiveNodeToAccessRuleset.c.ruletype == ruletype).all()
        inherited_ruleset_assocs = set(effective_ruleset_assocs) - set(own_ruleset_assocs)

        effective_rulesets = [rsa.ruleset for rsa in effective_ruleset_assocs]
        rule_assocs_in_rulesets = [r for rs in effective_rulesets for r in rs.rule_assocs]

        def assoc_filter(assocs, to_remove):

            def _f(a):
                for rem in to_remove:
                    if a.rule == rem.rule and a.invert == rem.invert and a.blocking == rem.blocking:
                        return False
                return True

            return [a for a in assocs if _f(a)]

        remaining_rule_assocs = assoc_filter(rule_assocs, rule_assocs_in_rulesets)
        special_ruleset = node.get_special_access_ruleset(ruletype)
        special_rule_assocs = special_ruleset.rule_assocs if special_ruleset else []

        return chain(
            [u"Rulesets:"] if own_ruleset_assocs or inherited_ruleset_assocs else [""],
            ("\t" + format_access_ruleset_assoc(rs, inherited=False)
             for rs in own_ruleset_assocs),
            ("\t" + format_access_ruleset_assoc(rs, inherited=True)
             for rs in inherited_ruleset_assocs),
            [u"Special Rules:"] if special_rule_assocs else [""],
            ("\t" + format_access_rule_assoc(r) for r in special_rule_assocs),
            [u"", u"RULES NOT IN A RULESET (INVALID!)"] if remaining_rule_assocs else [""],
            ("\t" + format_access_rule_assoc(r) for r in remaining_rule_assocs)
        )

    return _info_producer


def file_info_producer(node):
    return [u"{} {} {} ({})".format(a.filetype,
                                    a.mimetype,
                                    a.path,
                                    humanize.filesize.naturalsize(a.size) if a.exists else "missing!")
            for a in sorted(node.files, key=lambda f: (f.filetype, f.mimetype))]


INFO_PRODUCERS = OrderedDict([
    ("parents", lambda node: (u"{} {}:  {}".format(n.id, n.name, n.type) for n in node.parents)),
    ("children", lambda node: (u"{} {}:  {}".format(n.id, n.name, n.type) for n in node.children)),
    ("attributes", lambda node: (u"{} = {}".format(name, value)
                                 for name, value in sorted(iteritems(node.attrs), key=lambda a: a[0]))),
    ("system_attributes", lambda node: (u"{} = {}".format(name, value)
                                 for name, value in sorted(iteritems(node.system_attrs), key=lambda a: a[0]))),
    ("files", file_info_producer),
    ("read_rules", make_info_producer_access_rules("read")),
    ("write_rules", make_info_producer_access_rules("write")),
    ("data_rules", make_info_producer_access_rules("data")),
])


def print_info_for_category(category, limit=None):
    if limit is None:
        limit = limit_number_of_info_lines

    print(u"\t" + category.replace("_", " ").capitalize() + ":")
    info_producer = INFO_PRODUCERS[category]

    for line in islice(info_producer(cnode), 0, limit):
        print(u"\t\t{}".format(line).encode("utf8"))


def needs_init(min_state):
    def _needs_init(f):
        @wraps(f)
        def _inner(self, *args, **kwargs):
            if initmodule.init_state_reached(min_state):
                return f(self, *args, **kwargs)
            else:
                print("mediaTUM is not initialized properly. You must run '%init {}' first." .format(min_state))
        return _inner

    return _needs_init


@magics_class
class MediatumMagics(Magics):

    def __init__(self, shell):
        super(MediatumMagics, self).__init__(shell)

    @magic_arguments()
    @argument("nid", nargs="?", default="")
    @line_magic
    def cd(self, line):
        """Changes to node with id `nid`"""
        global cnode, lastnode
        args = parse_argstring(self.cd, line)
        nid = args.nid
        if nid == "":
            cnode, lastnode = root, cnode

        elif nid == "-":
            cnode, lastnode = lastnode, cnode
        else:
            new_node = q(Node).get(nid)
            if new_node:
                cnode, lastnode = new_node, cnode
            else:
                print(u"node {} not found.".format(nid))

    @magic_arguments()
    @argument("name")
    @line_magic("child")
    @line_magic("ch")
    def child(self, line):
        global cnode, lastnode
        args = parse_argstring(self.child, line)
        name = args.name.strip("\"'")
        try:
            cnode, lastnode = cnode.children.filter_by(name=name).one(), cnode
        except NoResultFound:
            print(u"Child {} not found!".format(args.name))

    @line_magic("list_all")
    @line_magic("l")
    def list_all(self, line):
        print(cnode)
        for category in INFO_PRODUCERS:
            if not category.endswith("_rules"):
                print_info_for_category(category)

    @line_magic("list_attributes")
    @line_magic("la")
    def list_attributes(self, line):
        print_info_for_category("attributes")

    @line_magic("list_system_attributes")
    @line_magic("lsa")
    def list_system_attributes(self, line):
        print_info_for_category("system_attributes")

    @line_magic("list_children")
    @line_magic("lc")
    def list_children(self, line):
        print_info_for_category("children")

    @line_magic("list_parents")
    @line_magic("lp")
    def list_parents(self, line):
        print_info_for_category("parents")

    @line_magic("list_files")
    @line_magic("lf")
    def list_files(self, line):
        print_info_for_category("files")

    @line_magic("list_rules")
    @line_magic("lr")
    def list_rules(self, line):
        print_info_for_category("read_rules")
        print_info_for_category("write_rules")
        print_info_for_category("data_rules")

    @needs_init("basic")
    @magic_arguments()
    @argument("nid")
    @line_magic
    def remove(self, line):
        args = parse_argstring(self.remove, line)
        try:
            child = cnode.children.filter_by(id=long(args.nid)).one()
        except NoResultFound:
            print(u"Child {} not found!".format(args.nid))
            return
        cnode.children.remove(child)

    @needs_init("basic")
    @magic_arguments()
    @argument("nid")
    @line_magic("link")
    @line_magic("ln")
    def ln(self, line):
        args = parse_argstring(self.ln, line)
        new_child = q(Node).get(args.nid)
        cnode.children.append(new_child)

    @needs_init("basic")
    @magic_arguments()
    @argument("ruletype")
    @argument("name")
    @argument("-i", "--invert", action="store_true")
    @line_magic
    def link_ruleset(self, line):
        args = parse_argstring(self.link_ruleset, line)
        existing_assoc = cnode.access_ruleset_assocs.filter_by(ruleset_name=args.name, ruletype=args.ruletype).scalar()
        if existing_assoc is not None:
            logg.warn(
                "ruleset %s (%s, %s) already used by current node, ignored",
                args.name,
                inversion_label(
                    not existing_assoc.invert),
                args.ruletype)
        else:
            new_assoc = NodeToAccessRuleset(ruleset_name=args.name, ruletype=args.ruletype, invert=args.invert)
            cnode.access_ruleset_assocs.append(new_assoc)

    @needs_init("basic")
    @magic_arguments()
    @argument("ruletype")
    @argument("name")
    @line_magic
    def unlink_ruleset(self, line):
        args = parse_argstring(self.unlink_ruleset, line)
        assoc = cnode.access_ruleset_assocs.filter_by(ruleset_name=args.name, ruletype=args.ruletype).scalar()
        if assoc is None:
            logg.warn("ruleset %s (%s) not used by current node, ignored", args.name, args.ruletype)
        else:
            cnode.access_ruleset_assocs.remove(assoc)

    @needs_init("basic")
    @magic_arguments()
    @argument("ruletype")
    @argument("-i", "--invert", action="store_true")
    @argument("-b", "--blocking", action="store_true")
    @line_magic
    def add_rule(self, line):
        args = parse_argstring(self.link_ruleset, line)
        rule = AccessRule()
        assoc = NodeToAccessRule(rule=rule, ruletype=args.ruletype, invert=args.invert, blocking=args.blocking)
        cnode.access_ruleset_assocs.append(assoc)

    @needs_init("basic")
    @magic_arguments()
    @argument("ruleset_name")
    @line_magic
    def ruleset(self, line):
        args = parse_argstring(self.ruleset, line)
        ars = q(AccessRuleset).get(args.ruleset_name)
        for ra in ars.rule_assocs:
            print(format_access_rule_assoc(ra))

    @needs_init("basic")
    @magic_arguments()
    @argument("-f", "--fix", action="store_true")
    @argument("-a", "--all", action="store_true", help="check all masks of current metadatatypes")
    @argument("-m", "--allmasks", action="store_true", help="check all masks of *all* metadatatypes")
    @defaults(fix=False)
    @line_magic
    def checkmask(self, line):
        args = parse_argstring(self.checkmask, line)
        import schema.schema as metadatatypes
        if args.all:
            def check_masks_of_mdt(mdt):
                for mask in mdt.masks:
                    print("-" * 80)
                    print(u"checking mask {} of mdt {}".format(mask.name, mdt.name))
                    metadatatypes.checkMask(mask, fix=args.fix, verbose=1, show_unused=1)

            if args.allmasks:
                for mdt in q(Metadatatype):
                    print("=" * 80)
                    print("checking metadatatype", mdt.name)
                    check_masks_of_mdt(mdt)
            else:
                check_masks_of_mdt(cnode)
        else:
            metadatatypes.checkMask(cnode, fix=args.fix, verbose=1, show_unused=1)

    @needs_init("basic")
    @magic_arguments()
    @argument("oldmask")
    @argument("newmask")
    @line_magic
    def clonemask(self, line):
        raise NotImplementedError("not yet implemented in mediaTUM postgres")
        args = parse_argstring(self.clonemask, line)
        import schema.schema as metadatatypes
        metadatatypes.cloneMask(cnode.children.filter_by(name=args.oldmask), args.newmask)

    @needs_init("basic")
    @magic_arguments()
    @argument("nid", default=None)
    @line_magic
    def postprocess(self, line):
        args = parse_argstring(self.postprocess, line)
        if not args.nid:
            node = cnode
        else:
            node = q(Node).get(args.nid)
        if hasattr(node, "event_metadata_changed"):
            node.event_metadata_changed()
            logg.info("called event_metadata_changed")
        if hasattr(node, "event_files_changed"):
            node.event_files_changed()
            logg.info("called event_files_changed")

    @needs_init("basic")
    @line_magic
    def citeproc(self, line):
        import schema.citeproc as citeproc
        citeproc.check_mappings()

    @magic_arguments()
    @argument("state", nargs="?", help="init state. Full initializes everything, basic only important stuff")
    @line_magic
    def init(self, line):
        args = parse_argstring(self.init, line)
        new_state = args.state
        if new_state == "basic":
            initmodule.basic_init()
        elif new_state == "full":
            # drop reassignment warnings because we want to reassign node classes when plugins are loaded later, for example
            warnings.filterwarnings("ignore", "Reassigning polymorphic.*")
            initmodule.full_init()
        else:
            print("current init state is: " + initmodule.get_current_init_state())

    @line_magic
    def purge_nodes(self, line):
        res = delete_unreachable_nodes(synchronize_session=False)
        s.expire_all()
        print(res, "nodes deleted")

    @needs_init("full")
    @magic_arguments()
    @argument("login_name", default=None)
    @argument("password", nargs="?", default=None)
    @line_magic
    def password(self, line):
        args = parse_argstring(self.password, line)

        if args.password is None:
            pw = getpass.getpass()
        else:
            pw = args.password

        user = q(User).filter_by(login_name=args.login_name).one()
        user.change_password(pw)

    @needs_init("full")
    @magic_arguments()
    @argument("login_name", default=None)
    @argument("password", nargs="?", default=None)
    @line_magic
    def check_login(self, line):
        from core.auth import authenticate_user_credentials
        args = parse_argstring(self.check_login, line)

        if args.password is None:
            pw = getpass.getpass()
        else:
            pw = args.password

        user = authenticate_user_credentials(args.login_name, pw, {})

        if user is None:
            user = q(User).filter_by(login_name=args.login_name).scalar()
            if user is None:
                print(u"login failed, no user with login name '{}'!".format(args.login_name))
            else:
                print(u"user with login_name '{}' found, but login failed!".format(args.login_name))
        else:
            print(u"login ok")
        return user


ip = get_ipython()  # @UndefinedVariable


def current_prompt():
    change_indicator = "(changes !) " if s.dirty or s.new or s.deleted else ""
    if cnode:
        name = cnode.name
        name = name if len(name) < 80 else name[:77] + "..."
        prompt = u"{}cnode: {} {} \"{}\"\n[\\#]: ".format(change_indicator, cnode.id, cnode.type, name)
    else:
        prompt = "no cnode [\\#] "
    return prompt


def set_prompt(ip):
    ip.magic("config PromptManager.in_template = current_prompt()")

ip.set_hook("pre_prompt_hook", set_prompt)

# setup custom exception handler for automatic rollbacks on SQLAlchemy errors


def explain(query, analyze=False, pygments_style="native"):
    """Prints EXPLAIN (ANALYZE) query in current session."""
    explained = alchemyext.explain(query, s, analyze)
    from pygments.lexers import PostgresConsoleLexer
    from pygments import highlight

    if IPYTHON_NOTEBOOK:
        from pygments.formatters import HtmlFormatter
        formatter = HtmlFormatter
    else:
        from pygments.formatters import Terminal256Formatter
        formatter = Terminal256Formatter

    explained = highlight(
        explained,
        PostgresConsoleLexer(),
        formatter(style=pygments_style))

    if IPYTHON_NOTEBOOK:
        formatted_statement = db.statement_history.format_statement(
            db.statement_history.last_statement,
            formatter_cls=HtmlFormatter)
        from IPython.display import HTML
        return HTML(
            "<style>" +
            HtmlFormatter().get_style_defs('.highlight') +
            "</style>" +
            formatted_statement +
            "<br>" +
            explained)
    else:
        # strip EXPLAIN (ANALYZE)
        stmt_start = 16 if analyze else 8
        stmt = db.statement_history.last_statement[stmt_start:]
        formatted_statement = db.statement_history.format_statement(stmt)
        print()
        print(formatted_statement)
        print(explained)


def handle_sqla_exception(self, etype, value, tb, tb_offset=None):
    from core import db
    db.session.rollback()
    self.showtraceback((etype, value, tb), tb_offset=0)
    stb = self.InteractiveTB.structured_traceback(
        (etype, value, tb), tb_offset=tb_offset)
    return stb

ip.set_custom_exc((SQLAlchemyError,), handle_sqla_exception)

try:
    from sql.magic import SqlMagic
except ImportError:
    print("SQL magic not found! You should install the IPython sql extension: pip install ipython-sql")
    SQLMagics = None
else:
    @magics_class
    class SQLMagics(SqlMagic):

        """Some additions to ipython-sql, could be merged"""

        @needs_local_scope
        @line_magic("select")
        def select(self, line, cell='', local_ns={}):
            return self.execute("SELECT " + line, cell, local_ns)

        @needs_local_scope
        @line_magic("delete")
        def delete(self, line, cell='', local_ns={}):
            return self.execute("DELETE " + line, cell, local_ns)

        @needs_local_scope
        @line_magic("insert")
        def insert(self, line, cell='', local_ns={}):
            return self.execute("INSERT " + line, cell, local_ns)

        @needs_local_scope
        @line_magic("update")
        def update(self, line, cell='', local_ns={}):
            return self.execute("UPDATE " + line, cell, local_ns)

        @needs_local_scope
        @line_magic("expl")
        def explain_analyze(self, line, cell='', local_ns={}):
            return self.execute("EXPLAIN ANALYZE " + line, cell, local_ns)


def load_ipython_extensions(ip):
    ip.register_magics(MediatumMagics)
    if SQLMagics:
        ip.register_magics(SqlMagic)
        ip.register_magics(SQLMagics)
        ip.magic("sql {SQLMAGICS_CONNECTION_FACTORY()}")

load_ipython_extensions(ip)

ip.magic("autocall 1")
