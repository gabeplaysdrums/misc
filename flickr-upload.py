from optparse import OptionParser
import flickrapi
import fnmatch
import hashlib
import os
import sys
import threadpool
from datetime import datetime, timedelta

API_KEY = 'f5b40cdc2dfac381aefcfd48687ddaba'
API_SECRET = '30bce1a79b59ea4a'
PHOTO_PATTERNS = ('*.jpg', '*.jpeg', '*.png', '*.bmp')
MOVIE_PATTERNS = ('*.mov', '*.mp4', '*.mpg', '*.mpeg', '*.avi')
PYFLICKR_TAG = 'PyFlickr'
THREADPOOL_SIZE = 15
UPLOADED_FILE_SUFFIX = '.uploaded'

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] input_path'
    )

    parser.add_option(
        '-d', '--directory', dest='is_directory', default=False,
        help='input path is a directory (will recursively search for photos and upload them all)',
        action='store_true',
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
    )

    parser.add_option(
        '--skip-uploaded-check', dest='skip_uploaded_check', default=False,
        help='don\'t query the service to determine which photos have already been uploaded',
        action='store_true',
    )

    return parser.parse_args()

(options, args) = parse_command_line()

if len(args) < 1:
    print 'Please specify input path'
    sys.exit(1)

input_path = args[0]

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
tags = ','.join(tags)
print 'Tags: %s' % (tags,)

print 'Getting previously uploaded photos ...'
uploaded = set()
for photo in flickr.walk(user_id='me', tag_mode='all', tags=PYFLICKR_TAG):
    uploaded.add(photo.get('title'))

count = 0
total = 0
completed = 0
checkpoint_completed = 0
checkpoint_time = None

def upload_photo(path):
    global count
    global total
    global completed
    global checkpoint_completed
    global checkpoint_time
    count += 1
    print '#%d/%d Uploading %s' % (count, total, path)
    sys.stdout.flush()
    uploaded_path = path + UPLOADED_FILE_SUFFIX
    if os.path.exists(uploaded_path):
        print '  Skipping ... photo appears to have been uploaded already.'
        return
    title = '%s__%s' % (
        os.path.basename(path),
        hashlib.md5(open(path, 'rb').read()).hexdigest()
    )
    if title in uploaded:
        print '  Skipping ... photo appears to have been uploaded already.'
    	open(uploaded_path, 'w').close()
        return
    if options.is_dry_run:
        return
    def upload_callback(progress, done):
        print '  Progress: %s% ... ' % (progress,)
    flickr.upload(
        filename=path,
        title=title,
        callback=upload_callback,
        tags=tags,
        is_public=(1 if options.is_public else 0),
        is_friend=(1 if options.is_friend else 0),
        is_family=(1 if options.is_family else 0),
        hidden=(2 if options.is_public_search else 1),
    )
    print '  Done!'
    completed += 1
    open(uploaded_path, 'w').close()
    # print photos per minute every 60 seconds
    now = datetime.now()
    delta = now - checkpoint_time
    if delta > timedelta(seconds=60):
        uploads_per_minute = 60 * float(completed - checkpoint_completed) / delta.total_seconds()
        minutes_remaining = (total - count) / uploads_per_minute if uploads_per_minute != 0 else 0
        print '=== Current rate: %.2f uploads/minute (%.2f minutes remaining) ===' % (
            uploads_per_minute, minutes_remaining
        )
        sys.stdout.flush()
        checkpoint_time = now
        checkpoint_completed = completed

if options.is_directory:
    patterns = PHOTO_PATTERNS + MOVIE_PATTERNS
    paths = []
    for root, dirs, files in os.walk(input_path):
        for pat in patterns:
            for filename in fnmatch.filter(files, pat):
                path = os.path.join(root, filename)
                uploaded_path = path + UPLOADED_FILE_SUFFIX
                if os.path.exists(uploaded_path):
                    continue
                paths.append(path)
    total = len(paths)
    choice = None
    while not choice or not (choice == 'y' or choice == 'n'):
        print 'Will now upload %d photos to flickr.' % (total,)
        choice = raw_input('Continue? (y/n): ').lower()
    if not choice == 'y':
        sys.exit(2)
    pool = threadpool.ThreadPool(THREADPOOL_SIZE)
    def exc_callback(req, exception_details):
        print 'Exception occurred.  Putting the request back in the worker queue.'
        req2 = threadpool.WorkRequest(upload_photo, args=req.args, exc_callback=req.exc_callback)
        pool.putRequest(req2)
    requests = threadpool.makeRequests(upload_photo, paths, exc_callback=exc_callback)
    checkpoint_time = datetime.now()
    for req in requests:
        pool.putRequest(req)
    pool.wait()
else:
    total = 1
    upload_photo(input_path)
