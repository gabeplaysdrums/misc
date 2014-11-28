#!/bin/python

"""
Clean up old branches from a git repository
"""

from optparse import OptionParser


def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options]'
    )

    parser.add_option(
        '-x', '--exclude', dest='exclude_filters', default=[], metavar='PATTERN',
        help='exclude branches whose names match the given pattern',
        action='append',
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


def cmd_lines(*args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT).split('\n')


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
        return self.__updated


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

    branch = parse_branch(line)

    if any(fnmatch.fnmatch(branch.name, pattern) for pattern in options.exclude_filters):
        continue

    branches.append(branch)

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

for branch in sorted(filter(lambda x: x.remote is not None, branches), key=lambda x: x.last_updated_date):
    f.write('# %-30s # %s\n' % (branch.fqn, branch.last_updated_date.strftime(DATE_FORMAT)))

f.write('\n')
f.close()

# find editor command

editor_command = None

try:
    for line in cmd_lines('git', 'config', 'core.editor'):
        line = line.strip()
        if line:
            editor_command = line
            break
except subprocess.CalledProcessError:
    pass

if not editor_command:
    editor_command = 'vi'

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