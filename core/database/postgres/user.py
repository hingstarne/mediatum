# -*- coding: utf-8 -*-
"""
    :copyright: (c) 2015 by the mediaTUM authors
    :license: GPL3, see COPYING for details
"""
from itertools import chain
import logging

from sqlalchemy import Unicode, Text, Boolean, Table, DateTime, UniqueConstraint, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm.session import object_session
from sqlalchemy_utils.types import EmailType

from core.database.postgres import DeclarativeBase, db_metadata
from core.database.postgres import rel, C
from core.database.postgres import TimeStamp, integer_fk, integer_pk
from core import config
from core.user import UserMixin
from core.usergroup import UserGroupMixin


logg = logging.getLogger(__name__)


class AuthenticatorInfo(DeclarativeBase):

    __tablename__ = "authenticator"

    id = integer_pk()
    name = C(Unicode, nullable=False)
    auth_type = C(Unicode, nullable=False)

    @property
    def authenticator_key(self):
        return (self.auth_type, self.name)

    def __repr__(self):
        return u"AuthenticatorInfo<id: {} key: ({}, {})> ({})".format(self.id, self.name,
                                                                        self.auth_type, object.__repr__(self)).encode("utf8")

    __table_args__ = (UniqueConstraint(name, auth_type),)

user_to_usergroup = Table("user_to_usergroup", db_metadata,
                          integer_fk("user.id", name="user_id", primary_key=True),
                          integer_fk("usergroup.id", name="usergroup_id", primary_key=True)
                          )


class UserGroup(DeclarativeBase, TimeStamp, UserGroupMixin):

    __tablename__ = "usergroup"
    __versioned__ = {}

    id = integer_pk()
    name = C(Unicode, nullable=False, unique=True)
    description = C(Unicode)
    hidden_edit_functions = C(ARRAY(Unicode), server_default="{}")

    is_editor_group = C(Boolean, server_default="false")
    is_workflow_editor_group = C(Boolean, server_default="false")
    is_admin_group = C(Boolean, server_default="false")

    def __repr__(self):
        return u"UserGroup<{} '{}'> ({})".format(self.id, self.name, object.__repr__(self)).encode("utf8")


def create_special_user_dirs():
    from contenttypes import Directory
    return [Directory(u"faulty", attrs={u"system.used_as": u"faulty"}),
            Directory(u"upload", attrs={u"system.used_as": u"upload"}),
            Directory(u"trash", attrs={u"system.used_as": u"trash"})]


class User(DeclarativeBase, TimeStamp, UserMixin):

    __tablename__ = "user"
    __versioned__ = {}

    id = integer_pk()
    login_name = C(Unicode, nullable=False)
    display_name = C(Unicode)

    lastname = C(Unicode)
    firstname = C(Unicode)
    telephone = C(Unicode)
    organisation = C(Unicode)
    comment = C(Unicode)
    email = C(EmailType)
    password_hash = C(String)
    salt = C(String)

    # user activity
    last_login = C(DateTime)
    active = C(Boolean, server_default="true")

    # options
    can_edit_shoppingbag = C(Boolean, server_default="false")
    can_change_password = C(Boolean, server_default="false")

    home_dir_id = integer_fk("node.id")
    private_group_id = integer_fk(UserGroup.id)

    # relationships
    private_group = rel(UserGroup)
    groups = rel(UserGroup, secondary=user_to_usergroup, backref='users')
    home_dir = rel("Directory", foreign_keys=[home_dir_id])

    authenticator_info = rel(AuthenticatorInfo)
    authenticator_id = integer_fk(AuthenticatorInfo.id, nullable=False)

    @property
    def group_ids(self):
        return [g.id for g in self.groups]

    @property
    def is_editor(self):
        return any(g.is_editor_group for g in self.groups)

    @property
    def is_admin(self):
        return any(g.is_admin_group for g in self.groups)

    @property
    def is_workflow_editor(self):
        return any(g.is_workflow_editor_group for g in self.groups)

    @property
    def hidden_edit_functions(self):
        return [f for group in self.groups for f in group.hidden_edit_functions or []]

    @property
    def upload_dir(self):
        from contenttypes import Directory
        if self.home_dir:
            return self.home_dir.children.filter(Directory.a[u"system.used_as"] == u"upload").one()

    @property
    def faulty_dir(self):
        from contenttypes import Directory
        if self.home_dir:
            return self.home_dir.children.filter(Directory.a[u"system.used_as"] == u"faulty").one()

    @property
    def trash_dir(self):
        from contenttypes import Directory
        if self.home_dir:
            return self.home_dir.children.filter(Directory.a[u"system.used_as"] == u"trash").one()

    def change_password(self, password):
        from core.auth import create_password_hash
        self.password_hash, self.salt = create_password_hash(password)

    def create_home_dir(self):
        from core import db
        from contenttypes.container import Directory, Home
        homedir_name = self.login_name
        home = Directory(homedir_name)
        home.children.extend(create_special_user_dirs())
        # XXX: add access rules
        db.session.query(Home).one().children.append(home)
        self.home_dir = home
        logg.info("created home dir for user '%s (id: %s)'", self.login_name, self.id)
        return home

    def __repr__(self):
        return u"User<{} '{}'> ({})".format(self.id, self.login_name, object.__repr__(self)).encode("utf8")

    __table_args__ = (UniqueConstraint(login_name, authenticator_id),)