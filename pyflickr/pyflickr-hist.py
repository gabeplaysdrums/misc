#!/usr/bin/python
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
        '-t', '--cluster-threshold', dest='cluster_thresh', default=25,
        help='number of photos per day considered significant when clustering',
    )

    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.print_usage()
        sys.exit(1)

    return (options, args)

if __name__ == "__main__":

    (options, args) = parse_command_line()

    class DateInfo:
        
        def __init__(self, date_string):
            self.date = datetime.strptime(date_string, '%Y-%m-%d').date()
            self._photos = []
            self._moments = None

        def add_photo(self, photo_id, date_taken, shorturl):
            self._photos.append({
                'photo_id': photo_id,
                'date_taken': datetime.strptime(date_taken, FLICKR_DATE_FORMAT),
                'shorturl': shorturl,
            })
            self._moments = None

        def moments(self):
            if self._moments:
                return self._moments
            self._photos.sort(key=lambda x: x['date_taken'])
            self._moments = []
            prev_date_taken = None
            for photo in self._photos:
                if not prev_date_taken or (photo['date_taken'] - prev_date_taken) > timedelta(seconds=1):
                    self._moments.append({
                        'date_taken': photo['date_taken'],
                        'last_date_taken': None,
                        'photos': [],
                    })
                self._moments[-1]['photos'].append(photo)
                prev_date_taken = photo['date_taken']
                self._moments[-1]['last_date_taken'] = prev_date_taken
            return self._moments

        def photos(self):
            return self._photos

    input_path = args[0]
    hist = dict()
    count = 0

    with open(input_path, 'rb') as csvfile:
        reader = DictReader(csvfile)
        for row in reader:
            date_string = re.match(r'\d{4}-\d{2}-\d{2}', row['date_taken']).group(0)
            if not date_string in hist:
                hist[date_string] = DateInfo(date_string)
            hist[date_string].add_photo(row['photo_id'], row['date_taken'], row['shorturl'])
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
            days = (self.end - self.start).days + 1
            return '%d moments from %s to %s (%d days, %d moments/day)' % (
                self.count,
                self.start.strftime('%Y-%m-%d'),
                self.end.strftime('%Y-%m-%d'),
                days,
                self.count / days,
            )

    curr_cluster = None
    cluster_thresh = int(options.cluster_thresh)
    output_path_split = os.path.splitext(options.output_path)
    moments_path = output_path_split[0] + '.moments' + output_path_split[1]
    clusters_path = output_path_split[0] + '.clusters' + output_path_split[1]

    with open(options.output_path, 'wb') as csvfile:
        writer = DictWriter(csvfile, extrasaction='ignore', fieldnames=(
            'date',
            'photo_count',
            'moment_count',
        ))
        writer.writeheader()
        with open(moments_path, 'wb') as moments_csvfile:
            moments_writer = DictWriter(moments_csvfile, extrasaction='ignore', fieldnames=(
                'moment_date_taken',
                'photo_count',
                'duration',
                'photo_id',
                'date_taken',
                'shorturl',
            ))
            moments_writer.writeheader()
            for date_string in sorted(hist.keys()):
                photo_count = len(hist[date_string].photos())
                moment_count = len(hist[date_string].moments())

                writer.writerow({
                    'date': date_string,
                    'photo_count': photo_count,
                    'moment_count': moment_count,
                })

                for moment in hist[date_string].moments():
                    moments_writer.writerow({
                        'moment_date_taken': moment['date_taken'].strftime(FLICKR_DATE_FORMAT),
                        'photo_count': len(moment['photos']),
                        'duration': (moment['last_date_taken'] - moment['date_taken']).total_seconds()
                    })
                    for photo in moment['photos']:
                        moments_writer.writerow({
                            'moment_date_taken': moment['date_taken'].strftime(FLICKR_DATE_FORMAT),
                            'photo_id': photo['photo_id'],
                            'date_taken': photo['date_taken'],
                            'shorturl': photo['shorturl'],
                        })

                if moment_count < cluster_thresh:
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
                    curr_cluster.count = moment_count
                    continue

                if delta and delta < cluster_delta:
                    curr_cluster.end = date
                    curr_cluster.count += moment_count
                    continue

                clusters.append(curr_cluster)
                curr_cluster = Cluster()
                curr_cluster.start = date
                curr_cluster.end = date
                curr_cluster.count = moment_count

            clusters.append(curr_cluster)

    with open(clusters_path, 'wb') as csvfile:
        writer = DictWriter(csvfile, extrasaction='ignore', fieldnames=(
            'date_start',
            'date_end',
            'date_span',
            'moment_count'
        ))
        writer.writeheader()
        print 'Significant clusters:'
        for cluster in reversed(sorted(clusters, key=lambda x: x.count)):
            print '  ' + str(cluster)
            writer.writerow({
                'date_start': cluster.start.strftime('%Y-%m-%d'),
                'date_end': cluster.end.strftime('%Y-%m-%d'),
                'date_span': (cluster.end - cluster.start).days + 1,
                'moment_count': cluster.count,
            })

    print 'Done!'
