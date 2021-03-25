import os
import sys
import re
import datetime
import shutil
import warnings
import time as ttime
import logging
import datetime
from pymongo import MongoClient
from silx.gui import qt

from bluesky import RunEngine
from bluesky.utils import get_history

import databroker
from databroker import Broker

from utils import loadPV

DEBUG_MODE = False
GATE_MODE = True

logger = logging.getLogger('__name__')
logging.basicConfig(format='%(asctime)-15s [%(name)s:%(levelname)s] %(message)s',
                    level=logging.ERROR)

warnings.filterwarnings("ignore", message="invalid value encountered in log")
warnings.filterwarnings("ignore", message="divide by zero encountered in log")
warnings.filterwarnings("ignore", message="divide by zero encountered in double_scalars")
warnings.filterwarnings("ignore", message="Creating an ndarray from ragged nested sequences")
warnings.filterwarnings("ignore", message="Setting the line's pick radius via set_picker is deprecated")
warnings.filterwarnings("ignore", message="The global colormaps dictionary is no longer considered public API")

# Set up a RunEngine
RE = RunEngine({})

# PV parameter loadings
pv_names = loadPV()

# Drop Previous db older than one week.
client = MongoClient('127.0.0.1', 27017)

try:
    db = client.metadatastore_production_v1

    oneWeekAgo = ttime.time() - 24 * 3600 * 7

    for item in db.list_collection_names():
        collection = db[item]
        collection.delete_many({ "time": { "$lt" : oneWeekAgo }})

except Exception as e:
    print("Error during clear mongodb : {}".format(e))

# Use Mongodb
config = {
    'description': 'BL1D production mongo',
    'metadatastore': {
        'module' : 'databroker.headersource.mongo',
        'class'  : 'MDS',
        'config' : {
            'host'     : 'localhost',
            'port'     : 27017,
            'database' : 'metadatastore_production_v1',
            'timezone' : 'Asia/Seoul'
        }
    },
    'assets': {
        'module' : 'databroker.assets.mongo',
        'class'  : 'Registry',
        'config' : {
            'host'     : 'localhost',
            'port'     : 27017,
            'database' : 'filestore',
        },
    },
}

db=Broker.from_config(config)

# Subscribe metadatastore to documents.
# If this is removed, data is not saved to metadatastore.
RE.subscribe(db.insert)

# Set up SupplementalData.
from bluesky import SupplementalData
sd = SupplementalData()
RE.preprocessors.append(sd)

# Add a progress bar.
from timeit import default_timer as timer

start = timer()
from bluesky.utils import ProgressBarManager
pbar_manager = ProgressBarManager()
#RE.waiting_hook = pbar_manager

# Register bluesky IPython magics.
from bluesky.magics import BlueskyMagics
get_ipython().register_magics(BlueskyMagics)

# At the end of every run, verify that files were saved and
# print a confirmation message.
from bluesky.callbacks.broker import verify_files_saved
# RE.subscribe(post_run(verify_files_saved), 'stop')

# Import matplotlib and put it in interactive mode.
import matplotlib.pyplot as plt
plt.ion()

# convenience imports
from bluesky.callbacks import *
from bluesky.callbacks.broker import *
from bluesky.simulators import *
from bluesky.plans import *
import numpy as np

# Set up the BestEffortCallback.
from bluesky.callbacks.best_effort import BestEffortCallback
bec = BestEffortCallback()
# bec_token = RE.subscribe(bec)
# bec.disable_plots()
peaks = bec.peaks  # just as alias for less typing

from pathlib import Path
from historydict import HistoryDict

# be nice on segfaults
import faulthandler
faulthandler.enable()

# Set default timeouts
from ophyd.signal import EpicsSignalBase
EpicsSignalBase.set_default_timeout(timeout=10, connection_timeout=5)

RE.is_aborted = False

# Set up default metadata.
RE.md['group'] = 'pal'
RE.md['beamline_id'] = 'PAL'
RE.md['proposal_id'] = None

qt.QApplication.setAttribute(qt.Qt.AA_EnableHighDpiScaling)
app = qt.QApplication([])

font=qt.QFont()
font.setFamily('DejaVu Sans')
font.setPointSize(10)
app.setFont(font)

username, ok = qt.QInputDialog.getText(None, 'Info', "please Enter Your Name.")

# Set up default metadata.
if ok and username:
    RE.md['user'] = username
else:
    RE.md['user'] = 'bl1d'

print('1111')
stop1 = timer()

print(stop1 -start)
print('00 done')
