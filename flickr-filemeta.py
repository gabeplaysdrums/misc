"""
Gather file metadta from photos described in a CSV file produced by flickr-dump.py
"""

from csv import DictReader, DictWriter
from datetime import datetime
from optparse import OptionParser
import hashlib
import os
import sys

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] PHOTOS.csv INPUT_ROOT'
    )

    parser.add_option(
        '-o', '--output', dest='output_path', default=None,
        help='path to output CSV file',
    )

    return parser.parse_args()

if __name__ == "__main__":

    (options, args) = parse_command_line()

    if len(args) < 2:
        print 'not enough arguments'
        sys.exit(1)

    input_csv_path = args[0]
    input_root = args[1]

    # compute output path from input CSV path
    if not options.output_path:
        parts = os.path.splitext(input_csv_path)
        options.output_path = parts[0] + '.filemeta' + parts[1]

    print 'Finding corresponding photo files in %s ...' % (input_root,)

    class PhotoInfo:
        id = None
        title = None

        def __init__(self, id, title):
            self.id = id
            self.title = title
            self._path = None

        def filename(self):
            return self.title.split('__')[0]

        def filehash(self):
            return self.title.split('__')[1]

        def find(self):
            if self._path:
                return self._path
            paths = []
            for root, dirnames, filenames in os.walk(input_root):
                if self.filename() in filenames:
                    path = os.path.join(root, self.filename())
                    paths.append(path)
            if len(paths) == 1:
                # if there is only one file found, assume it is the right one
                self._path = paths[0]
            else:
                for path in paths:
                    # compute file hash
                    with open(path, 'rb') as f:
                        hash = str(hashlib.md5(f.read()).hexdigest())
                        print 'hash: ' + hash
                        if hash == self.filehash():
                            self._path = path
                            break
            return self._path

        def created(self):
            return datetime.fromtimestamp(os.path.getctime(self.find()))

        def modified(self):
            return datetime.fromtimestamp(os.path.getmtime(self.find()))

    photos = []
    with open(input_csv_path, 'rb') as csvfile:
        reader = DictReader(csvfile)
        for row in reader:
            photos.append(PhotoInfo(row['id'], row['title']))

    with open(options.output_path, 'wb') as csvfile:
        writer = DictWriter(csvfile, extrasaction='ignore', fieldnames=(
            'id',
            'filename',
            'filehash',
            'fullpath',
            'path',
            'created',
            'modified',
        ))
        writer.writeheader()
        for photo in photos:
            writer.writerow({
                'id': photo.id,
                'filename': photo.filename(),
                'filehash': photo.filehash(),
                'fullpath': photo.find(),
                'path': photo.find().split(input_root)[1],
                'created': photo.created().strftime('%Y-%m-%d %H:%M:%S'),
                'modified': photo.modified().strftime('%Y-%m-%d %H:%M:%S'),
            })

    print 'Done!'
