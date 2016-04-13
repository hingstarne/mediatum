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
import sys
sys.path.append('.')
import logging
import os
import subprocess
import exiftool
from utils.date import parse_date
from utils.date import validateDate
from utils.date import format_date
from utils.strings import ensure_unicode
from core import config
import collections
logger = logging.getLogger('editor')


def get_wanted_iptc_tags():
    '''
        Returns a dictionary [iptc_Tagname:size]
        from supported IPTC tags.
        :return: dictionary
    '''
    return collections.OrderedDict(sorted({
        'iptc_ActionAdvised': 'ActionAdvised |2',
        'iptc_ApplicationRecordVersion': 'ApplicationRecordVersion |5',
        'iptc_AudioType': 'AudioType |2',
        'iptc_AudioSamplingRate': 'AudioSamplingRate |6',
        'iptc_AudioSamplingResolution': 'AudioSamplingResolution |2',
        'iptc_AudioDuration': 'AudioDuration |6',
        'iptc_AudioOutcue': 'AudioOutcue |64',
        'iptc_By-line': 'By-line |32',
        'iptc_By-lineTitle': 'By-lineTitle |32',
        'iptc_Caption-Abstract': 'Caption-Abstract |2000',
        'iptc_CatalogSets': 'CatalogSets |256',
        'iptc_Category': 'Category |3',
        'iptc_City': 'City |32',
        'iptc_ClassifyState': 'ClassifyState |64',
        'iptc_Contact': 'Contact |128',
        'iptc_ContentLocationCode': 'ContentLocationCode |3',
        'iptc_ContentLocationName': 'ContentLocationName |64',
        'iptc_Country-PrimaryLocationCode': 'Country-PrimaryLocationCode |3',
        'iptc_Country-PrimaryLocationName': 'Country-PrimaryLocationName |64',
        'iptc_CopyrightNotice': 'CopyrightNotice |128',
        'iptc_Credit': 'Credit |32',
        'iptc_DateCreated': 'DateCreated |8',
        'iptc_DocumentNotes': 'DocumentNotes |1024',
        'iptc_DocumentHistory': 'DocumentHistory |256',
        'iptc_DigitalCreationDate': 'DigitalCreationDate |8',
        'iptc_DigitalCreationTime': 'DigitalCreationTime |11',
        'iptc_EditStatus': 'EditStatus |64',
        'iptc_EditorialUpdate': 'EditorialUpdate |2',
        'iptc_ExifCameraInfo': 'ExifCameraInfo |4096',
        'iptc_ExpirationDate': 'ExpirationDate |8',
        'iptc_ExpirationTime': 'ExpirationTime |11',
        'iptc_FixtureIdentifier': 'FixtureIdentifier |32',
        'iptc_Headline': 'Headline |256',
        'iptc_ImageType': 'ImageType |2',
        'iptc_ImageOrientation': 'ImageOrientation |1',
        'iptc_JobID': 'JobID |64',
        'iptc_Keywords': 'Keywords |64',
        'iptc_LanguageIdentifier': 'LanguageIdentifier |3',
        'iptc_LocalCaption': 'LocalCaption |256',
        'iptc_MasterDocumentID': 'MasterDocumentID |256',
        'iptc_ObjectAttributeReference': 'ObjectAttributeReference |68',
        'iptc_ObjectCycle': 'ObjectCycle |1',
        'iptc_ObjectName': 'ObjectName |64',
        'iptc_ObjectPreviewFileFormat': 'ObjectPreviewFileFormat |29',
        'iptc_ObjectPreviewFileVersion': 'ObjectPreviewFileVersion |5',
        'iptc_ObjectPreviewData': 'ObjectPreviewData |256000',
        'iptc_ObjectTypeReference': 'ObjectTypeReference |67',
        'iptc_OriginalTransmissionReference': 'OriginalTransmissionReference |32',
        'iptc_OriginatingProgram': 'OriginatingProgram |32',
        'iptc_OwnerID': 'OwnerID |128',
        'iptc_Prefs': 'Prefs |64',
        'iptc_ProgramVersion': 'ProgramVersion |10',
        'iptc_Province-State': 'Province-State |32',
        'iptc_RasterizedCaption': 'RasterizedCaption |7360',
        'iptc_ReferenceService': 'ReferenceService |10',
        'iptc_ReferenceDate': 'ReferenceDate |8',
        'iptc_ReferenceNumber': 'ReferenceNumber |8',
        'iptc_ReleaseDate': 'ReleaseDate |8',
        'iptc_ReleaseTime': 'ReleaseTime |11',
        'iptc_SimilarityIndex': 'SimilarityIndex |32',
        'iptc_ShortDocumentID': 'ShortDocumentID |64',
        'iptc_SpecialInstructions': 'SpecialInstructions |256',
        'iptc_SubjectReference': 'SubjectReference |236',
        'iptc_Sub-location': 'Sub-location |32',
        'iptc_Source': 'Source |32',
        'iptc_SupplementalCategories': 'SupplementalCategories |32',
        'iptc_TimeCreated': 'TimeCreated |11',
        'iptc_Urgency': 'Urgency |1',
        'iptc_UniqueDocumentID': 'UniqueDocumentID |128',
        'iptc_Writer-Editor': 'Writer-Editor |32'
    }.items()))


def get_iptc_tags(image_path, tags=None):
    """
        get the IPTC tags/values from a given
        image file

        :rtype : object
        :param image_path: path to the image file
        :param tags: dictionary with wanted iptc tags
        :return: dictionary with tag/value
    """
    if tags == None:
        tags = get_wanted_iptc_tags()

    if not isinstance(tags, dict):
        logger.info('No Tags to read.')
        return

    if image_path is None:
        logger.info('No file path for reading iptc.')
        return

    if not os.path.exists(image_path):
        logger.info('Could not read IPTC metadata from non existing file.')
        return

    if os.path.basename(image_path).startswith('-'):
        logger.info('Will not read IPTC metadata to files starting with a hyphen, caused by exiftool security issues.')
        return

    # fetch metadata dict from exiftool
    exiftool_exe = config.get("external.exiftool", "exiftool")
    with exiftool.ExifTool(exiftool_exe) as et:
        iptc_metadata = et.get_metadata(image_path)

    ret = {}

    for iptc_tag in tags.keys():
        key = iptc_tag.replace('iptc_', 'IPTC:')
        tag = iptc_tag.split('iptc_')[-1]
        if key in iptc_metadata.keys():
            value = iptc_metadata[key]

            # format dates for date fields
            if tag == 'DateCreated':
                if validateDate(parse_date(value, format='%Y:%m:%d')):
                    value = format_date(parse_date(value, format='%Y:%m:%d'))
                else:
                    logger.error('Could not validate: {} as date value.'.format(value))

            # join lists to strings
            if isinstance (value, list):
                value = ';'.join(value)

            ret[tag] = ensure_unicode(value, silent=True)

    logger.info('{} read from file.'.format(ret))

    return ret


def write_iptc_tags(image_path, tag_dict):
    '''
        Writes iptc tags with exiftool to a
        given image path (overwrites the sourcefile).
        Emty tags (tagname='') will be removed.

        :param image_path: imaqe path to write
        :param tag_dict: tagname / tagvalue

        :return  status
    '''
    try:
        subprocess.call(['exiftool'])
    except OSError:
        logger.error('No exiftool installed.')
        return

    image_path = os.path.abspath(image_path)

    if not os.path.exists(image_path):
        logger.info(u'Image {} for writing IPTC metadata does not exist.'.format(image_path))
        return

    if not isinstance(tag_dict, dict):
        logger.error(u'No dictionary of tags.')
        return

    command_list = [u'exiftool']
    command_list.append(u'-overwrite_original')

    command_list.append(u'-charset')
    command_list.append(u'iptc=UTF8')

    command_list.append(image_path)

    for tag_name in tag_dict.keys():
        tag_value = tag_dict[tag_name]

        if tag_dict[tag_name] == '':
            command_list.append(u'-{}='.format(tag_name))

        elif tag_name == u'DateCreated':
            if validateDate(parse_date(tag_value.split('T')[0], format='%Y-%m-%d')):
                tag_value = format_date(parse_date(tag_value.split('T')[0], format='%Y-%m-%d'), '%Y:%m:%d')
            else:
                logger.error(u'Could not validate {}.'.format(tag_value))

        command_list.append(u'-charset iptc=UTF8')
        command_list.append(u'-{}={}'.format(tag_name, tag_value))

    logger.info(u'Command: {} will be executed.'.format(command_list))
    process = subprocess.Popen(command_list, stdout=subprocess.PIPE)
    output, error = process.communicate()

    if error is not None:
        logger.info('Exiftool output: {}'.format(output))
        logger.error('Exiftool error: {}'.format(error))
