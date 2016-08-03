#!python
"""
Generate conversation statistics from logs

Dependencies
------------

Beautiful Soup
https://www.crummy.com/software/BeautifulSoup/
pip install beautifulsoup4

"""

from __future__ import print_function
from optparse import OptionParser
import os
import sys
from bs4 import BeautifulSoup
import fnmatch
import re
from datetime import date, time, datetime


def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] DIRECTORY'
    )
    
    # options

    """
    parser.add_option(
        '-o', '--output', dest='output_path', default='output.txt',
        help='output path',
    )
    """
    
    (options, args) = parser.parse_args()

    # args

    if len(args) < 1:
        parser.print_usage()
        sys.exit(1)

    return options, args


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

#TODO: remove
#current_tag = None


def process_html(path):
    #TODO: remove
    #global current_tag

    def gaim_extract_date(soup):
        if soup.title:
            m = re.match(r'Conversation with .* at (\d{4})-(\d{2})-(\d{2}) \d{2}:\d{2}:\d{2} on .* \(aim\)', soup.title.get_text())
            if m:
                year = int(m.group(1))
                month = int(m.group(2))
                day = int(m.group(3))
                return date(year, month, day)
        return None

    def gaim_extract_time(tag):
        if tag.font:
            m = re.match(r'\((\d{2}):(\d{2}):(\d{2})\)', tag.font.get_text())
            if m:
                hours = int(m.group(1))
                minutes = int(m.group(2))
                seconds = int(m.group(3))
                return time(hours, minutes, seconds)
        return None

    def gaim_extract_alias(tag):
        if tag.b:
            m = re.match(r'^(.*):', tag.b.get_text())
            if m:
                alias = m.group(1)
                if u'<AUTO-REPLY>' not in alias:
                    return alias
        return None

    with open(path, 'r') as f:
        soup = BeautifulSoup(f, 'html.parser')
        curr_date = gaim_extract_date(soup)
        if curr_date and soup.find(sml='AIM/ICQ'):
            print('gaim log detected')

            timestamp = None
            alias = None

            for tag in soup.body.find_all('font', recursive=False):
                #TODO: remove
                #current_tag = tag

                if tag.get('sml') == 'AIM/ICQ':
                    message = tag.get_text().strip()
                    yield alias, message, timestamp
                else:
                    curr_time = gaim_extract_time(tag)
                    curr_alias = gaim_extract_alias(tag)
                    if curr_time and curr_alias:
                        timestamp = datetime.combine(curr_date, curr_time)
                        alias = curr_alias


def main(options, args):
    input_root = args[0]
    message_count = 0

    for (root, dirs, files) in os.walk(input_root):
        for name in fnmatch.filter(files, '*.html'):
            path = os.path.join(root, name)
            print('Processing %s ...' % (path,))
            for alias, message, timestamp in process_html(path):
                message_count += 1

    print('Processed %d messages' % message_count)

if __name__ == '__main__':
    main(*parse_command_line())