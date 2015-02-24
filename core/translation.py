"""
 mediatum - a multimedia content repository

 Copyright (C) 2007 Arne Seifert <seiferta@in.tum.de>
 Copyright (C) 2007 Matthias Kramm <kramm@in.tum.de>
 Copyright (C) 2011 Peter Heckl <heckl@ub.tum.de>

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
from . import config
import os
import stat
import time
import thread
import codecs
from utils.strings import ensure_unicode_returned


class _POFile:
    filedates = {}

    def __init__(self, filenames):
        self.lock = thread.allocate_lock()
        self.filenames = filenames
        self.map = {}
        self.lastchecktime = None
        for fil in self.filenames:
            self.loadFile(fil)

    def loadFile(self, filename):
        self.filedates[filename] = os.stat(filename)[stat.ST_MTIME]
        self.lastchecktime = time.time()

        with codecs.open(filename, "rb", encoding='utf8') as fi:
            id = None
            for line in fi.readlines():
                if line.startswith("msgid"):
                    id = line[5:].strip()
                    if id[0] == '"' and id[-1] == '"':
                        id = id[1:-1]
                elif line.startswith("msgstr"):
                    text = line[6:].strip()
                    if text[0] == '"' and text[-1] == '"':
                        text = text[1:-1]
                    self.map[id] = text

    def getTranslation(self, key):
        self.lock.acquire()
        try:
            if self.lastchecktime + 10 < time.time():
                self.lastchecktime = time.time()
                for fil in self.filenames:
                    if os.stat(fil)[stat.ST_MTIME] != self.filedates[fil]:
                        self.loadFile(fil)
        finally:
            self.lock.release()
        return self.map[key]

    def addKeys(self, items):
        for item in items:
            if item[0] not in self.map.keys():
                self.map[item[0]] = item[1]

    def addFilename(self, filepath):
        if filepath not in self.filenames:
            self.filenames.append(filepath)

lang2po = {}
addlangitems = {}
addlangfiles = []


@ensure_unicode_returned(silent=True)
def translate(key, language=None, request=None):
    if request and not language:
        language = lang(request)

    if not language:
        return "?%s?" % key

    if language not in lang2po:
        plist = []
        i18dir = os.path.join(config.basedir, "i18n")
        for root, dirs, files in os.walk(i18dir, topdown=True):
            for n in [f for f in files if f.endswith("%s.po" % language)]:
                plist.append(os.path.join(i18dir, n))

        for f in addlangfiles:
            if os.path.exists(f):
                plist.append(f)

        if not plist:
            return key

        lang2po[language] = _POFile(plist)

    try:
        pofile = lang2po[language]
        return pofile.getTranslation(key)
    except KeyError:
        # try additional keys
        try:
            return addlangitems[language][key]
        except KeyError:
            return key


def addLabels(labels={}):
    for key in labels:
        if key not in addlangitems.keys():
            addlangitems[key] = {}

        for item in labels[key]:
            addlangitems[key][item[0]] = item[1]


def addPoFilepath(filepath=[]):
    for f in filepath:
        if f not in addlangfiles:
            addlangfiles.append(f)


def lang(req):
    if "change_language" in req.params and req.params["change_language"]:
        req.session["language"] = req.params["change_language"]
        return req.session["language"]
    elif "language" in req.session and req.session["language"]:
        return req.session["language"]

    allowed_languages = config.get("i18n.languages", "en").split(",")
    if "Accept-Language" in req.request_headers:
        languages = req.request_headers["Accept-Language"]
        for language in languages.split(";"):
            if language and language in allowed_languages:
                req.session["language"] = language
                return language
    if allowed_languages and allowed_languages[0]:
        req.session["language"] = allowed_languages[0]
        return allowed_languages[0]
    else:
        return "en"


def switch_language(req, language):
    allowed_languages = config.get("i18n.languages", "en").split(",")
    if language is None and len(allowed_languages) > 0:
        language = allowed_languages[0]
    elif language not in allowed_languages:
        raise "Language %s not configured" % language
    req.session["language"] = language


def t(target, key):
    if isinstance(target, basestring):
        return translate(key, language=target)
    else:
        return translate(key, request=target)


def getDefaultLanguage():
    return config.get("i18n.languages").split(",")[0].strip()
