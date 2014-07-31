PYFLICKR_ROOT=/Users/Gabe/Repos/pyflickr

#python $PYFLICKR_ROOT/pyflickr-upload.py --tag=arijascamera "/Users/Gabe/Pictures/Arijas Camera/" -o /Users/Gabe/Skydrive/uploaded.csv --no-movies $*
#python $PYFLICKR_ROOT/pyflickr-upload.py --tag=arijascamera "/Users/Gabe/Pictures/Arijas Camera/" -o /Users/Gabe/Skydrive/uploaded.csv --no-pictures --threadpool-size=3 $*
python $PYFLICKR_ROOT/pyflickr-upload.py --tag=arijascamera "/Volumes/Untitled/Users/Arija/Desktop/camera contents - sort this" -o /Users/Gabe/Skydrive/uploaded.csv --no-pictures --threadpool-size=1 $*
