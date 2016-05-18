"""
 mediatum - a multimedia content repository

 Copyright (C) 2007 Arne Seifert <seiferta@in.tum.de>
 Copyright (C) 2007 Matthias Kramm <kramm@in.tum.de>

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from warnings import warn
import core.config as config


class UserMixin(object):

    """Provides legacy methods for user objects.
    """

    def getName(self):
        warn("deprecated, use User.display_name or User.login_name instead", DeprecationWarning)
        return self.display_name or self.login_name

    def getGroups(self):
        warn("deprecated, use User.groups instead", DeprecationWarning)
        return self.groups

    def getLastName(self):
        warn("deprecated, use User.lastname instead", DeprecationWarning)
        return self.lastname

    def setLastName(self, value):
        warn("deprecated, use User.lastname instead", DeprecationWarning)
        self.lastname = value

    def getFirstName(self):
        warn("deprecated, use User.firstname instead", DeprecationWarning)
        return self.firstname

    def setFirstName(self, value):
        warn("deprecated, use User.firstname instead", DeprecationWarning)
        self.firstname = value

    def getTelephone(self):
        warn("deprecated, use User.telephone instead", DeprecationWarning)
        return self.telephone

    def setTelephone(self, value):
        warn("deprecated, use User.telephone instead", DeprecationWarning)
        self.telephone = value

    def getComment(self):
        warn("deprecated, use User.comment instead", DeprecationWarning)
        return self.comment

    def setComment(self, value):
        warn("deprecated, use User.comment instead", DeprecationWarning)
        self.comment = value

    def getEmail(self):
        warn("deprecated, use User.email instead", DeprecationWarning)
        return self.email

    def setEmail(self, m):
        warn("deprecated, use User.email instead", DeprecationWarning)
        self.email = m

    def getPassword(self):
        raise NotImplementedError("does not work anymore!")

    def setPassword(self, p):
        warn("deprecated, use User.password instead", DeprecationWarning)
        raise NotImplementedError("does not work anymore!")

    def inGroup(self, id):
        warn("deprecated, use User.groups instead", DeprecationWarning)
        return id in self.group_ids

    def getOption(self):
        raise NotImplementedError("obsolete, use User.can_change_password")

    def setOption(self, o):
        raise NotImplementedError("obsolete, use User.can_change_password")

    def isGuest(self):
        return self.name == config.get("user.guestecser")

    def isAdmin(self):
        warn("deprecated, use User.is_admin instead", DeprecationWarning)
        return self.is_admin

    def isEditor(self):
        warn("deprecated, use User.is_editor instead", DeprecationWarning)
        return self.is_editor

    def isWorkflowEditor(self):
        warn("deprecated, use User.is_workflow_editor instead", DeprecationWarning)
        return self.is_workflow_editor

    def stdPassword(self):
        raise NotImplementedError("no standard passwords!")

    def resetPassword(self, newPwd):
        warn("deprecated, use User.password instead", DeprecationWarning)

    def setUserType(self, value):
        raise NotImplementedError("obsolete, use User.authenticator")

    def getUserType(self):
        raise NotImplementedError("obsolete, use User.authenticator")

    def setOrganisation(self, value):
        warn("deprecated, use User.organisation instead", DeprecationWarning)
        self.set("organisation", value)

    def getOrganisation(self):
        warn("deprecated, use User.organisation instead", DeprecationWarning)
        return self.organisation

    def canChangePWD(self):
        raise NotImplementedError("later!")
        if self.isAdmin():
            return 0
        if self.getUserType() == "users":
            return "c" in self.getOption()
        else:
            from core.users import authenticators
            return authenticators[self.getUserType()].canChangePWD()

    def getUserID(self):
        warn("deprecated, use User.id instead", DeprecationWarning)
        return self.id


class GuestUser(UserMixin):

    """
    This is a lame attempt at caching the information for the guest user ;)
    Many normal user operations will fail, but it should be sufficient for get_guest_user().
    GuestUser.get_db_object() returns the proper database user object.
    """

    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()

        return cls._instance

    def __init__(self):

        db_obj = self.get_db_object()
        self.__dict__.update(db_obj.to_dict())

        for prop in ("group_ids", "is_editor", "is_admin", "is_workflow_editor",
                     "hidden_edit_functions", "upload_dir", "trash_dir"):
            setattr(self, prop, getattr(db_obj, prop))

    def get_db_object(self):
        from core import User
        from core import db
        return db.query(User).filter_by(login_name=config.get("user.guestuser", u"guest")).one()
