from optparse import OptionParser
import flickrapi
import fnmatch
import os
import sys
import hashlib

API_KEY = 'f5b40cdc2dfac381aefcfd48687ddaba'
API_SECRET = '30bce1a79b59ea4a'
PHOTO_PATTERNS = ('*.jpg', '*.jpeg', '*.png', '*.bmp')
MOVIE_PATTERNS = ('*.mov', '*.mp4', '*.mpg', '*.mpeg', '*.avi')
PYFLICKR_TAG = 'PyFlickr'

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
uploaded = []
for photo in flickr.walk(user_id='me', tag_mode='all', tags=PYFLICKR_TAG):
    uploaded.append(photo.get('title'))

count = 0
total = 0
def upload_photo(path):
    global count
    global total
    count += 1
    print '#%d/%d Uploading %s' % (count, total, path)
    sys.stdout.flush()
    title = '%s__%s' % (
        os.path.basename(path),
        hashlib.md5(open(path, 'rb').read()).hexdigest()
    )
    if title in uploaded:
        print '  Skipping ... photo appears to have been uploaded already.'
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

if options.is_directory:
    patterns = PHOTO_PATTERNS + MOVIE_PATTERNS
    for root, dirs, files in os.walk(input_path):
        for pat in patterns:
            total += len(fnmatch.filter(files, pat))
    print 'Will now upload %d photos fo flickr.' % (total,)
    if not raw_input('Continue? (y/n): ').lower() == 'y':
        sys.exit(2)
    for root, dirs, files in os.walk(input_path):
        for pat in patterns:
            for filename in fnmatch.filter(files, pat):
                path = os.path.join(root, filename)
                upload_photo(path)
else:
    total = 1
    upload_photo(input_path)
