import requests
from optparse import OptionParser

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] USERNAME PASSWORD'
    )
    
    return parser.parse_args()

(options, args) = parse_command_line()

print 'logging in ...'
r = requests.post(
    'http://192.168.0.1/goform/act_set_web_login',
    data = {
        "page": "index.html",
        "admin_user_name": args[0],
        "admin_password": args[1],
    },
)

if not r.ok:
    raise Exception('failed to log in')

print 'setting connection status ...'
r = requests.post(
    'http://192.168.0.1/goform/act_ifx_set_system_status',
    data = {
        "page": "modemstatus_real.html",
        "var:conname": "",
        "var:contype": "",
        "connectflag": "2",
    },
)
