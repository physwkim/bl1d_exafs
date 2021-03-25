__author__ = "Sang-Woo Kim, Pohang Accelerator Laboratory"
__contact__ = "physwkim@postech.ac.kr"
__license__ = "MIT"
__copyright__ = "Pohang Accelerator Laboratory, Pohang, South Korea"


import sys
import re
import os
import time as ttime
import numpy as np

from silx.gui import qt
from silx.gui.utils.concurrent import submitToQtMainThread as _submit

from utils import path, loadJson
from utils import addWidgets, addStretchWidget
from utils import addLabelWidget, addLabelWidgetUnit, addLabelWidgetVert

_hc = 12398.5
_si_111 = 5.4309/np.sqrt(3)


class FlyControlWidget(qt.QMainWindow):
    """Scan Control Widget"""

    def __init__(self, parent=None):
        super(FlyControlWidget, self).__init__(parent)
        self._parent = parent
        self.create_widgets()
        self.layout_widgets()
        self.make_connections()

    def create_widgets(self):
        self.main_panel = qt.QWidget(self)
        self.main_panel.setLayout(qt.QVBoxLayout())
        self.setCentralWidget(self.main_panel)

        self.flyStartE = qt.QDoubleSpinBox(self)
        self.flyStartE.setAlignment(qt.Qt.AlignCenter)
        self.flyStartE.setMinimumSize(qt.QSize(130, 30))
        self.flyStartE.setMaximumSize(qt.QSize(130, 30))
        self.flyStartE.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.flyStartE.setDecimals(2)
        self.flyStartE.setMinimum(-9999999.99)
        self.flyStartE.setMaximum(9999999.99)
        self.flyStartE.setSingleStep(0.0)
        self.flyStartE.setProperty("value", -200.0)

        self.flyStopE = qt.QDoubleSpinBox(self)
        self.flyStopE.setAlignment(qt.Qt.AlignCenter)
        self.flyStopE.setMinimumSize(qt.QSize(130, 30))
        self.flyStopE.setMaximumSize(qt.QSize(130, 30))
        self.flyStopE.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.flyStopE.setDecimals(2)
        self.flyStopE.setMinimum(-9999999.99)
        self.flyStopE.setMaximum(9999999.99)
        self.flyStopE.setSingleStep(0.01)
        self.flyStopE.setProperty("value", 600)

        self.flyResolutionE = qt.QDoubleSpinBox(self)
        self.flyResolutionE.setAlignment(qt.Qt.AlignCenter)
        self.flyResolutionE.setMinimumSize(qt.QSize(130, 30))
        self.flyResolutionE.setMaximumSize(qt.QSize(130, 30))
        self.flyResolutionE.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.flyResolutionE.setDecimals(2)
        self.flyResolutionE.setMinimum(0.01)
        self.flyResolutionE.setMaximum(9999999.99)
        self.flyResolutionE.setSingleStep(0.01)
        self.flyResolutionE.setProperty("value", 0.4)

        self.flyScanTime = qt.QDoubleSpinBox(self)
        self.flyScanTime.setAlignment(qt.Qt.AlignCenter)
        self.flyScanTime.setMinimumSize(qt.QSize(130, 30))
        self.flyScanTime.setMaximumSize(qt.QSize(130, 30))
        self.flyScanTime.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.flyScanTime.setDecimals(2)
        self.flyScanTime.setMinimum(0.01)
        self.flyScanTime.setMaximum(9999999.99)
        self.flyScanTime.setSingleStep(0.01)
        self.flyScanTime.setProperty("value", 180)

        self.flyMotorSpeed = qt.QLineEdit(self)
        self.flyMotorSpeed.setMinimumSize(qt.QSize(130, 30))
        self.flyMotorSpeed.setMaximumSize(qt.QSize(130, 30))
        self.flyMotorSpeed.setAlignment(qt.Qt.AlignCenter)
        self.flyMotorSpeed.setStyleSheet("background : transparent")
        self.flyMotorSpeed.setReadOnly(True)
        self.flyMotorSpeed.setText("0.0214")

        self.flyEncoderStepSize = qt.QLineEdit(self)
        self.flyEncoderStepSize.setMinimumSize(qt.QSize(130, 30))
        self.flyEncoderStepSize.setMaximumSize(qt.QSize(130, 30))
        self.flyEncoderStepSize.setAlignment(qt.Qt.AlignCenter)
        self.flyEncoderStepSize.setStyleSheet("background : transparent")
        self.flyEncoderStepSize.setReadOnly(True)
        self.flyEncoderStepSize.setText("26")

        self.flyNumOfPoints = qt.QLineEdit(self)
        self.flyNumOfPoints.setMinimumSize(qt.QSize(130, 30))
        self.flyNumOfPoints.setMaximumSize(qt.QSize(130, 30))
        self.flyNumOfPoints.setAlignment(qt.Qt.AlignCenter)
        self.flyNumOfPoints.setStyleSheet("background : transparent")
        self.flyNumOfPoints.setReadOnly(True)
        self.flyNumOfPoints.setText("1973")

        self.flyCoolTime = qt.QDoubleSpinBox(self)
        self.flyCoolTime.setAlignment(qt.Qt.AlignCenter)
        self.flyCoolTime.setMinimumSize(qt.QSize(130, 30))
        self.flyCoolTime.setMaximumSize(qt.QSize(130, 30))
        self.flyCoolTime.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.flyCoolTime.setDecimals(0)
        self.flyCoolTime.setMinimum(1)
        self.flyCoolTime.setMaximum(9999999.99)
        self.flyCoolTime.setSingleStep(1)
        self.flyCoolTime.setProperty("value", 30)

    def layout_widgets(self):
        flyInfoWg = qt.QWidget(self)
        flyInfoWg.setLayout(qt.QVBoxLayout())
        flyInfoWg.layout().addWidget(addLabelWidget("Calculated motor speed [Deg/sec] : ",
                                                    self.flyMotorSpeed,
                                                    labelWidth=250,
                                                    align='right'))

        flyInfoWg.layout().addWidget(addLabelWidget("Encoder Steps per Point : ",
                                                    self.flyEncoderStepSize,
                                                    labelWidth=250,
                                                    align='right'))

        flyInfoWg.layout().addWidget(addLabelWidget("Estimated Number of Scan Points : ",
                                                    self.flyNumOfPoints,
                                                    labelWidth=250,
                                                    align='right'))

        self.main_panel.layout().addWidget(flyInfoWg)

        scanSetupGB = qt.QGroupBox("Fly Scan Setup", self)
        scanSetupGB.setLayout(qt.QVBoxLayout())
        scanSetupGB.layout().addWidget(
            addWidgets([
                addLabelWidgetVert("Start energy[eV]", self.flyStartE, align='center'),
                addLabelWidgetVert("Stop energy[eV]", self.flyStopE, align='center'),
                addLabelWidgetVert("Resolution[eV]", self.flyResolutionE, align='center'),
                addLabelWidgetVert("Scan Time[s]", self.flyScanTime, align='center')], align='uniform'))
        scanSetupGB.layout().addWidget(addLabelWidget("Cooling Time[s]", self.flyCoolTime, align='right'))

        self.main_panel.layout().addWidget(scanSetupGB)

    def make_connections(self):
        self.flyStartE.editingFinished.connect(self.updateFlyInfo)
        self.flyStopE.editingFinished.connect(self.updateFlyInfo)
        self.flyResolutionE.editingFinished.connect(self.updateFlyInfo)
        self.flyScanTime.editingFinished.connect(self.updateFlyInfo)

    def updateFlyInfo(self):
        try:
            startE = self.flyStartE.value()
            stopE = self.flyStopE.value()
            resolution = self.flyResolutionE.value()
            time = self.flyScanTime.value()
            E0 = self._parent.edit_E0.value()
            encResolution = self._parent.parent.ophydDict['dcm'].encResolution.get()

            # Angles at E0 and E0 + Resolution
            th0 = np.rad2deg(np.arcsin(_hc/(2.*_si_111*float(E0))))
            th0_plus_step = np.rad2deg(np.arcsin(_hc/(2.*_si_111*float(E0 + resolution))))
            th0_step = abs(th0 - th0_plus_step)

            if th0_step < encResolution:
                th0_step = encResolution
                newEnergyResolution = round(abs(_hc/(2.*_si_111*np.sin(np.deg2rad(th0-th0_step))) - E0), 2)
                self.flyResolutionE.setValue(newEnergyResolution)

            Energy_start = E0 + startE
            th_start = np.rad2deg(np.arcsin(_hc/(2.*_si_111*float(Energy_start))))

            currentTab = self._parent.tabWidget.currentIndex()
            currentStack = self._parent.stackedWidget.currentIndex()

            # When currentTab is 'Energy Scan' and currentStack is in 'fly-mode'
            if currentTab == 0 and currentStack == 1:

                # Switch startE and stopE
                if startE > stopE:
                    # Swap
                    tmp = startE
                    startE = stopE
                    stopE  = tmp

                    _submit(self.flyStartE.setValue, startE)
                    _submit(self.flyStopE.setValue, stopE)

                Energy_stop = E0 + stopE
                th_stop = np.rad2deg(np.arcsin(_hc/(2.*_si_111*float(Energy_stop))))

                # DCM fly-scan speed [Deg/sec]
                estimated_speed = round(abs(th_stop - th_start) / time, 4)

                # Check encoder steps per point
                enc_steps_per_point = int(th0_step / encResolution)

                # Set total scan counts
                scan_total_counts = int(abs(th_start - th_stop) / encResolution / enc_steps_per_point) + 1

                # Check number of scan points
                maxPoints = int(self._parent.parent.pv_names['Scaler']['HC10E_FlyMaxPoints'])

                if scan_total_counts > maxPoints:
                    while 1:
                        enc_steps_per_point += 1

                        # Calculate scan_total_counts again
                        scan_total_counts = int(abs(th_start - th_stop) / encResolution / enc_steps_per_point) + 1

                        # Escape
                        if scan_total_counts < maxPoints:
                            break

                    new_th0_step = enc_steps_per_point * encResolution
                    newEnergyResolution = round(abs(_hc/(2.*_si_111*np.sin(np.deg2rad(th0-new_th0_step))) - E0), 2)
                    self.flyResolutionE.setValue(newEnergyResolution)

                elif scan_total_counts < 30:
                    while 1:
                        enc_steps_per_point -= 1

                        # Calculate scan_total_counts again
                        scan_total_counts = int(abs(th_start - th_stop) / encResolution / enc_steps_per_point) + 1

                        # Escape
                        if scan_total_counts > 30:
                            break

                    new_th0_step = enc_steps_per_point * encResolution
                    newEnergyResolution = round(abs(_hc/(2.*_si_111*np.sin(np.deg2rad(th0-new_th0_step))) - E0), 2)
                    self.flyResolutionE.setValue(newEnergyResolution)


                # Check speed range
                speed = estimated_speed
                vmax = self._parent.parent.ophydDict['dcm_etc'].mono_vmax.get()
                vmin = self._parent.parent.ophydDict['dcm_etc'].mono_vbas.get()

                if speed > vmax:
                    new_time = round(abs(th_stop-th_start)/vmax + 0.01, 2)
                    self.flyScanTime.setValue(new_time)
                    speed = round(abs(th_stop-th_start)/new_time, 3)

                elif speed < vmin:
                    new_time = round(abs(th_stop-th_start)/vmin - 0.01, 2)
                    self.flyScanTime.setValue(new_time)
                    speed = round(abs(th_stop-th_start)/new_time, 3)

                _submit(self.flyMotorSpeed.setText, str(speed))
                _submit(self.flyEncoderStepSize.setText, str(enc_steps_per_point))
                _submit(self.flyNumOfPoints.setText, str(scan_total_counts))
        except Exception as e:
            print("Exception in FlyControlWidget.updateFlyInfo : {}".format(e))

if __name__ == '__main__':
    app = qt.QApplication(sys.argv)
    main = FlyControlWidget()
    main.show()
    sys.exit(app.exec_())
