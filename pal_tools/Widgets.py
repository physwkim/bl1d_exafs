import time
import epics
from silx.gui import qt
from silx.gui.utils.concurrent import submitToQtMainThread as _submit

class ScrollBarTwoValue(qt.QScrollBar):
    def __init__(self, sbarWidth, parent=None, *args, **kwargs):
        super(ScrollBarTwoValue, self).__init__(parent=parent, *args, **kwargs)

        self.setMinimumSize(qt.QSize(sbarWidth, 30))
        self.setMaximumSize(qt.QSize(sbarWidth, 30))
        self.setMinimum(0)
        self.setMaximum(1000)
        self.setSingleStep(1000)
        self.setOrientation(qt.Qt.Horizontal)
        self.setInvertedAppearance(False)

        self.valueChanged.connect(self.checkValue)

    def checkValue(self):
        if self.value() < 500:
            self.setValue(0)
        else:
            self.setValue(1000)

class ComboBoxAligned(qt.QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditable(True)
        self.lineEdit = self.lineEdit()
        self.lineEdit.setAlignment(qt.Qt.AlignCenter)
        self.lineEdit.setReadOnly(True)

class GainRbvLabel(qt.QLabel):
    def __init__(self, pv, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumSize(qt.QSize(100, 30))
        self.setMaximumSize(qt.QSize(100, 30))
        self.setFrameShape(qt.QFrame.Panel)
        self.setFrameShadow(qt.QFrame.Sunken)
        self.setAlignment(qt.Qt.AlignCenter)
        self.setText("not connected")

        self.formatStr = "{}"

        self.pv = epics.PV(pv, auto_monitor=True)
        self.pv.add_callback(self.update_value)

        # Set initial value from pv
        if self.pv.connected:
            _submit(self.setText, self.pv.get())

    def __del__(self, *args, **kwargs):
        self.pv.disconnect()

    def update_value(self, *args, **kwargs):
        value = kwargs['value']
        _submit(self.setText, self.formatStr.format(value))

class ZeroCheckRbvLabel(qt.QLabel):
    def __init__(self, pv, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setMinimumSize(qt.QSize(100, 30))
        self.setMaximumSize(qt.QSize(100, 30))
        self.setFrameShape(qt.QFrame.Panel)
        self.setFrameShadow(qt.QFrame.Sunken)
        self.setAlignment(qt.Qt.AlignCenter)
        self.setText("not connected")

        self.pv = epics.PV(pv, auto_monitor=True)
        self.pv.add_callback(self.update_value)

        # Set initial value from pv
        if self.pv.connected:
            _submit(self.update_value)

    def update_value(self, *args, **kwargs):
        if 'value' in kwargs.keys():
            value = kwargs['value']
        else:
            value = self.pv.get()

        if value == 0:
            text = 'Off'
        elif value == 1:
            text = 'On'
        elif value == 2:
            text = 'AutoCorrect'

        _submit(self.setText, text)

class RbvLabel(qt.QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumSize(qt.QSize(80, 30))
        self.setMaximumSize(qt.QSize(80, 30))
        self.setFrameShape(qt.QFrame.Panel)
        self.setFrameShadow(qt.QFrame.Sunken)
        self.setAlignment(qt.Qt.AlignCenter)
        self.setText("not conn.")

class DarkCurrentRbvLabel(RbvLabel):
    def __init__(self, *args, **kwargs):
        super(DarkCurrentRbvLabel, self).__init__(*args, **kwargs)
        self.setMinimumSize(qt.QSize(100, 30))
        self.setMaximumSize(qt.QSize(100, 30))
        self.setStyleSheet("QLabel { background-color: #e0e0e0 }")
        self.setText("0")

class GainComboBox(qt.QComboBox):
    def __init__(self, pv, read_pv=None, suppression=False, *args, **kwargs):
        super(GainComboBox, self).__init__(*args, **kwargs)

        self.lastUpdate = 0

        self.setEditable(True)
        self.lineEdit = self.lineEdit()
        self.lineEdit.setAlignment(qt.Qt.AlignCenter)
        self.lineEdit.setReadOnly(True)

        self.setMinimumSize(qt.QSize(100, 30))
        self.setMaximumSize(qt.QSize(100, 30))
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.setItemText(0, "1E3 V/A")
        self.setItemText(1, "1E4 V/A")
        self.setItemText(2, "1E5 V/A")
        self.setItemText(3, "1E6 V/A")
        self.setItemText(4, "1E7 V/A")
        self.setItemText(5, "1E8 V/A")
        self.setItemText(6, "1E9 V/A")
        self.setItemText(7, "1E10 V/A")

        self.suppression = suppression

        if suppression:
            self.prefix = pv[:-4]
            self.suppressionValuePV = epics.PV(self.prefix + 'SuppressionValue', auto_monitor=True)
            self.suppressionExponentPV = epics.PV(self.prefix + 'SuppressionExponent', auto_monitor=True)

        self.pv = epics.PV(pv, auto_monitor=True)

        if read_pv:
            self.read_pv = epics.PV(read_pv, auto_monitor=True)
        else:
            self.read_pv = self.pv

        self.read_pv.add_callback(self.update_value)

        # Set initial value from pv
        if self.read_pv.connected:
            _submit(self.update_value)

        self.currentIndexChanged.connect(self.update_pv)

    def update_pv(self, value, *args, **kwargs):
        if value != self.pv.get():
            self.pv.put(value)

            if self.suppression:
                if value == 0:
                    # Suppression : -0.05E-3
                    self.suppressionValuePV.put(-0.05)
                    self.suppressionExponentPV.put(6)
                elif value == 1:
                    # Suppression : -5E-6
                    self.suppressionValuePV.put(-5)
                    self.suppressionExponentPV.put(3)
                elif value == 2:
                    # Suppression : -0.5E-6
                    self.suppressionValuePV.put(-0.5)
                    self.suppressionExponentPV.put(3)
                elif value == 3:
                    # Suppression : -0.05E-6
                    self.suppressionValuePV.put(-0.05)
                    self.suppressionExponentPV.put(3)
                elif value == 4:
                    # Suppression : -5E-9
                    self.suppressionValuePV.put(-5)
                    self.suppressionExponentPV.put(0)
                elif value == 5:
                    # Suppression : -0.5E-9
                    self.suppressionValuePV.put(-0.5)
                    self.suppressionExponentPV.put(0)
                elif value == 6:
                    # Suppression : -0.05E-9
                    self.suppressionValuePV.put(-0.05)
                    self.suppressionExponentPV.put(0)
                elif value == 7:
                    # Suppression : -0.005E-9
                    self.suppressionValuePV.put(-0.005)
                    self.suppressionExponentPV.put(0)
                else:
                    pass

            self.lastUpdate = time.time()

    def update_value(self, *args, **kwargs):
        delta = abs(time.time() - self.lastUpdate)

        # Prevent looping
        if delta > 1:
            _submit(self.setCurrentIndex, self.pv.get())

class RiseTimeComboBox(qt.QComboBox):
    """ pv : list """
    def __init__(self, pv, read_pv=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lastUpdate = 0

        self.setEditable(True)
        self.lineEdit = self.lineEdit()
        self.lineEdit.setAlignment(qt.Qt.AlignCenter)
        self.lineEdit.setReadOnly(True)

        self.setMinimumSize(qt.QSize(100, 30))
        self.setMaximumSize(qt.QSize(100, 30))
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.addItem("")
        self.setItemText(0, "10 usec")
        self.setItemText(1, "30 usec")
        self.setItemText(2, "100 usec")
        self.setItemText(3, "300 usec")
        self.setItemText(4, "1 msec")
        self.setItemText(5, "3 msec")
        self.setItemText(6, "10 msec")
        self.setItemText(7, "30 msec")
        self.setItemText(8, "100 msec")
        self.setItemText(9, "300 msec")

        if type(pv) in (list, tuple):
            self.pvs = {}
            for idx, _pv in enumerate(pv):
                self.pvs[idx] = epics.PV(_pv, auto_monitor=True)
        else:
            self.pvs[0] = epics.PV(pv, auto_monitor=True)

        if read_pv:
            self.read_pv = epics.PV(read_pv, auto_monitor=True)
        else:
            self.read_pv = self.pvs[0]

        self.read_pv.add_callback(self.update_value)

        # Set initial value from pv
        if self.read_pv.connected:
            _submit(self.update_value)

        self.currentIndexChanged.connect(self.update_pv)

    def update_pv(self, value, *args, **kwargs):
        if value != self.pvs[0].get():
            for key in self.pvs:
                self.pvs[key].put(value)

            self.lastUpdate = time.time()

    def update_value(self, *args, **kwargs):
        delta = abs(time.time() - self.lastUpdate)

        # Prevent looping
        if delta > 1:
            _submit(self.setCurrentIndex, self.read_pv.get())

class TweakDoubleSpinBox(qt.QDoubleSpinBox):
    def __init__(self, pv, *args, **kwargs):
        super(TweakDoubleSpinBox, self).__init__(*args, **kwargs)

        self.lastUpdate = 0

        self.setMinimumSize(qt.QSize(130, 30))
        self.setMaximumSize(qt.QSize(130, 30))
        self.setAlignment(qt.Qt.AlignCenter)
        self.setButtonSymbols(qt.QAbstractSpinBox.UpDownArrows)
        self.setDecimals(3)
        self.setMinimum(-9999999.0)
        self.setMaximum(9999999.99)
        self.setSingleStep(0.01)

        self.pv = epics.PV(pv, auto_monitor=True)
        self.pv.add_callback(self.update_value)

        # Set initial value from pv
        _submit(self.setValue, self.pv.get())

        self.valueChanged.connect(self.update_pv)
        self.setKeyboardTracking(False)

    def __del__(self, *args, **kwargs):
        self.pv.disconnect()

    def update_pv(self, *args, **kwargs):
        self.pv.put(self.value())
        self.lastUpdate = time.time()

    def update_value(self, *args, **kwargs):
        delta = abs(time.time() - self.lastUpdate)

        # Prevent looping
        if delta > 1:
            _submit(self.setValue, self.pv.get())


class EpicsValueLabel(qt.QLabel):
    def __init__(self, pv, moving_pv=None, moving_val = 0, precision=5, convert=None, *args, **kwargs):
        super(EpicsValueLabel, self).__init__(*args, **kwargs)

        # Value conversion function
        self.convert = convert

        self.precision = precision
        self.setMinimumSize(qt.QSize(130, 30))
        self.setMaximumSize(qt.QSize(130, 30))
        self.setFrameShape(qt.QFrame.Panel)
        self.setFrameShadow(qt.QFrame.Sunken)
        self.setAlignment(qt.Qt.AlignCenter)
        self.setText("not connected")

        self.formatStr = "{:." + str(self.precision) + "f}"

        self.moving_val = moving_val

        self.pv = epics.PV(pv, auto_monitor=True)
        self.pv.add_callback(self.update_value)

        if moving_pv is not None:
            self.moving_pv = epics.PV(moving_pv, auto_monitor=True)
            self.moving_pv.add_callback(self.update_color)

        # Set initial value from pv
        if self.pv.connected:
            _submit(self.setText, str(round(self.pv.get(), self.precision)))

    def __del__(self, *args, **kwargs):
        self.pv.disconnect()

    def update_value(self, *args, **kwargs):
        value = kwargs['value']

        if self.convert:
            value = self.convert(value)

        _submit(self.setText, self.formatStr.format(value))

    def update_color(self, *args, **kwargs):
        if self.moving_pv.get() == self.moving_val:
            _submit(self.setStyleSheet, "QLabel { background-color: green }")
        else:
            _submit(self.setStyleSheet, "QLabel { background-color: 0 }")


class DoubleSpinBoxWithSignal(qt.QDoubleSpinBox):
    """ QDoubleSpinBox with return key signal """
    return_stroked = qt.Signal()

    def keyPressEvent(self, ev):
        """
        Parameters
        ----------
        ev : QEvent
        """
        if ev.key() in (qt.Qt.Key_Return, qt.Qt.Key_Enter):
            self.return_stroked.emit()
        else:
            super(DoubleSpinBoxWithSignal, self).keyPressEvent(ev)

class EpicsDoubleSpinBox(qt.QDoubleSpinBox):
    def __init__(self, pv, *args, read_pv=None, maximum=None, minimum=None, step=None, precision=None, **kwargs):
        super().__init__(*args, **kwargs)

        if maximum:
            self.setMaximum(maximum)
        if minimum:
            self.setMinimum(minimum)
        if step:
            self.setSingleStep(step)
        if precision:
            self.setDecimals(precision)

        self.valueBeingSet = False

        self.setMinimumSize(qt.QSize(130, 30))
        self.setMaximumSize(qt.QSize(130, 30))

        self.pv = epics.PV(pv)

        if read_pv:
            self.read_pv = epics.PV(read_pv, auto_monitor=True)
        else:
            self.read_pv = self.pv

        # Set initial value from pv
        if self.read_pv.connected:
            _submit(self.setValue, self.read_pv.get())

        self.read_pv.add_callback(self.update_value)

    def send_value(self):
        value = self.value()

        if not self.valueBeingSet:
            self.pv.put(value)

    def update_value(self, *args, **kwargs):
        value = kwargs['value']

        if value is None:
            return

        self.valueBeingSet = True
        self.setValue(value)
        self.valueBeingSet = False

    def keyPressEvent(self, ev):
        """
        Parameters
        ----------
        ev : QEvent
        """
        if ev.key() in (qt.Qt.Key_Return, qt.Qt.Key_Enter):
            self.send_value()
        else:
            super(EpicsDoubleSpinBox, self).keyPressEvent(ev)

class EpicsStringLabel(qt.QLabel):
    def __init__(self, pv, *args, **kwargs):
        super(EpicsStringLabel, self).__init__(*args, **kwargs)

        self._dummyIndex = 0

        self.setMinimumSize(qt.QSize(130, 30))
        self.setMaximumSize(qt.QSize(130, 30))
        self.setFrameShape(qt.QFrame.Panel)
        self.setFrameShadow(qt.QFrame.Sunken)
        self.setAlignment(qt.Qt.AlignCenter)
        self.setText("not connected")

        self.pv = epics.PV(pv, auto_monitor=True)
        self.pv.add_callback(self.update_value)

        self.notifyTimer = qt.QTimer()
        self.notifyTimer.timeout.connect(self._notifyColor)
        self.notifyTimer.start(1000)

        # Set initial value from pv
        if self.pv.connected:
            if self.pv.get():
                _submit(self.setText, str("On"))

    def __del__(self, *args, **kwargs):
        self.pv.disconnect()

    def update_value(self, *args, **kwargs):
        value = kwargs['value']
        if value:
            _submit(self.setText, "On")
        else:
            _submit(self.setText, "Off")

    def _notifyColor(self):
        try:
            value = self.text().lower()

            if value == 'off':
                if self._dummyIndex == 0:
                    self.setStyleSheet("QLabel { background-color: red }")
                    self._dummyIndex += 1
                else:
                    self.setStyleSheet("QLabel { background-color: 0 }")
                    self._dummyIndex = 0
            else:
                    self.setStyleSheet("QLabel { background-color: 0 }")
        except Exception as e:
            print("Error on EpicsStringLabel {}".format(e))


class CounterRbvLabel(qt.QLabel):
    def __init__(self, pv, scaler_pv=None, moving_pv=None, moving_val=0, precision=0, limit_hi=900, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if scaler_pv:
            self.count_mode = epics.PV(scaler_pv + '.CONT')
            self.count_time = epics.PV(scaler_pv + '.TP')
            self.auto_count_time = epics.PV(scaler_pv + '.TP1')

        self.setMinimumSize(qt.QSize(120, 30))
        self.setMaximumSize(qt.QSize(120, 30))

        self.precision = precision
        self.setFrameShape(qt.QFrame.Panel)
        self.setFrameShadow(qt.QFrame.Sunken)
        self.setAlignment(qt.Qt.AlignCenter)
        self.setText("not connected")

        self.formatStr = "{:." + str(self.precision) + "f}"

        self.moving_val = moving_val

        self.pv = epics.PV(pv, auto_monitor=True)
        self.pv.add_callback(self.update_value)

        if moving_pv is not None:
            self.moving_pv = epics.PV(moving_pv, auto_monitor=True)
            self.moving_pv.add_callback(self.update_color)

        self.limit_hi = limit_hi
        self._dummyIndex = 0

        self.notifyTimer = qt.QTimer()
        self.notifyTimer.timeout.connect(self._notifyColor)
        self.notifyTimer.start(1000)

    def _notifyColor(self):
        try:
            value = float(self.text())

            if value > self.limit_hi:
                if self._dummyIndex == 0:
                    self.setStyleSheet("QLabel { background-color: red }")
                    self._dummyIndex += 1
                else:
                    self.setStyleSheet("QLabel { background-color: 0 }")
                    self._dummyIndex = 0
            else:
                    self.setStyleSheet("QLabel { background-color: 0 }")
        except:
            pass

    def update_value(self, *args, **kwargs):
        mode = int(self.count_mode.get())
        if mode:
            time = self.auto_count_time.get()
        else:
            time = self.count_time.get()

        # Counts per seconds
        value = float(kwargs['value']) / time
        _submit(self.setText, self.formatStr.format(value))

class CounterRbvVoltLabel(qt.QLabel):
    """ Read counter value and display in voltage[0-10V] """
    def __init__(self, pv, scaler_pv=None, moving_pv=None, moving_val=0, precision=3, limit_hi=9, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if scaler_pv:
            self.count_mode = epics.PV(scaler_pv + '.CONT')
            self.count_time = epics.PV(scaler_pv + '.TP')
            self.auto_count_time = epics.PV(scaler_pv + '.TP1')

        self.setMinimumSize(qt.QSize(120, 30))
        self.setMaximumSize(qt.QSize(120, 30))

        self.precision = precision
        self.setFrameShape(qt.QFrame.Panel)
        self.setFrameShadow(qt.QFrame.Sunken)
        self.setAlignment(qt.Qt.AlignCenter)
        self.setText("not connected")

        self.formatStr = "{:." + str(self.precision) + "f}"

        self.moving_val = moving_val

        self.pv = epics.PV(pv, auto_monitor=True)
        self.pv.add_callback(self.update_value)

        if moving_pv is not None:
            self.moving_pv = epics.PV(moving_pv, auto_monitor=True)
            self.moving_pv.add_callback(self.update_color)

        self.limit_hi = limit_hi
        self._dummyIndex = 0

        self.notifyTimer = qt.QTimer()
        self.notifyTimer.timeout.connect(self._notifyColor)
        self.notifyTimer.start(1000)

    def _notifyColor(self):
        try:
            value = float(self.text())

            if value > self.limit_hi:
                if self._dummyIndex == 0:
                    self.setStyleSheet("QLabel { background-color: red }")
                    self._dummyIndex += 1
                else:
                    self.setStyleSheet("QLabel { background-color: 0 }")
                    self._dummyIndex = 0
            else:
                    self.setStyleSheet("QLabel { background-color: 0 }")
        except:
            pass

    def update_value(self, *args, **kwargs):
        mode = int(self.count_mode.get())
        if mode:
            time = self.auto_count_time.get()
        else:
            time = self.count_time.get()

        # Counts per seconds and then convert in voltage
        value = float(kwargs['value']) / time / 1e5

        # Update readback
        _submit(self.setText, self.formatStr.format(value))


class MainToolBar(qt.QToolBar):
    """
    Toolbar consisted with text labeled actions
    """

    sigSetStage = qt.Signal(object)

    def __init__(self, parent=None, *args, **kwargs):
        super(MainToolBar, self).__init__(parent=parent, *args, **kwargs)

        # Setup font
        self.font = qt.QFont("Verdana")
        self.font.setPointSize(16)

        # Mode action group
        self.modeActionGroup = qt.QActionGroup(self)

        # Align right
        self.setLayoutDirection(qt.Qt.RightToLeft)

        # Build children
        self.buildActions()

    def buildActions(self):
        action = qt.QAction("EXAFS", self)
        # action.triggered.connect(partial(self.setMode, mode='exafs'))
        action.setFont(self.font)
        # action.setProperty("isMode", True)
        action.setCheckable(True)
        action.setActionGroup(self.modeActionGroup)
        action.setChecked(True)
        self.addAction(action)


if __name__ == "__main__":
    app = qt.QApplication([])
    main = qt.QWidget()
    layout = qt.QVBoxLayout(main)
    main.setLayout(layout)
    wg = CounterRbvLabel("BL8C:scaler1_calc1.D", limit_hi=1000)
    layout.addWidget(wg)
    main.show()
    app.exec_()
