#!/bin/bash
#echo sleeping for 45 minutes ...
#sleep 2700
#python pyflickr-upload.py --no-pictures --tag=arijascamera --tag=wave2 "/Volumes/Untitled/Users/Arija/Desktop/camera contents - sort this/" --threadpool-size=3 --unattend
#python pyflickr-upload.py --no-movies --tag=arijascamera --tag=wave2 "/Volumes/Untitled/Users/Arija/Desktop/camera contents - sort this/" --unattend

# Update date taken of movies now that we can read the metadata from the mov file
python pyflickr-upload.py --tag=arijascamera --tag=wave4 "/Volumes/Untitled/Users/Arija/Desktop/camera contents - sort this/" -o uploaded.csv --no-upload-new-files --unattend --threadpool-size=25 $*
