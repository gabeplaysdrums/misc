import subprocess
import re


def cmd_lines(*args):
    """
    Run a command and return output lines
    :param args: list of command line arguments
    :return: iterable of output lines
    """
    return subprocess.check_output(args, stderr=subprocess.STDOUT).split('\n')


def get_editor_command():
    """
    Get the git editor command
    :return: the command
    """
    try:
        for line in cmd_lines('git', 'config', 'core.editor'):
            line = line.strip()
            if line:
                return line
    except subprocess.CalledProcessError:
        pass

    return 'vi'


def load_author_groups(filename):
    """
    Load list of author groups from a file
    :param filename:
    :return: dict of groups
    """
    groups = dict()
    group_name = None

    for line in open(filename):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'\[(.*)\]', line)
        if m:
            group_name = m.group(1)
            groups[group_name] = []
            continue
        groups[group_name].append(line)

    return groups