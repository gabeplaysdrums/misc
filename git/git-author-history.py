#!/bin/python

"""
Write log files of git commit history per author
"""

from optparse import OptionParser
import shlex


def parse_command_line():

    parser = OptionParser(
        usage='%prog [options]'
    )

    parser.add_option(
        '-g', '--groups', dest='groups_path', default=None, metavar='PATH',
        help='file denoting author groups',
    )

    parser.add_option(
        '--git-log-options', dest='git_log_options', default=None, metavar='OPTIONS',
        help='additional options to pass to "git log"',
    )

    return parser.parse_args()


(options, args) = parse_command_line()


from git_helpers import cmd_lines, load_author_groups
import subprocess


def get_log_file(author):
    return author.replace('@', '_at_').replace('.', '_') + '.log'


def write_log_file(authors, filename, extra_options=[]):
    args = ['git', 'log'] + [ '--author=' + author for author in authors ] + extra_options
    open(filename, 'w').write(
        subprocess.check_output(args, stderr=subprocess.STDOUT)
    )
    print filename


extra_options = []

if options.git_log_options:
    extra_options = shlex.split(options.git_log_options)

print 'Author commits logged to these files:\n'

if options.groups_path:

    groups = load_author_groups(options.groups_path)

    for group_name, authors in groups.items():
        write_log_file(authors, get_log_file(group_name), extra_options)

else:

    authors = set()

    for line in cmd_lines(*(['git', 'log', '--format=%aE'] + extra_options)):
        line = line.strip()

        if not line:
            continue

        authors.add(line)

    for author in authors:
        write_log_file([author], get_log_file(author), extra_options)

print '\n'