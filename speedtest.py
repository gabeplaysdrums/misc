import os
from datetime import datetime
import time
import re
from csv import DictWriter

if __name__ == "__main__":

    FIELDS = (
        'Date',
        'Ping',
        'Download',
        'Upload',
    )

    path = 'speedtest-results.csv'
    append = os.path.isfile(path)

    with open(path, 'ab') as csvfile:
        writer = DictWriter(csvfile, FIELDS, extrasaction='ignore')
        if not append:
            writer.writeheader()
        while True:
            print 'Running speed test ...'

            data = dict()
            for field in FIELDS:
                data[field] = None

            data['Date'] = datetime.now()

            for line in os.popen('speedtest-cli --simple').readlines():
                m = re.match(r'Ping:\s+(\d+(\.\d+)?)\s+ms', line)
                if m:
                    data['Ping'] = float(m.group(1))
                m = re.match(r'Download:\s+(\d+(\.\d+)?)\s+Mbits/s', line)
                if m:
                    data['Download'] = float(m.group(1))
                m = re.match(r'Upload:\s+(\d+(\.\d+)?)\s+Mbits/s', line)
                if m:
                    data['Upload'] = float(m.group(1))

            writer.writerow(data)
            print 'Ping: %.2f ms, Download: %.2f Mbits/s, Upload: %.2f Mbits/s' % (
                data['Ping'], data['Download'], data['Upload']
            )
            time.sleep(60*10)
