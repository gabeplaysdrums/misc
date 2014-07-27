#!/usr/bin/python
"""
Remove duplicate photos on Flickr
"""

from csv import DictReader
from flickrapi.exceptions import FlickrError
from optparse import OptionParser
from pyflickr_utils import *
import flickrapi
import flickrapi.shorturl
import sys
import time

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] uploaded.csv'
    )

    parser.add_option(
        '-n', '--dry-run', dest='is_dry_run', default=False,
        help='perform a dry run (don\'t create anything)',
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

def get_elem_text(elem):
    return elem.text.strip() if elem.text else ''

def get_photosets(flickr):
    page_count = None
    result = dict()
    def process_page(page=1):
        rsp = flickr.photosets_getList(page=page, per_page=500)
        photosets = rsp.find('photosets')
        for photoset in photosets.findall('photoset'):
            title = get_elem_text(photoset.find('title'))
            result[title] = {
                'id': photoset.get('id'),
                'title': title,
                'description': get_elem_text(photoset.find('description')),
            }
        if page == 1:
            page_count = int(photosets.get('pages'))
            return page_count
    page_count = process_page()
    for page in range(2, page_count + 1):
        process_page(page=page)
    return result

if __name__ == "__main__":

    (options, args) = parse_command_line()
    input_path = args[0]

    print 'Authenticating ...'
    flickr = flickrapi.FlickrAPI(API_KEY, API_SECRET)
    flickr.authenticate_console(perms='write')

    print 'Finding existing photosets ...'
    known_sets = get_photosets(flickr)
    print 'Found %d photosets on Flickr' % (len(known_sets),)

    class Photoset:
        def __init__(self, title):
            self.photoset_id = None
            self.title = title
            self.primary_photo_id = None
            if title in known_sets:
                self.photoset_id = known_sets[title]['id']
            self.photos = []

        def create(self):
            if not self.primary_photo_id:
                self.primary_photo_id = self.photos[0]['photo_id']
            if self.photoset_id:
                return self.photoset_id
            rsp = flickr.photosets_create(
                title=self.title, 
                primary_photo_id=self.primary_photo_id,
            )
            self.photoset_id = rsp.find('photoset').get('id')
            return self.photoset_id

        def add_photos(self):
            self.photos.sort(key=lambda x: x['date_taken'])
            photo_ids = [ photo['photo_id'] for photo in self.photos ]
            photo_ids_string = ','.join(photo_ids)
            exc = None
            for i in range(5):
                try:
                    flickr.photosets_editPhotos(
                        photoset_id=self.photoset_id,
                        primary_photo_id=self.primary_photo_id,
                        photo_ids=photo_ids_string,
                    )
                    return
                except Error, e:
                    exc = e
                    time.sleep(5)
                    pass
            raise exc

    monthly_photosets = dict()

    with open(input_path, 'rb') as csvfile:
        reader = DictReader(csvfile)
        for row in reader:
            date_taken = datetime.strptime(row['date_taken'], FLICKR_DATE_FORMAT)
            title = date_taken.strftime('%B %Y') # July 2014
            if not title in monthly_photosets:
                monthly_photosets[title] = Photoset(title)
            monthly_photosets[title].photos.append(row)

    # sort monthly photosets chronologically
    photosets = sorted(monthly_photosets.values(), key=lambda x: datetime.strptime(x.title, '%B %Y'))

    print 'Will now create or modify %d photosets.' % (len(photosets),)

    # confirm
    if not options.is_unattend:
        choice = None
        print ''
        while not choice or not (choice == 'y' or choice == 'n'):
            choice = raw_input('Continue? (y/n): ').lower()
        print ''
        if not choice == 'y':
            sys.exit(2)

    for photoset in photosets:
        print 'Updating "%s" (%d photos) ...' % (photoset.title, len(photoset.photos)) 
        if options.is_dry_run:
            continue
        photoset.create()
        photoset.add_photos()

    print '\nDone!'
