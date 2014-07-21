"""
Fix photo metadata (e.g. date taken) using file meta data produced by flickr-filemeta.py
"""

from optparse import OptionParser
import flickrapi
import os
from csv import DictReader, DictWriter
from datetime import datetime
import json

API_KEY = 'f5b40cdc2dfac381aefcfd48687ddaba'
API_SECRET = '30bce1a79b59ea4a'
PYFLICKR_TAG = 'PyFlickr'
PYFLICKR_FILEMETA_TOKEN='[!PyFlickr.filemeta]'

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] photos.filemeta.csv'
    )

    return parser.parse_args()

if __name__ == "__main__":

    (options, args) = parse_command_line()

    if len(args) < 1:
        print 'not enough arguments'
        sys.exit(1)

    input_path = args[0]

    print 'Authenticating ...'
    flickr = flickrapi.FlickrAPI(API_KEY, API_SECRET)
    flickr.authenticate_console(perms='write')

    with open(input_path, 'rb') as csvfile:
        reader = DictReader(csvfile)
        for row in reader:
            print 'Updating %s ...' % (row['filename'],)
            created = datetime.strptime(row['created'], '%Y-%m-%d %H:%M:%S')
            modified = datetime.strptime(row['modified'], '%Y-%m-%d %H:%M:%S')
            date_taken = min(created, modified).strftime('%Y-%m-%d %H:%M:%S')
            print '  date taken: ' + date_taken
            flickr.photos_setDates(photo_id=row['id'], date_taken=date_taken)
            desc = '\n'.join([
                PYFLICKR_FILEMETA_TOKEN,
                json.dumps(row),
                PYFLICKR_FILEMETA_TOKEN
            ])
            flickr.photos_setMeta(
                photo_id=row['id'],
                title=row['filename'] + '__' + row['filehash'],
                description=desc
            )

    print 'Done!'
