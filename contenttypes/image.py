#!/usr/bin/python
# -*- coding: utf-8 -*-
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
import logging
import os
from subprocess import check_call
import tempfile
from PIL import Image as PILImage, ImageDraw

from core import config, File, db
from core.attachment import filebrowser
from core.translation import t
from core.styles import getContentStyles
from core.transition.postgres import check_type_arg_with_schema
from contenttypes.data import Content
from utils.utils import splitfilename, isnewer, iso2utf8, utf8_decode_escape

import lib.iptc.IPTC



logg = logging.getLogger(__name__)

# XXX: some refactoring has to be done for the next two methods, many similarities ...

def make_thumbnail_image(src_filepath, dest_filepath):
    """make thumbnail (jpeg 128x128)"""

    if isnewer(dest_filepath, src_filepath):
        return

    pic = PILImage.open(src_filepath)
    temp_jpg_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)

    try:
        temp_jpg_file.close()
        tmpjpg = temp_jpg_file.name

        convert = config.get("external.convert", "convert")
        if pic.mode == "CMYK" and (src_filepath.endswith("jpg") or src_filepath.endswith("jpeg")) or pic.mode in ["P", "L"]:
            check_call([convert, "-quality", "100", "-draw", 'rectangle 0,0 1,1', src_filepath, tmpjpg])
            pic = PILImage.open(tmpjpg)

        pic.load()
        width = pic.size[0]
        height = pic.size[1]

        if width > height:
            newwidth = 128
            newheight = height * newwidth / width
        else:
            newheight = 128
            newwidth = width * newheight / height

        pic = pic.resize((newwidth, newheight), PILImage.ANTIALIAS)

        try:
            im = PILImage.new(pic.mode, (128, 128), (255, 255, 255))
        except:
            im = PILImage.new("RGB", (128, 128), (255, 255, 255))

        x = (128 - newwidth) / 2
        y = (128 - newheight) / 2
        im.paste(pic, (x, y, x + newwidth, y + newheight))

        draw = ImageDraw.ImageDraw(im)
        draw.line([(0, 0), (127, 0), (127, 127), (0, 127), (0, 0)], (128, 128, 128))

        im = im.convert("RGB")
        im.save(dest_filepath, "jpeg")
    finally:
        os.unlink(tmpjpg)


def make_presentation_image(src_filepath, dest_filepath):

    if isnewer(dest_filepath, src_filepath):
        return

    pic = PILImage.open(src_filepath)
    temp_jpg_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)

    try:
        temp_jpg_file.close()
        tmpjpg = temp_jpg_file.name

        convert = config.get("external.convert", "convert")
        if pic.mode == "CMYK" and (src_filepath.endswith("jpg") or src_filepath.endswith("jpeg")) or pic.mode in ["P", "L"]:
            check_call([convert, "-quality", "100", "-draw", 'rectangle 0,0 1,1', src_filepath, tmpjpg])
            pic = PILImage.open(tmpjpg)

        pic.load()

        width = pic.size[0]
        height = pic.size[1]

        resize = 1
        if resize:
            # resize images only if they are actually too big
            if width > height:
                newwidth = 320
                newheight = height * newwidth / width
            else:
                newheight = 320
                newwidth = width * newheight / height
            pic = pic.resize((newwidth, newheight), PILImage.ANTIALIAS)

        try:
            pic.save(dest_filepath, "jpeg")
        except IOError:
            pic.convert('RGB').save(dest_filepath, "jpeg")

    finally:
        os.unlink(tmpjpg)


def make_original_png_image(src_filepath, dest_filepath):
    """Create a PNG with filename `dest_filepath` from a file at `src_filepath`
    """
    assert dest_filepath.endswith(".png")
    convert = config.get("external.convert", "convert")
    check_call([convert, src_filepath, dest_filepath])


def getImageDimensions(image):
    pic = PILImage.open(image)
    width = pic.size[0]
    height = pic.size[1]
    return width, height


def getJpegSection(image, section):  # section character
    data = ""
    try:
        with open(image, "rb") as fin:
            done = False
            capture = False

            while not done:
                c = fin.read(1)
                if capture and ord(c) != 0xFF and ord(c) != section:
                    data += c

                if ord(c) == 0xFF:  # found tag start
                    if capture:
                        done = True

                    c = fin.read(1)
                    if ord(c) == section:  # found tag
                        capture = True
    except:
        logg.exception("exception in getJpegSection")
        data = ""
    return data


def dozoom(self):
    b = 0
    svg = 0
    for file in self.files:
        if file.filetype == "zoom":
            b = 1
        if file.base_name.lower().endswith('svg') and file.type == "original":
            svg = 1
    if self.get("width") and self.get("height") and (int(self.get("width")) > 2000 or int(self.get("height")) > 2000) and not svg:
        b = 1
    return b


""" image class for internal image-type """


@check_type_arg_with_schema
class Image(Content):

    @classmethod
    def get_default_edit_menu_tabs(cls):
        return "menulayout(view);menumetadata(metadata;files;admin;lza);menuclasses(classes);menusecurity(acls)"

    @classmethod
    def get_sys_filetypes(cls):
        return [u"original", u"thumb", u"image", u"presentation", u"zoom"]

    @classmethod
    def get_upload_filetype(cls):
        return u"original"

    @property
    def zoom_available(self):
        zoom_file = self.files.filter_by(filetype=u"zoom").scalar()
        return zoom_file is not None

    # prepare hash table with values for TAL-template
    def _prepareData(self, req):
        obj = super(Image, self)._prepareData(req)
        if obj["deleted"]:
            # no more processing needed if this object version has been deleted
            # rendering has been delegated to current version
            return obj

        node = self

        tif = ""
        can_see_original = self.has_data_access()

        if can_see_original:
            archive_path = self.system_attrs.get(u"archive_path")
            if archive_path:
                tif = u"file/{}/{}".format(self.id, archive_path)
            else:
                original_file = self.files.filter_by(filetype=u"original").scalar()
                if original_file is not None:
                    tif = self.base_name

        files, sum_size = filebrowser(self, req)

        obj['attachment'] = files
        obj['sum_size'] = sum_size
        obj['tif'] = tif
        obj['zoom'] = dozoom(node)
        obj['tileurl'] = u"/tile/{}/".format(node.id)
        obj['canseeoriginal'] = can_see_original
        obj['originallink'] = u"getArchivedItem('{}/{}')".format(node.id, tif)
        obj['archive'] = node.system_attrs.get(u"archive_type", "")

        full_style = req.args.get("style", "full_standard")
        if full_style:
            obj['style'] = full_style

        return obj

    """ format big view with standard template """
    def show_node_big(self, req, template="", macro=""):
        if not template:
            styles = getContentStyles("bigview", contenttype=self.type)
            if len(styles) >= 1:
                template = styles[0].getTemplate()
        return req.getTAL(template, self._prepareData(req), macro)

    """ make a copy of the svg file in png format """
    def svg_to_png(self, filename, imgfile):
        # convert svg to png (imagemagick + ghostview)
        os.system("convert -alpha off -colorspace RGB %s -background white %s" % (filename, imgfile))

    """ postprocess method for object type 'image'. called after object creation """
    def event_files_changed(self):
        """ postprocess method for object type 'image'. called after object creation """
        logg.debug("Postprocessing node %s", self.id)
        for f in self.files:
            if f.base_name.lower().endswith('svg'):
                self.svg_to_png(f.abspath, f.abspath[:-4] + ".png")
                self.files.remove(f)
                self.files.append(File(f.abspath, "original", f.mimetype))
                self.files.append(File(f.abspath, "image", f.mimetype))
                self.files.append(File(f.abspath[:-4] + ".png", "tmppng", "image/png"))
                break
        orig = 0
        thumb = 0
        for f in self.files:
            if f.type == "original":
                orig = 1
            if f.type == "thumb":
                thumb = 1

        if orig == 0:
            for f in self.files:
                if f.type == "image":

                    if f.mimetype == "image/tiff":
                        # move old file to "original", create a new png to be used as "image"
                        self.files.remove(f)

                        path, ext = splitfilename(f.abspath)
                        pngname = path + ".png"

                        if not os.path.isfile(pngname):
                            make_original_png_image(f.abspath, pngname)

                            width, height = getImageDimensions(pngname)
                            self.set("width", width)
                            self.set("height", height)

                        else:
                            width, height = getImageDimensions(pngname)
                            self.set("width", width)
                            self.set("height", height)

                        self.files.append(File(pngname, "image", "image/png"))
                        self.files.append(File(f.abspath, "original", "image/tiff"))
                        break
                    else:
                        self.files.append(File(f.abspath, "original", f.mimetype))

        # retrieve technical metadata.
        for f in self.files:
            if (f.type == "image" and not f.base_name.lower().endswith("svg")) or f.type == "tmppng":
                width, height = getImageDimensions(f.abspath)
                self.set("origwidth", width)
                self.set("origheight", height)
                self.set("origsize", f.getSize())

                if f.mimetype == "image/jpeg":
                    self.set("jpg_comment", iso2utf8(getJpegSection(f.abspath, 0xFE).strip()))

        if thumb == 0:
            for f in self.files:
                if (f.type == "image" and not f.base_name.lower().endswith("svg")) or f.type == "tmppng":
                    path, ext = splitfilename(f.abspath)

                    thumbname = path + ".thumb"
                    thumbname2 = path + ".thumb2"

                    assert not os.path.isfile(thumbname)
                    assert not os.path.isfile(thumbname2)
                    width, height = getImageDimensions(f.abspath)
                    make_thumbnail_image(f.abspath, thumbname)
                    make_presentation_image(f.abspath, thumbname2)
                    if f.mimetype is None:
                        if f.base_name.lower().endswith("jpg"):
                            f.mimetype = "image/jpeg"
                        else:
                            f.mimetype = "image/tiff"
                    self.files.append(File(thumbname, "thumb", "image/jpeg"))
                    self.files.append(File(thumbname2, "presentation", "image/jpeg"))
                    self.set("width", width)
                    self.set("height", height)

        #fetch unwanted tags to be omitted
        unwanted_attrs = self.unwanted_attributes()

        # Exif
        try:
            from lib.Exif import EXIF
            files = self.files

            for file in files:
                if file.type == "original":
                    with open(file.abspath, 'rb') as f:
                        tags = EXIF.process_file(f)
                        tags.keys().sort()

                    for k in tags.keys():
                        # don't set unwanted exif attributes
                        if any(tag in k for tag in unwanted_attrs):
                            continue
                        if tags[k] != "" and k != "JPEGThumbnail":
                            self.set("exif_" + k.replace(" ", "_"),
                                     utf8_decode_escape(ustr(tags[k])))
                        elif k == "JPEGThumbnail":
                            if tags[k] != "":
                                self.set("Thumbnail", "True")
                            else:
                                self.set("Thumbnail", "False")

        except:
            logg.exception("exception get EXIF attributes")

        if dozoom(self) == 1:
            tileok = 0
            for f in self.files:
                if f.type.startswith("tile"):
                    tileok = 1
            if not tileok and self.get("width") and self.get("height"):
                zoom.getImage(self.id, 1)

        # iptc
        for file in self.files:
            if file.type == "original":

                tags = lib.iptc.IPTC.get_iptc_values(file.abspath, lib.iptc.IPTC.get_wanted_iptc_tags())
                for k in tags.keys():
                    self.attrs[k] = tags[k]


        for f in self.files:
            if f.base_name.lower().endswith("png") and f.type == "tmppng":
                self.files.remove(f)
                break

        db.session.commit()


    def unwanted_attributes(self):
        '''
        Returns a list of unwanted exif tags which are not to be extracted from uploaded images
        @return: list
        '''
        return ['BitsPerSample',
                'IPTC/NAA',
                'WhitePoint',
                'YCbCrCoefficients',
                'ReferenceBlackWhite',
                'PrimaryChromaticities',
                'ImageDescription',
                'StripOffsets',
                'StripByteCounts',
                'CFAPattern',
                'CFARepeatPatternDim',
                'YCbCrSubSampling',
                'Tag',
                'TIFFThumbnail',
                'JPEGThumbnail',
                'Thumbnail_BitsPerSample',
                'GPS',
                'CVAPattern',
                'ApertureValue',
                'ShutterSpeedValue',
                'MakerNote',
                'jpg_comment',
                'UserComment',
                'FlashPixVersion',
                'ExifVersion',
                'Caption',
                'Byline',
                'notice']

    """ list with technical attributes for type image """
    def getTechnAttributes(self):
        return {"Standard": {"creator": "Ersteller",
                             "creationtime": "Erstelldatum",
                             "updateuser": "Update Benutzer",
                             "updatetime": "Update Datum",
                             "updatesearchindex": "Update Suche",
                             "height": "H&ouml;he Thumbnail",
                             "width": "Breite Thumbnail",
                             "faulty": "Fehlerhaft",
                             "workflow": "Workflownummer",
                             "workflownode": "Workflow Knoten",
                             "origwidth": "Originalbreite",
                             "origheight": "Originalh&ouml;he",
                             "origsize": "Dateigr&ouml;&szlig;e"},

                "Exif": {"exif_EXIF_ComponentsConfiguration": "EXIF ComponentsConfiguration",
                         "exif_EXIF_LightSource": "EXIF LightSource",
                         "exif_EXIF_FlashPixVersion": "EXIF FlashPixVersion",
                         "exif_EXIF_ColorSpace": "EXIF ColorSpace",
                         "exif_EXIF_MeteringMode": "EXIF MeteringMode",
                         "exif_EXIF_ExifVersion": "EXIF ExifVersion",
                         "exif_EXIF_Flash": "EXIF Flash",
                         "exif_EXIF_DateTimeOriginal": "EXIF DateTimeOriginal",
                         "exif_EXIF_InteroperabilityOffset": "EXIF InteroperabilityOffset",
                         "exif_EXIF_FNumber": "EXIF FNumber",
                         "exif_EXIF_FileSource": "EXIF FileSource",
                         "exif_EXIF_ExifImageLength": "EXIF ExifImageLength",
                         "exif_EXIF_SceneType": "EXIF SceneType",
                         "exif_EXIF_CompressedBitsPerPixel": "EXIF CompressedBitsPerPixel",
                         "exif_EXIF_ExposureBiasValue": "EXIF ExposureBiasValue",
                         "exif_EXIF_ExposureProgram": "EXIF ExposureProgram",
                         "exif_EXIF_ExifImageWidth": "EXIF ExifImageWidth",
                         "exif_EXIF_DateTimeDigitized": "EXIF DateTimeDigitized",
                         "exif_EXIF_FocalLength": "EXIF FocalLength",
                         "exif_EXIF_ExposureTime": "EXIF ExposureTime",
                         "exif_EXIF_ISOSpeedRatings": "EXIF ISOSpeedRatings",
                         "exif_EXIF_MaxApertureValue": "EXIF MaxApertureValue",

                         "exif_Image_Model": "Image Model",
                         "exif_Image_Orientation": "Image Orientation",
                         "exif_Image_DateTime": "Image DateTime",
                         "exif_Image_YCbCrPositioning": "Image YCbCrPositioning",
                         "exif_Image_ImageDescription": "Image ImageDescription",
                         "exif_Image_ResolutionUnit": "Image ResolutionUnit",
                         "exif_Image_XResolution": "Image XResolution",
                         "exif_Image_Make": "Image Make",
                         "exif_Image_YResolution": "Image YResolution",
                         "exif_Image_ExifOffset": "Image ExifOffset",

                         "exif_Thumbnail_ResolutionUnit": "Thumbnail ResolutionUnit",
                         "exif_Thumbnail_DateTime": "Thumbnail DateTime",
                         "exif_Thumbnail_JPEGInterchangeFormat": "Thumbnail JPEGInterchangeFormat",
                         "exif_Thumbnail_JPEGInterchangeFormatLength": "Thumbnail JPEGInterchangeFormatLength",
                         "exif_Thumbnail_YResolution": "Thumbnail YResolution",
                         "exif_Thumbnail_Compression": "Thumbnail Compression",
                         "exif_Thumbnail_Make": "Thumbnail Make",
                         "exif_Thumbnail_XResolution": "Thumbnail XResolution",
                         "exif_Thumbnail_Orientation": "Thumbnail Orientation",
                         "exif_Thumbnail_Model": "Thumbnail Model",
                         "exif_JPEGThumbnail": "JPEGThumbnail",
                         "Thumbnail": "Thumbnail"}}

    """ fullsize popup-window for image node """
    def popup_fullsize(self, req):
        d = {}
        svg = 0
        if (not self.has_data_access() and not dozoom(self)) or not self.has_read_access():
            req.write(t(req, "permission_denied"))
            return
        zoom_exists = 0
        for file in self.files:
            if file.filetype == "zoom":
                zoom_exists = 1
            if file.base_name.lower().endswith('svg') and file.filetype == "original":
                svg = 1

        d["svg"] = svg
        d["width"] = self.get("origwidth")
        d["height"] = self.get("origheight")
        d["key"] = req.params.get("id", "")
        # we assume that width==origwidth, height==origheight
        d['flash'] = dozoom(self) and zoom_exists
        d['tileurl'] = "/tile/{}/".format(self.id)
        req.writeTAL("contenttypes/image.html", d, macro="imageviewer")

    def popup_thumbbig(self, req):
        if (not self.has_data_access() and not dozoom(self)) or not self.has_read_access():
            req.write(t(req, "permission_denied"))
            return

        thumbbig = None
        for file in self.files:
            if file.filetype == "thumb2":
                thumbbig = file
                break
        if not thumbbig:
            self.popup_fullsize(req)
        else:
            im = PILImage.open(thumbbig.abspath)
            req.writeTAL("contenttypes/image.html", {"filename": '/file/{}/{}'.format(self.id, thumbbig.base_name),
                                                     "width": im.size[0],
                                                     "height": im.size[1]},
                         macro="thumbbig")

    def processImage(self, type="", value="", dest=""):
        import os

        img = None
        for file in self.files:
            if file.filetype == "image":
                img = file
                break

        if img:
            pic = PILImage.open(img.abspath)
            pic.load()

            if type == "percentage":
                w = pic.size[0] * int(value) / 100
                h = pic.size[1] * int(value) / 100

            if type == "pixels":
                if pic.size[0] > pic.size[1]:
                    w = int(value)
                    h = pic.size[1] * int(value) / pic.size[0]
                else:
                    h = int(value)
                    w = pic.size[0] * int(value) / pic.size[1]

            elif type == "standard":
                w, h = value.split("x")
                w = int(w)
                h = int(h)

                if pic.size[0] < pic.size[1]:
                    factor_w = w * 1.0 / pic.size[0]
                    factor_h = h * 1.0 / pic.size[1]

                    if pic.size[0] * factor_w < w and pic.size[1] * factor_w < h:
                        w = pic.size[0] * factor_w
                        h = pic.size[1] * factor_w
                    else:
                        w = pic.size[0] * factor_h
                        h = pic.size[1] * factor_h
                else:
                    factor_w = w * 1.0 / pic.size[0]
                    factor_h = h * 1.0 / pic.size[1]

                    if pic.size[0] * factor_w < w and pic.size[1] * factor_w < h:
                        w = pic.size[0] * factor_h
                        h = pic.size[1] * factor_h
                    else:
                        w = pic.size[0] * factor_w
                        h = pic.size[1] * factor_w

            else:  # do nothing but copy image
                w = pic.size[0]
                h = pic.size[1]

            pic = pic.resize((int(w), int(h)), PILImage.ANTIALIAS)
            if not os.path.isdir(dest):
                os.mkdir(dest)
            pic.save(dest + self.id + ".jpg", "jpeg")
            return 1
        return 0

    def event_metadata_changed(self):
        """ Handles metadata content if changed.
            Creates a 'new' original [old == upload].
        """
        upload_file = None
        original_path = None
        original_file = None

        for f in self.files:
            if f.getType() == 'original':
                original_file = f
                if os.path.exists(f.abspath):
                    original_path = f.abspath
                if os.path.basename(original_path).startswith('-'):
                    return

            if f.type == 'upload':
                if os.path.exists(f.abspath):
                    upload_file = f

        if not original_file:
            logg.info('No original upload for writing IPTC.')
            return

        if not upload_file:
            upload_path = '{}_upload{}'.format(os.path.splitext(original_path)[0], os.path.splitext(original_path)[-1])
            import shutil
            shutil.copy(original_path, upload_path)
            self.files.append(File(upload_path, "upload", original_file.mimetype))
            db.session.commit()

        tag_dict = {}

        for field in self.getMetaFields():
            if field.get('type') == "meta" and field.getValueList()[0] != '' and 'on' in field.getValueList():
                tag_name = field.getValueList()[0].split('iptc_')[-1]

                field_value = self.get('iptc_{}'.format(field.getName()))

                if field.getValueList()[0] != '' and 'on' in field.getValueList():
                    tag_dict[tag_name] = field_value

        lib.iptc.IPTC.write_iptc_tags(original_path, tag_dict)
