#!python
"""
Read an .idl file and produce a header that deprecates all symbols it declares
"""

from optparse import OptionParser
import os
import sys
import re


def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options]'
    )
    
    # options

    parser.add_option(
        '-o', '--output', dest='output_path', default='deprecate.h',
        help='output path',
    )
    
    (options, args) = parser.parse_args()

    # args

    if len(args) < 1:
        parser.print_usage()
        sys.exit(1)

    return (options, args)


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
KEYWORDS = (
    'typedef enum',
    'typedef struct',
    'interface',
    'runtimeclass',
)

if __name__ == '__main__':

    (options, args) = parse_command_line()
    input_path = args[0]

    symbols = set()

    with open(input_path, 'r') as f:
        line_no = 1
        for line in f:
            for k in KEYWORDS:
                expr = r'^\s*(?P<type>%s)\s+(?P<symbol>[A-Z]\w+)\b[^.]' % (k,)
                m = re.match(expr, line)
                if m:
                    type = m.group('type')
                    symbol = m.group('symbol')
                    print '%d:' % (line_no,), type, symbol
                    symbols.add((symbol, type))
            line_no += 1

    with open(options.output_path, 'w') as f:
        f.writelines(
            [
                '#pragma once\r\n',
            ] +
            [ '#pragma deprecated (%s) /* %s */\r\n' % (s,t) for (s,t) in sorted(symbols, key=lambda x: x[0]) ]
        )