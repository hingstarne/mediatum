#!/usr/bin/python
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
from __future__ import print_function
import logging
import os
import sys
import codecs
import tempfile

logg = logging.getLogger(__name__)

basedir = os.path.abspath(__file__).rsplit(os.sep, 2)[0]
# append our own fallback lib directory
sys.path.append(os.path.join(basedir, "external"))

#: set to True in initialize() if no config file was found
is_default_config = None
#: holds the loaded / default config values
settings = None
#: parsed form of the config key 'i18n.languages' (list)
languages = None


class ConfigException(Exception):
    pass


def get_default_data_dir():
    home = os.path.expanduser("~")
    default_data_dir = os.path.join(home, "mediatum_data")
    return default_data_dir


def get_config_filepath():
    """Looks for a config file and returns its path if found, in the following order:
    1. MEDIATUM_CONFIG env var
    3. <mediatum_install_dir>/mediatum.cfg (for example, the git working dir in development)
    2. ~/.config/mediatum/mediatum.cfg
    4. None (use default config)
    """

    env_config_filepath = os.getenv("MEDIATUM_CONFIG")
    if env_config_filepath:
        return env_config_filepath

    basedir_config_filepath = os.path.join(basedir, "mediatum.cfg")
    if os.path.exists(basedir_config_filepath):
        return basedir_config_filepath

    home_config_filepath = os.path.join(os.path.expanduser("~/.config/mediatum"), "mediatum.cfg")
    if os.path.exists(home_config_filepath):
        return home_config_filepath


def get(key, default=None):
    return settings.get(key, default)


def get_bool(key, default=None):
    val = get(key)
    if not val:
        return default

    if val in ("true", "True", "yes", "Yes"):
        return True
    elif val in ("false", "False", "no", "No"):
        return False
    else:
        raise ConfigException("boolean config value must be true|false, True|False, yes|no or Yes|No")


def getsubset(prefix):
    options = {}
    for k, v in settings.items():
        if k.startswith(prefix):
            k = k[len(prefix):]
            if k[0] == '.':
                k = k[1:]
            options[k] = v
    return options


def resolve_datadir_path(path):
    """Resolves paths relative to the datadir location"""
    return os.path.join(get("paths.datadir"), path)


def _read_ini_file(basedir, filepath):
    lineno = 0
    params = {}

    with codecs.open(filepath, "rb", encoding='utf8') as fi:
        module = ""
        for line in fi.readlines():
            lineno = lineno + 1
            # remove comments
            hashpos = line.find("#")
            if hashpos >= 0:
                line = line[0:hashpos]
            # remove whitespace
            line = line.strip()

            if line == "":
                pass  # skip empty line
            elif line[0] == '[':
                if line[-1] != ']':
                    raise ValueError("Syntax error in line {} of file {}:\n{}".format(lineno, filepath, line))
                module = line[1:-1]
            else:
                equals = line.find("=")
                if equals < 0:
                    raise ValueError("Syntax error in line {} of file {}:\n{}".format(lineno, filepath, line))
                key = module + "." + line[0:equals].strip()
                value = line[equals + 1:].strip()
                if(len(value) and value[0] == '\'' and value[-1] == '\''):
                    value = value[1:-1]
                params[key] = value

    # add the filepath from where the config was loaded.
    # This could differ from get_config_filepath() called at a later time, but that's quite unrealistic ;)
    params["config.filepath"] = filepath
    return params


def check_create_dir(dirpath, label):
    """Checks if dir with `dirpath` already exists and creates it if it doesn't exists.
    :param dirpath: path of directory
    :param label: short, readable directory description to show in messages
    """
    dirpath = os.path.expanduser(dirpath)

    if not os.path.isabs(dirpath):
        print("CONFIG ERROR 1, path must be absolute: {} ({})".format(dirpath, label))
        sys.exit(1)

    if not os.path.exists(dirpath):
        try:
            os.mkdir(dirpath)
        except OSError as e:
            print("CONFIG ERROR 2, couldn't create directory '{}' ({}): {}".format(dirpath, label, e.strerror))
            sys.exit(2)

        print("created directory '{}' ({})".format(dirpath, label))

    elif not os.path.isdir(dirpath):
        print("CONFIG ERROR 3, path is not a directory: '{}' ({})".format(dirpath, label))
        sys.exit(3)
    else:
        print("found dir '{}' ({})".format(label, dirpath))


def set_default_values():
    if not "paths.datadir" in settings:
        settings["paths.datadir"] = get_default_data_dir()

    if not "paths.tempdir" in settings:
        settings["paths.tempdir"] = tempfile.gettempdir()


def expand_paths():
    for confkey in ["paths.datadir", "paths.tempdir", "logging.file"]:
        if confkey in settings:
            settings[confkey] = os.path.expanduser(settings[confkey])


def fix_dirpaths():
    for confkey in ["paths.datadir", "paths.tempdir"]:
        if confkey in settings:
            # we need the trailing slash because concatenation is used in some places in the codebase.
            # XXX: remove this when all concatenations are replaced by os.path.join()!
            if not settings[confkey].endswith("/"):
                settings[confkey] += "/"


def initialize(config_filepath=None):
    if not config_filepath:
        config_filepath = get_config_filepath()

    global settings, languages, is_default_config

    if config_filepath is not None:
        print("using config file at", config_filepath)
        settings = _read_ini_file(basedir, config_filepath)
        is_default_config = False
    else:
        print("WARNING: config file", config_filepath, "not found, using default test config!")
        settings = {}
        is_default_config = True

    set_default_values()
    expand_paths()
    fix_dirpaths()

    languages = [lang.strip() for lang in settings.get("i18n.languages", "en").split(",") if lang.strip()]

    # create dirs if neccessary
    data_path = settings.get("paths.datadir")

    check_create_dir(data_path, "datadir")
    check_create_dir(os.path.join(data_path, "html"), "datadir/html")
    check_create_dir(settings.get("paths.tempdir"), "tempdir")
    check_create_dir(os.path.join(data_path, "incoming"), "incoming")

    # extract log dir from log file path and create it if neccessary

    log_filepath = settings.get("logging.file")
    if log_filepath:
        log_dirpath = os.path.dirname(log_filepath)
        check_create_dir(log_dirpath, "dir for logging.file")


def check_create_test_db_dir():
    data_path = settings.get("paths.datadir", get_default_data_dir())
    dirpath = os.path.join(data_path, "test_db")
    check_create_dir(dirpath, "datadir/test_db")
    return dirpath

#
# resolve given filename to correct path/file
#


def resolve_filename(filename):
    templatepath = settings.get("template.path", "")
    templatename = settings.get("template.name", None)
    if templatepath.startswith("/") or templatepath.startswith("\\"):
        pathlist = [templatepath]
    else:
        pathlist = [basedir, templatepath]
    if templatename:
        pathlist += [templatename]
    pathlist += [filename]

    newname = os.path.join(*pathlist)
    if os.path.exists(newname):
        return newname
    else:
        if filename.find("admin_") >= 0:
            return pathlist[0] + "/admin/template/" + filename
        elif filename.startswith("m_"):
            return pathlist[0] + "/metatypes/" + filename
    return filename
