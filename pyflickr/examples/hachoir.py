from hachoir_core.error import HachoirError
from hachoir_core.cmd_line import unicodeFilename
from hachoir_parser import createParser
from hachoir_core.tools import makePrintable
from hachoir_metadata import extractMetadata
from hachoir_core.i18n import getTerminalCharset
from sys import argv, stderr, exit

if len(argv) != 2:
    print >>stderr, "usage: %s filename" % argv[0]
    exit(1)
filename = argv[1]
filename, realname = unicodeFilename(filename), filename
parser = createParser(filename, realname)
if not parser:
    print >>stderr, "Unable to parse file"
    exit(1)
try:
    metadata = extractMetadata(parser)
except HachoirError, err:
    print "Metadata extraction error: %s" % unicode(err)
    metadata = None
if not metadata:
    print "Unable to extract metadata"
    exit(1)

text = metadata.exportPlaintext()
charset = getTerminalCharset()
for line in text:
    print makePrintable(line, charset)
