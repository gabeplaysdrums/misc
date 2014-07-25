"""
Produce a histogram of photos by date from a CSV of photo data
"""

from csv import DictReader, DictWriter
from datetime import datetime, timedelta
from optparse import OptionParser
from pyflickr_utils import *
import os
import re
import sys

def parse_command_line():

    parser = OptionParser(
        usage = '%prog [options] uploaded.csv'
    )

    parser.add_option(
        '-o', '--output', dest='output_path', default='hist.csv',
        help='path to output CSV file',
    )

    parser.add_option(
        '-n', '--num-samples', dest='num_samples', default=None,
        help='maximum number of samples from input CSV',
    )

    parser.add_option(
        '-t', '--cluster-threshold', dest='cluster_thresh', default=50,
        help='number of photos per day considered significant when clustering',
    )

    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.print_usage()
        sys.exit(1)

    return (options, args)

if __name__ == "__main__":

    (options, args) = parse_command_line()

    input_path = args[0]
    hist = dict()
    count = 0

    with open(input_path, 'rb') as csvfile:
        reader = DictReader(csvfile)
        for row in reader:
            date = re.match(r'\d{4}-\d{2}-\d{2}', row['date_taken']).group(0)
            if not date in hist:
                hist[date] = 0
            hist[date] += 1
            count += 1
            if options.num_samples and count > options.num_samples:
                break

    print 'Processed %d samples'  % (count,)

    prev_date = None
    cluster_delta = timedelta(days=2)
    clusters = []

    class Cluster:
        start = None
        end = None
        count = 0

        def __str__(self):
            return '%d photos from %s to %s (%d days)' % (
                self.count,
                self.start.strftime('%Y-%m-%d'),
                self.end.strftime('%Y-%m-%d'),
                (self.end - self.start).days + 1,
            )

    curr_cluster = None
    cluster_thresh = int(options.cluster_thresh)

    with open(options.output_path, 'wb') as csvfile:
        writer = DictWriter(csvfile, extrasaction='ignore', fieldnames=(
            'date',
            'count',
        ))
        writer.writeheader()
        for date_string in sorted(hist.keys()):
            writer.writerow({
                'date': date_string,
                'count': hist[date_string],
            })

            if hist[date_string] < cluster_thresh:
                continue

            date = datetime.strptime(date_string, '%Y-%m-%d')
            delta = None
            if prev_date:
                delta = date - prev_date
            prev_date = date

            if not curr_cluster:
                curr_cluster = Cluster()
                curr_cluster.start = date
                curr_cluster.end = date
                curr_cluster.count = hist[date_string]
                continue

            if delta and delta < cluster_delta:
                curr_cluster.end = date
                curr_cluster.count += hist[date_string]
                continue

            clusters.append(curr_cluster)
            curr_cluster = Cluster()
            curr_cluster.start = date
            curr_cluster.end = date
            curr_cluster.count = hist[date_string]

        clusters.append(curr_cluster)

    output_path_split = os.path.splitext(options.output_path)
    clusters_path = output_path_split[0] + '.clusters' + output_path_split[1]

    with open(clusters_path, 'wb') as csvfile:
        writer = DictWriter(csvfile, extrasaction='ignore', fieldnames=(
            'date_start',
            'date_end',
            'date_span',
            'count'
        ))
        writer.writeheader()
        print 'Significant clusters:'
        for cluster in reversed(sorted(clusters, key=lambda x: x.count)):
            print '  ' + str(cluster)
            writer.writerow({
                'date_start': cluster.start.strftime('%Y-%m-%d'),
                'date_end': cluster.end.strftime('%Y-%m-%d'),
                'date_span': (cluster.end - cluster.start).days + 1,
                'count': cluster.count,
            })

    print 'Done!'
