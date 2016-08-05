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


def process_html(path):
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

    def purple_extract_date(soup):
        if soup.title:
            m = re.match(r'Conversation with .* at (\d\d?)/(\d\d?)/(\d{4}) \d\d?:\d{2}:\d{2} (AM|PM) on .* \(aim\)', soup.title.get_text())
            if m:
                year = int(m.group(3))
                month = int(m.group(1))
                day = int(m.group(2))
                return date(year, month, day)
        return None

    def purple_extract_time(tag):
        if tag.font:
            m = re.match(r'\((\d\d?):(\d{2}):(\d{2})\s+(AM|PM)\)', tag.font.get_text())
            if m:
                hours = int(m.group(1))
                minutes = int(m.group(2))
                seconds = int(m.group(3))
                if m.group(4) == 'PM':
                    hours += 12

                #TODO: bug! message occurred the next day
                if hours > 23:
                    hours -= 24

                return time(hours, minutes, seconds)
        return None

    def purple_extract_message(tag):
        message = ''
        for sibling in tag.next_siblings:
            if sibling.name == 'font':
                break
            elif not sibling.name:
                message += unicode(sibling).strip() + '\n'
        return message.strip()

    def purple_extract_alias(tag):
        return gaim_extract_alias(tag)

    with open(path, 'r') as f:
        soup = BeautifulSoup(f, 'html.parser')
        soup.prettify()
        gaim_date = gaim_extract_date(soup)
        purple_date = purple_extract_date(soup)
        if gaim_date and soup.find(sml='AIM/ICQ'):
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
                        timestamp = datetime.combine(gaim_date, curr_time)
                        alias = curr_alias
        elif purple_date:
            print('purple log detected')

            for tag in soup.body.find_all('font', recursive=False):
                # TODO: remove
                # current_tag = tag

                curr_time = purple_extract_time(tag)
                curr_alias = purple_extract_alias(tag)
                if curr_time and curr_alias:
                    timestamp = datetime.combine(purple_date, curr_time)
                    alias = curr_alias
                    message = purple_extract_message(tag)
                    yield alias, message, timestamp

        elif soup.head and soup.head.noscript and 'facebook.com' in soup.head.noscript.get_text():
            print('facebook log detected')
            for tag in soup.body.find_all(class_='msg'):
                alias = tag.find(class_='actor').get_text()
                message_tag = tag.find(attrs={'data-sigil': 'message-text'})

                # remove links
                for link_tag in message_tag.find_all('a'):
                    link_tag.decompose()

                # remove attachments
                for attach_tag in message_tag.find_all(class_='messageAttachments'):
                    attach_tag.decompose()

                message = message_tag.get_text().strip()
                timestamp_as_millis = json.loads(message_tag.get('data-store'))['timestamp']
                timestamp = datetime.fromtimestamp(timestamp_as_millis / 1000.0)
                yield alias, message, timestamp
        else:
            print('unrecognized log format')


def process_txt(path):
    def purple_extract_date(line):
        if line:
            m = re.match(r'Conversation with .* at (\d\d?)/(\d\d?)/(\d{4}) \d\d?:\d{2}:\d{2} (AM|PM) on .* \(aim\)', line)
            if m:
                year = int(m.group(3))
                month = int(m.group(1))
                day = int(m.group(2))
                return date(year, month, day)
        return None

    def purple_extract(line):
        curr_time = None
        curr_alias = None
        curr_message_part = None
        if line and '<AUTO-REPLY>' not in line:
            m = re.match(r'^\((\d\d?):(\d{2}):(\d{2})\s+(AM|PM)\) ([a-zA-Z0-9 ]+): (.*)$', line)
            if m:
                hours = int(m.group(1))
                minutes = int(m.group(2))
                seconds = int(m.group(3))
                if m.group(4) == 'PM':
                    hours += 12

                #TODO: bug! message occurred the next day
                if hours > 23:
                    hours -= 24

                curr_time = time(hours, minutes, seconds)
                curr_alias = m.group(5).strip()
                curr_message_part = m.group(6)
            else:
                curr_message_part = line
        return curr_time, curr_alias, curr_message_part

    with open(path) as fin:
        first_line = fin.readline()
        purple_date = purple_extract_date(first_line)
        if purple_date:
            print('purple log detected')

            timestamp = None
            alias = None
            message = None

            for line in fin:
                curr_time, curr_alias, curr_message_part = purple_extract(line)
                if curr_time and curr_alias:
                    if timestamp and alias and message:
                        yield alias, message.strip(), timestamp
                    timestamp = datetime.combine(purple_date, curr_time)
                    alias = curr_alias
                    message = curr_message_part
                elif curr_message_part:
                    message += curr_message_part

            if timestamp and alias and message:
                yield alias, message.strip(), timestamp
        else:
            print('unrecognized log format')


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
    ("don't'", "don't"),
    ('cuz', 'because'),
    ('np', 'no problem'),
    ('lemme', 'let me'),
    ('btw', 'by the way'),
    ('esp', 'especially'),
    ('tho', 'though'),
    ('convo', 'conversation'),
    ('ko', 'ok'),
    ('kk', 'ok'),
    ('sok', "it's ok"),
    (r'aw[w]*', 'aww'),
    (r'yo[o]*', 'yo'),
    ('ap', 'app'),
    ('discovercard', 'discover card'),
    ('ttyl', 'talk to you later'),
    ('watcha', 'what are you'),
    (r'oo[o]*[h]?', 'ooh'),
)


def main(options, args):
    input_path = args[0]

    class Context:
        def __init__(self):
            self.message_count = 0
            self.message_text = ''
    ctx = Context()
    del Context

    if os.path.isdir(input_path):
        def process_files(root, names, fn):
            for name in names:
                path = os.path.join(root, name)
                print('Processing %s ...' % (path,))
                for alias, message, timestamp in fn(path):
                    #print('alias=', alias, 'message=', repr(message), 'timestamp=', timestamp)
                    try:
                        message = message.encode('ascii', 'ignore')
                        ctx.message_count += 1
                        ctx.message_text += message + '\n'
                    except UnicodeDecodeError:
                        pass

        for (root, dirs, files) in os.walk(os.path.abspath(input_path)):
            html_files = list(fnmatch.filter(files, '*.html')) + list(fnmatch.filter(files, '*.htm'))
            process_files(root, html_files, process_html)
            txt_files = fnmatch.filter(files, '*.txt')
            process_files(root, txt_files, process_txt)

        print('Processed %d messages' % ctx.message_count)

        if options.message_text_output_path:
            with open(os.path.normpath(options.message_text_output_path), 'w') as f:
                f.write(ctx.message_text)
    else:
        with open(input_path, 'r') as f:
            ctx.message_text = f.read()

    ctx.message_text = re.sub('\d*', '', ctx.message_text)

    for a, b in SUBSTITUTES:
        ctx.message_text = re.sub(r'\b' + a + r'\b', b, ctx.message_text, flags=re.IGNORECASE | re.MULTILINE)

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

    wordcloud = WordCloud(width=1280, height=720, max_words=1000, stopwords=stopwords).generate(ctx.message_text)

    for word, weight in sorted(wordcloud.words_, key=lambda x: x[1], reverse=True):
        print('%-30s %.6f' % (word, weight))

    image = wordcloud.to_image()
    image.show()

    if options.output_path:
        image.save(options.output_path)

if __name__ == '__main__':
    main(*parse_command_line())