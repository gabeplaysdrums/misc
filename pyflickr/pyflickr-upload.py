#!/usr/bin/python
"""
Recursively searches a directory and uploads photos to Flickr
"""

from csv import DictReader, DictWriter
from datetime import datetime, timedelta
from optparse import OptionParser
from pyflickr_utils import *
import flickrapi
import flickrapi.shorturl
import fnmatch
import hashlib
import os
import sys
import threadpool

# maximum sizes:
# https://help.yahoo.com/kb/flickr/upload-limitations-flickr-sln15628.html?impressions=true
MAX_PICTURE_FILE_SIZE = 209715200 # 200 MB
MAX_MOVIE_FILE_SIZE = 1073700000 # 1 GB

PHOTO_PATTERNS = ('*.jpg', '*.jpeg', '*.png', '*.bmp')
MOVIE_PATTERNS = ('*.mov', '*.mp4', '*.mpg', '*.mpeg', '*.avi')

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] INPUT_ROOT'
    )

    parser.add_option(
        '-o', '--output', dest='output_path', default='uploaded.csv',
        help='path to output CSV file',
    )

    parser.add_option(
        '-i', '--input-csv', dest='input_csv_path', default=None,
        help='override input CSV file (defaults to output file)',
    )

    parser.add_option(
        '-n', '--dry-run', dest='is_dry_run', default=False,
        help='perform a dry run (don\'t upload anything)',
        action='store_true',
    )

    parser.add_option(
        '-p', '--public', dest='is_public', default=False,
        help='make photos public',
        action='store_true',
    )

    parser.add_option(
        '--friends', dest='is_friend', default=False,
        help='make photos visible to friends',
        action='store_true',
    )

    parser.add_option(
        '--family', dest='is_family', default=False,
        help='make photos visible to family',
        action='store_true',
    )

    parser.add_option(
        '--public-search', dest='is_public_search', default=False,
        help='photos are eligible for public search',
        action='store_true',
    )

    parser.add_option(
        '--tag', dest='tags', default=[],
        help='add a tag to uploaded photos',
        action='append',
        metavar='TAG',
    )

    parser.add_option(
        '--skip-uploaded-check', dest='skip_uploaded_check', default=False,
        help='don\'t query the service to determine which photos have already been uploaded',
        action='store_true',
    )

    parser.add_option(
        '--unattend', dest='is_unattend', default=False,
        help='run without prompting',
        action='store_true',
    )

    parser.add_option(
        '--no-movies', dest='upload_movies', default=True,
        help='do not upload movie files',
        action='store_false',
    )

    parser.add_option(
        '--no-pictures', dest='upload_pictures', default=True,
        help='do not upload picture files',
        action='store_false',
    )

    parser.add_option(
        '--threadpool-size', dest='threadpool_size', default=15,
        help='size of the threadpool',
        type='int',
    )

    parser.add_option(
        '--no-known-titles', dest='seed_known_titles', default=True,
        help='do not seed the list of known titles from the CSV file',
        action='store_false',
    )

    parser.add_option(
        '--no-upload-new-files', dest='upload_new_files', default=True,
        help='do not upload new files (useful for re-generating the CSV)',
        action='store_false',
    )

    parser.add_option(
        '--update', dest='update', default=False,
        help='Update file metadata (dates).  Requires -i (--input-csv) option.',
        action='store_true',
    )

    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.print_usage()
        sys.exit(1)

    if options.update:
        if not options.input_csv_path:
            parser.print_usage()
            sys.exit(1)
        options.seed_known_titles = True
        options.skip_uploaded_check = True
        options.upload_new_files = False

    if not options.input_csv_path:
        options.input_csv_path = options.output_path

    return (options, args)

if __name__ == '__main__':

    (options, args) = parse_command_line()
    input_root = args[0]

    print 'Authenticating ...'
    flickr = flickrapi.FlickrAPI(API_KEY, API_SECRET)
    flickr.authenticate_console(perms='write')

    # compute tags
    tags = [PYFLICKR_TAG]
    for tag in options.tags:
        if ' ' in tag:
            tags.append('"%s"' % (tag,))
        else:
            tags.append(tag)
    tags_string = ' '.join(tags)
    print 'Tags: ' + tags_string

    # build patterns list
    patterns = ()
    if options.upload_pictures:
        patterns += PHOTO_PATTERNS
    if options.upload_movies:
        patterns += MOVIE_PATTERNS
    patterns += tuple(x.upper() for x in patterns)

    paths = []
    excluded_paths = set()

    # build excluded paths and known titles lists
    known_titles = set()
    append = os.path.exists(options.output_path)
    post_upload_args = []
    upload_count = 0

    if os.path.exists(options.input_csv_path):
        if options.update:
            print 'Gathering photo data from %s ...' % (options.input_csv_path,)
        with open(options.input_csv_path) as csvfile:
            reader = DictReader(csvfile)
            for row in reader:
                path = os.path.join(input_root, row['relpath'])
                if options.update:
                    for pat in patterns:
                        if fnmatch.fnmatch(path, pat):
                            upload_count += 1
                            filemeta, title, description, date_taken = \
                                get_photo_meta(path, row['relpath'], row['filehash'])
                            post_upload_args.append((
                                upload_count,
                                title,
                                filemeta,
                                datetime.strptime(row['upload_start'], FLICKR_DATE_FORMAT),
                                datetime.strptime(row['upload_end'], FLICKR_DATE_FORMAT),
                                date_taken,
                                description,
                                row['photo_id'],
                            ))
                            paths.append(path)
                else:
                    excluded_paths.add(path)
                if options.seed_known_titles:
                    known_titles.add(row['title'])

    # build path list from input directory
    if not options.update:
        for root, dirs, files in os.walk(input_root):
            for pat in patterns:
                for filename in fnmatch.filter(files, pat):
                    path = os.path.join(root, filename)
                    if path in excluded_paths:
                        continue
                    paths.append(path)

    # build excluded titles list
    excluded_titles = dict()
    if not options.skip_uploaded_check:
        print 'Getting previously uploaded photos ...'
        uploaded_photos = get_uploaded_photos(flickr)
        for (photo_id, title) in uploaded_photos:
            excluded_titles[title] = photo_id
        print 'Found %d photos on flickr (%d unique titles)' % (len(uploaded_photos), len(excluded_titles))

    # confirm
    print 'Will now upload %d photos to flickr.' % (len(paths),)
    if not options.is_unattend:
        choice = None
        print ''
        while not choice or not (choice == 'y' or choice == 'n'):
            choice = raw_input('Continue? (y/n): ').lower()
        print ''
        if not choice == 'y':
            sys.exit(2)

    # setup output csv writer
    with open(options.output_path, 'ab') as csvfile:
        writer = make_csv_writer(csvfile)

        if not append:
            writer.writeheader()

        # start the write csv threadpool
        write_csv_pool = threadpool.ThreadPool(1)

        # start the post-upload threadpool
        post_upload_pool = threadpool.ThreadPool(options.threadpool_size)

        with open('pyflickr-upload.log', 'w') as logfile:

            def log(s):
                print s
                sys.stdout.flush()
                logfile.write(s + '\n')
                logfile.flush()

            upload_total = len(paths)
            start_time = datetime.now()
            checkpoint_time = start_time

            def write_csv(row):
                writer.writerow(row)

            def post_upload(
                count,
                title, 
                filemeta, 
                upload_start_date, 
                upload_end_date, 
                date_taken_date, 
                description, 
                photo_id,
            ):
                global upload_count
                global upload_total
                global start_time
                global checkpoint_time
                global excluded_titles

                log('[Uploaded] #%d/%d: %s (%.2f s)' % (
                    count, upload_total, filemeta['relpath'],
                    (upload_end_date - upload_start_date).total_seconds(),
                ))

                # get info about the photo we just uploaded
                log('[Get Info] #%d/%d: %s' % (
                    count, upload_total, filemeta['relpath'],
                ))
                res = flickr.photos_getInfo(photo_id=photo_id)
                photo_info = res.find('photo')
                media = photo_info.get('media')
                original_format = photo_info.get('originalformat')
                url = photo_info.find('urls').find('url').text
                server = photo_info.get('server')
                title2 = photo_info.get('title')
                description2 = photo_info.find('description').text.strip()
                date_taken_date2 = datetime.strptime(photo_info.find('dates').get('taken'), '%Y-%m-%d %H:%M:%S')

                if date_taken_date.date() != date_taken_date2.date():
                    # this is a good indication that the date is wrong.  fix the date taken.
                    log('[Date Fixup] #%d/%d: %s (new date taken: %s)' % (
                        count, upload_total, filemeta['relpath'],
                        date_taken_date.strftime(FLICKR_DATE_FORMAT),
                    ))
                    flickr.photos_setDates(
                        photo_id=photo_id,
                        date_taken=date_taken_date.strftime(FLICKR_DATE_FORMAT)
                    )
                else:
                    date_taken_date = date_taken_date2

                if title != title2 or description != description2:
                    log('[Metadata Fixup] #%d/%d: %s' % (
                        count, upload_total, filemeta['relpath'],
                    ))
                    flickr.photos_setMeta(
                        photo_id=photo_id,
                        title=title,
                        description=description
                    )

                upload_start = upload_start_date.strftime(FLICKR_DATE_FORMAT)
                upload_end = upload_end_date.strftime(FLICKR_DATE_FORMAT)
                date_taken = date_taken_date.strftime(FLICKR_DATE_FORMAT)
                shorturl = flickrapi.shorturl.url(photo_id)
                row = locals()
                row.update(filemeta)

                # put the row in the write csv threadpool
                req = threadpool.WorkRequest(write_csv, args=(row,))
                write_csv_pool.putRequest(req)

                # add it to the list of known titles in case there are duplicates
                known_titles.add(title)

                log('[Done] #%d/%d: %s' % (
                    count, upload_total, filemeta['relpath'],
                ))

                # print upload rate statistics
                now = datetime.now()

                if (now - checkpoint_time).total_seconds() > 60:
                    checkpoint_time = now
                    minutes = (now - start_time).total_seconds() / 60
                    rate = upload_count / minutes
                    log('== current rate: %.2f uploads/min (%.2f minutes remaining) ==' % (
                        rate,
                        (upload_total - upload_count) / rate,
                    ))

            def post_upload_exc(req, exception_details):
                log(str(exception_details))
                log('Exception occurred.  Putting the request back in the worker queue.')
                req2 = threadpool.WorkRequest(post_upload, args=req.args, exc_callback=req.exc_callback)
                post_upload_pool.putRequest(req2)

            # start upload threadpool
            def upload_photo(path):
                global upload_count
                global upload_total
                global options

                upload_count += 1
                count = upload_count
                relpath = path.split(input_root)[1]
                log('[Start] #%d/%d: %s' % (count, upload_total, relpath))
                upload_start = datetime.now()
                filehash = None
                with open(path, 'rb') as f:
                    filehash = str(hashlib.md5(f.read()).hexdigest())

                filemeta, title, description, date_taken = \
                    get_photo_meta(path, relpath, filehash)
                
                photo_id = None

                if options.is_dry_run:
                    return

                if title in known_titles:
                    # if found in the list of known titles, don't attempt to
                    # upload or fix metadata
                    log('[Known] #%d/%d: %s' % (count, upload_total, relpath))
                    return

                if title in excluded_titles:
                    log('[Skip] #%d/%d: %s' % (count, upload_total, relpath))
                    photo_id = excluded_titles[title]
                elif options.upload_new_files:
                    # upload the photo!
                    res = flickr.upload(
                        filename=path,
                        title=title,
                        description=description,
                        tags=tags_string,
                        is_public=(1 if options.is_public else 0),
                        is_friend=(1 if options.is_friend else 0),
                        is_family=(1 if options.is_family else 0),
                        hidden=(2 if options.is_public_search else 1),
                    )
                    photo_id = res.find('photoid').text.strip()
                else:
                    log('[No Upload] #%d/%d: %s' % (count, upload_total, relpath))
                    return

                upload_end = datetime.now()
                req = threadpool.WorkRequest(post_upload, exc_callback=post_upload_exc, args=(
                    count, 
                    title, filemeta, upload_start, upload_end, date_taken, description, photo_id,
                ))
                post_upload_pool.putRequest(req)

            upload_pool = threadpool.ThreadPool(options.threadpool_size)
            def upload_exc(req, exception_details):
                global upload_total
                print exception_details
                print 'Exception occurred.  Putting the request back in the worker queue.'
                upload_total += 1
                req2 = threadpool.WorkRequest(upload_photo, args=req.args, exc_callback=req.exc_callback)
                upload_pool.putRequest(req2)

            if options.update:
                upload_count = len(post_upload_args)
                for args in post_upload_args:
                    req = threadpool.WorkRequest(post_upload, args=args, exc_callback=post_upload_exc)
                    post_upload_pool.putRequest(req)
            else:
                requests = threadpool.makeRequests(upload_photo, paths, exc_callback=upload_exc)
                for req in requests:
                    upload_pool.putRequest(req)

            upload_pool.wait()
            post_upload_pool.wait()
            write_csv_pool.wait()
