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

from utils import addWidgets, addStretchWidget, addLabelWidgetWidget
from utils import addLabelWidget, addLabelWidgetUnit, addLabelWidgetVert
from utils import loadPV

from scan_utils import angle_to_energy

from Widgets import CounterRbvLabel
from Widgets import EpicsValueLabel, EpicsStringLabel

class StatusWidget(qt.QMainWindow):
    """Scan status display widget"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.pv = loadPV()

        bigBoldFont = qt.QFont()
        bigBoldFont.setPointSize(9)
        bigBoldFont.setBold(True)

        self.engineLabel = qt.QLabel("State : ")
        self.engineLabel.setMinimumHeight(50)
        self.engineLabel.setMaximumHeight(50)

        self.engineStatus = qt.QLabel("EngineStatus")
        self.engineStatus.setFrameShape(qt.QFrame.Box)
        self.engineStatus.setFrameShadow(qt.QFrame.Sunken)
        self.engineStatus.setAlignment(qt.Qt.AlignCenter)
        self.engineStatus.setMinimumSize(qt.QSize(150, 50))
        self.engineStatus.setMaximumSize(qt.QSize(150, 50))

        self.abortButton = qt.QPushButton(self)
        self.abortButton.setText("Scan Abort")
        self.abortButton.setMinimumSize(qt.QSize(130, 50))
        self.abortButton.setMaximumSize(qt.QSize(115, 50))

        # high limit for scaler counts
        limit_hi = 900000

        self.I0_rbv = CounterRbvLabel(pv=self.pv['Scaler']['I0_counter_cal'],
                                      scaler_pv=self.pv['Scaler']['scaler'],
                                      limit_hi=limit_hi)

        self.It_rbv = CounterRbvLabel(pv=self.pv['Scaler']['It_counter_cal'],
                                      scaler_pv=self.pv['Scaler']['scaler'],
                                      limit_hi=limit_hi)

        self.If_rbv = CounterRbvLabel(pv=self.pv['Scaler']['If_counter_cal'],
                                      scaler_pv=self.pv['Scaler']['scaler'],
                                      limit_hi=limit_hi)

        self.Ir_rbv = CounterRbvLabel(pv=self.pv['Scaler']['Ir_counter_cal'],
                                      scaler_pv=self.pv['Scaler']['scaler'],
                                      limit_hi=limit_hi)

        self.theta_angle_label = EpicsValueLabel(self.pv['DCM']['mono_theta'] + '.RBV',
                                                 moving_pv=self.pv['DCM']['mono_theta_dmov'])
        self.theta_angle_label.setMinimumSize(qt.QSize(130, 30))
        self.theta_angle_label.setMaximumSize(qt.QSize(130, 30))

        self.theta_energy_label = EpicsValueLabel(self.pv['DCM']['mono_theta'] + '.RBV',
                                                  moving_pv=self.pv['DCM']['mono_theta_dmov'],
                                                  convert=angle_to_energy)

        self.theta_energy_label.setMinimumSize(qt.QSize(130, 30))
        self.theta_energy_label.setMaximumSize(qt.QSize(130, 30))

        self.life_time_label = EpicsValueLabel(self.pv['Beam']['LifeTime'],
                                               precision=2,
                                               convert=lambda x: x/3600.)
        self.life_time_label.setMinimumSize(qt.QSize(100, 30))
        self.life_time_label.setFrameShape(qt.QFrame.Panel)
        self.life_time_label.setFrameShadow(qt.QFrame.Sunken)
        self.life_time_label.setAlignment(qt.Qt.AlignCenter)

        self.topup_label = EpicsValueLabel(self.pv['Beam']['TopUpCount'],
                                           precision=2)
        self.topup_label.setMinimumSize(qt.QSize(100, 30))
        self.topup_label.setFrameShape(qt.QFrame.Panel)
        self.topup_label.setFrameShadow(qt.QFrame.Sunken)
        self.topup_label.setAlignment(qt.Qt.AlignCenter)

        self.beam_current_label = EpicsValueLabel(self.pv['Beam']['Current'],
                                                  precision=2)
        self.beam_current_label.setMinimumSize(qt.QSize(100, 30))
        self.beam_current_label.setMaximumSize(qt.QSize(100, 30))
        self.beam_current_label.setFrameShape(qt.QFrame.Panel)
        self.beam_current_label.setFrameShadow(qt.QFrame.Sunken)
        self.beam_current_label.setAlignment(qt.Qt.AlignCenter)

        self.num_of_steps_label = qt.QLabel("not conn.")
        self.num_of_steps_label.setMinimumSize(qt.QSize(100, 30))
        self.num_of_steps_label.setMaximumSize(qt.QSize(100, 30))
        self.num_of_steps_label.setFrameShape(qt.QFrame.Panel)
        self.num_of_steps_label.setFrameShadow(qt.QFrame.Sunken)
        self.num_of_steps_label.setAlignment(qt.Qt.AlignCenter)

        self.scan_point_label = qt.QLabel("not conn.")
        self.scan_point_label.setMinimumSize(qt.QSize(90, 30))
        self.scan_point_label.setMaximumSize(qt.QSize(90, 30))
        self.scan_point_label.setFrameShape(qt.QFrame.Panel)
        self.scan_point_label.setFrameShadow(qt.QFrame.Sunken)
        self.scan_point_label.setAlignment(qt.Qt.AlignCenter)

        self.scanInfoLoopTimeLabel = qt.QLabel('LoopTime : ')

        self.loop_time_label = qt.QLabel("not conn.")
        self.loop_time_label.setMinimumSize(qt.QSize(90, 30))
        self.loop_time_label.setMaximumSize(qt.QSize(90, 30))
        self.loop_time_label.setFrameShape(qt.QFrame.Panel)
        self.loop_time_label.setFrameShadow(qt.QFrame.Sunken)
        self.loop_time_label.setAlignment(qt.Qt.AlignCenter)

        self.num_of_history_spin_box = qt.QDoubleSpinBox(self)
        self.num_of_history_spin_box.setMinimumSize(qt.QSize(220, 30))
        self.num_of_history_spin_box.setMaximumSize(qt.QSize(220, 30))
        self.num_of_history_spin_box.setAlignment(qt.Qt.AlignCenter)
        self.num_of_history_spin_box.setDecimals(0)
        self.num_of_history_spin_box.setMinimum(1.0)
        self.num_of_history_spin_box.setMaximum(10.0)
        self.num_of_history_spin_box.setSingleStep(1.0)
        self.num_of_history_spin_box.setProperty("value", 1.0)

        self.x_axis_type_combo_box = qt.QComboBox(self)
        self.x_axis_type_combo_box.setMinimumSize(qt.QSize(220, 30))
        self.x_axis_type_combo_box.setMaximumSize(qt.QSize(220, 30))
        self.x_axis_type_combo_box.addItem("")
        self.x_axis_type_combo_box.addItem("")
        self.x_axis_type_combo_box.setItemText(0, "Delta(E-E0)")
        self.x_axis_type_combo_box.setItemText(1, "Energy(eV)")

        self.y_axis_type_combo_box = qt.QComboBox(self)
        self.y_axis_type_combo_box.setMinimumSize(qt.QSize(130, 30))
        self.y_axis_type_combo_box.setMaximumSize(qt.QSize(130, 30))
        self.y_axis_type_combo_box.addItem("")
        self.y_axis_type_combo_box.addItem("")
        self.y_axis_type_combo_box.addItem("")
        self.y_axis_type_combo_box.addItem("")
        self.y_axis_type_combo_box.addItem("")
        self.y_axis_type_combo_box.addItem("")
        self.y_axis_type_combo_box.addItem("")
        self.y_axis_type_combo_box.setItemText(0, "Transmittance")
        self.y_axis_type_combo_box.setItemText(1, "Fluorescence")
        self.y_axis_type_combo_box.setItemText(2, "Reference")
        self.y_axis_type_combo_box.setItemText(3, "View I0(1) Only")
        self.y_axis_type_combo_box.setItemText(4, "View IT(2) Only")
        self.y_axis_type_combo_box.setItemText(5, "View IF(3) Only")
        self.y_axis_type_combo_box.setItemText(6, "View IR(4) Only")

        self.derivativeCB = qt.QCheckBox(self)
        self.derivativeCB.setText('deriv.')

        main_panel = qt.QWidget(self)
        main_panel.setLayout(qt.QHBoxLayout())
        self.setCentralWidget(main_panel)

        REWidget = qt.QWidget(self)
        REWidget.setLayout(qt.QFormLayout())
        REWidget.layout().setLabelAlignment(qt.Qt.AlignRight)
        REWidget.layout().setFormAlignment(qt.Qt.AlignBottom)
        REWidget.layout().setContentsMargins(0, 0, 0, 0)
        REWidget.layout().addWidget(self.engineStatus)
        REWidget.layout().addWidget(self.abortButton)

        REWidget.layout().addRow(self.engineLabel, addWidgets([self.engineStatus,
                                                               self.abortButton]))

        counterGB = qt.QGroupBox("Counters", main_panel)
        counterGB.setLayout(qt.QHBoxLayout())
        counterGB.layout().setSpacing(20)
        counterGB.layout().addWidget(addLabelWidgetVert('I0', self.I0_rbv))
        counterGB.layout().addWidget(addLabelWidgetVert('It', self.It_rbv))
        counterGB.layout().addWidget(addLabelWidgetVert('Ir', self.Ir_rbv))
        counterGB.layout().addWidget(addLabelWidgetVert('If', self.If_rbv))

        dcmGB = qt.QGroupBox("Monochromator", main_panel)
        dcmGB.setLayout(qt.QFormLayout())
        dcmGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        dcmGB.layout().addRow('Angle [Deg.] : ', self.theta_angle_label)
        dcmGB.layout().addRow('Energy [eV]: ', self.theta_energy_label)

        beamGB = qt.QGroupBox("Beam", main_panel)
        beamGB.setLayout(qt.QFormLayout())
        beamGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        beamGB.layout().addRow('Life Time [hours] : ', self.life_time_label)
        beamGB.layout().addRow('TopUp Count [sec.] : ', self.topup_label)
        beamGB.layout().addRow('Current [mA] : ', self.beam_current_label)

        scanInfoGB = qt.QGroupBox("Scan Info", main_panel)
        scanInfoGB.setLayout(qt.QFormLayout())
        scanInfoGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        scanInfoGB.layout().addRow('NoOfSteps : ', self.num_of_steps_label)
        scanInfoGB.layout().addRow('ScanPoint : ', self.scan_point_label)
        scanInfoGB.layout().addRow(self.scanInfoLoopTimeLabel, self.loop_time_label)

        plotControlGB = qt.QGroupBox("Plot Control", main_panel)
        plotControlGB.setLayout(qt.QFormLayout())
        plotControlGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        plotControlGB.layout().addRow('# Of History : ', self.num_of_history_spin_box)
        plotControlGB.layout().addRow('X-axis type : ', self.x_axis_type_combo_box)
        plotControlGB.layout().addRow('Y-axis type : ',
                                      addWidgets([self.y_axis_type_combo_box, self.derivativeCB]))

        main_panel.layout().addWidget(addStretchWidget(REWidget))
        main_panel.layout().addStretch(1)
        main_panel.layout().addWidget(addStretchWidget(dcmGB))
        main_panel.layout().addWidget(addStretchWidget(counterGB))
        main_panel.layout().addWidget(addStretchWidget(beamGB))
        main_panel.layout().addWidget(addStretchWidget(scanInfoGB))
        main_panel.layout().addWidget(addStretchWidget(plotControlGB))


if __name__ == '__main__':
    font=qt.QFont()
    font.setFamily('DejaVu Sans')
    font.setPointSize(10)

    app = qt.QApplication(sys.argv)
    app.setFont(font)

    main = StatusWidget()
    main.show()
    sys.exit(app.exec_())
