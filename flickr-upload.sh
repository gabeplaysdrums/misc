#!/bin/bash
python flickr-upload.py "/Volumes/Untitled/Users/Arija/Desktop/camera contents - sort this/" -d -o pyflickr-out/ --tag=arijascamera --skip-uploaded-check --no-pictures --threadpool-size=3 $*
