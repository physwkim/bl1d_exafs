import sys
import re
import os
import math
import time as ttime
import numpy as np
import datetime
import threading
from collections import OrderedDict, deque
from timeit import default_timer as timer
import zmq
import warnings

import logging

import bluesky.plans as bp
from bluesky.callbacks.core import CallbackBase
from databroker import Broker

from silx.gui import qt
from silx.gui.utils.concurrent import submitToQtMainThread as _submit

from StatusWidget import StatusWidget
from Plot1DCustom import Plot1DCustom

from utils import path, derivative, loadPV

from thread import QThreadFuture, manager

from scan_utils import UpdatePlotThread
from scan_utils import CheckDcmThread

logger = logging.getLogger('__name__')
logging.basicConfig(format='%(asctime)-15s [%(name)s:%(levelname)s] %(message)s',
                    level=logging.ERROR)

_hc = 12398.5
_si_111 = 5.4309/np.sqrt(3)

DEBUG = False

ColorDict = {}
ColorDict[0] = 'blue'
ColorDict[1] = 'red'
ColorDict[2] = 'green'
ColorDict[3] = 'orange'
ColorDict[4] = 'pink'
ColorDict[5] = 'brown'
ColorDict[6] = 'darkCyan'
ColorDict[7] = 'violet'
ColorDict[8] = 'darkblue'
ColorDict[9] = 'gray'
ColorDict[10] = 'darkBrown'

ZOrder = {}
ZOrder[0] = 30
ZOrder[10] = 9
ZOrder[1] = 8
ZOrder[2] = 7
ZOrder[3] = 6
ZOrder[4] = 5
ZOrder[5] = 4
ZOrder[6] = 3
ZOrder[7] = 2
ZOrder[8] = 1
ZOrder[9] = 0

#ZeroMQ Context
CONTEXT = zmq.Context()

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

class TestThread(qt.QThread):

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.event = threading.Event()
        self.force_update = deque()

        self.xdata = np.arange(2000)
        self.ydata = np.random.rand(2000)

    def run(self):
        idx = 1
        while True:
            logger.error("waiting")
            self.event.wait()
            logger.error("start")
            xdata = self.xdata[:idx]
            ydata = self.ydata[:idx]

            curve = self.parent.plot.getCurve('Data 0')

            if curve:
                oldXData = curve.getXData(copy=True)
                oldYData = curve.getYData(copy=True)

                if np.any(oldXData != xdata) or np.any(oldYData != ydata):
                    _submit(self.parent.plot.addCurve,
                                                    xdata,
                                                    ydata,
                                                    legend='Data 0',
                                                    color=ColorDict[0],
                                                    linestyle='-',
                                                    resetzoom=True,
                                                    z=ZOrder[0],
                                                    selectable=False)

                    _submit(self.parent.plot.addCurve,
                                                    xdata,
                                                    ydata* 5,
                                                    legend='Data 1',
                                                    color=ColorDict[1],
                                                    linestyle='-',
                                                    resetzoom=True,
                                                    z=ZOrder[1],
                                                    selectable=False)
            else:
                _submit(self.parent.plot.addCurve,
                                                xdata,
                                                ydata,
                                                legend='Data 0',
                                                color=ColorDict[0],
                                                linestyle='-',
                                                resetzoom=True,
                                                z=ZOrder[0],
                                                selectable=False)

                _submit(self.parent.plot.addCurve,
                                                xdata,
                                                ydata,
                                                legend='Data 1',
                                                color=ColorDict[1],
                                                linestyle='-',
                                                resetzoom=True,
                                                z=ZOrder[1],
                                                selectable=False)


            if idx >= 2000:
                idx = 1
            else:
                idx += 10

            ttime.sleep(0.1)
            logger.error("clear")
            self.event.clear()

    def trigger(self):
        """force plot update"""
        self.update()
        self.force_update.append(1)

    def update(self, *args):
        """ Update DataViewer """
        self.event.set()

class DataViewer(qt.QMainWindow):
    """Standalone DataViewer"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # PV names
        self.pv_names = loadPV()

        # ZMQ Ports
        self.zmqSendPort = 5301
        self.zmqRecvPort = 5201

        try:
            self.zmqSendSock = CONTEXT.socket(zmq.PUB)
            self.zmqSendSock.bind("tcp://*:" + str(self.zmqSendPort))
        except:
            self.zmqSendSock = None
            print("Failed to bind to socket : {}".format(self.zmqSendPort))

        # MainWindow Title
        self.setWindowTitle("DataViewer")

        # Initialize
        self._dragging = False
        self._last_y_axis_type = 0
        self._last_tab_index = 0
        self.plot_type = 'measure'
        self.start_timer = 0

        self.settings = {}
        self.settings['E0'] = 8333
        self.settings['sdd'] = False
        self.settings['ratio'] = 0.7
        self.settings['plot_type'] = 'measure'
        self.settings['blink'] = False
        self.settings['scanCounts'] = 1

        # DataBroker
        self.dbv1 = Broker.from_config(config)
        self.db = self.dbv1.v2

        # Main QWidget
        main_panel = qt.QWidget(self)
        main_panel.setLayout(qt.QVBoxLayout())
        self.setCentralWidget(main_panel)

        # Status Widget
        self.status = StatusWidget(self)
        self.status.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)

        # Intialize plot
        self.plot = Plot1DCustom(self, 'mpl')
        self.plot.getLegendsDockWidget().show()
        self.plot.setBackgroundColor('#FCF9F6')
        self.plot.setGraphXLabel("Energy [eV]")
        self.plot.setGraphYLabel("Counts [Arbs.]")
        self.plot.setDataMargins(0.01, 0.01, 0.01, 0.01)

        # Layout
        main_panel.layout().addWidget(self.status)
        main_panel.layout().addWidget(self.plot)

        # Adjust operation graph's margin(left, bottom, width height)
        self.plot._backend.ax.set_position([0.1, 0.05, 0.83, 0.93])
        self.plot._backend.ax2.set_position([0.1, 0.05, 0.83, 0.93])

        # self.updatePlotThread = UpdatePlotThread(self)
        # self.updatePlotThread.daemon = True
        # self.updatePlotThread.start()

        self.updatePlotThread = TestThread(self)
        self.updatePlotThread.daemon = True
        self.updatePlotThread.start()

        # Upper pannel for safety
        self.status.abortButton.clicked.connect(self.abortScan)

        # Manage zoom history of plot
        self.status.x_axis_type_combo_box.currentIndexChanged.connect(self.clearZoomHistory)
        self.status.y_axis_type_combo_box.currentIndexChanged.connect(self.clearZoomHistory)

        # Start ZMQ Recv Thread
        self.zmqRecvThread = QThreadFuture(self.receiveZmq)
        self.zmqRecvThread.start()

        if self.status:
            # RunEngine Notifier
            self._dummyIndex = 0
            self.notifyTimer = qt.QTimer()
            self.notifyTimer.timeout.connect(self._notifyColor)
            self.notifyTimer.start(1000)

        # As a thread that monitors the DCM moving state, check the case
        # that it is normally located but is displaying as moving
        # self.checkDcmThread = CheckDcmThread()
        # self.checkDcmThread.daemon = True
        # self.checkDcmThread.start()

        # Connections
        self.status.num_of_history_spin_box.valueChanged.connect(self.updatePlotThread.trigger)
        self.status.x_axis_type_combo_box.currentIndexChanged.connect(self.updatePlotThread.trigger)
        self.status.y_axis_type_combo_box.currentIndexChanged.connect(self.updatePlotThread.trigger)
        self.status.derivativeCB.stateChanged.connect(self.updatePlotThread.trigger)

        # Check for dragging
        self.plot.sigPlotSignal.connect(self.checkDragging)

        # Initial query
        self.sendZmq('ViewerInitialized')

        # self.status.backend_combo_box.currentIndexChanged.connect(self.setBackend)

        # Set plotbackend to opengl
        # self.setBackend(1)

    def checkDragging(self, obj):
        if 'legend' in obj.keys():
            if obj['legend'] == '__SELECTION_AREA__':
                if obj['action'] == 'add':
                    self.dragging = True
                else:
                    self.dragging = False

    @property
    def dragging(self):
        return self._dragging

    @dragging.setter
    def dragging(self, value):
        self._dragging = value

    def sendZmq(self, msg):
        """Send message"""
        if self.zmqSendSock:
            self.zmqSendSock.send(msg.encode())
        else:
            print("Zmq send sock is not exist")

    def receiveZmq(self):
        sock = CONTEXT.socket(zmq.SUB)
        sock.connect("tcp://localhost:" + str(self.zmqRecvPort))
        sock.setsockopt_string(zmq.SUBSCRIBE, '')

        while True:
            msg = sock.recv().decode()
            logger.error("{}".format(msg))
            if len(msg):
                try:
                    if msg.startswith('tabChanged'):
                        index = int(msg.split(':')[-1].strip())
                        self.tabChanged(index)

                    elif msg.startswith('UpdateViewer'):
                        self.updatePlotThread.update()

                    elif msg.startswith('XLabel:'):
                        label = msg.split(':')[-1]
                        _submit(self.plot.setGraphXLabel, label)

                    elif msg.startswith('YLabel:'):
                        label = msg.split(':')[-1]
                        _submit(self.plot.setGraphYLabel, label)

                    elif msg.startswith('Blink:'):
                        value = msg.split(':')[-1]
                        if value.lower() in ('true', '1'):
                            self.settings['blink'] = True
                        else:
                            self.settings['blink'] = False
                    elif msg.startswith('RunEngine:'):
                        value = msg.split(':')[-1]
                        _submit(self.status.engineStatus.setText, value)

                    elif msg.startswith('RemoveCurves'):
                        _submit(self.plot.clearCurves)

                    elif msg.startswith('RemoveCurve:'):
                        value = msg.split(':')[-1]
                        _submit(self.plot.removeCurve, value)

                    elif msg.startswith('FlyStartTime:'):
                        value = np.double(msg.split(':')[-1])
                        self.start_timer = value

                    elif msg.startswith('DisableAbortButton:'):
                        value = msg.split(':')[-1]
                        if value.lower() in ('true', '1'):
                            _submit(self.status.abortButton.setDisabled, True)
                        else:
                            _submit(self.status.abortButton.setDisabled, False)
                except Exception as e:
                    print("Exception in receiveZmq : {}".format(e))

    def abortScan(self):
        """Abort RunEngine"""
        msg = 'Abort'
        self.sendZmq(msg)

    def setBackend(self, index):
        """Change graph's backend to matplotlib or opengl"""
        if index == 0:
            self.plot.setBackend('mpl')

            # Adjust operation graph's margin(left, bottom, width height)
            self.plot._backend.ax.set_position([0.1, 0.05, 0.83, 0.93])
            self.plot._backend.ax2.set_position([0.1, 0.05, 0.83, 0.93])
        else:
            self.plot.setBackend('opengl')

    # Run Engine running status notify with color
    def _notifyColor(self):
        if self.settings['blink'] is True:
            if self._dummyIndex == 0:
                self.status.engineStatus.setStyleSheet(\
                        "QLabel { background-color: yellow }")
                self._dummyIndex += 1

            else:
                self.status.engineStatus.setStyleSheet(\
                        "QLabel { background-color: orange }")
                self._dummyIndex = 0
        else:
            self.status.engineStatus.setStyleSheet(
                    "QLabel { background-color: 0 }")

    def update_scan_status(self, dataFrame=None, meta_data=None):

        data = dataFrame
        current_points = len(data['I0'])
        scan_mode = meta_data['scan_mode']

        # update scanPoint
        _submit(self.status.scan_point_label.setText, str(current_points))

        if current_points > 2:
            if scan_mode == 'normal':
                # Set loop time in seconds
                loop_time = np.round(float(data['time'][-1]-data['time'][-2]), 2)

                # Label Name to 'LoopTime : '
                if self.status.scanInfoLoopTimeLabel.text() != 'LoopTime : ':
                    _submit(self.status.scanInfoLoopTimeLabel.setText, 'LoopTime : ')

                # Update loop time
                _submit(self.status.loop_time_label.setText, str(loop_time))

            elif scan_mode == 'fly':
                # Set elapsed time
                elapsed_time = ttime.time() - meta_data['time']

                # Label Name to 'ElapsedTime : '
                if self.status.scanInfoLoopTimeLabel.text() != 'ElapsedTime : ':
                    _submit(self.status.scanInfoLoopTimeLabel.setText,
                                                    'ElapsedTime : ')

                # Update Elapsed time
                _submit(self.status.loop_time_label.setText,
                                                str(round(elapsed_time, 1)))

        if self.plot_type != 'align':
            total_points = meta_data['scan_points']
            # total number
            _submit(self.status.num_of_steps_label.setText, str(total_points))

            # current_points+1 is due to first element always excluded from dataFrame
            msg = "ProgressBar:{:d}".format(int((current_points+1)/total_points*100))
            self.zmqSendSock.send(msg.encode())
        else:
            _submit(self.status.num_of_steps_label.setText, "")
            _submit(self.status.progressBar.setValue, 0)

    def clear_extra_graph(self, num_of_history):
        null_data = np.array([])
        for idx in range(10):
            if idx >= num_of_history:
                # clear data on plot
                _submit(self.plot.removeCurve, "Data " + str(idx))

    def closeEvent(self, args):
        manager.stop()

    def tabChanged(self, index):
        if index == 0:
            self.plot_type = 'measure'

            if self._last_tab_index not in [0]:
                idx = self._last_y_axis_type
                _submit(self.status.y_axis_type_combo_box.setCurrentIndex, idx)

            _submit(self.status.derivativeCB.setChecked, False)
            _submit(self.plot.removeCurve, 'derivative')
            _submit(self.plot.setGraphXLabel, "Energy [eV]")

        elif index == 1:
            self.plot_type = 'calibration'

            # Save previous y-axis selection
            if self._last_tab_index in [0]:
                self._last_y_axis_type = self.status.y_axis_type_combo_box.currentIndex()

            # default as Transmission for calibration
            _submit(self.status.y_axis_type_combo_box.setCurrentIndex, 0)

            _submit(self.status.derivativeCB.setChecked, True)
            _submit(self.plot.setGraphXLabel, "Energy [eV]")

        else:
            self.plot_type = 'align'

            # Save previous y-axis selection
            if self._last_tab_index in [0]:
                self._last_y_axis_type = self.status.y_axis_type_combo_box.currentIndex()

            # Set y-axis type to I0 Only
            _submit(self.status.y_axis_type_combo_box.setCurrentIndex, 4)
            _submit(self.status.derivativeCB.setChecked, False)
            _submit(self.plot.removeCurve, 'derivative')
            _submit(self.plot.setGraphXLabel, "index")

        # Last tab index
        self._last_tab_index = index

    def clearZoomHistory(self, **kwargs):
        """Clear the zoom history of the plot"""
        self.plot._limitsHistory.clear()

    def clear_graph(self):
        for idx in range(10):
            _submit(self.plot.removeCurve, "Data " + str(idx))

if __name__ == '__main__':
    warnings.filterwarnings("ignore", message="invalid value encountered in log")
    warnings.filterwarnings("ignore", message="divide by zero encountered in log")
    warnings.filterwarnings("ignore", message="divide by zero encountered in double_scalars")

    font=qt.QFont()
    font.setFamily('DejaVu Sans')
    font.setPointSize(10)

    app = qt.QApplication([])
    app.setFont(font)
    viewer = DataViewer()
    viewer.setWindowIcon(qt.QIcon('icon/viewer.png'))

    mon = qt.QDesktopWidget().screenGeometry(0)
    viewer.move(mon.left(), mon.top())
    viewer.resize(2400, 1300)
    viewer.show()
    sys.exit(app.exec_())

