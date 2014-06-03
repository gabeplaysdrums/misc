import requests
from optparse import OptionParser
import time

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

tries = 5
connected = False
RETRY_SECONDS = 5

while not connected and tries > 0:

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
    
    if not (r.ok and 'modemstatus_real.html' in r.text):
        raise Exception('failed to set connection status')
    
    print 'getting connection status ...'
    r = requests.get('http://192.168.0.1/modemstatus_real.html')
    
    if not r.ok:
        raise Exception('failed to get connection status')
    
    connected = (
        'var iphy_conn_state = "1";' in r.text and 
        'var iisp_conn_state = "1";' in r.text
    )

    tries -= 1
    
    print 'connected: %s' % (connected,)

    if connected:
        break

    if tries == 0:
        break

    print 'Retrying in %d seconds (%d remaining) ...' % (RETRY_SECONDS, tries)
    time.sleep(RETRY_SECONDS)

if connected:
    print 'Success!'
else:
    print 'Failed!'
