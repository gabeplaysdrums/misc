#!/bin/python

"""
Clean up old branches from a git repository
"""

from optparse import OptionParser


def parse_command_line():

    parser = OptionParser(
        usage='%prog [options]'
    )

    parser.add_option(
        '-x', '--exclude', dest='exclude_filters', default=[], metavar='PATTERN',
        help='exclude branches whose names match the given pattern',
        action='append',
    )

    parser.add_option(
        '-v', '--verbose', dest='verbose', default=False,
        help='print verbose output',
        action='store_true',
    )

    return parser.parse_args()

(options, args) = parse_command_line()


import subprocess
import tempfile
import os
import sys
import re
from datetime import datetime
import fnmatch
from git_helpers import cmd_lines, get_editor_command


class Branch:
    def __init__(self, name, remote=None):
        self.name = name
        self.remote = remote
        self.__updated = None

    @property
    def fqn(self):
        if self.remote:
            return REMOTE_PREFIX + self.remote + '/' + self.name
        return self.name

    @property
    def last_updated_date(self):
        if self.__updated is None:
            for line in cmd_lines('git', 'log', '-g', '-n', '1', '--date=local', '--pretty=%gd', self.fqn, '--'):
                m = re.search(r'\{(.*)\}', line)
                if m:
                    # Thu Nov 27 19:17:23 2014
                    self.__updated = datetime.strptime(m.group(1), DATE_FORMAT)
                    break
            printv('branch last updated: branch=', self, ', date=', self.__updated)
        return self.__updated

    def __str__(self):
        return 'remote=%s, name=%s' % (self.remote, self.name)


def printv(*args):
    if options.verbose:
        print ' '.join(str(x) for x in args)


REMOTE_PREFIX = 'remotes/'
DATE_FORMAT = '%a %b %d %H:%M:%S %Y'


def parse_branch(s):
    if s.startswith(REMOTE_PREFIX):
        s = s[len(REMOTE_PREFIX):]
        i = s.index('/')
        remote = s[:i]
        name = s[i+1:]
        return Branch(name, remote)
    else:
        return Branch(s)


# build list of branches

branches = []

for line in cmd_lines('git', 'branch', '--all'):
    line = line.strip()

    # skip empty lines
    if not line:
        continue

    # skip the current branch
    if line[0] == '*':
        continue

    if not re.match(r'[a-zA-Z0-9-\._]+(\/[a-zA-Z0-9-\._]+)*$', line):
        continue

    branch = parse_branch(line)

    if any(fnmatch.fnmatch(branch.name, pattern) for pattern in options.exclude_filters):
        continue

    branches.append(branch)
    printv('found branch:', branch)

filename = os.path.join(tempfile.gettempdir(), 'GIT_CLEANUP_BRANCHES_LIST')
f = open(filename, 'w')

f.writelines([
    '# List the branches you wish to delete.\n',
    '# Lines beginning with "#" will be ignored.\n',
    '# Oldest branches (least recently updated) are listed first.\n',
    '\n',
    '# !! Remote branches will be permanently deleted from the remote !!\n',
])

f.writelines([
    '\n',
    '# Local Branches\n',
    '# ==============\n',
])

for branch in sorted(filter(lambda x: x.remote is None, branches), key=lambda x: x.last_updated_date):
    f.write('# %-30s # %s\n' % (branch.fqn, branch.last_updated_date.strftime(DATE_FORMAT)))

f.writelines([
    '\n',
    '# Remote Branches\n',
    '# ===============\n',
])

def compare_dates(x, y):
    if x is None and y is None:
        return 0
    if x is None:
        return -1
    if y is None:
        return 1
    return int((x - y).total_seconds())

for branch in sorted(filter(lambda x: x.remote is not None, branches), key=lambda x: x.last_updated_date, cmp=compare_dates):
    f.write('# %-30s # %s\n' % (branch.fqn, branch.last_updated_date.strftime(DATE_FORMAT) if branch.last_updated_date is not None else '(unknown)'))

f.write('\n')
f.close()

# find editor command

editor_command = get_editor_command()

# show the list

os.system(editor_command + ' ' + filename)

# parse the list

branches = []
f = open(filename, 'r')

for line in f:
    try:
        line = line[:line.index('#')]
    except ValueError:
        pass
    line = line.strip()
    if not line:
        continue
    branch = parse_branch(line)

    if any(fnmatch.fnmatch(branch.name, pattern) for pattern in options.exclude_filters):
        continue

    branches.append(branch)

f.close()

# confirm

if not branches:
    print 'Empty branch list.  Aborting.'
    sys.exit(1)

print ''
print 'Will now permanently delete %d branches:' % (len(branches),)
print ''
for branch in branches:
    print '    ', branch.fqn
print ''

if raw_input('Would you like to continue? (y/n) ') != 'y':
    print 'Aborted.'
    sys.exit(2)

# delete the branches

for branch in branches:
    if branch.remote:
        os.system('git push ' + branch.remote + ' :' + branch.name)
    else:
        os.system('git branch -D ' + branch.name)
