#!python
"""
Dump email to a static file using IMAP
"""

from __future__ import print_function
from optparse import OptionParser
import os
import sys
from ConfigParser import ConfigParser
import imaplib
import getpass
import traceback
from pprint import PrettyPrinter
import re
import email
from datetime import datetime


def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options]'
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

    """
    if len(args) < 1:
        parser.print_usage()
        sys.exit(1)
    """

    return (options, args)


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
msg = None


def main(options, args):
    global msg
    config = ConfigParser()
    config.read(['maildump.cfg'])
    pp = PrettyPrinter(indent=4)

    def get_config_option(section, option, default):
        if config.has_option(section, option):
            return config.get(section, option)
        return default

    for section in filter(lambda x: x.startswith('Server:'), config.sections()):
        server_name = section.split('Server:')[1]
        print('[%s]' % (server_name,))
        try:
            # connect and login
            host = config.get(section, 'host')
            user = config.get(section, 'user')
            print('Connecting to', host, 'as', user, '...')
            mail = imaplib.IMAP4_SSL(host)
            if config.has_option(section, 'password'):
                password = config.get(section, 'password')
            else:
                password = getpass.getpass('Enter password for %s: ' % (user,))
            mail.login(user, password)

            # list mailboxes
            rv, data = mail.list()
            assert rv == 'OK'
            print('Mailboxes:')
            pp.pprint(data)

            # compile list of mailboxes to search
            mailboxes = []
            for s in data:
                m = re.match(r'^\((?P<flags>.*)\)\s+"(.*)"\s+"(?P<mailbox>.*)"$', s)
                if m:
                    flags = m.group('flags')
                    mailbox = m.group('mailbox')
                    #print('flags=', flags, 'mailbox=', mailbox)
                    if r'\All' in flags:
                        mailboxes = [mailbox]
                        break
                    else:
                        mailboxes.append(mailbox)
            print('Mailboxes to search:')
            pp.pprint(mailboxes)

            # search mailboxes
            for mailbox in mailboxes:
                print('Selecting mailbox', mailbox)
                rv, data = mail.select(mailbox, readonly=True)
                assert rv == 'OK'
                your_addresses = re.split(r'\s*,\s*', config.get('Search', 'your_addresses').strip())
                their_addresses = re.split(r'\s*,\s*', config.get('Search', 'their_addresses').strip())

                def process_search_results(rv, data):
                    global msg
                    assert rv == 'OK'
                    results = data[0].split()
                    print('Found', len(results), 'results')
                    for id in results:
                        print('Fetching message', id)
                        rv, data = mail.fetch(id, '(RFC822)')
                        assert rv == 'OK'
                        #print(data)
                        msg = email.message_from_string(data[0][1])
                        print('Subject:', msg['Subject'])
                        timestamp = None
                        date_tuple = email.utils.parsedate_tz(msg['Date'])
                        if date_tuple:
                            timestamp = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                            print('Local Date:', timestamp.strftime("%a, %d %b %Y %H:%M:%S"))
                        print('From:', msg['From'])
                        print('To:', msg['To'])
                        print('Cc:', msg['Cc'])
                        print('Bcc:', msg['Bcc'])
                        print('multipart?:', msg.is_multipart())
                        print('content-type', msg.get_content_type())
                        addresses = [x[1] for x in email.utils.getaddresses(
                            msg.get_all('From', []) +
                            msg.get_all('To', []) +
                            msg.get_all('Cc', []) +
                            msg.get_all('Bcc', [])
                        )]
                        print('addresses:', addresses)


                        if msg.get_content_type() == 'multipart/mixed':
                            continue

                        raw_body = ''
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == 'text/plain':
                                    raw_body += part.get_payload() + '\n'
                        else:
                            raw_body = msg.get_payload()
                        #raw_body = msg.get_payload()[0].get_payload()
                        print('Body:', raw_body)

                for their_address in their_addresses:
                    print('Searching for messages from', their_address)
                    process_search_results(*mail.search(None, '(FROM %s)' % (their_address,)))
                    print('Searching for messages to', their_address)
                    process_search_results(*mail.search(None, '(TO %s)' % (their_address,)))

        except Exception:
            print(traceback.format_exc())


if __name__ == '__main__':
    main(*parse_command_line())
