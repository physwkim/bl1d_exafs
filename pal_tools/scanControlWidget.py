__author__ = "Sang-Woo Kim, Pohang Accelerator Laboratory"
__contact__ = "physwkim@postech.ac.kr"
__license__ = "MIT"
__copyright__ = "Pohang Accelerator Laboratory, Pohang, South Korea"


import sys

from silx.gui import qt
from utils import path, loadJson, loadPV, loadDefault, getDefault
from utils import addWidgets, addStretchWidget, addLabelWidgetWidget
from utils import addLabelWidget, addLabelWidgetUnit, addLabelWidgetVert


from FlyControlWidget import FlyControlWidget

from Widgets import GainRbvLabel, GainComboBox, DarkCurrentRbvLabel, RiseTimeComboBox
from Widgets import TweakDoubleSpinBox, EpicsValueLabel, ComboBoxAligned
from Widgets import ScrollBarTwoValue
from Widgets import EpicsDoubleSpinBox
from Widgets import DoubleSpinBoxWithSignal
from Widgets import ZeroCheckRbvLabel


class ScanControlWidget(qt.QMainWindow):
    """Scan Control Widget"""

    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.pv_names = loadPV()
        self.create_widgets()
        self.layout_widgets()
        self.load_elements()

        # load settings
        self.loadSettings()

        # default button behavior
        # self.defaultBtn.clicked.connect(self.setDefaultSettings)

    def setDefaultSettings(self):
        """ load default settings and set"""
        try:
            default = loadDefault()
            self.SRB_1.setValue(float(getDefault(default, "SRB_1")))
            self.SRB_2.setValue(float(getDefault(default, "SRB_2")))
            self.SRB_3.setValue(float(getDefault(default, "SRB_3")))
            self.SRB_4.setValue(float(getDefault(default, "SRB_4")))
            self.SRB_5.setValue(float(getDefault(default, "SRB_5")))
            self.SRB_6.setValue(float(getDefault(default, "SRB_6")))
            # self.SRB_7.setValue(float(getDefault(default, "SRB_7")))

            self.eMode_bar_1.setValue(int(getDefault(default, "EMODE_1")))
            self.eMode_bar_2.setValue(int(getDefault(default, "EMODE_2")))
            self.eMode_bar_3.setValue(int(getDefault(default, "EMODE_3")))
            self.eMode_bar_4.setValue(int(getDefault(default, "EMODE_4")))
            self.eMode_bar_5.setValue(int(getDefault(default, "EMODE_5")))
            self.eMode_bar_6.setValue(int(getDefault(default, "EMODE_6")))
            # self.eMode_bar_7.setValue(int(getDefault(default, "EMODE_7")))

            self.stepSize_1.setValue(float(getDefault(default, "StepSize_1")))
            self.stepSize_2.setValue(float(getDefault(default, "StepSize_2")))
            self.stepSize_3.setValue(float(getDefault(default, "StepSize_3")))
            self.stepSize_4.setValue(float(getDefault(default, "StepSize_4")))
            self.stepSize_5.setValue(float(getDefault(default, "StepSize_5")))
            # self.stepSize_6.setValue(float(getDefault(default, "StepSize_6")))
        except:
            pass

    def loadSettings(self):
        """ Load previous settings """
        qsettings = qt.QSettings('settings.ini', qt.QSettings.IniFormat)

        try:
            self.comboBox_element.setCurrentIndex(int(qsettings.value("comboBox_element")))
            self.comboBox_edge.setCurrentIndex(int(qsettings.value("comboBox_edge")))

            self.ecal_comboBox_element.setCurrentIndex(int(qsettings.value("comboBox_element")))
            self.ecal_comboBox_edge.setCurrentIndex(int(qsettings.value("comboBox_edge")))

            self.setDefaultSettings()

        except:
            pass

    def saveSettings(self):
        """ Save current settings """
        qsettings = qt.QSettings('settings.ini', qt.QSettings.IniFormat)

        qsettings.setValue("comboBox_element", self.comboBox_element.currentIndex())
        qsettings.setValue("comboBox_edge", self.comboBox_edge.currentIndex())


    def load_elements(self):
        # Element and energy selection widget
        self.elements_data = loadJson('edges_lines.json')

        self.comboBox_element.currentIndexChanged.connect(self.update_combo_edge)
        self.comboBox_edge.currentIndexChanged.connect(self.update_e0_value)

        self.ecal_comboBox_element.currentIndexChanged.connect(self.update_combo_edge2)
        self.ecal_comboBox_edge.currentIndexChanged.connect(self.update_e0_value2)

        elems = [item['name'] for item in self.elements_data]

        for i in range(21, 96):
            elems[i - 21] = '{} ({:3d})'.format(elems[i - 21], i)

        self.comboBox_element.addItems(elems)
        self.ecal_comboBox_element.addItems(elems)

        self.comboBox_element.setCurrentIndex(7)
        self.ecal_comboBox_element.setCurrentIndex(7)

    def update_combo_edge(self, index):
        # connect with ecal-panel
        currentIndex = self.comboBox_element.currentIndex()
        if self.ecal_comboBox_element.currentIndex() != currentIndex:
            self.ecal_comboBox_element.setCurrentIndex(currentIndex)

        self.comboBox_edge.clear()
        edges = [key for key in list(self.elements_data[index].keys())\
                  if key != 'name' and key != 'symbol']
        edges.sort()
        self.comboBox_edge.addItems(edges)


    def update_e0_value(self):
        try:
            if self.comboBox_edge.count() > 0:
                # connect with ecal edge
                currentIndex = self.comboBox_edge.currentIndex()
                if self.ecal_comboBox_edge.count() > 0:
                    if self.ecal_comboBox_edge.currentIndex() != currentIndex:
                        self.ecal_comboBox_edge.setCurrentIndex(currentIndex)

                val = float(self.elements_data[self.comboBox_element.currentIndex()][self.comboBox_edge.currentText()])
                self.edit_E0.setValue(val)
        except:
            pass


    def update_combo_edge2(self, index):
        currentIndex = self.ecal_comboBox_element.currentIndex()
        if self.comboBox_element.currentIndex() != currentIndex:
            self.comboBox_element.setCurrentIndex(currentIndex)

        self.ecal_comboBox_edge.clear()
        edges = [key for key in list(self.elements_data[index].keys())\
                  if key != 'name' and key != 'symbol']
        edges.sort()
        self.ecal_comboBox_edge.addItems(edges)

    def update_e0_value2(self):
        try:
            if self.ecal_comboBox_edge.count() > 0:
                # connect with measure-pannel edge
                currentIndex = self.ecal_comboBox_edge.currentIndex()
                if self.comboBox_edge.count() > 0:
                    if self.comboBox_edge.currentIndex() != currentIndex:
                        self.comboBox_edge.setCurrentIndex(currentIndex)

                self.ecal_edit_E0.setValue(
                    float(
                        self.elements_data[
                            self.ecal_comboBox_element.currentIndex()]\
                                          [self.ecal_comboBox_edge.currentText()]))
        except:
            pass

    def create_widgets(self):
        """Create Widgets"""

        bigBoldFont = qt.QFont()
        bigBoldFont.setPointSize(10)
        bigBoldFont.setBold(True)

        boldFont = qt.QFont()
        boldFont.setBold(True)

        self.main_panel = qt.QWidget(self)
        self.main_panel.setLayout(qt.QVBoxLayout())
        self.setCentralWidget(self.main_panel)

        # Energy Scan Tab
        self.energyScanWidget = qt.QWidget(self.main_panel)
        self.energyScanWidget.setLayout(qt.QVBoxLayout())

        # Energy Calibration Tab
        self.energyCalibWidget = qt.QWidget(self.main_panel)
        self.energyCalibWidget.setLayout(qt.QVBoxLayout())

        # Slit Control Tab
        self.slitControlWidget = qt.QWidget(self.main_panel)
        self.slitControlWidget.setLayout(qt.QVBoxLayout())

        # DCM Tab
        self.dcmWidget = qt.QWidget(self.main_panel)
        self.dcmWidget.setLayout(qt.QVBoxLayout())

        # Main Tab Widget
        self.tabWidget = qt.QTabWidget(self.main_panel)
        self.tabWidget.addTab(self.energyScanWidget,  "Energy Scan")
        self.tabWidget.addTab(self.energyCalibWidget, "Energy Calibration")
        self.tabWidget.addTab(self.slitControlWidget, "Slit Control")
        self.tabWidget.addTab(self.dcmWidget,         "DCM")
        self.main_panel.layout().addWidget(self.tabWidget)

        _controlWidth = 130

        self.comboBox_element = ComboBoxAligned(self)
        self.comboBox_element.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.comboBox_element.setMaximumSize(qt.QSize(_controlWidth, 30))

        self.comboBox_edge = ComboBoxAligned(self)
        self.comboBox_edge.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.comboBox_edge.setMaximumSize(qt.QSize(_controlWidth, 30))

        self.edit_E0 = qt.QDoubleSpinBox(self)
        self.edit_E0.setAlignment(qt.Qt.AlignCenter)
        self.edit_E0.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.edit_E0.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.edit_E0.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.edit_E0.setDecimals(2)
        self.edit_E0.setMaximum(9999999.99)
        self.edit_E0.setSingleStep(0.01)
        self.edit_E0.setProperty("value", 7112.0)

        self.E0_Angle_label = qt.QLabel(self)
        self.E0_Angle_label.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.E0_Angle_label.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.E0_Angle_label.setFrameShape(qt.QFrame.Panel)
        self.E0_Angle_label.setFrameShadow(qt.QFrame.Sunken)
        self.E0_Angle_label.setAlignment(qt.Qt.AlignCenter)
        self.E0_Angle_label.setText("16.140547")
        self.E0_Angle_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.comboBox_Si_mode = ComboBoxAligned(self)
        self.comboBox_Si_mode.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.comboBox_Si_mode.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.comboBox_Si_mode.addItem("")
        self.comboBox_Si_mode.setItemText(0, "Si(111)")

        self.E0_offset = EpicsValueLabel(self.pv_names['DCM']['mono_offset'], precision=6)
        self.E0_offset.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.E0_offset.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.E0_offset.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.ecal_E0_offset = EpicsValueLabel(self.pv_names['DCM']['mono_offset'], precision=6)
        self.ecal_E0_offset.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.ecal_E0_offset.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.ecal_E0_offset.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.move_to_E0 = qt.QPushButton(self)
        self.move_to_E0.setMinimumSize(qt.QSize(100, 40))
        self.move_to_E0.setMaximumSize(qt.QSize(100, 40))
        self.move_to_E0.setText("MoveE")
        self.move_to_E0.setFont(bigBoldFont)

        self.stop_E0_button = qt.QPushButton(self)
        self.stop_E0_button.setMinimumSize(qt.QSize(100, 40))
        self.stop_E0_button.setMaximumSize(qt.QSize(100, 40))
        self.stop_E0_button.setText("Stop")
        self.stop_E0_button.setFont(bigBoldFont)

        self.testEnergyLineEdit = DoubleSpinBoxWithSignal(self)
        self.testEnergyLineEdit.setMinimumSize(qt.QSize(130, 30))
        self.testEnergyLineEdit.setMaximumSize(qt.QSize(130, 30))
        self.testEnergyLineEdit.setDecimals(2)
        self.testEnergyLineEdit.setMaximum(2000)
        self.testEnergyLineEdit.setMinimum(-2000)
        self.testEnergyLineEdit.setSingleStep(1)
        self.testEnergyLineEdit.setValue(0)

        self.edit_delay_time = qt.QDoubleSpinBox(self)
        self.edit_delay_time.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.edit_delay_time.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.edit_delay_time.setAlignment(qt.Qt.AlignCenter)
        self.edit_delay_time.setDecimals(0)
        self.edit_delay_time.setMaximum(10000000.0)
        self.edit_delay_time.setSingleStep(0.01)
        self.edit_delay_time.setProperty("value", 1000.0)

        self.run_type = ComboBoxAligned(self)
        self.run_type.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.run_type.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.run_type.addItem("")
        self.run_type.addItem("")
        self.run_type.addItem("")
        self.run_type.setItemText(0, "Single Scan")
        self.run_type.setItemText(1, "Multi Scan")
        self.run_type.setItemText(2, "Fly Scan")

        self.use_batch_checkbox = qt.QCheckBox(self)
        self.use_batch_checkbox.setMinimumHeight(30)
        self.use_batch_checkbox.setMaximumHeight(30)
        self.use_batch_checkbox.setText('Batch Scan')
        self.use_batch_checkbox.setDisabled(True)

        self.number_of_scan_edit = qt.QDoubleSpinBox(self)
        self.number_of_scan_edit.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.number_of_scan_edit.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.number_of_scan_edit.setAlignment(qt.Qt.AlignCenter)
        self.number_of_scan_edit.setDecimals(0)
        self.number_of_scan_edit.setMinimum(1.0)
        self.number_of_scan_edit.setMaximum(9999999.0)
        self.number_of_scan_edit.setSingleStep(1.0)
        self.number_of_scan_edit.setProperty("value", 1.0)

        self.stackedWidget = qt.QStackedWidget(self)
        self.stackedWidget.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Expanding)
        self.flyControl = FlyControlWidget(self)

        # self.defaultBtn = qt.QPushButton(self)
        # self.defaultBtn.setText('Default')

        self.SRB_1 = qt.QDoubleSpinBox(self)
        self.SRB_1.setMinimumSize(qt.QSize(100, 30))
        self.SRB_1.setMaximumSize(qt.QSize(100, 30))
        self.SRB_1.setAlignment(qt.Qt.AlignCenter)
        self.SRB_1.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_1.setMinimum(-999999.0)
        self.SRB_1.setMaximum(9999999.99)
        self.SRB_1.setSingleStep(0.01)
        self.SRB_1.setProperty("value", -200.0)

        self.SRB_2 = qt.QDoubleSpinBox(self)
        self.SRB_2.setMinimumSize(qt.QSize(100, 30))
        self.SRB_2.setMaximumSize(qt.QSize(100, 30))
        self.SRB_2.setAlignment(qt.Qt.AlignCenter)
        self.SRB_2.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_2.setMinimum(-999999.0)
        self.SRB_2.setMaximum(9999999.99)
        self.SRB_2.setSingleStep(0.01)
        self.SRB_2.setProperty("value", -50.0)

        self.SRB_3 = qt.QDoubleSpinBox(self)
        self.SRB_3.setMinimumSize(qt.QSize(100, 30))
        self.SRB_3.setMaximumSize(qt.QSize(100, 30))
        self.SRB_3.setAlignment(qt.Qt.AlignCenter)
        self.SRB_3.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_3.setMinimum(-999999.0)
        self.SRB_3.setMaximum(9999999.99)
        self.SRB_3.setSingleStep(0.01)
        self.SRB_3.setProperty("value", -20.0)

        self.SRB_4 = qt.QDoubleSpinBox(self)
        self.SRB_4.setMinimumSize(qt.QSize(100, 30))
        self.SRB_4.setMaximumSize(qt.QSize(100, 30))
        self.SRB_4.setAlignment(qt.Qt.AlignCenter)
        self.SRB_4.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_4.setMinimum(-999999.0)
        self.SRB_4.setMaximum(9999999.99)
        self.SRB_4.setSingleStep(0.01)
        self.SRB_4.setProperty("value", 40.0)

        self.SRB_5 = qt.QDoubleSpinBox(self)
        self.SRB_5.setMinimumSize(qt.QSize(100, 30))
        self.SRB_5.setMaximumSize(qt.QSize(100, 30))
        self.SRB_5.setAlignment(qt.Qt.AlignCenter)
        self.SRB_5.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_5.setMinimum(-999999.0)
        self.SRB_5.setMaximum(9999999.99)
        self.SRB_5.setSingleStep(0.01)
        self.SRB_5.setProperty("value", 12.0)

        self.SRB_6 = qt.QDoubleSpinBox(self)
        self.SRB_6.setMinimumSize(qt.QSize(100, 30))
        self.SRB_6.setMaximumSize(qt.QSize(100, 30))
        self.SRB_6.setAlignment(qt.Qt.AlignCenter)
        self.SRB_6.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_6.setMinimum(-999999.0)
        self.SRB_6.setMaximum(9999999.99)
        self.SRB_6.setSingleStep(0.01)
        self.SRB_6.setProperty("value", 16.0)

        sbarWidth = 90
        self.eMode_bar_1 = ScrollBarTwoValue(sbarWidth, parent=self)
        self.eMode_bar_2 = ScrollBarTwoValue(sbarWidth, parent=self)
        self.eMode_bar_3 = ScrollBarTwoValue(sbarWidth, parent=self)
        self.eMode_bar_4 = ScrollBarTwoValue(sbarWidth, parent=self)
        self.eMode_bar_5 = ScrollBarTwoValue(sbarWidth, parent=self)
        self.eMode_bar_5.setValue(1000)
        self.eMode_bar_6 = ScrollBarTwoValue(sbarWidth, parent=self)
        self.eMode_bar_6.setValue(1000)

        self.stepSize_1 = qt.QDoubleSpinBox(self)
        self.stepSize_1.setMinimumSize(qt.QSize(80, 30))
        self.stepSize_1.setMaximumSize(qt.QSize(80, 30))
        self.stepSize_1.setAlignment(qt.Qt.AlignCenter)
        self.stepSize_1.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.stepSize_1.setDecimals(3)
        self.stepSize_1.setMaximum(9999999.99)
        self.stepSize_1.setSingleStep(0.001)
        self.stepSize_1.setProperty("value", 5.0)

        self.stepSize_2 = qt.QDoubleSpinBox(self)
        self.stepSize_2.setMinimumSize(qt.QSize(80, 30))
        self.stepSize_2.setMaximumSize(qt.QSize(80, 90))
        self.stepSize_2.setAlignment(qt.Qt.AlignCenter)
        self.stepSize_2.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.stepSize_2.setDecimals(3)
        self.stepSize_2.setMaximum(9999999.99)
        self.stepSize_2.setSingleStep(0.001)
        self.stepSize_2.setProperty("value", 1.0)

        self.stepSize_3 = qt.QDoubleSpinBox(self)
        self.stepSize_3.setMinimumSize(qt.QSize(80, 30))
        self.stepSize_3.setMaximumSize(qt.QSize(80, 30))
        self.stepSize_3.setAlignment(qt.Qt.AlignCenter)
        self.stepSize_3.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.stepSize_3.setDecimals(3)
        self.stepSize_3.setMaximum(9999999.99)
        self.stepSize_3.setSingleStep(0.001)
        self.stepSize_3.setProperty("value", 0.4)

        self.stepSize_4 = qt.QDoubleSpinBox(self)
        self.stepSize_4.setMinimumSize(qt.QSize(80, 30))
        self.stepSize_4.setMaximumSize(qt.QSize(80, 30))
        self.stepSize_4.setAlignment(qt.Qt.AlignCenter)
        self.stepSize_4.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.stepSize_4.setDecimals(3)
        self.stepSize_4.setMaximum(9999999.99)
        self.stepSize_4.setSingleStep(0.001)
        self.stepSize_4.setProperty("value", 0.03)

        self.stepSize_5 = qt.QDoubleSpinBox(self)
        self.stepSize_5.setMinimumSize(qt.QSize(80, 30))
        self.stepSize_5.setMaximumSize(qt.QSize(80, 30))
        self.stepSize_5.setAlignment(qt.Qt.AlignCenter)
        self.stepSize_5.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.stepSize_5.setDecimals(3)
        self.stepSize_5.setMaximum(9999999.99)
        self.stepSize_5.setSingleStep(0.001)
        self.stepSize_5.setProperty("value", 0.05)

        self.SRBOnOff_1 = qt.QCheckBox(self)
        self.SRBOnOff_1.setMinimumHeight(30)
        self.SRBOnOff_1.setChecked(True)
        self.SRBOnOff_1.setText("Use")

        self.SRBOnOff_2 = qt.QCheckBox(self)
        self.SRBOnOff_2.setMinimumHeight(30)
        self.SRBOnOff_2.setChecked(True)
        self.SRBOnOff_2.setText("Use")

        self.SRBOnOff_3 = qt.QCheckBox(self)
        self.SRBOnOff_3.setMinimumHeight(30)
        self.SRBOnOff_3.setChecked(True)
        self.SRBOnOff_3.setText("Use")

        self.SRBOnOff_4 = qt.QCheckBox(self)
        self.SRBOnOff_4.setMinimumHeight(30)
        self.SRBOnOff_4.setChecked(True)
        self.SRBOnOff_4.setText("Use")

        self.SRBOnOff_5 = qt.QCheckBox(self)
        self.SRBOnOff_5.setMinimumHeight(30)
        self.SRBOnOff_5.setChecked(True)
        self.SRBOnOff_5.setText("Use")

        self.SRB_time_1 = qt.QDoubleSpinBox(self)
        self.SRB_time_1.setMinimumSize(qt.QSize(60, 30))
        self.SRB_time_1.setMaximumSize(qt.QSize(60, 30))
        self.SRB_time_1.setAlignment(qt.Qt.AlignCenter)
        self.SRB_time_1.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_time_1.setDecimals(1)
        self.SRB_time_1.setMaximum(10000000.0)
        self.SRB_time_1.setSingleStep(0.1)
        self.SRB_time_1.setProperty("value", 1.0)

        self.SRB_time_2 = qt.QDoubleSpinBox(self)
        self.SRB_time_2.setMinimumSize(qt.QSize(60, 30))
        self.SRB_time_2.setMaximumSize(qt.QSize(60, 30))
        self.SRB_time_2.setAlignment(qt.Qt.AlignCenter)
        self.SRB_time_2.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_time_2.setDecimals(1)
        self.SRB_time_2.setMaximum(10000000.0)
        self.SRB_time_2.setSingleStep(0.1)
        self.SRB_time_2.setProperty("value", 1.0)

        self.SRB_time_3 = qt.QDoubleSpinBox(self)
        self.SRB_time_3.setMinimumSize(qt.QSize(60, 30))
        self.SRB_time_3.setMaximumSize(qt.QSize(60, 30))
        self.SRB_time_3.setAlignment(qt.Qt.AlignCenter)
        self.SRB_time_3.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_time_3.setDecimals(1)
        self.SRB_time_3.setMaximum(10000000.0)
        self.SRB_time_3.setSingleStep(0.1)
        self.SRB_time_3.setProperty("value", 1.0)

        self.SRB_time_4 = qt.QDoubleSpinBox(self)
        self.SRB_time_4.setMinimumSize(qt.QSize(60, 30))
        self.SRB_time_4.setMaximumSize(qt.QSize(60, 30))
        self.SRB_time_4.setAlignment(qt.Qt.AlignCenter)
        self.SRB_time_4.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_time_4.setDecimals(1)
        self.SRB_time_4.setMaximum(10000000.0)
        self.SRB_time_4.setSingleStep(0.1)
        self.SRB_time_4.setProperty("value", 1.0)

        self.SRB_time_5 = qt.QDoubleSpinBox(self)
        self.SRB_time_5.setMinimumSize(qt.QSize(60, 30))
        self.SRB_time_5.setMaximumSize(qt.QSize(60, 30))
        self.SRB_time_5.setAlignment(qt.Qt.AlignCenter)
        self.SRB_time_5.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.SRB_time_5.setDecimals(1)
        self.SRB_time_5.setMaximum(10000000.0)
        self.SRB_time_5.setSingleStep(0.1)
        self.SRB_time_5.setProperty("value", 1.0)

        self.gain_I0 = GainComboBox(self.pv_names['Amplifier']['I0_gain_set'],
                                    read_pv=self.pv_names['Amplifier']['I0_gain_get'],
                                    suppression=True)
        self.gain_It = GainComboBox(self.pv_names['Amplifier']['It_gain_set'],
                                    read_pv=self.pv_names['Amplifier']['It_gain_get'],
                                    suppression=True)
        self.gain_If = GainComboBox(self.pv_names['Amplifier']['If_gain_set'],
                                    read_pv=self.pv_names['Amplifier']['If_gain_get'],
                                    suppression=True)
        self.gain_Ir = GainComboBox(self.pv_names['Amplifier']['Ir_gain_set'],
                                    read_pv=self.pv_names['Amplifier']['Ir_gain_get'],
                                    suppression=True)

        self.riseTime = RiseTimeComboBox([self.pv_names['Amplifier']['I0_rise_time_set'],
                                          self.pv_names['Amplifier']['It_rise_time_set'],
                                          self.pv_names['Amplifier']['If_rise_time_set'],
                                          self.pv_names['Amplifier']['Ir_rise_time_set']],
                                         read_pv=self.pv_names['Amplifier']['I0_rise_time_get'])

        self.zeroCheck_rbv = ZeroCheckRbvLabel(self.pv_names['Amplifier']['I0_zero_check_get'])
        self.zeroCheck_rbv.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.zeroCheckButton = qt.QPushButton(self)
        self.zeroCheckButton.setMinimumSize(qt.QSize(100, 30))
        self.zeroCheckButton.setMaximumSize(qt.QSize(100, 30))
        self.zeroCheckButton.setText("Toggle")

        self.I0_dark_current = DarkCurrentRbvLabel(self)
        self.It_dark_current = DarkCurrentRbvLabel(self)
        self.If_dark_current = DarkCurrentRbvLabel(self)
        self.Ir_dark_current = DarkCurrentRbvLabel(self)

        self.data_save_path = qt.QTextBrowser(self)
        self.data_save_path.setMinimumSize(qt.QSize(400, 0))
        self.data_save_path.setMaximumSize(qt.QSize(16777215, 30))

        self.push_select_path = qt.QPushButton(self)
        self.push_select_path.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.push_select_path.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.push_select_path.setText("Select Path")

        self.description_edit = qt.QTextEdit(self)
        self.description_edit.setMaximumSize(qt.QSize(16777215, 70))

        self.filename_edit = qt.QLineEdit(self)
        self.filename_edit.setMinimumSize(qt.QSize(0, 30))
        self.filename_edit.setMaximumSize(qt.QSize(16777215, 30))
        self.filename_edit.setText("YourFileName")

        self.saved_path_label = qt.QLabel(self)
        self.saved_path_label.setMinimumSize(qt.QSize(0, 30))
        self.saved_path_label.setMaximumSize(qt.QSize(16777215, 30))
        self.saved_path_label.setFrameShape(qt.QFrame.Panel)
        self.saved_path_label.setFrameShadow(qt.QFrame.Sunken)
        self.saved_path_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.run_start = qt.QPushButton(self)
        self.run_start.setMinimumSize(qt.QSize(130, 50))
        self.run_start.setMaximumSize(qt.QSize(130, 50))
        self.run_start.setText("Run")
        self.run_start.setFont(bigBoldFont)

        # self.resumeButton = qt.QPushButton(self)
        # self.resumeButton.setMinimumSize(qt.QSize(130, 50))
        # self.resumeButton.setMaximumSize(qt.QSize(130, 50))
        # self.resumeButton.setText("Resume")
        # self.resumeButton.setFont(bigBoldFont)

        self.abortButton = qt.QPushButton(self)
        self.abortButton.setMinimumSize(qt.QSize(130, 50))
        self.abortButton.setMaximumSize(qt.QSize(130, 50))
        self.abortButton.setText("Scan Abort")
        self.abortButton.setFont(bigBoldFont)

        # self.pauseButton = qt.QPushButton(self)
        # self.pauseButton.setMinimumSize(qt.QSize(130, 50))
        # self.pauseButton.setMaximumSize(qt.QSize(130, 50))
        # self.pauseButton.setText("Pause")
        # self.pauseButton.setFont(bigBoldFont)

        ############ Energy Calibration Tab  ##################################

        self.ecal_comboBox_element = ComboBoxAligned(self)
        self.ecal_comboBox_element.setMinimumSize(qt.QSize(120, 30))
        self.ecal_comboBox_element.setMaximumSize(qt.QSize(120, 30))

        self.ecal_comboBox_edge = ComboBoxAligned(self)
        self.ecal_comboBox_edge.setMinimumSize(qt.QSize(120, 30))
        self.ecal_comboBox_edge.setMaximumSize(qt.QSize(120, 30))

        self.ecal_edit_E0 = qt.QDoubleSpinBox(self)
        self.ecal_edit_E0.setAlignment(qt.Qt.AlignCenter)
        self.ecal_edit_E0.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.ecal_edit_E0.setMinimumSize(qt.QSize(120, 30))
        self.ecal_edit_E0.setMaximumSize(qt.QSize(120, 30))
        self.ecal_edit_E0.setDecimals(2)
        self.ecal_edit_E0.setMaximum(9999999.99)
        self.ecal_edit_E0.setSingleStep(0.01)
        self.ecal_edit_E0.setProperty("value", 7112.0)

        self.ecal_E0_Angle_label = qt.QLabel(self)
        self.ecal_E0_Angle_label.setMinimumSize(qt.QSize(120, 30))
        self.ecal_E0_Angle_label.setMaximumSize(qt.QSize(120, 30))
        self.ecal_E0_Angle_label.setFrameShape(qt.QFrame.Panel)
        self.ecal_E0_Angle_label.setFrameShadow(qt.QFrame.Sunken)
        self.ecal_E0_Angle_label.setAlignment(qt.Qt.AlignCenter)
        self.ecal_E0_Angle_label.setText("16.140547")

        self.ecal_move_to_E0 = qt.QPushButton(self)
        self.ecal_move_to_E0.setMinimumSize(qt.QSize(100, 40))
        self.ecal_move_to_E0.setMaximumSize(qt.QSize(100, 40))
        self.ecal_move_to_E0.setText("MoveE")
        self.ecal_move_to_E0.setFont(bigBoldFont)

        self.ecal_stop_E0_button = qt.QPushButton(self)
        self.ecal_stop_E0_button.setMinimumSize(qt.QSize(100, 40))
        self.ecal_stop_E0_button.setMaximumSize(qt.QSize(100, 40))
        self.ecal_stop_E0_button.setText("Stop")
        self.ecal_stop_E0_button.setFont(bigBoldFont)

        # self.ecal_It_mode_checkbox = qt.QCheckBox(self)
        # self.ecal_It_mode_checkbox.setMinimumSize(qt.QSize(53, 30))
        # self.ecal_It_mode_checkbox.setMaximumSize(qt.QSize(53, 30))
        # self.ecal_It_mode_checkbox.setChecked(True)
        # self.ecal_It_mode_checkbox.setText("IT")

        # self.ecal_Ir_mode_checkbox = qt.QCheckBox(self)
        # self.ecal_Ir_mode_checkbox.setMinimumSize(qt.QSize(53, 30))
        # self.ecal_Ir_mode_checkbox.setMaximumSize(qt.QSize(53, 30))
        # self.ecal_Ir_mode_checkbox.setChecked(False)
        # self.ecal_Ir_mode_checkbox.setText("IR")

        self.ecal_start_edit = qt.QDoubleSpinBox(self)
        self.ecal_start_edit.setMinimumSize(qt.QSize(110, 30))
        self.ecal_start_edit.setMaximumSize(qt.QSize(110, 30))
        self.ecal_start_edit.setAlignment(qt.Qt.AlignCenter)
        self.ecal_start_edit.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.ecal_start_edit.setDecimals(2)
        self.ecal_start_edit.setMinimum(-9999999.0)
        self.ecal_start_edit.setMaximum(9999999.99)
        self.ecal_start_edit.setSingleStep(0.01)
        self.ecal_start_edit.setProperty("value", -10.0)

        self.ecal_step_size_edit = qt.QDoubleSpinBox(self)
        self.ecal_step_size_edit.setMinimumSize(qt.QSize(110, 30))
        self.ecal_step_size_edit.setMaximumSize(qt.QSize(110, 30))
        self.ecal_step_size_edit.setAlignment(qt.Qt.AlignCenter)
        self.ecal_step_size_edit.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.ecal_step_size_edit.setDecimals(3)
        self.ecal_step_size_edit.setMinimum(-9999999.0)
        self.ecal_step_size_edit.setMaximum(9999999.99)
        self.ecal_step_size_edit.setSingleStep(0.001)
        self.ecal_step_size_edit.setProperty("value", 0.4)

        self.ecal_stop_edit = qt.QDoubleSpinBox(self)
        self.ecal_stop_edit.setMinimumSize(qt.QSize(110, 30))
        self.ecal_stop_edit.setMaximumSize(qt.QSize(110, 30))
        self.ecal_stop_edit.setAlignment(qt.Qt.AlignCenter)
        self.ecal_stop_edit.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.ecal_stop_edit.setDecimals(2)
        self.ecal_stop_edit.setMinimum(-9999999.0)
        self.ecal_stop_edit.setMaximum(9999999.99)
        self.ecal_stop_edit.setSingleStep(0.01)
        self.ecal_stop_edit.setProperty("value", 50.0)

        self.ecal_time_edit = qt.QDoubleSpinBox(self)
        self.ecal_time_edit.setMinimumSize(qt.QSize(110, 30))
        self.ecal_time_edit.setMaximumSize(qt.QSize(110, 30))
        self.ecal_time_edit.setAlignment(qt.Qt.AlignCenter)
        self.ecal_time_edit.setDecimals(1)
        self.ecal_time_edit.setMinimum(-9999999.0)
        self.ecal_time_edit.setMaximum(10000000.0)
        self.ecal_time_edit.setSingleStep(0.1)
        self.ecal_time_edit.setProperty("value", 1.0)

        self.ecal_gain_I0 = GainComboBox(self.pv_names['Amplifier']['I0_gain_set'],
                                         read_pv=self.pv_names['Amplifier']['I0_gain_get'],
                                         suppression=True)
        self.ecal_gain_It = GainComboBox(self.pv_names['Amplifier']['It_gain_set'],
                                         read_pv=self.pv_names['Amplifier']['It_gain_get'],
                                         suppression=True)
        self.ecal_gain_If = GainComboBox(self.pv_names['Amplifier']['If_gain_set'],
                                         read_pv=self.pv_names['Amplifier']['If_gain_get'],
                                         suppression=True)
        self.ecal_gain_Ir = GainComboBox(self.pv_names['Amplifier']['Ir_gain_set'],
                                         read_pv=self.pv_names['Amplifier']['Ir_gain_get'],
                                         suppression=True)

        self.ecal_peak_energy_label = qt.QLabel(self)
        self.ecal_peak_energy_label.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.ecal_peak_energy_label.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.ecal_peak_energy_label.setFrameShape(qt.QFrame.Panel)
        self.ecal_peak_energy_label.setFrameShadow(qt.QFrame.Sunken)
        self.ecal_peak_energy_label.setAlignment(qt.Qt.AlignCenter)
        self.ecal_peak_energy_label.setText("0")
        self.ecal_peak_energy_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.ecal_energy_difference_label = qt.QLabel(self)
        self.ecal_energy_difference_label.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.ecal_energy_difference_label.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.ecal_energy_difference_label.setFrameShape(qt.QFrame.Panel)
        self.ecal_energy_difference_label.setFrameShadow(qt.QFrame.Sunken)
        self.ecal_energy_difference_label.setAlignment(qt.Qt.AlignCenter)
        self.ecal_energy_difference_label.setText("0")
        self.ecal_energy_difference_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        # self.ecal_num_of_steps_label = qt.QLabel(self)
        # self.ecal_num_of_steps_label.setMinimumSize(qt.QSize(70, 33))
        # self.ecal_num_of_steps_label.setMaximumSize(qt.QSize(70, 33))
        # self.ecal_num_of_steps_label.setFrameShape(qt.QFrame.Panel)
        # self.ecal_num_of_steps_label.setFrameShadow(qt.QFrame.Sunken)
        # self.ecal_num_of_steps_label.setText("")
        # self.ecal_num_of_steps_label.setAlignment(qt.Qt.AlignCenter)

        # self.ecal_scan_point_label = qt.QLabel(self)
        # self.ecal_scan_point_label.setMinimumSize(qt.QSize(70, 33))
        # self.ecal_scan_point_label.setMaximumSize(qt.QSize(70, 33))
        # self.ecal_scan_point_label.setFrameShape(qt.QFrame.Panel)
        # self.ecal_scan_point_label.setFrameShadow(qt.QFrame.Sunken)
        # self.ecal_scan_point_label.setText("")
        # self.ecal_scan_point_label.setAlignment(qt.Qt.AlignCenter)

        # self.ecal_loop_time_label = qt.QLabel(self)
        # self.ecal_loop_time_label.setMinimumSize(qt.QSize(70, 33))
        # self.ecal_loop_time_label.setMaximumSize(qt.QSize(70, 33))
        # self.ecal_loop_time_label.setFrameShape(qt.QFrame.Panel)
        # self.ecal_loop_time_label.setFrameShadow(qt.QFrame.Sunken)
        # self.ecal_loop_time_label.setText("")
        # self.ecal_loop_time_label.setAlignment(qt.Qt.AlignCenter)

        self.ecal_energy_offset_edit = qt.QDoubleSpinBox(self)
        self.ecal_energy_offset_edit.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.ecal_energy_offset_edit.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.ecal_energy_offset_edit.setAlignment(qt.Qt.AlignCenter)
        self.ecal_energy_offset_edit.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.ecal_energy_offset_edit.setDecimals(4)
        self.ecal_energy_offset_edit.setMinimum(-9999999.0)
        self.ecal_energy_offset_edit.setMaximum(9999999.99)
        self.ecal_energy_offset_edit.setSingleStep(0.001)
        self.ecal_energy_offset_edit.setProperty("value", 0.0)

        self.ecal_set_offset_button = qt.QPushButton(self)
        self.ecal_set_offset_button.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.ecal_set_offset_button.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.ecal_set_offset_button.setText("Set Offset")

        # self.ecal_data_save_path = qt.QTextBrowser(self)
        # self.ecal_data_save_path.setMinimumSize(qt.QSize(400, 0))
        # self.ecal_data_save_path.setMaximumSize(qt.QSize(16777215, 30))

        # self.ecal_push_select_path = qt.QPushButton(self)
        # self.ecal_push_select_path.setMinimumSize(qt.QSize(100, 30))
        # self.ecal_push_select_path.setMaximumSize(qt.QSize(100, 30))
        # self.ecal_push_select_path.setText("Select Path")

        self.ecal_filename_edit = qt.QLineEdit(self)
        self.ecal_filename_edit.setMinimumSize(qt.QSize(0, 30))
        self.ecal_filename_edit.setMaximumSize(qt.QSize(16777215, 30))
        self.ecal_filename_edit.setText("Ecal_Filename")

        self.ecal_saved_path_label = qt.QLabel(self)
        self.ecal_saved_path_label.setMinimumSize(qt.QSize(0, 30))
        self.ecal_saved_path_label.setMaximumSize(qt.QSize(16777215, 30))
        self.ecal_saved_path_label.setFrameShape(qt.QFrame.Panel)
        self.ecal_saved_path_label.setFrameShadow(qt.QFrame.Sunken)
        self.ecal_saved_path_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.run_calibrate_button = qt.QPushButton(self)
        self.run_calibrate_button.setMinimumSize(qt.QSize(_controlWidth, 50))
        self.run_calibrate_button.setMaximumSize(qt.QSize(_controlWidth, 50))
        self.run_calibrate_button.setText("Run")

        # self.ecal_pauseButton = qt.QPushButton(self)
        # self.ecal_pauseButton.setMinimumSize(qt.QSize(130, 50))
        # self.ecal_pauseButton.setMaximumSize(qt.QSize(130, 50))
        # self.ecal_pauseButton.setText("Pause")

        # self.ecal_resumeButton = qt.QPushButton(self)
        # self.ecal_resumeButton.setMinimumSize(qt.QSize(130, 50))
        # self.ecal_resumeButton.setMaximumSize(qt.QSize(130, 50))
        # self.ecal_resumeButton.setText("Resume")

        self.ecal_abortButton = qt.QPushButton(self)
        self.ecal_abortButton.setMinimumSize(qt.QSize(_controlWidth, 50))
        self.ecal_abortButton.setMaximumSize(qt.QSize(_controlWidth, 50))
        self.ecal_abortButton.setText("Scan Abort")

        ############ End Energy Calibration Tab  ##############################


        ############ Slit Control Tab  ##############################

        self.slit_select_motor_comboBox = ComboBoxAligned(self)
        self.slit_select_motor_comboBox.setMinimumSize(qt.QSize(130, 50))
        self.slit_select_motor_comboBox.setMaximumSize(qt.QSize(130, 50))
        self.slit_select_motor_comboBox.addItem("")
        self.slit_select_motor_comboBox.addItem("")
        self.slit_select_motor_comboBox.addItem("")
        self.slit_select_motor_comboBox.addItem("")
        self.slit_select_motor_comboBox.setItemText(0, "Left Slit")
        self.slit_select_motor_comboBox.setItemText(1, "Right Slit")
        self.slit_select_motor_comboBox.setItemText(2, "Up Slit")
        self.slit_select_motor_comboBox.setItemText(3, "Down Slit")

        self.slit_tweak_start_button = qt.QPushButton(self)
        self.slit_tweak_start_button.setMinimumSize(qt.QSize(150, 50))
        self.slit_tweak_start_button.setMaximumSize(qt.QSize(150, 50))
        self.slit_tweak_start_button.setText("START Count")

        self.slit_tweak_stop_button = qt.QPushButton(self)
        self.slit_tweak_stop_button.setMinimumSize(qt.QSize(150, 50))
        self.slit_tweak_stop_button.setMaximumSize(qt.QSize(150, 50))
        self.slit_tweak_stop_button.setText("STOP Count")

        self.slit_left_label = EpicsValueLabel(self.pv_names['Motor']['slit_left'])
        self.slit_left_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.slit_right_label = EpicsValueLabel(self.pv_names['Motor']['slit_right'])
        self.slit_right_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.slit_up_label = EpicsValueLabel(self.pv_names['Motor']['slit_up'])
        self.slit_up_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.slit_down_label = EpicsValueLabel(self.pv_names['Motor']['slit_down'])
        self.slit_down_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.slit_left_tweak_reverse_button = qt.QPushButton(self)
        self.slit_left_tweak_reverse_button.setEnabled(False)
        self.slit_left_tweak_reverse_button.setMinimumSize(qt.QSize(50, 30))
        self.slit_left_tweak_reverse_button.setMaximumSize(qt.QSize(50, 30))
        self.slit_left_tweak_reverse_button.setText("<")

        self.slit_left_tweak_forward_button = qt.QPushButton(self)
        self.slit_left_tweak_forward_button.setEnabled(False)
        self.slit_left_tweak_forward_button.setMinimumSize(qt.QSize(50, 30))
        self.slit_left_tweak_forward_button.setMaximumSize(qt.QSize(50, 30))
        self.slit_left_tweak_forward_button.setText(">")

        self.slit_right_tweak_reverse_button = qt.QPushButton(self)
        self.slit_right_tweak_reverse_button.setEnabled(False)
        self.slit_right_tweak_reverse_button.setMinimumSize(qt.QSize(50, 30))
        self.slit_right_tweak_reverse_button.setMaximumSize(qt.QSize(50, 30))
        self.slit_right_tweak_reverse_button.setText("<")

        self.slit_right_tweak_forward_button = qt.QPushButton(self)
        self.slit_right_tweak_forward_button.setEnabled(False)
        self.slit_right_tweak_forward_button.setMinimumSize(qt.QSize(50, 30))
        self.slit_right_tweak_forward_button.setMaximumSize(qt.QSize(50, 30))
        self.slit_right_tweak_forward_button.setText(">")

        self.slit_up_tweak_reverse_button = qt.QPushButton(self)
        self.slit_up_tweak_reverse_button.setEnabled(False)
        self.slit_up_tweak_reverse_button.setMinimumSize(qt.QSize(50, 30))
        self.slit_up_tweak_reverse_button.setMaximumSize(qt.QSize(50, 30))
        self.slit_up_tweak_reverse_button.setText("<")

        self.slit_up_tweak_forward_button = qt.QPushButton(self)
        self.slit_up_tweak_forward_button.setEnabled(False)
        self.slit_up_tweak_forward_button.setMinimumSize(qt.QSize(50, 30))
        self.slit_up_tweak_forward_button.setMaximumSize(qt.QSize(50, 30))
        self.slit_up_tweak_forward_button.setText(">")

        self.slit_down_tweak_reverse_button = qt.QPushButton(self)
        self.slit_down_tweak_reverse_button.setEnabled(False)
        self.slit_down_tweak_reverse_button.setMinimumSize(qt.QSize(50, 30))
        self.slit_down_tweak_reverse_button.setMaximumSize(qt.QSize(50, 30))
        self.slit_down_tweak_reverse_button.setText("<")

        self.slit_down_tweak_forward_button = qt.QPushButton(self)
        self.slit_down_tweak_forward_button.setEnabled(False)
        self.slit_down_tweak_forward_button.setMinimumSize(qt.QSize(50, 30))
        self.slit_down_tweak_forward_button.setMaximumSize(qt.QSize(50, 30))
        self.slit_down_tweak_forward_button.setText(">")

        self.slit_left_tweak_edit = TweakDoubleSpinBox(self.pv_names['Motor']['slit_left'] + '.TWV')
        self.slit_right_tweak_edit = TweakDoubleSpinBox(self.pv_names['Motor']['slit_right'] + '.TWV')
        self.slit_up_tweak_edit = TweakDoubleSpinBox(self.pv_names['Motor']['slit_up'] + '.TWV')
        self.slit_down_tweak_edit = TweakDoubleSpinBox(self.pv_names['Motor']['slit_down'] + '.TWV')

        ############ End Slit Control Tab  ####################################


        ############ DCM Tab  #################################################

        self.DCM_theta_rbv = EpicsValueLabel(self.pv_names['DCM']['mono_theta'] + '.RBV')
        self.DCM_theta_rbv.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.DCM_zt_rbv = EpicsValueLabel(self.pv_names['DCM']['mono_zt'] + '.RBV')
        self.DCM_zt_rbv.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.DCM_z1_rbv = EpicsValueLabel(self.pv_names['DCM']['mono_z1'] + '.RBV')
        self.DCM_z1_rbv.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.DCM_theta2_rbv = EpicsValueLabel(self.pv_names['DCM']['mono_theta2'] + '.RBV')
        self.DCM_theta2_rbv.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.DCM_z2_rbv = EpicsValueLabel(self.pv_names['DCM']['mono_z2'] + '.RBV')
        self.DCM_z2_rbv.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.DCM_gamma2_rbv = EpicsValueLabel(self.pv_names['DCM']['mono_gamma2'] + '.RBV')
        self.DCM_gamma2_rbv.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.DCM_axis_tweak_start_button = qt.QPushButton(self)
        self.DCM_axis_tweak_start_button.setMinimumSize(qt.QSize(150, 50))
        self.DCM_axis_tweak_start_button.setMaximumSize(qt.QSize(150, 50))
        self.DCM_axis_tweak_start_button.setText("START Count")

        self.DCM_axis_tweak_stop_button = qt.QPushButton(self)
        self.DCM_axis_tweak_stop_button.setMinimumSize(qt.QSize(150, 50))
        self.DCM_axis_tweak_stop_button.setMaximumSize(qt.QSize(150, 50))
        self.DCM_axis_tweak_stop_button.setText("STOP Count")

        self.DCM_I0_label = qt.QLabel(self)
        self.DCM_I0_label.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.DCM_I0_label.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.DCM_I0_label.setFrameShape(qt.QFrame.Panel)
        self.DCM_I0_label.setFrameShadow(qt.QFrame.Sunken)
        self.DCM_I0_label.setAlignment(qt.Qt.AlignCenter)
        self.DCM_I0_label.setText("0")
        self.DCM_I0_label.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.DCM_I0_doubleSpinBox = qt.QDoubleSpinBox(self)
        self.DCM_I0_doubleSpinBox.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.DCM_I0_doubleSpinBox.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.DCM_I0_doubleSpinBox.setAlignment(qt.Qt.AlignCenter)
        self.DCM_I0_doubleSpinBox.setDecimals(1)
        self.DCM_I0_doubleSpinBox.setSingleStep(1e-01)
        self.DCM_I0_doubleSpinBox.setProperty("value", 0.7)

        self.DCM_I0_label_2 = qt.QLabel(self)
        self.DCM_I0_label_2.setMinimumSize(qt.QSize(_controlWidth, 30))
        self.DCM_I0_label_2.setMaximumSize(qt.QSize(_controlWidth, 30))
        self.DCM_I0_label_2.setFrameShape(qt.QFrame.Panel)
        self.DCM_I0_label_2.setFrameShadow(qt.QFrame.Sunken)
        self.DCM_I0_label_2.setAlignment(qt.Qt.AlignCenter)
        self.DCM_I0_label_2.setText("0")
        self.DCM_I0_label_2.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        self.DCM_axis_position_rbv = EpicsValueLabel(self.pv_names['DCM']['mono_theta2'], precision=5)
        self.DCM_axis_position_rbv.setMinimumSize(qt.QSize(190, 30))
        self.DCM_axis_position_rbv.setMaximumSize(qt.QSize(190, 30))
        self.DCM_axis_position_rbv.setText("not connected")
        self.DCM_axis_position_rbv.setStyleSheet("QLabel { background-color: #e0e0e0 }")

        # self.DCM_axis_status = qt.QLabel(self)
        # self.DCM_axis_status.setMinimumSize(qt.QSize(190, 30))
        # self.DCM_axis_status.setMaximumSize(qt.QSize(190, 30))
        # self.DCM_axis_status.setFrameShape(qt.QFrame.Box)
        # self.DCM_axis_status.setFrameShadow(qt.QFrame.Sunken)
        # self.DCM_axis_status.setAlignment(qt.Qt.AlignCenter)
        # self.DCM_axis_status.setText("Ready")

        self.DCM_axis_set_edit = qt.QDoubleSpinBox(self)
        self.DCM_axis_set_edit.setMinimumSize(qt.QSize(190, 30))
        self.DCM_axis_set_edit.setMaximumSize(qt.QSize(190, 30))
        self.DCM_axis_set_edit.setAlignment(qt.Qt.AlignCenter)
        self.DCM_axis_set_edit.setButtonSymbols(qt.QAbstractSpinBox.NoButtons)
        self.DCM_axis_set_edit.setDecimals(4)
        self.DCM_axis_set_edit.setMinimum(-9999999.0)
        self.DCM_axis_set_edit.setMaximum(9999999.99)
        self.DCM_axis_set_edit.setSingleStep(0.01)
        self.DCM_axis_set_edit.setProperty("value", 0.0)

        self.DCM_axis_move_button = qt.QPushButton(self)
        self.DCM_axis_move_button.setEnabled(False)
        self.DCM_axis_move_button.setMinimumSize(qt.QSize(190, 30))
        self.DCM_axis_move_button.setMaximumSize(qt.QSize(190, 30))
        self.DCM_axis_move_button.setText('Move')

        self.DCM_axis_tweak_edit = qt.QDoubleSpinBox(self)
        self.DCM_axis_tweak_edit.setMinimumSize(qt.QSize(190, 30))
        self.DCM_axis_tweak_edit.setMaximumSize(qt.QSize(190, 30))
        self.DCM_axis_tweak_edit.setAlignment(qt.Qt.AlignCenter)
        self.DCM_axis_tweak_edit.setButtonSymbols(qt.QAbstractSpinBox.UpDownArrows)
        self.DCM_axis_tweak_edit.setDecimals(5)
        self.DCM_axis_tweak_edit.setMinimum(-9999999.0)
        self.DCM_axis_tweak_edit.setMaximum(9999999.99)
        self.DCM_axis_tweak_edit.setSingleStep(1e-05)
        self.DCM_axis_tweak_edit.setProperty("value", 0.0001)

        self.DCM_tweak_reverse_button = qt.QPushButton(self)
        self.DCM_tweak_reverse_button.setEnabled(False)
        self.DCM_tweak_reverse_button.setMinimumSize(qt.QSize(190, 30))
        self.DCM_tweak_reverse_button.setMaximumSize(qt.QSize(190, 30))
        self.DCM_tweak_reverse_button.setText("Reverse")

        self.DCM_tweak_forward_button = qt.QPushButton(self)
        self.DCM_tweak_forward_button.setEnabled(False)
        self.DCM_tweak_forward_button.setMinimumSize(qt.QSize(190, 30))
        self.DCM_tweak_forward_button.setMaximumSize(qt.QSize(190, 30))
        self.DCM_tweak_forward_button.setText("Forward")

    def layout_widgets(self):

        ###################### Energy Scan Tab ################################
        scanControlGB = qt.QWidget(self.energyScanWidget)
        scanControlGB.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Expanding)
        scanControlGB.setLayout(qt.QHBoxLayout())
        scanControlGB.layout().setContentsMargins(0, 0, 0, 0)
        self.energyScanWidget.layout().addWidget(scanControlGB)

        # scanSetupGB = qt.QWidget(self.energyScanWidget)
        scanSetupGB = qt.QWidget(self.stackedWidget)
        scanSetupGB.setLayout(qt.QHBoxLayout())
        scanSetupGB.layout().setContentsMargins(0, 0, 0, 0)
        scanSetupGB.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Expanding)

        self.stackedWidget.addWidget(scanSetupGB)
        self.stackedWidget.addWidget(self.flyControl)
        # self.energyScanWidget.layout().addWidget(addStretchWidget(self.defaultBtn, align='left'))
        self.energyScanWidget.layout().addWidget(self.stackedWidget)

        gainDarkCurrentGB = qt.QWidget(self.energyScanWidget)
        gainDarkCurrentGB.setLayout(qt.QVBoxLayout())
        self.energyScanWidget.layout().addWidget(gainDarkCurrentGB)

        dataFileGB = qt.QGroupBox("Data File", self.energyScanWidget)
        dataFileGB.setLayout(qt.QFormLayout())
        dataFileGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        self.energyScanWidget.layout().addWidget(dataFileGB)

        self.energyScanWidget.layout().addWidget(addWidgets(
            [self.run_start, self.abortButton], align='uniform'))

        self.energyScanWidget.layout().addStretch()

        elementGB = qt.QGroupBox("Energy", scanControlGB)
        elementGB.setLayout(qt.QFormLayout())
        elementGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        elementGB.layout().addRow('Element', self.comboBox_element)
        elementGB.layout().addRow('Edge', self.comboBox_edge)
        elementGB.layout().addRow('E0 [eV]', self.edit_E0)
        elementGB.layout().addRow('E0 Angle [Deg.]', self.E0_Angle_label)
        elementGB.layout().addRow('DeltaE [eV]', self.testEnergyLineEdit)
        elementGB.layout().addRow(addWidgets([self.move_to_E0, self.stop_E0_button],
                                             align='right'))
        scanControlGB.layout().addWidget(elementGB)

        scanTypeGB = qt.QGroupBox(scanControlGB)
        scanTypeGB.setLayout(qt.QFormLayout())
        scanTypeGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        scanTypeGB.layout().setFormAlignment(qt.Qt.AlignRight)
        scanTypeGB.layout().addRow('', self.use_batch_checkbox)
        scanTypeGB.layout().addRow('Step Delay Time [ms]', self.edit_delay_time)
        scanTypeGB.layout().addRow('Scan Type', self.run_type)
        scanTypeGB.layout().addRow('Scan Number', self.number_of_scan_edit)
        scanTypeGB.layout().addRow(qt.QLabel())
        scanTypeGB.layout().addRow('SiMode', self.comboBox_Si_mode)
        scanTypeGB.layout().addRow('Mono Offset [Deg.]', self.E0_offset)

        # scanTypeGB.layout().addRow('Curr. Sample Pos. [deg.]', self.sample_pos_label)
        # scanTypeGB.layout().addRow('Sample Position [deg.]', self.sample_pos_spinbox)

        scanControlGB.layout().addWidget(scanTypeGB)

        srbGB = qt.QGroupBox("SRB", scanSetupGB)
        srbGB.setLayout(qt.QVBoxLayout())
        srbGB.layout().addWidget(self.SRB_1)
        srbGB.layout().addWidget(self.SRB_2)
        srbGB.layout().addWidget(self.SRB_3)
        srbGB.layout().addWidget(self.SRB_4)
        srbGB.layout().addWidget(self.SRB_5)
        srbGB.layout().addWidget(self.SRB_6)
        srbGB.layout().addStretch()
        scanSetupGB.layout().addWidget(srbGB)
        scanSetupGB.layout().addStretch()

        emodeGB = qt.QGroupBox("eMode", scanSetupGB)
        emodeGB.setLayout(qt.QVBoxLayout())
        emodeGB.layout().addWidget(addLabelWidgetUnit('eV', self.eMode_bar_1, 'k'))
        emodeGB.layout().addWidget(addLabelWidgetUnit('eV', self.eMode_bar_2, 'k'))
        emodeGB.layout().addWidget(addLabelWidgetUnit('eV', self.eMode_bar_3, 'k'))
        emodeGB.layout().addWidget(addLabelWidgetUnit('eV', self.eMode_bar_4, 'k'))
        emodeGB.layout().addWidget(addLabelWidgetUnit('eV', self.eMode_bar_5, 'k'))
        emodeGB.layout().addWidget(addLabelWidgetUnit('eV', self.eMode_bar_6, 'k'))
        emodeGB.layout().addStretch()
        scanSetupGB.layout().addWidget(emodeGB)
        scanSetupGB.layout().addStretch()

        stepSizeGB = qt.QGroupBox("Step Size", scanSetupGB)
        stepSizeGB.setLayout(qt.QVBoxLayout())
        stepSizeGB.layout().addSpacing(20)
        stepSizeGB.layout().addWidget(self.stepSize_1)
        stepSizeGB.layout().addWidget(self.stepSize_2)
        stepSizeGB.layout().addWidget(self.stepSize_3)
        stepSizeGB.layout().addWidget(self.stepSize_4)
        stepSizeGB.layout().addWidget(self.stepSize_5)
        stepSizeGB.layout().addStretch()
        scanSetupGB.layout().addWidget(stepSizeGB)
        scanSetupGB.layout().addStretch()

        srbUseGB = qt.QGroupBox("SRB On/Off", scanSetupGB)
        srbUseGB.setLayout(qt.QVBoxLayout())
        srbUseGB.layout().addSpacing(20)
        srbUseGB.layout().addWidget(self.SRBOnOff_1)
        srbUseGB.layout().addWidget(self.SRBOnOff_2)
        srbUseGB.layout().addWidget(self.SRBOnOff_3)
        srbUseGB.layout().addWidget(self.SRBOnOff_4)
        srbUseGB.layout().addWidget(self.SRBOnOff_5)
        srbUseGB.layout().addStretch()
        srbUseGB.layout().setAlignment(qt.Qt.AlignCenter)
        scanSetupGB.layout().addWidget(srbUseGB)
        scanSetupGB.layout().addStretch()

        timeGB = qt.QGroupBox("Time(sec.)", scanSetupGB)
        timeGB.setLayout(qt.QVBoxLayout())
        timeGB.layout().addSpacing(20)
        timeGB.layout().addWidget(self.SRB_time_1)
        timeGB.layout().addWidget(self.SRB_time_2)
        timeGB.layout().addWidget(self.SRB_time_3)
        timeGB.layout().addWidget(self.SRB_time_4)
        timeGB.layout().addWidget(self.SRB_time_5)
        timeGB.layout().addStretch()
        timeGB.layout().setAlignment(qt.Qt.AlignCenter)
        scanSetupGB.layout().addWidget(timeGB)

        ampGB = qt.QGroupBox("Amplifier", gainDarkCurrentGB)
        ampGB.setLayout(qt.QVBoxLayout())
        gainDarkCurrentGB.layout().addWidget(ampGB)

        ampGB.layout().addWidget(addWidgets([
            addLabelWidgetVert('I0 Gain', self.gain_I0, align=""),
            addLabelWidgetVert('It Gain', self.gain_It, align=""),
            addLabelWidgetVert('If Gain', self.gain_If, align=""),
            addLabelWidgetVert('Ir Gain', self.gain_Ir, align=""),
            addLabelWidgetVert('Rise Time', self.riseTime, align="")], align='uniform'))

        zeroCheckSet = addLabelWidgetWidget('ZCheck', self.zeroCheck_rbv, self.zeroCheckButton, labelWidth=100, align='right')
        ampGB.layout().addWidget(zeroCheckSet)

        darkGB = qt.QGroupBox("Dark Current [cps]", ampGB)
        darkGB.setLayout(qt.QHBoxLayout())
        darkGB.layout().addWidget(addWidgets([
            addLabelWidgetVert('I0 Dark', self.I0_dark_current, align=""),
            addLabelWidgetVert('It Dark', self.It_dark_current, align=""),
            addLabelWidgetVert('Ir Dark', self.Ir_dark_current, align=""),
            addLabelWidgetVert('If Dark', self.If_dark_current, align="")], align='uniform'))
        gainDarkCurrentGB.layout().addWidget(darkGB)

        dataFileGB.layout().addRow(addLabelWidgetVert("Description", self.description_edit, align='left'))
        dataFileGB.layout().addRow(addLabelWidgetVert("Data path",
                                                      addWidgets([self.data_save_path,
                                                                  self.push_select_path]),
                                                      align='left'))
        dataFileGB.layout().addRow(addLabelWidgetVert("Filename prefix", self.filename_edit, align='left'))
        dataFileGB.layout().addRow(addLabelWidgetVert("Last saved file", self.saved_path_label, align='left'))

        ######  End Energy Scan Tab  ##########################################


        ######  Energy Calibration Tab  #######################################
        ecal_scanControlGB = qt.QWidget(self.energyCalibWidget)
        ecal_scanControlGB.setLayout(qt.QHBoxLayout())
        self.energyCalibWidget.layout().addWidget(ecal_scanControlGB)

        ecal_elementGB = qt.QGroupBox("Energy", ecal_scanControlGB)
        ecal_elementGB.setLayout(qt.QFormLayout())
        ecal_elementGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        ecal_elementGB.layout().addRow('Element', self.ecal_comboBox_element)
        ecal_elementGB.layout().addRow('Edge', self.ecal_comboBox_edge)
        ecal_elementGB.layout().addRow('E0 [eV]', self.ecal_edit_E0)
        ecal_elementGB.layout().addRow('E0 Angle [Deg.]', self.ecal_E0_Angle_label)
        ecal_elementGB.layout().addRow(addWidgets([self.ecal_move_to_E0, self.ecal_stop_E0_button], leftMargin=0, align='center'))

        ecal_scanRangeGB = qt.QGroupBox("Scan", ecal_scanControlGB)
        ecal_scanRangeGB.setLayout(qt.QFormLayout())
        ecal_scanRangeGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        # ecal_scanRangeGB.layout().addRow("Ref. film", addWidgets([self.ecal_It_mode_checkbox,
        #                                                           self.ecal_Ir_mode_checkbox]))
        ecal_scanRangeGB.layout().addRow("Start [eV]", self.ecal_start_edit)
        ecal_scanRangeGB.layout().addRow("Stop [eV]", self.ecal_stop_edit)
        ecal_scanRangeGB.layout().addRow("Step [eV]", self.ecal_step_size_edit)
        ecal_scanRangeGB.layout().addRow("Time [Sec.]", self.ecal_time_edit)
        # ecal_scanRangeGB.layout().addStretch()


        ecal_scanControlGB.layout().setContentsMargins(0, 0, 0, 0)
        ecal_scanControlGB.layout().addWidget(ecal_elementGB)
        ecal_scanControlGB.layout().addWidget(ecal_scanRangeGB)

        ecal_infoGB = qt.QGroupBox("Offset", self.energyCalibWidget)
        ecal_infoGB.setLayout(qt.QFormLayout())
        ecal_infoGB.layout().setLabelAlignment(qt.Qt.AlignRight)

        self.energyCalibWidget.layout().addWidget(ecal_infoGB)

        ecal_infoGB.layout().addRow('Mono Offset [Deg.]', self.ecal_E0_offset)
        ecal_infoGB.layout().addRow('Deriv. Peak Energy [eV]', self.ecal_peak_energy_label)
        ecal_infoGB.layout().addRow('Energy Difference [eV]', self.ecal_energy_difference_label)
        ecal_infoGB.layout().addRow('Set Energy Offset [eV]', addWidgets([self.ecal_energy_offset_edit, self.ecal_set_offset_button], align='left'))

        ecal_ampGB = qt.QGroupBox("Amplifier", self.energyCalibWidget)
        ecal_ampGB.setLayout(qt.QVBoxLayout())
        self.energyCalibWidget.layout().addWidget(ecal_ampGB)

        ecal_ampGB.layout().addWidget(addWidgets([
                                        addLabelWidgetVert('I0 Gain', self.ecal_gain_I0, align=""),
                                        addLabelWidgetVert('It Gain', self.ecal_gain_It, align=""),
                                        addLabelWidgetVert('If Gain', self.ecal_gain_If, align=""),
                                        addLabelWidgetVert('Ir Gain', self.ecal_gain_Ir, align="")],
                                      align='uniform'))

        ecal_dataFileGB = qt.QGroupBox("Data file", self.energyCalibWidget)
        ecal_dataFileGB.setLayout(qt.QVBoxLayout())

        # ecal_dataFileGB.layout().addWidget(addWidgets(
        #     [addLabelWidget("Data path", self.ecal_data_save_path, stretch=False), self.ecal_push_select_path], align=None))

        ecal_dataFileGB.layout().addWidget(addLabelWidgetVert("Enter the Filename prefix of your calibration data",
                                                              self.ecal_filename_edit, align='left'))
        ecal_dataFileGB.layout().addWidget(addLabelWidgetVert("Last saved file", self.ecal_saved_path_label, align='left'))

        self.energyCalibWidget.layout().addWidget(ecal_dataFileGB)

        self.energyCalibWidget.layout().addWidget(addWidgets(
            [self.run_calibrate_button, self.ecal_abortButton], align='uniform'))

        self.energyCalibWidget.layout().addStretch()

        ######  End Energy Calibration Tab  ###################################


        ######  Slit Control Tab  #############################################

        slitGB = qt.QGroupBox("Slit Control", self.slitControlWidget)
        slitGB.setLayout(qt.QFormLayout())
        slitGB.layout().setFormAlignment(qt.Qt.AlignRight)
        slitGB.layout().setLabelAlignment(qt.Qt.AlignRight)

        slitButtonWg = qt.QWidget(self.slitControlWidget)
        slitButtonWg.setLayout(qt.QHBoxLayout())
        slitButtonWg.layout().addWidget(self.slit_select_motor_comboBox)
        slitButtonWg.layout().addStretch()
        slitButtonWg.layout().addWidget(addWidgets([self.slit_tweak_start_button,
                                                    self.slit_tweak_stop_button], align='left'))


        self.slitControlWidget.layout().addWidget(slitButtonWg)
        self.slitControlWidget.layout().addWidget(slitGB)
        self.slitControlWidget.layout().addStretch()


        slitGB.layout().addRow("Left Slit Position [mm] :",
                               addWidgets([self.slit_left_label,
                                           self.slit_left_tweak_reverse_button,
                                           self.slit_left_tweak_edit,
                                           self.slit_left_tweak_forward_button],
                                          align='left'))

        slitGB.layout().addRow("Right Slit Position [mm] :",
                               addWidgets([self.slit_right_label,
                                           self.slit_right_tweak_reverse_button,
                                           self.slit_right_tweak_edit,
                                           self.slit_right_tweak_forward_button],
                                          align='left'))

        slitGB.layout().addRow("Up Slit Position [mm] :",
                               addWidgets([self.slit_up_label,
                                           self.slit_up_tweak_reverse_button,
                                           self.slit_up_tweak_edit,
                                           self.slit_up_tweak_forward_button],
                                          align='left'))

        slitGB.layout().addRow("Down Slit Position [mm] :",
                               addWidgets([self.slit_down_label,
                                           self.slit_down_tweak_reverse_button,
                                           self.slit_down_tweak_edit,
                                           self.slit_down_tweak_forward_button],
                                          align='left'))

        ###### End Slit Control Tab  ##########################################

        ###### DCM Control Tab       ##########################################
        dcmGB = qt.QWidget(self.dcmWidget)
        dcmGB.setLayout(qt.QVBoxLayout())

        dcmButtonWg = qt.QWidget(self.dcmWidget)
        dcmButtonWg.setLayout(qt.QHBoxLayout())
        dcmButtonWg.layout().addStretch()
        dcmButtonWg.layout().addWidget(addWidgets([self.DCM_axis_tweak_start_button,
            self.DCM_axis_tweak_stop_button], align=None))

        dcmGB.layout().addWidget(dcmButtonWg)

        infoGB = qt.QWidget(dcmGB)
        infoGB.setLayout(qt.QHBoxLayout())

        dcmGB.layout().addWidget(infoGB)

        dcmMonitorGB = qt.QGroupBox("DCM Position", dcmGB)
        dcmMonitorGB.setLayout(qt.QFormLayout())
        dcmMonitorGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        dcmMonitorGB.layout().addRow("Theta [Deg.]", self.DCM_theta_rbv)
        dcmMonitorGB.layout().addRow("Zt [mm]", self.DCM_zt_rbv)
        dcmMonitorGB.layout().addRow("Z1 [mm]", self.DCM_z1_rbv)
        dcmMonitorGB.layout().addRow("theta2 [Deg.]", self.DCM_theta2_rbv)
        dcmMonitorGB.layout().addRow("Z2 [mm]", self.DCM_z2_rbv)
        dcmMonitorGB.layout().addRow("Gamma2 [Deg.]", self.DCM_gamma2_rbv)

        infoGB.layout().addWidget(dcmMonitorGB)

        scanCountsGB = qt.QGroupBox("Scan Counts", dcmGB)
        scanCountsGB.setLayout(qt.QFormLayout())
        scanCountsGB.layout().setLabelAlignment(qt.Qt.AlignRight)
        scanCountsGB.layout().addRow("I0", self.DCM_I0_label)
        scanCountsGB.layout().addRow("Ratio", self.DCM_I0_doubleSpinBox)
        scanCountsGB.layout().addRow("I0 x Ratio", self.DCM_I0_label_2)

        infoGB.layout().addWidget(scanCountsGB)

        theta2ControlGB = qt.QGroupBox("DCM Theta2(pitch) Control", dcmGB)
        theta2ControlGB.setLayout(qt.QFormLayout())
        theta2ControlGB.layout().addRow("Axis Position [Deg.]", self.DCM_axis_position_rbv)
        theta2ControlGB.layout().addRow("Axis Set Position [Deg.]", self.DCM_axis_set_edit)
        theta2ControlGB.layout().addRow("Axis Move", self.DCM_axis_move_button)
        theta2ControlGB.layout().addRow("Axis Tweak Position [Deg.]", self.DCM_axis_tweak_edit)
        theta2ControlGB.layout().addRow("Tweak", addWidgets([self.DCM_tweak_reverse_button,
                                                             self.DCM_tweak_forward_button]))

        dcmGB.layout().addSpacing(50)
        dcmGB.layout().addWidget(theta2ControlGB)

        self.dcmWidget.layout().addWidget(dcmGB)
        self.dcmWidget.layout().addStretch()

if __name__ == '__main__':
    app = qt.QApplication(sys.argv)
    main = ScanControlWidget()
    main.show()
    sys.exit(app.exec_())
