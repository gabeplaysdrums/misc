#!python
"""
Generate conversation statistics from logs

Dependencies
------------

Beautiful Soup
https://www.crummy.com/software/BeautifulSoup/
pip install beautifulsoup4

amueller's word_cloud
https://github.com/amueller/word_cloud
pip install wordcloud

Pillow - The friendly PIL fork
https://python-pillow.org/
pip install pillow

"""

from __future__ import print_function
from optparse import OptionParser
import os
import sys
from bs4 import BeautifulSoup
import fnmatch
import re
from datetime import date, time, datetime
from wordcloud import WordCloud, STOPWORDS
import json


def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] DIRECTORY'
    )
    
    # options

    parser.add_option(
        '--message-text-output', dest='message_text_output_path', default=None,
        help='write message text to a file',
    )

    parser.add_option(
        '-o', '--output', dest='output_path', default=None,
        help='write word cloud to image file',
    )

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
        soup.prettify()
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
        elif soup.head and soup.head.noscript and 'facebook.com' in soup.head.noscript.get_text():
            print('facebook log detected')
            for tag in soup.body.find_all(class_='msg'):
                alias = tag.find(class_='actor').get_text()
                message_tag = tag.find(attrs={'data-sigil': 'message-text'})

                # remove links
                for link_tag in message_tag.find_all('a'):
                    link_tag.extract()

                # remove attachments
                for attach_tag in message_tag.find_all(class_='messageAttachments'):
                    attach_tag.extract()

                message = message_tag.get_text()
                timestamp_as_millis = json.loads(message_tag.get('data-store'))['timestamp']
                timestamp = datetime.fromtimestamp(timestamp_as_millis / 1000.0)
                yield alias, message, timestamp


SUBSTITUTES = (
    ('gues', 'guess'),
    ('ye', 'yes'),
    ('hah', 'ha'),
    ('heh', 'ha'),
    ('haha', 'ha'),
    ('ily', 'i love you'),
    ('iloveyou', 'i love you'),
    ('gn', 'good night'),
    ('goodnight', 'good night'),
    ('sd', 'sweet dreams'),
    ('sweetdreams', 'sweet dreams'),
    ('gnsdily', 'good night sweet dreams i love you'),
    ('goodnightsweetdreamsiloveyou', 'good night sweet dreams i love you'),
    ('prolly', 'probably'),
    ('Devils Halo 1001', 'devilshalo1001'),
    ('alway', 'always'),
    ('wanna', 'want to'),
    ('gonna', 'going to'),
    ('ppl', 'people'),
    ('brb', 'be right back'),
    ('hw', 'homework'),
    ('nite', 'night'),
    ('im', 'i am'),
    ("it'll", 'it will'),
    ('dont', "don't"),
    ("dont'", "don't"),
    ('cuz', 'because'),
    ('np', 'no problem'),
    ('lemme', 'let me'),
    ('btw', 'by the way'),
    ('esp', 'especially'),
    ('tho', 'though'),
    ('convo', 'conversation'),
    ('ko', 'ok'),
    ('kk', 'ok'),
    (r'aw[w]*', 'aww'),
    (r'yo[o]*', 'yo'),
    ('ap', 'app'),
    ('discovercard', 'discover card'),
)


wordcloud = None


def main(options, args):
    global wordcloud
    input_path = args[0]
    message_count = 0
    message_text = ''

    if os.path.isdir(input_path):
        for (root, dirs, files) in os.walk(input_path):
            html_files = list(fnmatch.filter(files, '*.html')) + list(fnmatch.filter(files, '*.htm'))
            for name in html_files:
                path = os.path.join(root, name)
                print('Processing %s ...' % (path,))
                for alias, message, timestamp in process_html(path):
                    message_count += 1
                    message_text += message + '\n'
                    print('alias=', alias, 'message=', message, 'timestamp=', timestamp)

        print('Processed %d messages' % message_count)

        if options.message_text_output_path:
            with open(options.message_text_output_path, 'w') as f:
                f.write(message_text.encode('utf8'))
    else:
        with open(input_path, 'r') as f:
            message_text = f.read().decode('utf8')

    for a, b in SUBSTITUTES:
        message_text = re.sub(r'\b' + a + r'\b', b, message_text, flags=re.IGNORECASE | re.MULTILINE)

    stopwords = {
        'yeah',
        'yup',
        'yups',
        'yep',
        'yeps',
        'nope',
        'nah',
        'mm',
        'well',
        'think',
        'thing',
        'something',
        'anything',
        'thing',
        'things',
        'oh',
        'ah',
        'ahh',
        'alright',
        'hmm',
        'hey',
        'hello',
        'hi',
        'yo',
        'anyway',
        'stuff',
        'also',
        'anyways',
        'kinda',
        'ok',
        'okay',
        'um',
        'umm',
        'newsboytko',
        'devilshalo1001',
        'pff',
        'psh',
        'eh',
        'meh',
        'PM',
        'sunday',
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
    }

    stopwords.update(STOPWORDS)

    wordcloud = WordCloud(width=1280, height=720, max_words=1000, stopwords=stopwords).generate(message_text)

    for word, weight in sorted(wordcloud.words_, key=lambda x: x[1], reverse=True):
        print('%-30s %.6f' % (word, weight))

    image = wordcloud.to_image()
    image.show()

    if options.output_path:
        image.save(options.output_path)

if __name__ == '__main__':
    main(*parse_command_line())