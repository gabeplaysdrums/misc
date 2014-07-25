"""
PyFlickr utilies module
"""

import json
from csv import DictWriter
import os
from datetime import datetime

API_KEY = 'f5b40cdc2dfac381aefcfd48687ddaba'
API_SECRET = '30bce1a79b59ea4a'
PYFLICKR_TAG = 'PyFlickr'
FLICKR_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
PYFLICKR_FILEMETA_TOKEN = '[!PyFlickr.filemeta]'

def photo_description(filemeta):
    return '\n'.join([
        PYFLICKR_FILEMETA_TOKEN,
        json.dumps(filemeta),
        PYFLICKR_FILEMETA_TOKEN
    ])

def make_csv_writer(csvfile):
    return DictWriter(csvfile, extrasaction='ignore', fieldnames=(
        'photo_id',
        'title',
        'relpath',
        'abspath',
        'filehash',
        'created',
        'modified',
        'filesize',
        'exif_original_date',
        'mov_created_date',
        'upload_start',
        'upload_end',
        'date_taken',
        'description',
        'shorturl',
        'url',
        'media',
        'original_format',
        'server',
    ))

def get_uploaded_photos(flickr):
    photos = []
    num_pages = 0
    total = 0
    count = 0
    def fetch(page, num_pages, total, photos, count):
        rsp = flickr.photos_search(user_id='me', per_page=500, page=page)
        if page == 1:
            num_pages = int(rsp.find('photos').get('pages'))
            total = int(rsp.find('photos').get('total'))
        for photo in rsp.find('photos').getchildren():
            title = photo.get('title')
            photo_id = photo.get('id')
            photos.append((photo_id, title))
            count += 1
        return num_pages, total, photos, count
    (num_pages, total, photos, count) = fetch(1, num_pages, total, photos, count)
    for page in range(2, num_pages + 1):
        (num_pages, total, photos, count) = fetch(page, num_pages, total, photos, count)
    assert count == total
    return photos


import exifread

def get_exif_original_date(path):
    if os.path.splitext(path)[1].lower() == '.jpg':
        with open(path, 'rb') as f:
            exif = exifread.process_file(f, details=False, stop_tag='DateTimeOriginal')
            return datetime.strptime(str(exif['EXIF DateTimeOriginal']), '%Y:%m:%d %H:%M:%S')
    return None


import hachoir_core.cmd_line
import hachoir_parser
import hachoir_metadata
import re

def get_mov_created_date(path):
    if os.path.splitext(path)[1].lower() == '.mov':
        filename, realname = hachoir_core.cmd_line.unicodeFilename(path), path
        parser = hachoir_parser.createParser(filename, realname)
        metadata = hachoir_metadata.extractMetadata(parser)
        text = metadata.exportPlaintext()
        for line in text:
            m = re.search(r'Creation date:\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})', line, re.I)
            if m:
                return datetime.strptime(str(m.group(1)) + ' ' + str(m.group(2)), '%Y-%m-%d %H:%M:%S')
    return None

def get_photo_dates(path):
    date_created = datetime.fromtimestamp(os.path.getctime(path))
    date_modified = datetime.fromtimestamp(os.path.getmtime(path))
    exif_date = get_exif_original_date(path)
    mov_date = get_mov_created_date(path)

    # compute the date taken
    date_taken = None
    if exif_date:
        date_taken = exif_date
    elif mov_date:
        date_taken = mov_date
    else:
        date_taken = min(date_created, date_modified)

    return (
        date_created,
        date_modified,
        exif_date,
        mov_date,
        date_taken
    )

def get_photo_meta(path, relpath, filehash):
    date_created, date_modified, exif_date, mov_date, date_taken = \
        get_photo_dates(path)
    filemeta = {
        'relpath': relpath,
        'abspath': os.path.abspath(path),
        'created': date_created.strftime(FLICKR_DATE_FORMAT),
        'modified': date_modified.strftime(FLICKR_DATE_FORMAT),
        'filehash': filehash,
        'filesize': os.path.getsize(path),
        'exif_original_date': exif_date.strftime(FLICKR_DATE_FORMAT) if exif_date else None,
        'mov_created_date': mov_date.strftime(FLICKR_DATE_FORMAT) if mov_date else None,
    }
    title = '%s__%s' % (os.path.basename(path), filehash)
    description = photo_description(filemeta)
    return (
        filemeta, 
        title,
        description,
        date_taken
    )
