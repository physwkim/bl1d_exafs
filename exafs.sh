#!/usr/bin/bash
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_MAX_ARRAY_BYTES=100000000
export QT_AUTO_SCREEN_SCALE_FACTOR=0
source activate bluesky_202101
cd /home/exafs/bluesky_1d/pal_tools
ipython --profile-dir=/home/exafs/bluesky_1d/profile_collection --gui=qt5 --matplotlib=qt5
