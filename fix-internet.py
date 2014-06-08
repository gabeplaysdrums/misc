from datetime import datetime
from optparse import OptionParser
import requests
import time

RETRY_SECONDS = 5

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] USERNAME PASSWORD'
    )
    
    parser.add_option(
        '-d', '--daemon', dest='daemon', default=False,
        help='run as a daemon (reset connection periodically)',
        action='store_true',
    )
    
    parser.add_option(
        '-t', '--interval', dest='reset_minutes', default=1,
        help='time between attempts in minutes',
    )
    
    return parser.parse_args()

(options, args) = parse_command_line()

if options.daemon:
    print 'running in daemon mode\n'

reset_minutes = int(options.reset_minutes)

while (True):

    print '-- ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' --'

    try:
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
    
        def check_connection():
            print 'getting connection status ...'
            r = requests.get('http://192.168.0.1/modemstatus_real.html')
            
            if not r.ok:
                raise Exception('failed to get connection status')
            
            return (
                'var iphy_conn_state = "1";' in r.text and 
                'var iisp_conn_state = "1";' in r.text
            )
        
        connected = check_connection()
        tries = 5
        
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
    
            connected = check_connection()
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

    except Exception as ex:
        print 'Warning: encountered an exception: ' + ex

    if not options.daemon:
        break

    print 'going back to sleep for %d minutes ...\n' % (reset_minutes,)
    time.sleep(reset_minutes * 60)
