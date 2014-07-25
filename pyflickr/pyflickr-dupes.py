"""
Remove duplicate photos on Flickr
"""

from csv import DictReader
from optparse import OptionParser
from pyflickr_utils import *
import flickrapi
import flickrapi.shorturl
import sys

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] uploaded.csv'
    )

    parser.add_option(
        '-n', '--dry-run', dest='is_dry_run', default=False,
        help='perform a dry run (don\'t delete anything)',
        action='store_true',
    )

    parser.add_option(
        '--unattend', dest='is_unattend', default=False,
        help='run without prompting',
        action='store_true',
    )

    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.print_usage()
        sys.exit(1)

    return (options, args)

if __name__ == "__main__":

    (options, args) = parse_command_line()
    input_path = args[0]

    print 'Authenticating ...'
    flickr = flickrapi.FlickrAPI(API_KEY, API_SECRET)
    flickr.authenticate_console(perms='delete')

    photos = dict()
    dupe_count = 0

    print 'Getting previously uploaded photos ...'
    uploaded_photos = get_uploaded_photos(flickr)
    for (photo_id, title) in uploaded_photos:
        if title in photos:
            dupe_count += 1
            photos[title].append(photo_id)
            continue
        photos[title] = [ photo_id ]

    print '%d duplicate photos found (of %d total).' % (dupe_count, len(uploaded_photos))

    # confirm
    if not options.is_unattend:
        choice = None
        print ''
        while not choice or not (choice == 'y' or choice == 'n'):
            choice = raw_input('Would you like to delete them? (y/n): ').lower()
        print ''
        if not choice == 'y':
            sys.exit(2)

    for title in photos.keys():
        if len(photos[title]) <= 1:
            del photos[title]
    
    with open(input_path, 'rb') as csvfile:
        reader = DictReader(csvfile)
        for row in reader:
            title = row['title']
            if title in photos:
                photo_ids = photos[title]
                print '%s has %d duplicates.' % (row['relpath'], len(photo_ids) - 1)
                primary_id = row['photo_id']
                if not primary_id:
                    print '  No primary id found.  Skipping ...'
                    continue
                shorturl = flickrapi.shorturl.url(primary_id)
                print '  Primary photo is %s [ %s ]' % (primary_id, shorturl)
                for photo_id in photo_ids:
                    if photo_id == primary_id:
                        continue
                    shorturl = flickrapi.shorturl.url(photo_id)
                    print '  Deleting photo %s [ %s ] ...' % (photo_id, shorturl)
                    if options.is_dry_run:
                        continue

                    # delete the photo!
                    flickr.photos_delete(photo_id=photo_id)

                del photos[title]

    if len(photos) > 0:
        print '\nCould not find primary photo for %d groups:' % (len(photos),)
        for title in sorted(photos.keys()):
            print '  %s (%d duplicates)' % (title, len(photos[title]) - 1)

    print '\nDone!'
