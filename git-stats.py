#!/bin/python

from optparse import OptionParser

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options]'
    )

    parser.add_option(
        '-g', '--groups', dest='groups_path', default=None, metavar='PATH',
        help='file denoting author groups',
    )

    parser.add_option(
        '-x', '--exclude', dest='exclude_filters', default=[], metavar='DIR',
        help='exclude the given path filter',
        action='append',
    )

    return parser.parse_args()

(options, args) = parse_command_line()

import subprocess
import re
import fnmatch

groups = dict()

if options.groups_path:
    group_name = None
    for line in open(options.groups_path):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'\[(.*)\]', line)
        if m:
            group_name = m.group(1)
            groups[group_name] = []
            continue
        groups[group_name].append(line)

if options.exclude_filters:
    print 'excluding:'
    for f in options.exclude_filters:
        print '    ' + f
    print ''

line_counts = dict()

for filename in subprocess.check_output(
    ['git', 'ls-tree', '-r', '--name-only', 'HEAD'],
    stderr=subprocess.STDOUT
).split('\n'):

    if not filename:
        continue

    if any(fnmatch.fnmatch(filename, f) for f in options.exclude_filters):
        continue

    print filename

    for line in subprocess.check_output(
        ['git', 'blame', '-e', 'HEAD', filename], stderr=subprocess.STDOUT
    ).split('\n'):

        if not line:
            continue

        m = re.search(r'[0-9a-f]{7}\s+.*\(\<(.+)\>\s+\d{4}-\d{2}-\d{2}', line)

        if (m):
            author = m.group(1)
            if not author in line_counts:
                line_counts[author] = 0
            line_counts[author] += 1
        else:
            print 'warning: could not parse line:'
            print '    "' + line[:60] + '..."'


def print_table(line_counts, author_label='Author'):

    total_lines = sum(line_counts.values())

    print ''
    print '%-40s %5s %7s' % (author_label, 'Count', 'Percent')
    print '%-40s %5s %7s' % ('======',     '=====', '=======')

    for author, count in reversed(sorted(
        line_counts.items(), key=lambda x: x[1]
    )):
        print '%-40s %5d %6.2f%%' % (
            author[:40], 
            count, 
            100.0 * count / total_lines
        )


print_table(line_counts)

if options.groups_path:
    group_counts = dict()
    other_count = sum(line_counts.values())
    for group_name, authors in groups.items():
        group_counts[group_name] = 0
        for author in authors:
            if not author in line_counts:
                continue
            group_counts[group_name] += line_counts[author]
            other_count -= line_counts[author]
    group_counts['(other)'] = other_count
    print_table(group_counts, author_label='Group')

print ''
