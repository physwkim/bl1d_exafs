__author__ = "Sang-Woo Kim, Pohang Accelerator Laboratory"
__contact__ = "physwkim@postech.ac.kr"
__license__ = "MIT"
__copyright__ = "Pohang Accelerator Laboratory, Pohang, South Korea"
__doc__ = """

    EXAFS DAQ Software on BL1D, Pohang Accelerator Laboratory

    # Revision history
    2018-09-13 v0.9.0 Rewritten from the EXAFS DAQ Software(Labview) written by Woul-Woo Lee(PAL)
    2018-10-15 v0.9.1
    2018-12-07 v0.9.2
    2019-09-03 v0.9.3 1. Changed from mongodb to sqlite,
                      2. Plotting library from chaco to silx,
                      3. Remove ui widgets
                      4. Added fly-scan mode
    2019-09-23 v0.9.4 1. Changed from sqlite to monodb due to performance issue during fly-scan
                      2. Changed k428 IOC
    2020-12-05 v0.9.5 1. Increase fly scan data points
    2021-03-05 v1.0.0 Separate controller and viewer

"""


import sys
import re
import os
import math
import time as ttime
import datetime
from timeit import default_timer as timer
import logging
import zmq
import subprocess

import numpy as np
import pandas as pd
from epics import caget, caput

from silx.gui import qt
from silx.gui.utils.concurrent import submitToQtMainThread as _submit

import bluesky.plans as bp
import bluesky.plan_stubs as bps

# from ControlWidget import ControlWidget
from scanControlWidget import ScanControlWidget
from Widgets import MainToolBar
from TableWindow import TableWindow
from SampleTable import SampleTable

from utils import path, derivative, loadPV
from utils import addLabelWidgetVert
from utils import nearest

from scan_utils import EnergyScanList
from scan_utils import Tweak
from scan_utils import AfterScanCallback

from thread import QThreadFuture, manager

logger = logging.getLogger('__name__')
logger.debug("main initialized")

_hc = 12398.5
_si_111 = 5.4309/np.sqrt(3)

DEBUG_MODE = False

#ZeroMQ Context
CONTEXT = zmq.Context()

# Set correctionTime to 4 Seconds
correctionTime = 4

class UserException(Exception):
    pass

class Main(qt.QMainWindow):
    """Main Window"""
    hided = qt.Signal(object)
    closed = qt.Signal(object)
    def __init__(self, RE=None, plan_funcs=None, db=None, dets=None,
                 motors=None, devices=None, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # ZMQ Ports
        self.zmqSendPort = 5201
        self.zmqRecvPort = 5301

        self.zmqSendSock = CONTEXT.socket(zmq.PUB)
        try:
            self.zmqSendSock.bind("tcp://*:" + str(self.zmqSendPort))
        except:
            print("Failed to bind to socket : {}".format(self.zmqSendPort))

        # Initialization
        self.dataViewerProc = None
        self._blinkStatus = False
        self.token = None

        # MainWindow Title
        self.setWindowTitle("BL1D EXAFS")

        # Hide minimize button
        self.setWindowFlag(qt.Qt.WindowMinimizeButtonHint, False)

        self.last_uid = ''
        self._need_meas_darkcurrent = True
        self._last_y_axis_type = 0

        # multi-scan stop flag
        self._flag_stop = False
        self._flag_pause = False

        # Default plot_type
        self.plot_type = 'measure'

        # 'normal' : Step-Scan, 'fly' : Fly-Scan
        self.scan_mode = 'normal'

        # load Parameters
        self.pv_names = loadPV()

        self.scan_total_count = 1

        self.dets    = dets
        self.motors  = motors
        self.devices = devices

        self.ophydDict = {}
        self.planDict = {}

        # Append ophyd devices to an dictionary
        if dets:
            for item in dets:
                self.ophydDict[item.name] = item

        if motors:
            for item in motors:
                self.ophydDict[item.name] = item

        if devices:
            for item in devices:
                self.ophydDict[item.name] = item

        # Plan dictionary
        if plan_funcs:
            for plan in plan_funcs:
                self.planDict[plan.__name__] = plan

        # Direction between mono_theta and encoder(HC10E)
        #  1 : same direction
        # -1 : reverse direction
        self.enc_sign = float(self.pv_names['Scaler']['HC10E_ENC_Direction'])

        try:
            # Check default motor speed and set to default if different
            default_speed = float(self.pv_names['DCM']['mono_theta_speed_default'])
            self._orig_mono_speed = self.ophydDict['energyFlyer'].fly_motor_speed.get()

            if not np.isclose(self._orig_mono_speed, default_speed):
                self._orig_mono_speed = default_speed
                self.ophydDict['energyFlyer'].fly_motor_speed.put(self._orig_mono_speed, wait=True)

        except Exception as e:
            print("Error during checking default speed : {}".format(e))

        self.xdata = []
        self.ydata_I0 = []
        self.ydata_It = []
        self.ydata_Inormal = []

        # Main QWidget
        main_panel = qt.QWidget(self)
        main_panel.setLayout(qt.QVBoxLayout())
        self.setCentralWidget(main_panel)

        # Control Widget
        self.control = ScanControlWidget(self, parent=self)
        self.control.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)

        # ToolBar
        self.toolbar = MainToolBar(self)
        # self.toolbar.sigSetStage.connect(self.setStage)
        self.addToolBar(self.toolbar)

        # DockWidget
        margin = 15
        self.rightWidget = qt.QDockWidget(parent=self)
        self.rightWidget.setContentsMargins(margin, margin, margin, margin)
        self.rightWidget.setFeatures(qt.QDockWidget.NoDockWidgetFeatures)
        self.rightWidget.hide()
        self.addDockWidget(qt.Qt.RightDockWidgetArea, self.rightWidget)

        self.rightBottomWidget = qt.QDockWidget(parent=self)
        self.rightBottomWidget.setContentsMargins(margin, margin, margin, margin)
        self.rightBottomWidget.setFeatures(qt.QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(qt.Qt.RightDockWidgetArea, self.rightBottomWidget)

        self.bottomWidget = qt.QDockWidget(parent=self)
        self.bottomWidget.setContentsMargins(margin, margin, margin, margin)
        self.bottomWidget.setFeatures(qt.QDockWidget.NoDockWidgetFeatures),
        self.addDockWidget(qt.Qt.BottomDockWidgetArea, self.bottomWidget)

        self.setCorner(qt.Qt.TopRightCorner, qt.Qt.RightDockWidgetArea)
        self.setCorner(qt.Qt.BottomRightCorner, qt.Qt.RightDockWidgetArea)

        self.sampleTable = SampleTable(self)
        self.sampleTable.setMinimumWidth(500)
        self.sampleTable.setMinimumHeight(800)
        self.sampleTable.load('sample.xlsx')

        # Infomation TabWidget
        self.stackedWidget = qt.QStackedWidget(main_panel)
        self.stackedWidget.insertWidget(0, self.sampleTable)
        self.stackedWidget.setCurrentIndex(0)
        self.rightWidget.setWidget(self.stackedWidget)

        # Log Widget
        self.logWidget = qt.QTextEdit()
        self.logWidget.setReadOnly(True)
        self.logWidget.setMinimumWidth(400)
        self.logWidget.setMinimumHeight(150)
        self.rightBottomWidget.setWidget(addLabelWidgetVert('Log', self.logWidget, align='left'))

        # ProgressBar
        self.progressBar = qt.QProgressBar(self)
        self.progressBar.setMaximumWidth(20)
        self.progressBar.setProperty("value", 0)
        self.progressBar.setOrientation(qt.Qt.Vertical)

        controlWithBar = qt.QWidget(self)
        controlWithBar.setLayout(qt.QHBoxLayout())
        controlWithBar.layout().addWidget(self.control)
        controlWithBar.layout().addWidget(self.progressBar)

        main_panel.layout().addWidget(controlWithBar)

        # Initialize path
        timenow = datetime.datetime.now()

        is_window = sys.platform.startswith('win')
        if is_window:
            self.base_path = os.path.abspath(self.pv_names['BasePath']%(str(timenow.year),
                                                                        str(timenow.month)))
        else:
            if DEBUG_MODE:
                home = os.path.expanduser('~')
                self.base_path = os.path.join(home, 'test_data')
            else:
                self.base_path = os.path.abspath(self.pv_names['BasePath']%(str(timenow.year),
                                                                            str(timenow.month)))

        # Make directory
        if not os.path.isdir(self.base_path):
            os.makedirs(self.base_path)

        _submit(self.control.data_save_path.setText, self.base_path)

        # multi-scan stop flag
        self._flag_stop = False

        # RunEngine
        self.RE=RE

        # DataBroker
        self.db = db

        if self.db is None:
            self.control.run_start.setEnabled(False)

        self.tweak = Tweak()

        # Initialize K428 Amplifiers
        for name in ['I0_amp', 'It_amp', 'If_amp', 'Ir_amp']:

            if not name in self.ophydDict.keys():
                continue

            device = self.ophydDict[name]

            # Skip disconnected devices
            if not device.connected:
                continue

            # Auto Filter Off
            device.autoFilter.put(0, wait=False)

            # Turn on filter
            device.filter.put(1, wait=False)

            # Default RiseTime to 300 msec
            device.riseTime.put(9, wait=False)

            # Set ZeroCheck False
            device.zeroCheck.put(0, wait=False)

            # Set x10 gain False
            device.x10.put(0, wait=False)

            # Turn Off auto suppression
            device.autoSupEnable.put(1, wait=False)

            # Turn On Suppression
            device.suppression.put(1, wait=False)

            # Set current control index
            if device.name == 'I0_amp':
                index = int(device.gain.value[2:-3]) - 3
                device.set_suppress(index)
                self.control.gain_I0.setCurrentIndex(index)

                index = device.riseTime.value
                self.control.riseTime.setCurrentIndex(index)

            elif device.name == 'It_amp':
                index = int(device.gain.value[2:-3]) - 3
                device.set_suppress(index)
                self.control.gain_It.setCurrentIndex(index)

            elif device.name == 'If_amp':
                index = int(device.gain.value[2:-3]) - 3
                device.set_suppress(index)
                self.control.gain_If.setCurrentIndex(index)

            elif device.name == 'Ir_amp':
                index = int(device.gain.value[2:-3]) - 3
                device.set_suppress(index)
                self.control.gain_Ir.setCurrentIndex(index)


        # RunEngine controllers in Energy scan tab
        self.control.run_start.clicked.connect(self.run_scan_energy)
        # self.control.pauseButton.clicked.connect(self._pause)
        # self.control.resumeButton.clicked.connect(self._resume)
        self.control.abortButton.clicked.connect(self._abort)

        # RunEngine controllers in Energy Calibration tab
        self.control.run_calibrate_button.clicked.connect(self.run_calibrate_energy)
        self.control.ecal_abortButton.clicked.connect(self._abort)

        self.control.edit_E0.valueChanged.connect(self.update_E0_Angle)
        self.control.ecal_edit_E0.valueChanged.connect(self.update_E0_Angle2)

        # Select path
        self.control.push_select_path.clicked.connect(self.select_path)
        self.control.data_save_path.textChanged.connect(self.checkDir)

        # Energy Calibration set offset
        self.control.ecal_set_offset_button.clicked.connect(self.set_energy_offset)

        # Scan Type Selection, default is single scan
        self.control.number_of_scan_edit.setEnabled(False)
        self.control.number_of_scan_edit.valueChanged.connect(self.activate_scan_number)
        self.control.run_type.currentIndexChanged.connect(self.activate_scan_number)

        # E0 pseudo-motor related
        self.control.move_to_E0.clicked.connect(self.moveEnergy)
        self.control.stop_E0_button.clicked.connect(self.stop_E0)

        self.control.ecal_move_to_E0.clicked.connect(self.moveEnergy)
        self.control.ecal_stop_E0_button.clicked.connect(self.stop_E0)

        # DCM Tweak
        self.control.DCM_axis_tweak_start_button.clicked.connect(self.run_DCM_tweak)
        self.control.DCM_axis_tweak_stop_button.clicked.connect(self._abort)
        self.control.DCM_tweak_reverse_button.clicked.connect(self.tweak_DCM_reverse)
        self.control.DCM_tweak_forward_button.clicked.connect(self.tweak_DCM_forward)
        self.control.DCM_axis_move_button.clicked.connect(self.tweak_DCM_abs)

        # slits Tweak
        self.control.slit_tweak_start_button.clicked.connect(self.run_slit_tweak)
        self.control.slit_tweak_stop_button.clicked.connect(self._abort)

        # slit left tweak
        self.control.slit_left_tweak_reverse_button.clicked.connect(
                self.tweak_slit_left_reverse)
        self.control.slit_left_tweak_forward_button.clicked.connect(
                self.tweak_slit_left_forward)

        # slit right tweak
        self.control.slit_right_tweak_reverse_button.clicked.connect(
                self.tweak_slit_right_reverse)
        self.control.slit_right_tweak_forward_button.clicked.connect(
                self.tweak_slit_right_forward)

        # slit up tweak
        self.control.slit_up_tweak_reverse_button.clicked.connect(
                self.tweak_slit_up_reverse)
        self.control.slit_up_tweak_forward_button.clicked.connect(
                self.tweak_slit_up_forward)

        # slit down tweak
        self.control.slit_down_tweak_reverse_button.clicked.connect(
                self.tweak_slit_down_reverse)
        self.control.slit_down_tweak_forward_button.clicked.connect(
                self.tweak_slit_down_forward)

        # Tab Widget
        self.control.tabWidget.currentChanged.connect(self.tabChanged)

        # Finalize callback
        self.after_scan_cb = AfterScanCallback(self)

        # Restrict special characters on filename
        regex = qt.QRegExp("[a-zA-Z0-9_]+")
        validator = qt.QRegExpValidator(regex)
        self.control.filename_edit.setValidator(validator)

        # Orignal width & height
        self.orig_width = self.width()
        self.orig_height = self.height()

        self.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Minimum)

        # Scan Type Selection
        self.control.run_type.currentIndexChanged.connect(self._changeStack)

        # Toggle batch scan
        self.control.use_batch_checkbox.toggled.connect(self._toggleBatch)

        # Update initial theta angle
        self.update_E0_Angle()
        self.update_E0_Angle2()

        # Change energy for overflow test
        self.control.testEnergyLineEdit.return_stroked.connect(self.moveEnergyForTest)

        # Start ZMQ Recv Thread
        self.zmqRecvThread = QThreadFuture(self.receiveZmq)
        self.zmqRecvThread.start()

        # Open DataViewer
        self.openDataViewer()

        # Update RunEngine Status
        self.timer = qt.QTimer()
        self.timer.timeout.connect(self.updateEngineStatus)
        self.timer.start(500)

        # Set gain control event
        self.control.gain_I0.currentIndexChanged.connect(self.setMeasureDarkCurrent)
        self.control.gain_It.currentIndexChanged.connect(self.setMeasureDarkCurrent)
        self.control.gain_If.currentIndexChanged.connect(self.setMeasureDarkCurrent)
        self.control.gain_Ir.currentIndexChanged.connect(self.setMeasureDarkCurrent)

        # Set Rise Time
        self.control.riseTime.currentIndexChanged.connect(self.set_riseTime)

        # Set Zero Check
        self.control.zeroCheckButton.clicked.connect(self.toggle_zeroCheck)


        # Update E0 Angle
        self.update_E0_Angle()
        self.update_E0_Angle2()

        if self.RE:
            # Subscribe updateViewer
            self.updateViewerToken = self.RE.subscribe(self.updateViewer)

        self.toLog("Initialize completed.")

    # ---------  init  -------------------------------------------------------

    def setMeasureDarkCurrent(self):
        """Set darkcurrent flag"""
        self._need_meas_darkcurrent = True

    def sendZmq(self, msg):
        """Send message"""
        self.zmqSendSock.send(msg.encode())

    def receiveZmq(self):
        sock = CONTEXT.socket(zmq.SUB)
        sock.connect("tcp://localhost:" + str(self.zmqRecvPort))
        sock.setsockopt_string(zmq.SUBSCRIBE, '')

        while True:
            msg = sock.recv().decode()
            if len(msg):
                if msg.startswith("EcalPeakEnergyLabel"):
                    value = msg.split(':')[-1]
                    _submit(self.control.ecal_peak_energy_label.setText, value)
                elif msg.startswith("EcalEnergyDifferenceLabel"):
                    value = msg.split(':')[-1]
                    _submit(self.control.ecal_energy_difference_label.setText, value)
                elif msg.startswith("DCM_I0:"):
                    value = msg.split(':')[-1]
                    _submit(self.control.DCM_I0_label.setText, value)
                elif msg.startswith("DCM_I0_2:"):
                    value = msg.split(':')[-1]
                    _submit(self.control.DCM_I0_label_2.setText, value)
                elif msg.startswith("ProgressBar:"):
                    value = int(msg.split(':')[-1])
                    _submit(self.progressBar.setValue, value)
                elif msg.startswith("Abort"):
                    self._abort()
                elif msg.startswith("ViewerInitialized"):
                    # Current tab index
                    currentTabIndex = self.control.tabWidget.currentIndex()
                    self.tabChanged(currentTabIndex)


    def updateEngineStatus(self):
        """Send RunEngine's status"""
        try:
            msg = 'RunEngine:{}'.format(self.RE.state)
            self.sendZmq(msg)

            msg = 'Blink:{}'.format(str(self.blinkStatus))
            self.sendZmq(msg)
        except Exception as e:
            self.toLog("Exception in updateEngineStatus", color='red')
            print("Exception in updateEngineStatus : {}".format(e))

    @property
    def blinkStatus(self):
        """Indicate RunEngine is running"""
        return self._blinkStatus

    @blinkStatus.setter
    def blinkStatus(self, value):
        """blinkStatus setter"""
        self._blinkStatus = value
        msg = 'Blink:{}'.format(str(value))
        self.sendZmq(msg)

    def updateViewer(self, *args, **kwargs):
        """Data update on DataViwer"""
        msg = 'UpdateViewer'
        self.sendZmq(msg)

    def openDataViewer(self):
        """ Open DataViewer in subprocess """

        _path = path('DataViewer.py')
        command = ['python', _path]
        self.dataViewerProc = subprocess.Popen(command)

    def moveEnergyForTest(self):
        """Move energy fot testing"""
        E0 = self.control.edit_E0.value()
        value = E0 + float(self.control.testEnergyLineEdit.value())
        self.moveToEnergy(value)

    def hideEvent(self, args):
        """hideEvent to quit ipython kernel when main window hided"""
        pass
        # manager.stop()
        # self.hided.emit(True)

    def closeEvent(self, args):
        manager.stop()
        self.closed.emit(True)

    def toLog(self, text, color='black'):
        """Append to log widget"""
        timenow = datetime.datetime.now()
        timeString = timenow.strftime("%Y-%m-%d %H:%M:%S")
        text = '[ ' + timeString + ' ]  ' + text

        self.logWidget.setTextColor(qt.QColor(color))
        _submit(self.logWidget.append, text)

    def delay(self, time):
        """Apply delay without gui freeze"""
        try:
            self.RE(bps.sleep(time))
        except:
            pass

    def _changeStack(self):
        index = self.control.run_type.currentIndex()
        if index == 2:
            self.control.stackedWidget.setCurrentIndex(1)
        else:
            self.control.stackedWidget.setCurrentIndex(0)

    def _toggleBatch(self, batch):
        if batch:
            _submit(self.rightWidget.show)
        else:
            _submit(self.rightWidget.hide)
            qt.QTimer.singleShot(100, self.resize_windows)

    def resize_windows(self):
        """Minimize window's width & height"""
        _submit(self.resize, 0, 0)

    def tabChanged(self, index):
        if index == 0:
            self.plot_type = 'measure'
        elif index == 1:
            self.plot_type = 'calibration'
        else:
            self.plot_type = 'align'

        msg = 'tabChanged:{:d}'.format(index)
        self.sendZmq(msg)

    def select_path(self):
        """ Select data save path """
        self.selected_path = qt.QFileDialog.getExistingDirectory(
                                        self,
                                        "Select a save path",
                                        self.base_path,
                                        qt.QFileDialog.ShowDirsOnly)

        _submit(self.control.data_save_path.setText, str(self.selected_path))

    def today(self):
        """ Set path to today """
        timenow = datetime.datetime.now()
        path = self.base_path + "\\" + str(timenow.day)
        _submit(self.control.data_save_path.setText, path)

    def control_enable(self, _set):
        """ Set path to today """
        if _set:
            _submit(self.control.comboBox_element.setEnabled, True)
            _submit(self.control.comboBox_edge.setEnabled, True)

            _submit(self.control.ecal_comboBox_element.setEnabled, True)
            _submit(self.control.ecal_comboBox_edge.setEnabled, True)

            _submit(self.control.comboBox_Si_mode.setEnabled, True)

            _submit(self.control.edit_E0.setEnabled, True)
            _submit(self.control.ecal_edit_E0.setEnabled, True)

            _submit(self.control.edit_delay_time.setEnabled, True)
            _submit(self.control.run_type.setEnabled, True)
            _submit(self.control.number_of_scan_edit.setEnabled, True)
            _submit(self.control.move_to_E0.setEnabled, True)
            _submit(self.control.stop_E0_button.setEnabled, True)

            _submit(self.control.SRB_1.setEnabled, True)
            _submit(self.control.SRB_2.setEnabled, True)
            _submit(self.control.SRB_3.setEnabled, True)
            _submit(self.control.SRB_4.setEnabled, True)
            _submit(self.control.SRB_5.setEnabled, True)
            _submit(self.control.SRB_6.setEnabled, True)

            _submit(self.control.eMode_bar_1.setEnabled, True)
            _submit(self.control.eMode_bar_2.setEnabled, True)
            _submit(self.control.eMode_bar_3.setEnabled, True)
            _submit(self.control.eMode_bar_4.setEnabled, True)
            _submit(self.control.eMode_bar_5.setEnabled, True)
            _submit(self.control.eMode_bar_6.setEnabled, True)

            _submit(self.control.stepSize_1.setEnabled, True)
            _submit(self.control.stepSize_2.setEnabled, True)
            _submit(self.control.stepSize_3.setEnabled, True)
            _submit(self.control.stepSize_4.setEnabled, True)
            _submit(self.control.stepSize_5.setEnabled, True)

            _submit(self.control.SRBOnOff_1.setEnabled, True)
            _submit(self.control.SRBOnOff_2.setEnabled, True)
            _submit(self.control.SRBOnOff_3.setEnabled, True)
            _submit(self.control.SRBOnOff_4.setEnabled, True)
            _submit(self.control.SRBOnOff_5.setEnabled, True)

            _submit(self.control.SRB_time_1.setEnabled, True)
            _submit(self.control.SRB_time_2.setEnabled, True)
            _submit(self.control.SRB_time_3.setEnabled, True)
            _submit(self.control.SRB_time_4.setEnabled, True)
            _submit(self.control.SRB_time_5.setEnabled, True)

            _submit(self.control.gain_I0.setEnabled, True)
            _submit(self.control.gain_It.setEnabled, True)
            _submit(self.control.gain_If.setEnabled, True)
            _submit(self.control.gain_Ir.setEnabled, True)

            _submit(self.control.riseTime.setEnabled, True)
            _submit(self.control.zeroCheckButton.setEnabled, True)

            _submit(self.control.ecal_gain_I0.setEnabled, True)
            _submit(self.control.ecal_gain_It.setEnabled, True)
            _submit(self.control.ecal_gain_If.setEnabled, True)
            _submit(self.control.ecal_gain_Ir.setEnabled, True)

            _submit(self.control.data_save_path.setEnabled, True)
            _submit(self.control.push_select_path.setEnabled, True)
            _submit(self.control.description_edit.setEnabled, True)
            _submit(self.control.filename_edit.setEnabled, True)

            _submit(self.control.run_start.setEnabled, True)
            _submit(self.control.ecal_start_edit.setEnabled, True)
            _submit(self.control.ecal_stop_edit.setEnabled, True)
            _submit(self.control.ecal_step_size_edit.setEnabled, True)
            _submit(self.control.ecal_time_edit.setEnabled, True)
            _submit(self.control.ecal_filename_edit.setEnabled, True)
            _submit(self.control.run_calibrate_button.setEnabled, True)

            _submit(self.control.slit_tweak_start_button.setEnabled, True)

            _submit(self.control.DCM_axis_tweak_start_button.setEnabled, True)
            _submit(self.control.DCM_axis_set_edit.setEnabled, True)
            _submit(self.control.DCM_axis_move_button.setEnabled, True)

            # _submit(self.control.use_batch_checkbox.setEnabled, True)
            _submit(self.control.testEnergyLineEdit.setEnabled, True)

            _submit(self.control.abortButton.setEnabled, True)
            _submit(self.control.ecal_abortButton.setEnabled, True)
            # _submit(self.control.pauseButton.setEnabled, True)
            # _submit(self.control.resumeButton.setEnabled, True)

            # Enable abortButton in DataViewer
            msg = 'DisableAbortButton:False'
            self.sendZmq(msg)

        else:
            _submit(self.control.comboBox_element.setEnabled, False)
            _submit(self.control.comboBox_edge.setEnabled, False)

            _submit(self.control.ecal_comboBox_element.setEnabled, False)
            _submit(self.control.ecal_comboBox_edge.setEnabled, False)

            _submit(self.control.comboBox_Si_mode.setEnabled, False)

            _submit(self.control.edit_E0.setEnabled, False)
            _submit(self.control.ecal_edit_E0.setEnabled, False)

            _submit(self.control.edit_delay_time.setEnabled, False)
            _submit(self.control.run_type.setEnabled, False)
            _submit(self.control.number_of_scan_edit.setEnabled, False)
            _submit(self.control.move_to_E0.setEnabled, False)
            _submit(self.control.stop_E0_button.setEnabled, False)

            _submit(self.control.SRB_1.setEnabled, False)
            _submit(self.control.SRB_2.setEnabled, False)
            _submit(self.control.SRB_3.setEnabled, False)
            _submit(self.control.SRB_4.setEnabled, False)
            _submit(self.control.SRB_5.setEnabled, False)
            _submit(self.control.SRB_6.setEnabled, False)

            _submit(self.control.eMode_bar_1.setEnabled, False)
            _submit(self.control.eMode_bar_2.setEnabled, False)
            _submit(self.control.eMode_bar_3.setEnabled, False)
            _submit(self.control.eMode_bar_4.setEnabled, False)
            _submit(self.control.eMode_bar_5.setEnabled, False)
            _submit(self.control.eMode_bar_6.setEnabled, False)

            _submit(self.control.stepSize_1.setEnabled, False)
            _submit(self.control.stepSize_2.setEnabled, False)
            _submit(self.control.stepSize_3.setEnabled, False)
            _submit(self.control.stepSize_4.setEnabled, False)
            _submit(self.control.stepSize_5.setEnabled, False)

            _submit(self.control.SRBOnOff_1.setEnabled, False)
            _submit(self.control.SRBOnOff_2.setEnabled, False)
            _submit(self.control.SRBOnOff_3.setEnabled, False)
            _submit(self.control.SRBOnOff_4.setEnabled, False)
            _submit(self.control.SRBOnOff_5.setEnabled, False)

            _submit(self.control.SRB_time_1.setEnabled, False)
            _submit(self.control.SRB_time_2.setEnabled, False)
            _submit(self.control.SRB_time_3.setEnabled, False)
            _submit(self.control.SRB_time_4.setEnabled, False)
            _submit(self.control.SRB_time_5.setEnabled, False)

            _submit(self.control.gain_I0.setEnabled, False)
            _submit(self.control.gain_It.setEnabled, False)
            _submit(self.control.gain_If.setEnabled, False)
            _submit(self.control.gain_Ir.setEnabled, False)

            _submit(self.control.riseTime.setEnabled, False)
            _submit(self.control.zeroCheckButton.setEnabled, False)

            _submit(self.control.ecal_gain_I0.setEnabled, False)
            _submit(self.control.ecal_gain_It.setEnabled, False)
            _submit(self.control.ecal_gain_If.setEnabled, False)
            _submit(self.control.ecal_gain_Ir.setEnabled, False)

            _submit(self.control.data_save_path.setEnabled, False)
            _submit(self.control.push_select_path.setEnabled, False)
            _submit(self.control.description_edit.setEnabled, False)
            _submit(self.control.filename_edit.setEnabled, False)

            _submit(self.control.run_start.setEnabled, False)

            _submit(self.control.ecal_start_edit.setEnabled, False)
            _submit(self.control.ecal_stop_edit.setEnabled, False)
            _submit(self.control.ecal_step_size_edit.setEnabled, False)
            _submit(self.control.ecal_time_edit.setEnabled, False)
            _submit(self.control.ecal_filename_edit.setEnabled, False)
            _submit(self.control.run_calibrate_button.setEnabled, False)

            _submit(self.control.slit_tweak_start_button.setEnabled, False)

            _submit(self.control.DCM_axis_tweak_start_button.setEnabled, False)
            _submit(self.control.DCM_axis_set_edit.setEnabled, False)

            # _submit(self.control.use_batch_checkbox.setEnabled, False)
            _submit(self.control.testEnergyLineEdit.setEnabled, False)

    def _pause(self):
        self._flag_pause = True
        self.toLog("RunEngine is paused!", color='red')
        self.RE.request_pause()

    def _abort(self):
        self._flag_stop = True

        # disable data saving
        try:
            self.unsubscribe_callback()
        except:
            ...

        self.toLog("RunEngine is aborted!", color='red')
        if self.RE.state != 'idle':
            self.RE.abort()

        # Disable buttons in control panel
        self.control.abortButton.setDisabled(True)
        self.control.ecal_abortButton.setDisabled(True)
        # self.control.pauseButton.setDisabled(True)
        # self.control.resumeButton.setDisabled(True)

        # Disable abortButton in DataViewer
        msg = 'DisableAbortButton:True'
        self.sendZmq(msg)

    def _resume(self):
        self.toLog("RunEngine is resumed!", color='red')
        self.RE.resume()

    def checkDir(self):
        # no special characters on path string
        _path_string = self.control.data_save_path.toPlainText()
        _match = re.match('^[a-zA-Z0-9_/]*$', _path_string)

        try:
            _path_string = _match[0]
        except:
            return

        if not _path_string.startswith(self.base_path):
            _submit(self.control.data_save_path.setText, self.base_path)

    # Tweak related ----------------------------------------------------------
    def run_DCM_tweak(self):
        try:
            self.toLog("Started DCM Tweak", color='blue')
            self.plot_type = 'align'

            # Disable start buttons
            _submit(self.control.DCM_axis_tweak_start_button.setEnabled, False)
            _submit(self.control.slit_tweak_start_button.setEnabled, False)
            _submit(self.control.run_calibrate_button.setEnabled, False)
            _submit(self.control.run_start.setEnabled, False)

            # set axis labels
            msg = 'XLabel:{}'.format('index')
            self.sendZmq(msg)

            # Check K428 Amplifier Settings
            for name in ['I0_amp', 'It_amp', 'If_amp', 'Ir_amp']:
                device = self.ophydDict[name]
                # Default RiseTime to 300 msec
                device.riseTime.put(9, wait=False)
                # Set ZeroCheck False
                device.zeroCheck.put(0, wait=False)
                # Set x10 gain False
                device.x10.put(0, wait=False)
                # Turn Off auto suppression
                # device.autoSupEnable.put(1, wait=False)
                # Turn On Suppression
                device.suppression.put(1, wait=False)

            # enable buttons
            _submit(self.control.DCM_tweak_reverse_button.setEnabled, True)
            _submit(self.control.DCM_tweak_forward_button.setEnabled, True)
            _submit(self.control.DCM_axis_move_button.setEnabled, True)

            # Set color notifiy on
            self.blinkStatus = True

            self.RE(self.planDict['tweak_custom'](self.ophydDict['scaler'],
                                                  'I0',
                                                  self.ophydDict['dcm_etc_theta2'],
                                                  self.control.DCM_axis_tweak_edit.value(),
                                                  time=1,
                                                  obj=self.tweak),
                    scan_type='tweak',
                    sdd=False)

        except Exception as e:
            print("Error occured during DCM tweak : {}".format(e))

        finally:
            # DEBUG tweak.wait should be 'True' whether tweak scan has been
            # terminated properly or not
            self.tweak.wait = True

            # Set color notifiy off
            self.blinkStatus = False

            # Enable controls
            _submit(self.control_enable, True)

            # Disable buttons
            _submit(self.control.DCM_tweak_reverse_button.setEnabled, False)
            _submit(self.control.DCM_tweak_forward_button.setEnabled, False)
            _submit(self.control.DCM_axis_move_button.setEnabled, False)

            # self.updatePlotThread.update_plot = False
            _submit(self.control.DCM_axis_tweak_start_button.setEnabled, True)

            self.toLog("DCM Tweak finished", color='blue')

    def tweak_DCM_abs(self):
        diff = float(self.control.DCM_axis_set_edit.value())-self.ophydDict['dcm_etc_theta2'].position
        self.tweak.step = diff
        ttime.sleep(0.2)
        self.tweak.wait = False

    def tweak_DCM_forward(self):
        self.tweak.step = float(self.control.DCM_axis_tweak_edit.value())
        ttime.sleep(0.2)
        self.tweak.wait = False

    def tweak_DCM_reverse(self):
        self.tweak.step = -1 * self.control.DCM_axis_tweak_edit.value()
        ttime.sleep(0.2)
        self.tweak.wait = False


    def run_slit_tweak(self):
        try:
            self.toLog("Slit Tweak Started", color='blue')
            self.plot_type = 'align'
            _submit(self.control.slit_tweak_start_button.setEnabled, False)

            # Check K428 Amplifier Settings
            for name in ['I0_amp', 'It_amp', 'If_amp', 'Ir_amp']:
                device = self.ophydDict[name]
                # Default RiseTime to 300 msec
                device.riseTime.put(9, wait=False)
                # Set ZeroCheck False
                device.zeroCheck.put(0, wait=False)
                # Set x10 gain False
                device.x10.put(0, wait=False)
                # Turn Off auto suppression
                # device.autoSupEnable.put(1, wait=False)
                # Turn On Suppression
                device.suppression.put(1, wait=False)

            # disables other RunEngine related buttons
            _submit(self.control.DCM_axis_tweak_start_button.setEnabled, False)
            _submit(self.control.run_calibrate_button.setEnabled, False)
            _submit(self.control.run_start.setEnabled, False)

            # set axis labels
            msg = 'XLabel:{}'.format('index')
            self.sendZmq(msg)

            if self.control.slit_select_motor_comboBox.currentIndex() == 0:
                motor = self.ophydDict['slit'].left
                step  = self.control.slit_left_tweak_edit.value()

                # Enable controls
                _submit(self.control.slit_left_tweak_reverse_button.setEnabled, True)
                _submit(self.control.slit_left_tweak_forward_button.setEnabled, True)

            elif self.control.slit_select_motor_comboBox.currentIndex() == 1:
                motor = self.ophydDict['slit'].right
                step  = self.control.slit_right_tweak_edit.value()

                # Enable controls
                _submit(self.control.slit_right_tweak_reverse_button.setEnabled, True)
                _submit(self.control.slit_right_tweak_forward_button.setEnabled, True)

            elif self.control.slit_select_motor_comboBox.currentIndex() == 2:
                motor = self.ophydDict['slit'].up
                step  = self.control.slit_up_tweak_edit.value()

                # Enable controls
                _submit(self.control.slit_up_tweak_reverse_button.setEnabled, True)
                _submit(self.control.slit_up_tweak_forward_button.setEnabled, True)

            else:
                motor = self.ophydDict['slit'].down
                step  = self.control.slit_down_tweak_edit.value()

                # Enable controls
                _submit(self.control.slit_down_tweak_reverse_button.setEnabled, True)
                _submit(self.control.slit_down_tweak_forward_button.setEnabled, True)

            # Set color notifiy on
            self._blinkStatus = True

            # Start RunEngine
            self.RE(self.planDict['tweak_custom'](self.ophydDict['scaler'],
                                                  'I0',
                                                  motor,
                                                  step,
                                                  time=1,
                                                  obj=self.tweak),
                    scan_type='tweak',
                    sdd=False)

        except Exception as e:
            print("Error occured during Slit Tweak : {}".format(e))

        finally:
            # DEBUG tweak.wait should be 'True' whether tweak scan has been
            # terminated properly or not
            self.tweak.wait = True

            # Set color notifiy off
            self.blinkStatus = False

            # Enable controls
            _submit(self.control_enable, True)

            # Disable controls
            _submit(self.control.slit_left_tweak_reverse_button.setEnabled, False)
            _submit(self.control.slit_left_tweak_forward_button.setEnabled, False)
            _submit(self.control.slit_right_tweak_reverse_button.setEnabled, False)
            _submit(self.control.slit_right_tweak_forward_button.setEnabled, False)
            _submit(self.control.slit_up_tweak_reverse_button.setEnabled, False)
            _submit(self.control.slit_up_tweak_forward_button.setEnabled, False)
            _submit(self.control.slit_down_tweak_reverse_button.setEnabled, False)
            _submit(self.control.slit_down_tweak_forward_button.setEnabled, False)

            self.toLog("Slit Tweak finished!", color='blue')


    def tweak_slit_left_forward(self):
        self.tweak.step = float(self.control.slit_left_tweak_edit.value())
        ttime.sleep(0.2)
        self.tweak.wait = False

    def tweak_slit_left_reverse(self):
        self.tweak.step = -1 * self.control.slit_left_tweak_edit.value()
        ttime.sleep(0.2)
        self.tweak.wait = False

    def tweak_slit_right_forward(self):
        self.tweak.step = float(self.control.slit_right_tweak_edit.value())
        ttime.sleep(0.2)
        self.tweak.wait = False

    def tweak_slit_right_reverse(self):
        self.tweak.step = -1 * self.control.slit_right_tweak_edit.value()
        ttime.sleep(0.2)
        self.tweak.wait = False

    def tweak_slit_up_forward(self):
        self.tweak.step = float(self.control.slit_up_tweak_edit.value())
        ttime.sleep(0.2)
        self.tweak.wait = False

    def tweak_slit_up_reverse(self):
        self.tweak.step = -1 * self.control.slit_up_tweak_edit.value()
        ttime.sleep(0.2)
        self.tweak.wait = False

    def tweak_slit_down_forward(self):
        self.tweak.step = float(self.control.slit_down_tweak_edit.value())
        ttime.sleep(0.2)
        self.tweak.wait = False

    def tweak_slit_down_reverse(self):
        self.tweak.step = -1 * self.control.slit_down_tweak_edit.value()
        ttime.sleep(0.2)
        self.tweak.wait = False

    #--------------------------------------------------------------------------


    def activate_scan_number(self):
        idx = int(self.control.run_type.currentIndex())
        if idx == 1 or idx == 2 :
            _submit(self.control.number_of_scan_edit.setEnabled, True)
        else:
            _submit(self.control.number_of_scan_edit.setValue, 1)
            _submit(self.control.number_of_scan_edit.setEnabled, False)

    def moveToEnergy(self, energy):
        """ energy in eV """
        dcm = self.ophydDict['dcm']
        stop_and_mv = self.planDict['stop_and_mv']

        try:
            self.control.abortButton.setDisabled(True)
            self.control.ecal_abortButton.setDisabled(True)
            self.control.run_start.setDisabled(True)

            # Disable abortButton
            msg = 'DisableAbortButton:True'
            self.sendZmq(msg)

            self.RE(stop_and_mv(dcm, energy))

        except Exception as e:
            print("Exception in moveToEnergy : {}".format(e))

        finally:
            self.control.abortButton.setDisabled(False)
            self.control.ecal_abortButton.setDisabled(False)
            self.control.run_start.setDisabled(False)

            # Enable abortButton
            msg = 'DisableAbortButton:False'
            self.sendZmq(msg)

    def moveEnergy(self):
        reply = qt.QMessageBox.question(self,
                        "Info", # title
                        "==============  warning  ================\n" \
                        "If you perform Move E0, the energy correction value" \
                        " will be lost. " \
                        "You can proceed the calibration again.\n\n" \
                        "Do you want to continue?\n" \
                        "=====================================", # text
                        qt.QMessageBox.Yes| qt.QMessageBox.No)

        if reply == qt.QMessageBox.Yes:
            self.move_E0()

    def move_E0(self):
        setValue = self.control.edit_E0.value()
        self._need_meas_darkcurrent = True

        # remove offset
        dcm = self.ophydDict['dcm']
        dcm.offset.put(0)

        try:
            self.control.abortButton.setDisabled(True)
            self.moveToEnergy(setValue)
        except:
            ...
        finally:
            self.control.abortButton.setDisabled(False)


    def stop_E0(self):
        self._flag_stop = True

        if self.RE.state != 'idle':
            self.RE.abort()

        item = self.ophydDict['dcm']
        item.spmg.set(0)
        ttime.sleep(0.5)
        item.spmg.put(3)

    # ----- zero-check --------------------------------------------------------
    def set_zcheck(self):
        zcheck_state = self.zcheck_set.isChecked()
        item = self.ophydDict['I0_amp']
        item.set_zcheck(zcheck_state)

        item = self.ophydDict['It_amp']
        item.set_zcheck(zcheck_state)

        item = self.ophydDict['If_amp']
        item.set_zcheck(zcheck_state)

        item = self.ophydDict['Ir_amp']
        item.set_zcheck(zcheck_state)

    def set_zcheck2(self):
        zcheck_state = self.zcheck_set_2.isChecked()

        item = self.ophydDict['I0_amp']
        item.set_zcheck(zcheck_state)

        item = self.ophydDict['It_amp']
        item.set_zcheck(zcheck_state)

        item = self.ophydDict['If_amp']
        item.set_zcheck(zcheck_state)

        item = self.ophydDict['Ir_amp']
        item.set_zcheck(zcheck_state)

    # ----- End zero-check ----------------------------------------------------

    def set_riseTime(self):
        index = self.control.riseTime.currentIndex()

        for name in ['I0_amp', 'It_amp', 'If_amp', 'Ir_amp']:
            device = self.ophydDict[name]
            device.riseTime.put(index, wait=False)

    def toggle_zeroCheck(self):
        for name in ['I0_amp', 'It_amp', 'If_amp', 'Ir_amp']:
            device = self.ophydDict[name]
            if name == 'I0_amp':
                zcheck = device.zeroCheck.value

            if zcheck == 0:
                device.zeroCheck.put(1, wait=False)
            else:
                device.zeroCheck.put(0, wait=False)

    def update_E0_Angle(self):
        _th = np.rad2deg(np.arcsin(_hc/(2.*_si_111*float(self.control.edit_E0.value()))))

        _submit(self.control.E0_Angle_label.setText, str(np.round(_th, 6)))
        self.control.flyControl.updateFlyInfo()

    def update_E0_Angle2(self):
        _th = np.rad2deg( np.arcsin(_hc/(2.*_si_111*float(self.control.ecal_edit_E0.value()))))

        _submit(self.control.ecal_E0_Angle_label.setText, str(np.round(_th, 6)))

    def run_calibrate_energy(self):

        self._flag_stop = False
        self._flag_pause = False

        # Save previous run's uid
        try:
            self._last_uid = self.db[-1].start['uid']
        except:
            self._last_uid = ''

        reply = qt.QMessageBox.question(self,
                        "Info", # title
                        "Ready for Energy Calibration.\n\n" \
                        "Do you Want to start?", # text
                        qt.QMessageBox.Yes| qt.QMessageBox.No)

        if reply == qt.QMessageBox.Yes:
            self.do_calibrate()

    def do_calibrate(self):
        try:
            self.toLog("Starting Energy Calibration", color='blue')

            self.plot_type = 'calibration'

            # Remove previous derivative curve
            msg = 'RemoveCurve:{}'.format('derivative')
            self.sendZmq(msg)

            # Set axis labels
            msg = 'XLabel:{}'.format('Energy [eV]')
            self.sendZmq(msg)

            # Disable control
            self.control_enable(False)

            E0 = self.control.ecal_edit_E0.value()

            # Check K428 Amplifier Settings
            for name in ['I0_amp', 'It_amp', 'If_amp', 'Ir_amp']:
                device = self.ophydDict[name]
                # Default RiseTime to 300 msec
                device.riseTime.put(9, wait=False)
                # Set ZeroCheck False
                device.zeroCheck.put(0, wait=False)
                # Set x10 gain False
                device.x10.put(0, wait=False)
                # Turn Off auto suppression
                # device.autoSupEnable.put(1, wait=False)
                # Turn On Suppression
                device.suppression.put(1, wait=False)

            delay_time = float(self.control.edit_delay_time.value())
            start = self.control.ecal_start_edit.value()
            stop  = self.control.ecal_stop_edit.value()
            step_size = self.control.ecal_step_size_edit.value()

            # Set preset_time to preset value in seconds
            item = self.ophydDict['scaler']
            item.preset_time.put(self.control.ecal_time_edit.value())

            # For information update
            self.scan_total_count = int((stop - start)/step_size) + 1

            # Retrieve meta data
            darkI0 = int(self.control.I0_dark_current.text())
            darkIt = int(self.control.It_dark_current.text())
            darkIf = int(self.control.If_dark_current.text())
            darkIr = int(self.control.Ir_dark_current.text())

            gainI0 = self.control.gain_I0.currentIndex() + 3
            gainIt = self.control.gain_It.currentIndex() + 3
            gainIf = self.control.gain_If.currentIndex() + 3
            gainIr = self.control.gain_Ir.currentIndex() + 3

            monoOffset = self.control.E0_offset.text()

            try:
                beamcurrent = caget(self.pv_names['Beam']['Current'], timeout = 1)
                beamcurrent = np.round(beamcurrent, 3)
            except:
                beamcurrent = 0.0

            sdd = None

            # set notify on
            self.blinkStatus = True

            # set offset to 0.0
            # dcm = self.ophydDict['dcm']
            # dcm.offset.put(0.0)
            # dcm.energy.move(E0)

            # hutch slits
            slits = self.ophydDict['slit']
            top = slits.up.user_readback.get()
            bottom = slits.down.user_readback.get()
            left = slits.left.user_readback.get()
            right = slits.right.user_readback.get()

            # bluesky runtime engine
            self.RE(self.planDict['delay_scan_with_cleanup'](detectors=[self.ophydDict['scaler']],
                                                                motor=self.ophydDict['dcm'],
                                                                E0=E0,
                                                                start=start,
                                                                stop=stop,
                                                                step_size=step_size,
                                                                delay_time=delay_time/1000),
                    scan_type='calibration',
                    scan_mode='normal',
                    E0=E0,
                    scan_points=self.scan_total_count,
                    darkI0=darkI0,
                    darkIt=darkIt,
                    darkIf=darkIf,
                    darkIr=darkIr,
                    gainI0=gainI0,
                    gainIt=gainIt,
                    gainIf=gainIf,
                    gainIr=gainIr,
                    sdd=sdd,
                    monoOffset=monoOffset,
                    slitTop=top,
                    slitBottom=bottom,
                    slitLeft=left,
                    slitRight=right,
                    beamcurrent=beamcurrent)
        except Exception as e:
            print("Error in do_calibrate : {}".format(e))
            ideal_energy = self.control.ecal_edit_E0.value()

            reply = qt.QMessageBox.question(self,
                            "Info", # title
                            "Calibration is aborted.\n\n" \
                            "Do you want to set offset?\n",
                            qt.QMessageBox.Yes| qt.QMessageBox.No,
                            qt.QMessageBox.No) # Default button

            if reply == qt.QMessageBox.Yes:
                self.calib()
                return
            else:
                print("moving to ideal_energy : {}".format(ideal_energy))
                self.moveToEnergy(ideal_energy)
                self.blinkStatus = False
                self.control_enable(True)
                return

    def calib(self):
        try:
            E0 = self.control.ecal_edit_E0.value()

            self.toLog("Scan completed", color='blue')

            # DEBUG tweak.wait should be 'True' whether tweak scan has been
            # terminated properly or not
            self.tweak.wait = True

            offset_energy = float(self.control.ecal_energy_difference_label.text())
            der_max_energy = float(self.control.ecal_peak_energy_label.text())

            reply = qt.QMessageBox.question(self,
                            "Info", # title
                            "The energy offset obtained from the scan"+
                            " is {:.4f} ".format(offset_energy)+
                            " eV.\n\n Do you want to compensate with this"+
                            " value?", # text
                            qt.QMessageBox.Yes| qt.QMessageBox.No)

            if reply == qt.QMessageBox.Yes:

                item = self.ophydDict['dcm']
                # calculate ideal energy & theta value
                ideal_energy = self.control.ecal_edit_E0.value()
                ideal_theta = np.rad2deg(np.arcsin(_hc/(2.*_si_111*ideal_energy)))

                # move to the measured derivative maximum energy
                self.moveToEnergy(ideal_energy + offset_energy)

                # get current theta & theta-offset
                current_theta = item.theta.user_readback.get()
                current_theta_off = item.offset.get()

                new_theta_off = ideal_theta - current_theta + current_theta_off

                # set new theta offset value
                item.offset.put(new_theta_off)
                self.toLog("New offset is " + str(new_theta_off), color='blue')

        except Exception as e:
            print("Error in do_calibrate : {}".format(e))

        finally:
            currentUid = self.db[-1].start['uid']
            if currentUid != self._last_uid:
                if self._flag_stop:
                    reply = qt.QMessageBox.question(self,
                                    "Info", # title
                                    "A scan is aborted.\n\n" \
                                    "Do you want to save data?\n",
                                    qt.QMessageBox.Yes| qt.QMessageBox.No,
                                    qt.QMessageBox.No) # Default button

                    self._flag_stop = False

                    if reply == qt.QMessageBox.Yes:
                        print("before save_data")
                        self.save_data()

            # Move to E0
            self.moveToEnergy(E0)

            # set notify off
            self.blinkStatus = False

            # Enable controls
            self.control_enable(True)


    def set_energy_offset(self):
        """Calculate and set dcm offset"""

        self.control_enable(False)

        ideal_energy = float(self.control.ecal_edit_E0.value())
        ideal_theta = np.rad2deg(np.arcsin(_hc/(2.*_si_111*ideal_energy)))

        offset_energy = float(self.control.ecal_energy_offset_edit.value())


        # set offset to 0.0
        dcm = self.ophydDict['dcm']
        dcm.offset.put(0.0)

        # move to the measured derivative maximum energy
        self.moveToEnergy(ideal_energy + offset_energy)

        # get current theta & theta-offset
        current_theta = dcm.theta.user_readback.get()
        current_theta_off = dcm.offset.get()

        new_theta_off = ideal_theta - current_theta + current_theta_off

        # set new theta offset value
        dcm.offset.put(new_theta_off)
        self.toLog("New offset is " + str(new_theta_off), color='blue')
        self.control_enable(True)

    def measDarkCurrent(self):
        """Start Darkcurrent measurement"""
        try:
            reply = qt.QMessageBox.question(self,
                            "Info", # title
                            "The Photon Shutter must be closed for dark current " \
                            "measurements. \n\nClose the Photon Shutter and" \
                            " press the Yes button.", # text
                            qt.QMessageBox.Yes| qt.QMessageBox.No)


            if reply == qt.QMessageBox.Yes:

                # Disable Pause and resume buttons
                # self.control.pauseButton.setEnabled(False)
                # self.control.resumeButton.setEnabled(False)

                # set notify on
                self.blinkStatus = True

                # Disable controls
                self.control_enable(False)

                # Do ZeroCorrect
                for name in ['I0_amp', 'It_amp', 'Ir_amp', 'If_amp']:
                    item = self.ophydDict[name]
                    item.do_correct()

                # Wait for zero correction
                self.toLog("Performing ZeroCorrection. It will take 4 seconds.")
                self.delay(correctionTime)

                # ZeroCheck off and set suppress
                for name in ['I0_amp', 'It_amp', 'Ir_amp', 'If_amp']:
                    item = self.ophydDict[name]
                    item.zeroCheck.put(0)

                    if name == 'I0_amp':
                        item.set_suppress(self.control.gain_I0.currentIndex())

                    if name == 'It_amp':
                        item.set_suppress(self.control.gain_It.currentIndex())

                    if name == 'Ir_amp':
                        item.set_suppress(self.control.gain_Ir.currentIndex())

                    if name == 'If_amp':
                        item.set_suppress(self.control.gain_If.currentIndex())

                # Set Scaler Preset and Count
                item = self.ophydDict['scaler']

                # Test run
                item.preset_time.put(1)
                self.RE(bp.count([item]), scan_type='test_run')

                # set preset_time to 10 seconds
                item.preset_time.put(10)

                self.toLog("Started Dark Current Measurement. Please wait 10 seconds.")

                # trigger scaler
                self.RE(bp.count([item]), scan_type='dark_current')

                # retrieve measured data & set dark current
                headers = self.db(scan_type='dark_current')
                for idx, header in enumerate(headers):
                    # Get the last dark current data only
                    if idx > 0:
                        break
                    try:
                        data = header.table()
                    except:
                        return

                    # Skip if DataFrame is empty
                    if not data.count().any():
                        return

                # counts per seconds
                I0 = int(data['I0']/10.0)
                It = int(data['It']/10.0)
                If = int(data['If']/10.0)
                Ir = int(data['Ir']/10.0)

                _submit(self.control.I0_dark_current.setText, str(I0))
                _submit(self.control.It_dark_current.setText, str(It))
                _submit(self.control.If_dark_current.setText, str(If))
                _submit(self.control.Ir_dark_current.setText, str(Ir))


                # Set notify off
                self.blinkStatus = False

                # Enable controls
                self.control_enable(True)

                self._need_meas_darkcurrent = False
                self.toLog("Dark Current Measurement is finished")

            else:
                return

        except Exception as e:

            self._need_meas_darkcurrent = True

            # Set notify off
            self.blinkStatus = False

            # Enable controls
            self.control_enable(True)

            self.toLog("Dark Current Measurement is not completed!")
            print("Dark current measurement is not completed : {}".format(e))

        finally:
            # Enable Pause and resume buttons
            #self.control.pauseButton.setEnabled(True)
            #self.control.resumeButton.setEnabled(True)
            ...


    def run_scan_energy(self):

        scan_type = self.control.run_type.currentIndex()

        # Save previous run's uid
        try:
            self._last_uid = self.db[-1].start['uid']
        except:
            self._last_uid = ''

        currentEnergy = self.ophydDict['dcm'].energy.get()
        E0 = self.control.edit_E0.value()

        # Dark current is not necessary for fly-scan
        if scan_type != 2:
            if self._need_meas_darkcurrent:
                reply = qt.QMessageBox.question(self,
                                "Info", # title
                                "Would you like to measure the dark current?", # text
                                qt.QMessageBox.Yes| qt.QMessageBox.No,
                                qt.QMessageBox.No) # Default button

                if reply == qt.QMessageBox.Yes:
                    self.measDarkCurrent()

        reply = qt.QMessageBox.question(self,
                        "Info", # title
                        "Ready for Scan.\n\n" \
                        "Please Open the Photon Shutter.\n\n " \
                        "Want to Start Scan?",
                        qt.QMessageBox.Yes| qt.QMessageBox.No,
                        qt.QMessageBox.Yes) # Default button

        if reply == qt.QMessageBox.No:
            # set notify off
            self.blinkStatus = False

            # enable control
            self.control_enable(True)
            return

        # single or multi-scan
        if self.control.run_type.currentIndex() == 0:
            number_of_scan = 1
        else:
            number_of_scan = int(self.control.number_of_scan_edit.value())

        self._flag_stop = False
        self._flag_pause = False

        batch = self.control.use_batch_checkbox.isChecked()
        fly = self.control.run_type.currentIndex() == 2

        if fly:
            # repeat scan as specified number_of_scan-times
            for idx in range(number_of_scan):

                if self._flag_stop is True:
                    break

                print("starting ")
                self.do_scan_and_save()
        else:
            if batch:
                self.toLog("Batch Scan is started")
                self.do_scan_and_save()
            else:
                # repeat scan as specified number_of_scan-times
                self.do_scan_and_save()

    def do_scan_and_save(self):
        """Do energy scan and save data"""
        try:
            logger.debug("EXAFS scan started!")
            self.toLog("A EXAFS scan started!", color='blue')
            scan_type = self.control.run_type.currentIndex()

            # Normal step-scan
            if scan_type == 0 or scan_type == 1:
                # Set the flags for the graph
                self.plot_type = 'measure'
                self.scan_mode = 'normal'

                # Set axis labels
                msg = "XLabel:{}".format('Energy [eV]')
                self.sendZmq(msg)

                # Disable control
                self.control_enable(False)

                # Check K428 Amplifier Settings
                for name in ['I0_amp', 'It_amp', 'If_amp', 'Ir_amp']:
                    device = self.ophydDict[name]
                    # Set ZeroCheck False
                    device.zeroCheck.put(0, wait=False)

                try:
                    beamcurrent = caget(self.pv_names['Beam']['Current'], timeout = 1)
                    beamcurrent = np.round(beamcurrent, 3)
                except:
                    beamcurrent = 0.0

                # Make energy list
                try:
                    eList=EnergyScanList(SRB=[self.control.SRB_1.value(),
                                            self.control.SRB_2.value(),
                                            self.control.SRB_3.value(),
                                            self.control.SRB_4.value(),
                                            self.control.SRB_5.value(),
                                            self.control.SRB_6.value()],
                                        eMode=[self.control.eMode_bar_1.value()!=1000,
                                            self.control.eMode_bar_2.value()!=1000,
                                            self.control.eMode_bar_3.value()!=1000,
                                            self.control.eMode_bar_4.value()!=1000,
                                            self.control.eMode_bar_5.value()!=1000,
                                            self.control.eMode_bar_6.value()!=1000],
                                        StepSize=[self.control.stepSize_1.value(),
                                                self.control.stepSize_2.value(),
                                                self.control.stepSize_3.value(),
                                                self.control.stepSize_4.value(),
                                                self.control.stepSize_5.value()],
                                        SRBOnOff=[self.control.SRBOnOff_1.isChecked(),
                                                self.control.SRBOnOff_2.isChecked(),
                                                self.control.SRBOnOff_3.isChecked(),
                                                self.control.SRBOnOff_4.isChecked(),
                                                self.control.SRBOnOff_5.isChecked()],
                                        Time=[self.control.SRB_time_1.value(),
                                            self.control.SRB_time_2.value(),
                                            self.control.SRB_time_3.value(),
                                            self.control.SRB_time_4.value(),
                                            self.control.SRB_time_5.value()])
                except:
                    reply = qt.QMessageBox.information(self,
                                                       "Info", # title
                                                       "Please check scan range settings.\n")

                    raise UserException()


                E0 = self.control.edit_E0.value()
                energy_list = np.array(eList.energy_list, dtype=object) + float(E0)

                # For information update
                self.scan_total_count = 0
                for item in energy_list:
                    self.scan_total_count += len(item)

                time_list = eList.time_list
                delay_time = float(self.control.edit_delay_time.value())


                # Set notify on
                self.blinkStatus = True

                # Should wait until the auto-count of the scaler is finished
                waitTime = self.ophydDict['scaler'].auto_count_time.get() * 1.5

                dets = [self.ophydDict['scaler']]
                sdd = False

                # Retrieve meta data
                darkI0 = int(float(self.control.I0_dark_current.text()))
                darkIt = int(float(self.control.It_dark_current.text()))
                darkIf = int(float(self.control.If_dark_current.text()))
                darkIr = int(float(self.control.Ir_dark_current.text()))

                gainI0 = self.control.gain_I0.currentIndex() + 3
                gainIt = self.control.gain_It.currentIndex() + 3
                gainIf = self.control.gain_If.currentIndex() + 3
                gainIr = self.control.gain_Ir.currentIndex() + 3

                # hutch slits
                slits = self.ophydDict['slit']
                top = slits.up.user_readback.get()
                bottom = slits.down.user_readback.get()
                left = slits.left.user_readback.get()
                right = slits.right.user_readback.get()

                monoOffset = self.control.E0_offset.text()

                # Bluesky runtime engine
                plan = self.planDict['multi_exafs_scan_with_cleanup']

                self.RE(plan(detectors=[self.ophydDict['scaler']],
                             motor=self.ophydDict['dcm_energy'],
                             E0=E0,
                             energy_list=energy_list,
                             time_list=time_list,
                             delay_time=delay_time/1000,
                             waitTime=waitTime,
                             device_dict=self.ophydDict,
                             parent=self),
                        scan_type='measure',
                        scan_mode='normal',
                        E0=E0,
                        scan_points=self.scan_total_count,
                        darkI0=darkI0,
                        darkIt=darkIt,
                        darkIf=darkIf,
                        darkIr=darkIr,
                        gainI0=gainI0,
                        gainIt=gainIt,
                        gainIf=gainIf,
                        gainIr=gainIr,
                        slitTop=top,
                        slitBottom=bottom,
                        slitLeft=left,
                        slitRight=right,
                        sdd=sdd,
                        monoOffset=monoOffset,
                        beamcurrent=beamcurrent)

            # Fly Scan Mode
            elif scan_type == 2:
                # set notify on
                self.blinkStatus = True

                # Set the flags for the graph
                self.plot_type = 'measure'
                self.scan_mode = 'fly'
                # self.updatePlotThread.update_plot = False

                _flyer = self.ophydDict['energyFlyer']

                # Put scaler in normal mode
                _flyer.scaler_mode.put(0, wait=False)

                self._orig_mono_speed = _flyer.fly_motor_speed.get()

                # Check K428 Amplifier Settings
                for name in ['I0_amp', 'It_amp', 'If_amp', 'Ir_amp']:
                    device = self.ophydDict[name]

                    # Set ZeroCheck False
                    device.zeroCheck.put(0, wait=False)

                    # Set x10 gain False
                    device.x10.put(0, wait=False)

                    # Turn Off auto suppression
                    # device.autoSupEnable.put(1, wait=False)

                    # Turn On Suppression
                    device.suppression.put(1, wait=False)

                # Set axis labels
                msg = "XLabel:{}".format('Energy [eV]')
                self.sendZmq(msg)

                # Disable control
                self.control_enable(False)

                # _submit(self.control.pauseButton.setEnabled, False)
                # _submit(self.control.resumeButton.setEnabled, False)

                E0 = float(self.control.edit_E0.value())
                start_energy_rel = self.control.flyControl.flyStartE.value()
                stop_energy_rel = self.control.flyControl.flyStopE.value()
                enc_resolution = _flyer.fly_motor_eres.get()

                # Scan Paramters
                startE = E0 + start_energy_rel
                stopE = E0 + stop_energy_rel
                scan_encoder_steps = float(self.control.flyControl.flyEncoderStepSize.text())
                motor_speed = float(self.control.flyControl.flyMotorSpeed.text())

                # Set original mono speed for normal step-scan
                if motor_speed > self._orig_mono_speed:
                    self.ophydDict['energyFlyer'].fly_motor_speed.put(motor_speed, wait=True)

                if self._flag_stop:
                    raise UserException()

                self.toLog("Moving energy to {:.3f}. And wait for 1 second.".format(startE-200.0))
                # Move energy to startE-200 eV and wait 1 seconds for stablization
                self.RE(self.planDict['mv_and_wait'](self.ophydDict['dcm'], energy=(startE-200.0), delay=1))

                if self._flag_stop:
                    raise UserException()

                self.toLog("Moving energy to {:.3f}. And wait for 2 seconds.".format(startE))
                # Move energy to startE and wait 2 seconds for stablization
                self.RE(self.planDict['mv_and_wait'](self.ophydDict['dcm'], energy=startE, delay=2))

                # Calculate Total Scan Counts
                dcm = self.ophydDict['dcm']

                # Status update
                dcm.statusUpdate.put(1)
                # wait for status update
                self.delay(0.2)

                startTh = dcm.theta.user_readback.get()
                stopTh = np.rad2deg(np.arcsin(_hc/(2.*_si_111*float(stopE))))
                self.scan_total_count = int(abs(startTh - stopTh) / enc_resolution / scan_encoder_steps)

                cooling_time = self.control.flyControl.flyCoolTime.value()

                # Set Scan Paramters on dcmFlyer
                _flyer.setStartEnergy(startE)
                _flyer.setTargetEnergy(stopE)
                _flyer.setSpeed(motor_speed)
                _flyer.setEncSteps(scan_encoder_steps)
                _flyer.setNumOfCounts(self.scan_total_count)

                # hutch slits
                slits = self.ophydDict['slit']
                top = slits.up.user_readback.get()
                bottom = slits.down.user_readback.get()
                left = slits.left.user_readback.get()
                right = slits.right.user_readback.get()

                try:
                    beamcurrent = caget(self.pv_names['Beam']['Current'], timeout = 1)
                    beamcurrent = np.round(beamcurrent, 3)
                except:
                    beamcurrent = 0.0

                gainI0 = self.control.gain_I0.currentIndex() + 3
                gainIt = self.control.gain_It.currentIndex() + 3
                gainIf = self.control.gain_If.currentIndex() + 3
                gainIr = self.control.gain_Ir.currentIndex() + 3

                msg = 'FlyStartTime:{}'.format(ttime.time())
                self.sendZmq(msg)

                if self._flag_stop:
                    raise UserException()

                # Run fly scan
                self.RE(self.planDict['fly_scan_with_cleanup'](E0,
                                                               motor_speed,
                                                               self.ophydDict,
                                                               self),

                        scan_type='measure',
                        scan_mode='fly',
                        scan_points=self.scan_total_count,
                        startE=startE,
                        startTh=startTh,
                        stopE=stopE,
                        stopTh=stopTh,
                        enc_resolution=enc_resolution,
                        scan_encoder_steps=scan_encoder_steps,
                        motor_speed=motor_speed,
                        coolTime=cooling_time,
                        slitTop=top,
                        slitBottom=bottom,
                        slitLeft=left,
                        slitRight=right,
                        E0=E0,
                        gainI0=gainI0,
                        gainIt=gainIt,
                        gainIf=gainIf,
                        gainIr=gainIr,
                        darkI0=0,
                        darkIt=0,
                        darkIf=0,
                        darkIr=0,
                        beamcurrent=beamcurrent,
                        sdd=False)

        except Exception as e:
            print("Exception in do_scan_and_save : {}".format(e))

            self._flag_stop = True

            fly = self.control.run_type.currentIndex() == 2

            if fly:
                setValue = self.control.edit_E0.value()
                try:
                    self.control.abortButton.setDisabled(True)
                    self.moveToEnergy(setValue)
                except:
                    ...
                finally:
                    self.control.abortButton.setDisabled(False)

            # Restore control when unexpected exception
            if self.RE.state != 'paused':
                self.control_enable(True)
                self.blinkStatus = False


        finally:
            # TODO Clean up should go to finalize wrapper
            # scan_type = self.control.run_type.currentIndex()

            # if fly scan, set original dcm values
            # if scan_type == 2:
            #     # Set original mono speed for normal step-scan
            #     self.ophydDict['energyFlyer'].fly_motor_speed.put(self._orig_mono_speed, wait=True)

            #     # Set original mono speed for normal step-scan
            #     self.ophydDict['energyFlyer'].fly_motor_stop.put(1, wait=False)

            currentUid = self.db[-1].start['uid']
            if currentUid != self._last_uid:
                if self._flag_stop:
                    reply = qt.QMessageBox.question(self,
                                    "Info", # title
                                    "A scan is aborted.\n\n" \
                                    "Do you want to save data?\n",
                                    qt.QMessageBox.Yes| qt.QMessageBox.No,
                                    qt.QMessageBox.No) # Default button

                    if reply == qt.QMessageBox.Yes:
                        self.save_data()

    def subscribe_callback(self):
        """Subscribe AfterScanCallback"""
        self.token = self.RE.subscribe(self.after_scan_cb)

    def unsubscribe_callback(self):
        """Unsubscribe AfterScanCallback"""
        self.RE.unsubscribe(self.token)

    def save_data(self):
        '''
        export data to a txt file
        '''

        header = self.db[-1]

        meta_data = header.start
        scan_type = meta_data['scan_type']
        scan_mode = meta_data['scan_mode']

        path = self.control.data_save_path.toPlainText()
        if scan_type == 'measure':
            filename = self.control.filename_edit.text()
        else:
            filename = self.control.ecal_filename_edit.text()

        # if directory is not exists, make one recursively
        if not os.path.exists(path):
            os.makedirs(path)

        re_pat = re.compile('[0-9]+')
        last_scan_num = -1
        with os.scandir(path) as it:
            for item in it:
                if item.is_file():
                    _filename = item.name.split('.')[0]
                    idx = item.name.split('.')[-1]
                    if _filename != filename:
                        continue

                    if re_pat.match(idx):
                        try:
                            if int(idx) > last_scan_num:
                                last_scan_num = int(idx)
                        except:
                            pass

        file_path = os.path.abspath(os.path.join(path, filename + '.{:03d}'.format(last_scan_num + 1)))

        with open(file_path, 'w') as file:
            file.write('Data were Taken at BL1D KIST-PAL in Pohang Light Source')
            file.write('(PLS-II) by : ' + meta_data['user'] + '\t')

            file.write('Number of Points : ')
            file.write(str(meta_data['scan_points']) + '\t')

            if scan_type in ('measure'):
                file.write('Scanning Mode : ')

                if self.control.run_type.currentIndex() == 0:
                    scan_mode = 'Step-Scan'
                elif self.control.run_type.currentIndex() == 2:
                    scan_mode = 'Fly-Scan'
                else:
                    scan_mode = 'Multi-Scan'

                file.write(scan_mode + '\n')

            else:
                file.write('Scanning Mode : ')
                scan_mode = 'Step-Scan'
                file.write(scan_mode + '\n')

            file.write('Date and Time : ')

            if 'time' in list(header.stop.keys()):
                end_time = header.stop['time']
            else:
                end_time = ttime.time()

            start_time = datetime.datetime.fromtimestamp(header.start['time'])
            stop_time = datetime.datetime.fromtimestamp(end_time)
            file.write(start_time.strftime('%Y-%m-%d %H:%M:%S') + ' ~ ' + stop_time.strftime('%H:%M:%S') +'\t')

            file.write('Energy Origin(E0) : ')
            file.write(str(self.control.edit_E0.value()) + '\t')

            file.write('Mono Offset(deg) : ')
            file.write(self.control.E0_offset.text() + '\t')

            # Scan time in minutes
            scan_time = (end_time - header.start['time']) / 60
            file.write('Scanning Time : ' + str(np.round(scan_time, 4)) + ' (min)\t')
            file.write('Crystal Type : Si(111)\n')

            file.write('Slit Top : {:.3f} (mm)\tBottom : {:.3f} (mm)\tLeft : {:.3f}\tRight : {:.3f})\t'.format(float(meta_data['slitTop']),
                                                                                                               float(meta_data['slitBottom']),
                                                                                                               float(meta_data['slitLeft']),
                                                                                                               float(meta_data['slitRight'])))

            file.write('SR E-beam energy : 3.0 (GeV)\t')
            file.write('SR current (start) : {} (mA)\t'.format(str(meta_data['beamcurrent'])))
            file.write('SR Injection mode : Top-up\n')

            # 4th line
            file.write('Description : {}\n'.format(self.control.description_edit.toPlainText()
                                                                                .replace('\n', ' ')))

            scan_mode = meta_data['scan_mode']
            # Save SRB settings
            if scan_type == 'measure' and scan_mode == 'normal':
                eList=EnergyScanList(SRB=[self.control.SRB_1.value(),
                                            self.control.SRB_2.value(),
                                            self.control.SRB_3.value(),
                                            self.control.SRB_4.value(),
                                            self.control.SRB_5.value(),
                                            self.control.SRB_6.value()],
                                    eMode=[self.control.eMode_bar_1.value()!=1000,
                                            self.control.eMode_bar_2.value()!=1000,
                                            self.control.eMode_bar_3.value()!=1000,
                                            self.control.eMode_bar_4.value()!=1000,
                                            self.control.eMode_bar_5.value()!=1000,
                                            self.control.eMode_bar_6.value()!=1000],
                                    StepSize=[self.control.stepSize_1.value(),
                                                self.control.stepSize_2.value(),
                                                self.control.stepSize_3.value(),
                                                self.control.stepSize_4.value(),
                                                self.control.stepSize_5.value()],
                                    SRBOnOff=[self.control.SRBOnOff_1.isChecked(),
                                                self.control.SRBOnOff_2.isChecked(),
                                                self.control.SRBOnOff_3.isChecked(),
                                                self.control.SRBOnOff_4.isChecked(),
                                                self.control.SRBOnOff_5.isChecked()],
                                    Time=[self.control.SRB_time_1.value(),
                                            self.control.SRB_time_2.value(),
                                            self.control.SRB_time_3.value(),
                                            self.control.SRB_time_4.value(),
                                            self.control.SRB_time_5.value()])

                # 5th line
                text_srb = 'SRB := '
                for idx, value in enumerate(eList.energy_start_points):
                    text_srb += str(np.round(value, 3)) + ' (eV)\t'
                file.write(text_srb)
                file.write('\n')

                # ----------------------------------------------------------------------------------------

                # 6th ~ 11th line
                _idx = 1
                text_step_time = ''
                for value in eList.SRBOnOff:
                    if value:
                        if _idx == 1:
                            text_step_time += '1st '
                        elif _idx == 2:
                            text_step_time += '2nd '
                        elif _idx == 3:
                            text_step_time += '3rd '
                        else:
                            text_step_time += str(_idx) + 'th '

                        text_step_time += 'Energy step & Integration time : '

                        if eList.eMode[_idx-1]:
                            text_step_time += str(np.round(eList.StepSize[_idx-1], 3)) + ' (eV) & '
                        else:
                            text_step_time += str(np.round(eList.StepSize[_idx-1], 3)) + ' (k) & '

                        text_step_time += str(np.round(eList.time_list[_idx-1], 3)) + ' (sec)\n'

                        #Increase index
                        _idx += 1

                file.write(text_step_time)

                while _idx <= 6:
                    file.write('#\n')
                    _idx += 1
                    # ------------------------------------------------------------------------------------
            if scan_type == 'measure' and scan_mode == 'fly':
                startE = self.control.flyControl.flyStartE.value()
                stopE =  self.control.flyControl.flyStopE.value()
                resolution = self.control.flyControl.flyResolutionE.value()
                scan_time = self.control.flyControl.flyScanTime.value()
                encoder_step = self.control.flyControl.flyEncoderStepSize.text()

                text_energy_step = "E-Start(Rel.) : {}\tE-End(Rel.) : {}\tResolution : {}\tEncoderStep : {}\tTime(sec) : {}\n".format(startE,
                                                                                                                                    stopE,
                                                                                                                                    resolution,
                                                                                                                                    encoder_step,
                                                                                                                                    scan_time)
                text_energy_step += "#\n" * 6
                file.write(text_energy_step)

            elif scan_type == 'calibration':
                start = self.control.ecal_start_edit.value()
                stop =  self.control.ecal_stop_edit.value()
                step = self.control.ecal_step_size_edit.value()
                scan_time = self.control.ecal_time_edit.value()

                text_energy_step = "E-Start : {}\tE-End : {}\tE-Step : {}Time : {}\n".format(start,
                                                                                             stop,
                                                                                             step,
                                                                                             scan_time)
                text_energy_step += "#\n" * 6
                file.write(text_energy_step)

            if scan_mode in ('normal'):
                # 12th line
                # gain settings
                file.write('GAINS(Dark I) : {}(DI0 = {})\t {}(DIt = {})\t'.format(
                            meta_data['gainI0'],
                            meta_data['darkI0'],
                            meta_data['gainIt'],
                            meta_data['darkIt']
                    ))

                file.write('{}(DIf = {})\t {}(DIr = {})\n'.format(
                    meta_data['gainIf'],
                    meta_data['darkIf'],
                    meta_data['gainIr'],
                    meta_data['darkIr']))
            else:
                # 12th line
                # gain settings
                file.write('GAINS(Dark I) : {}(DI0 = {})\t {}(DIt = {})\t'.format(
                            meta_data['gainI0'],
                            0,
                            meta_data['gainIt'],
                            0
                    ))

                file.write('{}(DIf = {})\t {}(DIr = {})\n'.format(
                    meta_data['gainIf'],
                    0,
                    meta_data['gainIr'],
                    0))

        # Get E0
        E0 = meta_data['E0']

        # Retrieve scan data
        if scan_type == 'measure' and scan_mode == 'normal':
            data = header.table('primary')
            # compensate dark current
            data['I0'] = data['I0'] - meta_data['darkI0'] * data['scaler_time']
            data['It'] = data['It'] - meta_data['darkIt'] * data['scaler_time']
            data['If'] = data['If'] - meta_data['darkIf'] * data['scaler_time']
            data['Ir'] = data['Ir'] - meta_data['darkIr'] * data['scaler_time']

            if data is not None:
                data.to_csv(file_path,
                            float_format='%6.3f',
                            sep='\t',
                            index=False,
                            mode='a',
                            header=['Energy(eV)',
                                    'Ch1 (I0)',
                                    'Ch2 (IT)',
                                    'Ch3 (IF)',
                                    'Ch4 (IR)'],
                            columns=['dcm_energy',
                                     'I0',
                                     'It',
                                     'If',
                                     'Ir']
                            )


        elif scan_type == 'measure' and scan_mode == 'fly':
            try:
                data_orig = header.table('primary')
                meta_data = header.start

                # Convert encoder to energy
                data_enc = np.array(data_orig.ENC)

                enc_resolution = meta_data['enc_resolution']

                # Multiply sign for direction conversion. -1 : Increased encoder counter means the th-angle decreases
                scan_pos_th = self.enc_sign * data_enc * enc_resolution + meta_data['startTh']
                energy = _hc/(2.*_si_111*np.sin(np.deg2rad(scan_pos_th)))


                # Create a DataFrame, remove first and second elements for saving
                data = pd.DataFrame({ 'dcm_energy'            : np.array(energy),
                                      'I0'                    : np.array(data_orig.I0),
                                      'It'                    : np.array(data_orig.It),
                                      'If'                    : np.array(data_orig.If),
                                      'Ir'                    : np.array(data_orig.Ir)})

            except:
                data = None

            if data is not None:
                data.to_csv(file_path,
                            float_format='%6.3f',
                            sep='\t',
                            index=False,
                            mode='a',
                            header=['Read-Energy(eV)',
                                    'Ch1 (I0)',
                                    'Ch2 (IT)',
                                    'Ch3 (IF)',
                                    'Ch4 (IR)'],
                            columns=['dcm_energy',
                                     'I0',
                                     'It',
                                     'If',
                                     'Ir']
                            )
        elif scan_type == 'calibration':
            data = header.table('primary')

            # compensate dark current
            data['I0'] = data['I0'] - meta_data['darkI0'] * data['scaler_time']
            data['It'] = data['It'] - meta_data['darkIt'] * data['scaler_time']
            data['If'] = data['If'] - meta_data['darkIf'] * data['scaler_time']
            data['Ir'] = data['Ir'] - meta_data['darkIr'] * data['scaler_time']

            data.to_csv(file_path,
                        float_format='%6.3f',
                        sep='\t',
                        index=False,
                        mode='a',
                        header=['Energy(eV)',
                                'Ch1 (I0)',
                                'Ch2 (IT)',
                                'Ch3 (IF)',
                                'Ch4 (IR)'],
                        columns=['dcm_energy',
                                 'I0',
                                 'It',
                                 'If',
                                 'Ir']
                        )

        if scan_type in ('measure'):
            # Display last saved file
            self.control.saved_path_label.setText(file_path)
        elif scan_type == 'calibration':
            self.control.ecal_saved_path_label.setText(file_path)

        # Log message
        self.toLog("Data file is saved to " + file_path)

    def _sort_array(self, xdata, ydata):
        """ convert to numpy array for sorting """
        try:
            if isinstance(xdata, list) or \
                    isinstance(xdata, pd.core.series.Series):
                xdata = np.array(xdata)
            if isinstance(xdata, (int, float)):
                xdata = np.array([xdata])

            if isinstance(ydata, list):
                ydata = np.array(ydata)
            if isinstance(xdata, (int, float)):
                ydata = np.array([ydata])

            arg_sort = np.argsort(xdata)
            xdata = xdata[arg_sort]
            ydata = ydata[arg_sort]
        except:
            xdata = np.array([])
            ydata = xdata

        # Check finiteness
        # check xdata
        _check = False in np.isfinite(xdata)
        if _check:
            raise ValueError('xdataShouldBeFinite')

        _check = False in np.isfinite(ydata)
        if _check:
            raise ValueError('ydataShouldBeFinite')


        # Check xdata has 0 difference
        xdata_diff = np.diff(xdata)
        if 0. in xdata_diff:
            raise ValueError('xdataShouldBeDifferent')

        return np.array(xdata), np.array(ydata)

if __name__ == '__main__':
    app = qt.QApplication(sys.argv)
    main = Main()
    main.show()
    sys.exit(app.exec_())

