import time as ttime
import numpy as np
import threading
from collections import OrderedDict, deque
import logging

from xarray import Dataset
import pandas as pd

from epics import PV, caget

from silx.gui import qt
from silx.gui.utils.concurrent import submitToQtMainThread as _submit
from bluesky.callbacks.core import CallbackBase

from utils import derivative, loadPV

logger = logging.getLogger(__name__)

ColorDict = {}
ColorDict[0] = 'blue'
ColorDict[1] = 'red'
ColorDict[2] = 'green'
ColorDict[3] = 'orange'
ColorDict[4] = 'pink'
ColorDict[5] = 'brown'
ColorDict[6] = 'darkCyan'
ColorDict[7] = 'violet'
ColorDict[8] = 'darkBlue'
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

pv_names = loadPV()

_hc = 12398.5
_si_111 = 5.4309/np.sqrt(3)

def angle_to_energy(angle):
    """convert dcm angle to energy in keV"""
    energy = _hc/(2.*_si_111*np.sin(np.deg2rad(angle)))
    return float(energy)

def retrieve_data(data, meta_data, x_type, y_type):
    """retrieve data from catalog and returns xdata, ydata"""

    if 'sdd' in meta_data.keys():
        sdd = meta_data['sdd']
    else:
        sdd = False

    if meta_data['scan_type'] == 'tweak':
        xdata = np.array(range(len(data['time'])))
    else:
        E0 = meta_data['E0']

        # x_type : delta energy[eV]
        if x_type == 0:
            xdata = data['dcm_energy'] - E0
        # x_type : energy[eV]
        else:
            xdata = data['dcm_energy']

    # y_type : Transmittance
    if y_type == 0:
        I0 = data['I0']
        It = data['It']
        try:
            ydata = -1 * np.log(It/I0)
        except:
            ydata = None

    # y_type : Fluorescence
    elif y_type == 1:
        I0 = data['I0']
        If = data['If']
        try:
            ydata = If/I0
        except:
            ydata = None

    # y_type : Reference
    elif y_type == 2:
        It = data['It']
        Ir = data['Ir']
        try:
            ydata = -1 * np.log(Ir/It)
        except:
            ydata = None

    # y_type : I0 only
    elif y_type == 3:
        ydata = data['I0']

    # y_type : It only
    elif y_type == 4:
        ydata = data['It']

    # y_type : If only
    elif y_type == 5:
        ydata = data['If']

    # y_type : Ir only
    elif y_type == 6:
        ydata = data['Ir']

    else:
        return None, None

    return xdata, ydata

class CheckDcmThread(qt.QThread):
    """Check dcm moving traped status thread"""

    def __init__(self):
        super(CheckDcmThread, self).__init__()
        self.running = False
        self.theta_rbv  = PV(pv_names['DCM']['ThetaRBV'])
        self.theta_spmg = PV(pv_names['DCM']['ThetaSPMG'])
        self.theta_dmov = PV(pv_names['DCM']['ThetaDMOV'])
        self.theta_rcnt = PV(pv_names['DCM']['ThetaRCNT'])
        self.y2_rbv     = PV(pv_names['DCM']['Y2RBV'])
        self.y2_dmov    = PV(pv_names['DCM']['Y2DMOV'])
        self.y2_spmg    = PV(pv_names['DCM']['Y2SPMG'])
        self.y2_rcnt    = PV(pv_names['DCM']['Y2RCNT'])
        self.moving     = PV(pv_names['DCM']['Moving'])
        self.move       = PV(pv_names['DCM']['Move'])

    def start(self):
        """Start the update thread"""
        self.running = True
        super(CheckDcmThread, self).start()

    def stop(self):
        """Stop thread"""
        self.running = False

    def run(self):
        """Thread loop that updates the plot"""
        while self.running:
            try:
                ttime.sleep(0.2)

                # BL8C DCM is not working when the same energy with current value is targeted
                if self.theta_dmov.get() and self.y2_dmov.get() and self.moving.get():
                    theta_prev = self.theta_rbv.get()
                    rcnt_prev = self.theta_rcnt.get()

                    ttime.sleep(1)
                    if self.theta_dmov.get() and self.y2_dmov.get() and self.moving.get():
                        theta = self.theta_rbv.get()
                        rcnt  = self.theta_rcnt.get()
                        if np.isclose(theta, theta_prev, rtol=1e-8):
                            if np.isclose(rcnt, rcnt_prev, rtol=1e-8):
                                self.move.put(1)

                # When Aborting dcm motion, theta motor stucked
                if not self.theta_dmov.get() and self.moving.get():
                    theta_prev = self.theta_rbv.get()
                    rcnt_prev = self.theta_rcnt.get()

                    ttime.sleep(1)
                    if not self.theta_dmov.get() and self.moving.get():
                        theta = self.theta_rbv.get()
                        rcnt  = self.theta_rcnt.get()

                        if np.isclose(theta, theta_prev, rtol=1e-8):
                            if np.isclose(rcnt, rcnt_prev, rtol=1e-8):
                                # stop theta
                                self.theta_spmg.put(0)
                                ttime.sleep(0.5)
                                # go theta
                                self.theta_spmg.put(3)

                # When Aborting dcm motion, y2 motor stucked
                if not self.y2_dmov.get() and self.moving.get():
                    y2_prev = self.y2_rbv.get()
                    rcnt_prev = self.y2_rcnt.get()

                    ttime.sleep(1)
                    if not self.y2_dmov.get() and self.moving.get():
                        y2 = self.y2_rbv.get()
                        rcnt = self.y2_rcnt.get()
                        if np.isclose(y2, y2_prev, rtol=1e-8):
                            if np.isclose(rcnt, rcnt_prev, rtol=1e-8):
                                # stop theta
                                self.y2_spmg.put(0)
                                ttime.sleep(0.5)
                                # go theta
                                self.y2_spmg.put(3)
            except:
                pass


class UpdatePlotThread(qt.QThread):
    """Update plot in the different thread"""

    def __init__(self, parent):
        self.parent = parent
        self.event = threading.Event()
        self.force_update = deque()

        self.pv_names = loadPV()

        self.encPV = PV(self.pv_names['Scaler']['HC10E_ENC_WF'])
        self.I0PV  = PV(self.pv_names['Scaler']['HC10E_I0_WF'])
        self.ItPV  = PV(self.pv_names['Scaler']['HC10E_It_WF'])
        self.IfPV  = PV(self.pv_names['Scaler']['HC10E_If_WF'])
        self.IrPV  = PV(self.pv_names['Scaler']['HC10E_Ir_WF'])

        # Encoder Dicrection
        self.enc_sign  = float(self.pv_names['Scaler']['HC10E_ENC_Direction'])

        super(UpdatePlotThread, self).__init__()

    def start(self):
        """Start the update thread"""
        self.running = True
        self.event.set()
        super(UpdatePlotThread, self).start()

    def stop(self):
        """Stop this thread"""
        self.event.set()
        self.running = False

    def update(self, *args):
        """ Update DataViewer """
        self.event.set()

    def trigger(self):
        """force plot update"""
        self.update()
        self.force_update.append(1)

    def run(self):
        """Thread loop that updates the plot"""
        while self.running:

            try:
                # Check force update
                self.force_update.pop()
            except:
                # Wait for update event
                self.event.wait()

            try:
                num_of_history = int(self.parent.status.num_of_history_spin_box.value())

                # Remove extra curves
                for idx in range(num_of_history, 10):
                    self.parent.plot.removeCurve('Data {:d}'.format(idx))

                x_type = self.parent.status.x_axis_type_combo_box.currentIndex()
                y_type = self.parent.status.y_axis_type_combo_box.currentIndex()

                # derivate status
                derivativeStatus = bool(self.parent.status.derivativeCB.isChecked())

                # plot for energy scan
                if self.parent.plot_type == 'measure':

                    # clear unnecessary graph
                    _submit(self.parent.clear_extra_graph, num_of_history)

                    search_results = self.parent.db.search({'scan_type' : 'measure'}).items()

                    for idx, (_, run) in enumerate(search_results):

                        if idx >= num_of_history:
                            break

                        meta_data = run.metadata['start']
                        scan_mode = meta_data['scan_mode']

                        if 'sdd' in meta_data.keys():
                            sdd = meta_data['sdd']
                        else:
                            sdd = False

                        # get dark current
                        I0_dark_current = meta_data['darkI0']
                        It_dark_current = meta_data['darkIt']
                        If_dark_current = meta_data['darkIf']
                        Ir_dark_current = meta_data['darkIr']

                        # Get E0
                        E0 = meta_data['E0']

                        # Retrieve scan data
                        if scan_mode == 'normal':
                            try:
                                data = run.primary.read()
                            except:
                                # Do reset when there is no zoomed history
                                resetzoom = len(self.parent.plot.getLimitsHistory()) == 0 and not self.parent.dragging

                                # Plot with null data
                                _submit(self.parent.plot.addCurve,
                                                                [],
                                                                [],
                                                                legend='Data ' + str(idx),
                                                                color=ColorDict[idx],
                                                                linestyle='-',
                                                                resetzoom=resetzoom,
                                                                z=ZOrder[idx],
                                                                selectable=False)
                                continue

                            # To eV unit
                            # data['dcm_energy'] *= 1000.0

                            # compensate dark current
                            data['I0'] = data['I0'] - I0_dark_current * data['scaler_time']
                            data['It'] = data['It'] - It_dark_current * data['scaler_time']
                            data['If'] = data['If'] - If_dark_current * data['scaler_time']
                            data['Ir'] = data['Ir'] - Ir_dark_current * data['scaler_time']

                            if sdd:
                                # DeadTime correction
                                mca1_icr = data['falconX4_mca1InputCountRate']
                                mca2_icr = data['falconX4_mca2InputCountRate']
                                mca3_icr = data['falconX4_mca3InputCountRate']
                                mca4_icr = data['falconX4_mca4InputCountRate']

                                mca1_ocr = data['falconX4_mca1OutputCountRate']
                                mca2_ocr = data['falconX4_mca2OutputCountRate']
                                mca3_ocr = data['falconX4_mca3OutputCountRate']
                                mca4_ocr = data['falconX4_mca4OutputCountRate']

                                data['falconX4_mca1_rois_roi0_count'] *= mca1_icr / mca1_ocr
                                data['falconX4_mca2_rois_roi0_count'] *= mca2_icr / mca2_ocr
                                data['falconX4_mca3_rois_roi0_count'] *= mca3_icr / mca3_ocr
                                data['falconX4_mca4_rois_roi0_count'] *= mca4_icr / mca4_ocr

                                # MCA Sum
                                data['mcaSum'] = data['falconX4_mca1_rois_roi0_count'] +\
                                                data['falconX4_mca2_rois_roi0_count'] +\
                                                data['falconX4_mca3_rois_roi0_count'] +\
                                                data['falconX4_mca4_rois_roi0_count']

                        elif scan_mode == 'fly':

                            # header
                            headers = self.parent.dbv1(scan_type='measure')

                            for _idx, hd in enumerate(headers):
                                header = hd
                                if idx == _idx:
                                    break

                            if 'primary' in header.stream_names:
                                data = header.table('primary')
                                meta_data = header.start

                                # Convert encoder to energy
                                data_enc = np.array(data['ENC'])
                                enc_resolution = meta_data['enc_resolution']
                                startTh = meta_data['startTh']

                                # Multiply sign for direction conversion. Increased encoder counter means the th-angle decreases
                                scan_pos_th = self.enc_sign * data_enc * enc_resolution + startTh
                                energy = _hc/(2.*_si_111*np.sin(np.deg2rad(scan_pos_th)))
                                data['dcm_energy'] = energy

                            else:
                                # delay for monitor update
                                ttime.sleep(0.2)

                                # During fly-scan, retrieve data from EPICS IOC
                                enc_pos = np.array(self.encPV.get())
                                chan1   = np.array(self.I0PV.get())
                                chan2   = np.array(self.ItPV.get())
                                chan3   = np.array(self.IfPV.get())
                                chan4   = np.array(self.IrPV.get())

                                _arrayMinSize = int(min(enc_pos.size, chan1.size, chan2.size, chan3.size, chan4.size))

                                # The arrays must be the same size
                                if _arrayMinSize < enc_pos.size:
                                    enc_pos = enc_pos[:_arrayMinSize]

                                if _arrayMinSize < chan1.size:
                                    chan1 = chan1[:_arrayMinSize]

                                if _arrayMinSize < chan2.size:
                                    chan2 = chan2[:_arrayMinSize]

                                if _arrayMinSize < chan3.size:
                                    chan3 = chan3[:_arrayMinSize]

                                if _arrayMinSize < chan4.size:
                                    chan4 = chan4[:_arrayMinSize]

                                # Load scan parameters
                                enc_resolution = meta_data['enc_resolution']
                                startTh    = meta_data['startTh']

                                # Multiply sign for direction conversion. Increased encoder counter means the th-angle decreases
                                scan_pos_th = self.enc_sign * enc_pos * enc_resolution + startTh
                                energy = np.array(_hc/(2.*_si_111*np.sin(np.deg2rad(scan_pos_th))))

                                # Drop the first element and create a DataFrame
                                data = pd.DataFrame({'dcm_energy'    : energy,
                                                     'I0'            : chan1,
                                                     'It'            : chan2,
                                                     'If'            : chan3,
                                                     'Ir'            : chan4})

                        # Skip if DataFrame is empty
                        if not bool(int(data['dcm_energy'].count())):
                            continue

                        # Update scan status
                        # Don't update for fly scan
                        if idx == 0 :
                            _submit(self.parent.update_scan_status, data, meta_data)

                        xdata, ydata = retrieve_data(data, meta_data, x_type, y_type)

                        if ydata is None:
                            continue

                        xdata = np.array(xdata)
                        ydata = np.array(ydata)

                        # Select only finite values
                        _finiteIndex = np.isfinite(ydata)
                        xdata = xdata[_finiteIndex]
                        ydata = ydata[_finiteIndex]

                        # Do reset when there is no zoomed history
                        resetzoom = len(self.parent.plot.getLimitsHistory()) == 0 and not self.parent.dragging

                        # Data plot
                        curve = self.parent.plot.getCurve('Data '+ str(idx))

                        if curve:
                            oldXData = curve.getXData(copy=True)
                            oldYData = curve.getYData(copy=True)

                            if np.any(oldXData != xdata) or np.any(oldYData != ydata):
                                _submit(self.parent.plot.addCurve,
                                                                xdata,
                                                                ydata,
                                                                legend='Data ' + str(idx),
                                                                color=ColorDict[idx],
                                                                linestyle='-',
                                                                resetzoom=resetzoom,
                                                                z=ZOrder[idx],
                                                                selectable=False)
                        else:
                            _submit(self.parent.plot.addCurve,
                                                            xdata,
                                                            ydata,
                                                            legend='Data ' + str(idx),
                                                            color=ColorDict[idx],
                                                            linestyle='-',
                                                            resetzoom=resetzoom,
                                                            z=ZOrder[idx],
                                                            selectable=False)

                        # Derivative plot
                        if idx == 0:
                            # derivative axis
                            if derivativeStatus:
                                _derivative = np.array(derivative(xdata, ydata))

                                # Select only finite values
                                _finiteIndex = np.isfinite(_derivative)
                                _xdata = xdata[_finiteIndex]
                                _derivative = _derivative[_finiteIndex]

                                # Previous derivative curve
                                curve = self.parent.plot.getCurve('derivative')

                                # Derivative Plot
                                if curve:
                                    oldXData = curve.getXData(copy=True)
                                    oldYData = curve.getYData(copy=True)
                                    if np.any(oldXData != _xdata) or np.any(oldYData != _derivative):
                                        _submit(
                                                self.parent.plot.addCurve,
                                                _xdata,
                                                _derivative,
                                                yaxis='right',
                                                linestyle='-',
                                                color=ColorDict[10],
                                                resetzoom=resetzoom,
                                                legend='derivative',
                                                z=ZOrder[10],
                                                selectable=False)
                                else:
                                    _submit(
                                            self.parent.plot.addCurve,
                                            _xdata,
                                            _derivative,
                                            yaxis='right',
                                            linestyle='-',
                                            color=ColorDict[10],
                                            resetzoom=resetzoom,
                                            legend='derivative',
                                            z=ZOrder[10],
                                            selectable=False)

                            else:
                                _submit(
                                        self.parent.plot.removeCurve,
                                        'derivative')

                # plot for energy calibration
                elif self.parent.plot_type == 'calibration':

                    # clear unnecessary graph
                    _submit(self.parent.clear_extra_graph, num_of_history)

                    search_results = self.parent.db.search({'scan_type' : 'calibration'}).items()

                    for idx, (_, run) in enumerate(search_results):

                        if idx >= num_of_history:
                            break

                        # scan meta data
                        meta_data = run.metadata['start']

                        # get dark current
                        I0_dark_current = meta_data['darkI0']
                        It_dark_current = meta_data['darkIt']
                        If_dark_current = meta_data['darkIf']
                        Ir_dark_current = meta_data['darkIr']

                        # Retrieve scan data
                        try:
                            data = run.primary.read()
                        except:
                            # Do reset when there is no zoomed history
                            resetzoom = len(self.parent.plot.getLimitsHistory()) == 0 and not self.parent.dragging

                            # Plot with null data
                            _submit(self.parent.plot.addCurve,
                                                            [],
                                                            [],
                                                            legend='Data ' + str(idx),
                                                            color=ColorDict[idx],
                                                            linestyle='-',
                                                            resetzoom=resetzoom,
                                                            z=ZOrder[idx],
                                                            selectable=False)
                            continue

                        # data['dcm_energy'] *= 1000.0

                        # compensate dark current
                        data['I0'] = data['I0'] - I0_dark_current * data['scaler_time']
                        data['It'] = data['It'] - It_dark_current * data['scaler_time']
                        data['If'] = data['If'] - If_dark_current * data['scaler_time']
                        data['Ir'] = data['Ir'] - Ir_dark_current * data['scaler_time']

                        # Get E0
                        # To eV unit
                        E0 = meta_data['E0']

                        # Skip if DataFrame is empty
                        if not bool(len(data['time'])):
                            continue

                        # update scan status
                        if idx == 0:
                            _submit(self.parent.update_scan_status, data, meta_data)

                        xdata, ydata = retrieve_data(data, meta_data, x_type, y_type)

                        if ydata is None:
                            continue

                        xdata = np.array(xdata)
                        ydata = np.array(ydata)

                        # Select only finite values
                        _finiteIndex = np.isfinite(ydata)
                        xdata = xdata[_finiteIndex]
                        ydata = ydata[_finiteIndex]

                        resetzoom = len(self.parent.plot.getLimitsHistory()) == 0 and not self.parent.dragging

                        # Set data
                        curve = self.parent.plot.getCurve('Data '+ str(idx))
                        if curve is not None:
                            oldXData = curve.getXData(copy=True)
                            oldYData = curve.getYData(copy=True)

                            if np.any(oldXData != xdata) or np.any(oldYData != ydata):
                                _submit(self.parent.plot.addCurve,
                                                                xdata,
                                                                ydata,
                                                                legend='Data ' + str(idx),
                                                                color=ColorDict[idx],
                                                                linestyle='-',
                                                                resetzoom=resetzoom,
                                                                z=ZOrder[idx],
                                                                selectable=False)
                        else:
                            _submit(self.parent.plot.addCurve,
                                                            xdata,
                                                            ydata,
                                                            legend='Data ' + str(idx),
                                                            color=ColorDict[idx],
                                                            linestyle='-',
                                                            resetzoom=resetzoom,
                                                            z=ZOrder[idx],
                                                            selectable=False)

                        # Derivative plot
                        if len(xdata) > 2 and idx == 0:
                            _derivative = np.array(derivative(xdata, ydata))

                            # Select only finite values
                            _finiteIndex = np.isfinite(_derivative)
                            _xdata = xdata[_finiteIndex]
                            _derivative = _derivative[_finiteIndex]

                            derivative_max = max(_derivative)
                            idx_max = np.where(_derivative == derivative_max)[0][0]

                            # x_type == 0 : delta energy, x_type == 1 : energy[eV]
                            if x_type == 0:
                                energy_derivative_max = _xdata[idx_max] + E0
                            else:
                                energy_derivative_max = _xdata[idx_max]


                            msg = "EcalPeakEnergyLabel:{}".format(str(
                                np.round(float(energy_derivative_max), 4)))
                            self.parent.sendZmq(msg)

                            msg = "EcalEnergyDifferenceLabel:{}".format(str(
                                np.round(float(energy_derivative_max - E0), 4)))
                            self.parent.sendZmq(msg)

                            # derivative axis
                            if derivativeStatus:
                                _derivative = np.array(derivative(xdata, ydata))

                                # Select only finite values
                                _finiteIndex = np.isfinite(_derivative)
                                _xdata = xdata[_finiteIndex]
                                _derivative = _derivative[_finiteIndex]

                                # Previous derivative curve
                                curve = self.parent.plot.getCurve('derivative')

                                # Derivative Plot
                                if curve is not None:
                                    oldXData = curve.getXData(copy=True)
                                    oldYData = curve.getYData(copy=True)
                                    if np.any(oldXData != _xdata) or np.any(oldYData != _derivative):
                                        _submit(
                                                self.parent.plot.addCurve,
                                                _xdata,
                                                _derivative,
                                                yaxis='right',
                                                linestyle='-',
                                                color=ColorDict[10],
                                                resetzoom=resetzoom,
                                                legend='derivative',
                                                z=ZOrder[10],
                                                selectable=False)
                                else:
                                    _submit(
                                            self.parent.plot.addCurve,
                                            _xdata,
                                            _derivative,
                                            yaxis='right',
                                            linestyle='-',
                                            color=ColorDict[10],
                                            resetzoom=resetzoom,
                                            legend='derivative',
                                            z=ZOrder[10],
                                            selectable=False)

                            else:
                                _submit(
                                        self.parent.plot.removeCurve,
                                        'derivative')

                # plot for tweak plan
                elif self.parent.plot_type == 'align':

                    # clear unnecessary graph
                    _submit(self.parent.clear_extra_graph, num_of_history)
                    _submit(self.parent.plot.removeCurve, 'derivative')

                    search_results = self.parent.db.search({'scan_type' : 'tweak'}).items()

                    for idx, (_, run) in enumerate(search_results):

                        if idx >= 1:
                            break

                        try:
                            data = run.primary.read()
                        except:
                            continue

                        meta_data = run.metadata['start']

                        # Skip if DataFrame is empty
                        if not bool(len(data['time'])):
                            continue

                        # update scan status
                        if idx == 0:
                            _submit(self.parent.update_scan_status, data, meta_data)

                        xdata, ydata = retrieve_data(data, meta_data, x_type, y_type)

                        if ydata is None:
                            continue

                        ydata = np.array(ydata)

                        # Select only finite values
                        _finiteIndex = np.isfinite(ydata)
                        xdata = xdata[_finiteIndex]
                        ydata = ydata[_finiteIndex]

                        resetzoom = len(self.parent.plot.getLimitsHistory()) == 0 and not self.parent.dragging
                        ratio = float(self.parent.settings['ratio'])

                        _submit(self.parent.plot.addCurve,
                                xdata,
                                ydata,
                                legend='Data 0',
                                color=ColorDict[0],
                                linestyle='-',
                                resetzoom=resetzoom,
                                z=ZOrder[0],
                                selectable=False)

                        msg = "DCM_I0:{}".format(str(np.round(ydata[-1], 2)))
                        self.parent.sendZmq(msg)

                        msg = "DCM_I0_2:{}".format(str(np.round(ydata[-1]*ratio, 2)))
                        self.parent.sendZmq(msg)

            except Exception as e:
                print("Exception occured in scan_utils.UpdatePlotThread {}", e)

            # Set wait for events
            self.event.clear()

class EnergyScanList:
    """ make an E-Scan array """
    def __init__(self, SRB=None, eMode=None, StepSize=None,\
                 SRBOnOff=None, Time=None):

        self.SRB = SRB
        self.eMode = eMode
        self.StepSize = StepSize
        self.SRBOnOff = SRBOnOff
        self.time_list = Time
        self.energy_list = []
        self.energy_start_points = []
        self.makeArray()

    def makeArray(self):
        """ make an energy scan list """
        for idx in range(len(self.SRB)-1):
            active = self.SRBOnOff[idx]
            eMode = self.eMode[idx]
            eMode_next = self.eMode[idx+1]

            if active:
                if eMode and eMode_next:
                    # Calculate energy list
                    if len(self.energy_list):
                        last_point = self.energy_list[-1][-1]
                        last_step = self.StepSize[idx-1]

                        # Check start point
                        if last_point + last_step > self.SRB[idx]:
                            last_point = last_point + self.StepSize[idx]

                        item = np.arange(last_point,
                                         self.SRB[idx+1],
                                         self.StepSize[idx])

                        # Check end point
                        if np.isclose(item[-1] + self.StepSize[idx], self.SRB[idx+1]):
                            item = np.append(item, self.SRB[idx+1])

                    else:
                        last_point = self.SRB[idx]
                        item = np.arange(self.SRB[idx],
                                         self.SRB[idx+1],
                                         self.StepSize[idx])

                        # Check end point
                        if np.isclose(item[-1] + self.StepSize[idx], self.SRB[idx+1]):
                            item = np.append(item, self.SRB[idx+1])

                    # Save energy start points in eV
                    self.energy_start_points.append(item[0])

                    self.energy_list.append(np.round(item, 5))

                elif not eMode and eMode_next:
                    # Calculate energy list
                    item = np.arange(self.energy_list[-1][-1],
                                     self.SRB[idx+1],
                                     self.StepSize[idx])
                    self.energy_list.append(np.round(item, 5))

                    # Save energy start points in eV
                    self.energy_start_points.append(item[0])

                else:
                    if not len(self.energy_list):
                        raise ValueError


                    # Calculate energy list
                    item = self.kMode(self.energy_list[-1][-1],
                                      self.SRB[idx+1],
                                      self.StepSize[idx])

                    self.energy_list.append(np.round(item, 5))

                    # Save energy start points in eV
                    self.energy_start_points.append(item[0])

        # End energy point in eV
        self.energy_start_points.append(self.energy_list[-1][-1])

        self.energy_list = np.array(self.energy_list, dtype=object)
        self.time_list = self.time_list[:len(self.energy_list)]

    def kMode(self, start_energy_eV, stop_energy_k, step_energy_k):
        """ kMode energy list """
        k_energy_list = []
        a = np.sqrt(start_energy_eV) * 0.512
        stop_energy_eV = (stop_energy_k/0.512)**2
        N = 1

        while True:
            energy_eV = (((step_energy_k * N)+a)/0.512)**2

            if (energy_eV >= stop_energy_eV):
                break

            k_energy_list.append(energy_eV)
            N += 1

        return k_energy_list

class Tweak():
    wait = True
    step = 0.1

class ScanNumber():
    num = 0

class AfterScanCallback(CallbackBase):
    """ Callback function which is called at the end of a scan"""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.num_of_scan_edit = self.parent.control.number_of_scan_edit

    def __call__(self, name, doc):
        super().__call__(name, doc)

    def stop(self, doc):
        ''' Finalize scan '''
        # Save data
        self.parent.save_data()

# https://stackoverflow.com/questions/40932639/pyqt-messagebox-automatically
# -closing-after-few-seconds
class TimerMessageBox(qt.QMessageBox):
    def __init__(self, parent=None, timeout=14):
        super(TimerMessageBox, self).__init__(parent)
        self.setWindowTitle("Dark Current")
        self.time_to_wait = timeout
        self.setText("Measuring dark current (Done in {0} secondes.)".format(timeout))
        self.setStandardButtons(qt.QMessageBox.NoButton)
        self.timer = qt.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.changeContent)
        self.timer.start()

    def changeContent(self):
        self.setText("Please wait 10 seconds for the dark current measurement.\n\n\
                      This window closes automatically after {} seconds".format(self.time_to_wait))
        self.time_to_wait -= 1
        if self.time_to_wait <= 0:
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
