import json
import pathlib
import numpy as np
import pandas as pd

from silx.gui import qt

def nearest(arr, val):
    """
    return nearest value's index in arr

    Parameters
    ----------
    arr : Search array
    val : Search value
    """
    return np.abs(arr-val).argmin()

def path(filename: str):
    """
    codes from Xi-cam.gui/static/__init__.py
    (https://github.com/Xi-CAM/Xi-cam.gui)

    Parameter
    ---------
    filename : The file name in the same directory as the current file

    return relative path

    """
    return str(pathlib.Path(pathlib.Path(__file__).parent, filename))

def loadJson(filename: str):
    """
    Load json file

    Parameters
    ----------
    filename : jsonfile

    """
    with open(path(filename), 'r') as f:
        _dict = json.load(f)

    return _dict

def toArray(df):
    """
    Convert pandas dataFrame to index array and numpy data array

    Parameters
    ----------
    df : pandas dataFrame
    labels : first is element name, remaining is data label
    """

    data_array = []


    for n, label in enumerate(df.columns):
        if n == 0:
            idx_array = list(df[label])
        else:
            data_array.append(df[label])

    data = np.array(data_array).T

    return idx_array, data

def loadExcel(filename):
    """
    Load excel file to pandas dataframe
    """
    return pd.read_excel(filename)

def saveExcel(filename, df):
    """
    Save to excel file from pandas df
    """
    df.to_excel(filename, index=False)

def loadPV():
    """
    Return pv_list.json and return result as dict
    """
    return loadJson(path('pv_list.json'))

def loadDefault():
    """
    Return default settings
    """
    return loadExcel(path('default.xlsx'))

def getDefault(pd, name=None):
    """Return default value from pandas"""
    if name is not None:
        idx = pd.index[pd['Name'] == name].tolist()[0]
    else:
        return -99999

    return pd['Value'].get(idx)

def loadOffset():
    """
    Return previous DCM offset value
    """
    return np.loadtxt(path('dcm_offset.dat'))[0]

def saveOffset(offset):
    """
    Save current DCM offset value
    """
    if not(isinstance(offset, np.array) or isinstance(offset, list)):
        offset = [offset]

    return np.savetxt(path('dcm_offset.dat'), [offset])

def addWidgets(widgets, leftMargin=0, Type='h', align=None, spacing=None):
    # create a mother widget to make sure both qLabel & qLineEdit will
    # always be displayed side by side
    widget = qt.QWidget()

    if Type == 'h':
        widget.setLayout(qt.QHBoxLayout())
    else:
        widget.setLayout(qt.QVBoxLayout())

    if align == 'center':
        widget.layout().setAlignment(qt.Qt.AlignCenter)

    if align == 'bottom' or align == 'right':
        widget.layout().addStretch()

    widget.layout().setContentsMargins(0, 0, 0, 0)
    widget.layout().addSpacing(leftMargin)
    for wg in widgets:
        widget.layout().addWidget(wg)
        if align == 'uniform':
            if wg != widgets[-1]:
                widget.layout().addStretch()

    if align == 'top' or align == 'left':
        widget.layout().addStretch()

    return widget

def addStretchWidget(QWidget, align='bottom'):
    # append a stretch at above/bottom/left/right side of a QWidget
    widget = qt.QWidget()

    if align=='top' or align=='bottom':
        widget.setLayout(qt.QVBoxLayout())
    elif align=='left' or align=='right':
        widget.setLayout(qt.QHBoxLayout())
    else:
        return None

    widget.layout().setSpacing(0)
    widget.layout().setContentsMargins(0, 0, 0, 0)

    if align == 'bottom' or align == 'right':
        widget.layout().addStretch()

    widget.layout().addWidget(QWidget)

    if align == 'top' or align == 'left':
        widget.layout().addStretch()

    return widget

def addLabelWidget(labelText, QWidget, labelWidth=None, align='left'):
    # create a mother widget to make sure both qLabel & qLineEdit will
    # always be displayed side by side
    widget = qt.QWidget()
    widget.setLayout(qt.QHBoxLayout())
    widget.layout().setContentsMargins(0, 0, 0, 0)

    label = qt.QLabel(labelText)
    label.setAlignment(qt.Qt.AlignRight | qt.Qt.AlignVCenter)

    if labelWidth != None:
        label.setMinimumWidth(labelWidth)
        label.setMaximumWidth(labelWidth)

    if align.lower() == 'right':
        widget.layout().addStretch(1)

    widget.layout().addWidget(label)
    widget.layout().addWidget(QWidget)

    if align.lower() == 'left':
        widget.layout().addStretch(1)

    return widget

def addLabelWidgetWidget(labelText, QWidgetRbv, QWidgetSet, labelWidth=None, align="left"):
    # create a mother widget to make sure both qLabel & qLineEdit will
    # always be displayed side by side
    widget = qt.QWidget()
    widget.setLayout(qt.QHBoxLayout())
    widget.layout().setContentsMargins(0, 0, 0, 0)
    label = qt.QLabel(labelText)
    label.setAlignment(qt.Qt.AlignRight | qt.Qt.AlignVCenter)
    if labelWidth != None:
        label.setMinimumWidth(labelWidth)
        label.setMaximumWidth(labelWidth)
    if align:
        if align.lower() == 'right':
            widget.layout().addStretch(1)
    widget.layout().addWidget(label)
    widget.layout().addWidget(QWidgetRbv)
    widget.layout().addWidget(QWidgetSet)
    if align:
        if align.lower() == 'left':
            widget.layout().addStretch(1)
    return widget

def addLabelWidgetUnit(labelText, QWidget, UnitText, labelWidth=None, align='left'):
    # create a mother widget to make sure both qLabel & qLineEdit will
    # always be displayed side by side

    widget = qt.QWidget()
    widget.setLayout(qt.QHBoxLayout())
    widget.layout().setContentsMargins(0, 0, 0, 0)

    label = qt.QLabel(labelText)
    label.setAlignment(qt.Qt.AlignRight | qt.Qt.AlignVCenter)

    if labelWidth != None:
        label.setMinimumWidth(labelWidth)
        label.setMaximumWidth(labelWidth)

    unit = qt.QLabel(UnitText)

    if align.lower() == 'right':
        widget.layout().addStretch(1)

    widget.layout().addWidget(label)
    widget.layout().addWidget(QWidget)
    widget.layout().addWidget(unit)

    if align.lower() == 'left':
        widget.layout().addStretch(1)

    return widget

def addLabelWidgetVert(labelText, QWidget, align='center'):
    # create a mother widget to make sure both qLabel & qLineEdit will
    # always be displayed vertically
    widget = qt.QWidget()
    widget.setLayout(qt.QVBoxLayout())

    widget.layout().setSpacing(0)
    widget.layout().setContentsMargins(0, 0, 0, 0)

    label = qt.QLabel(labelText)

    if align.lower() == 'center':
        label.setAlignment(qt.Qt.AlignCenter)

    widget.layout().addWidget(label)
    widget.layout().addWidget(QWidget)

    return widget

def addLabelWidgetVertFixed(labelText, QWidget, align='center'):
    # create a mother widget to make sure both qLabel & qLineEdit will
    # always be displayed vertically
    widget = qt.QWidget()
    widget.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
    widget.setLayout(qt.QVBoxLayout())

    widget.layout().setSpacing(0)
    widget.layout().setContentsMargins(0, 0, 0, 0)

    label = qt.QLabel(labelText)

    if align.lower() == 'center':
        label.setAlignment(qt.Qt.AlignCenter)

    widget.layout().addWidget(label)
    widget.layout().addWidget(QWidget)

    return widget

# Referenced from http://kitchingroup.cheme.cmu.edu/blog/2013/02/27/Numeric-derivatives-by-differences/
def derivative(x, y):
    """
    Parameter
    ---------
    x : x list
    y : y list
    """
    der = np.zeros(len(x))
    # Forward derivative
    # for i in range(len(y)-1):
    #     der[i] = (y[i+1] - y[i])/(x[i+1] - x[i])
    # # Use backward difference only for last point
    # der[-1] = (y[-1] - y[-2])/(x[-1] - x[-2])

    try:
        # Backward derivative
        der[0] = (y[0] - y[1])/(x[0] - x[1])
        for i in range(1, len(y)):
            der[i] = (y[i] - y[i-1])/(x[i] - x[i-1])
    except ZeroDivisionError as error:
        print("ZeroDivisionError Occured during derivative!")
        der = np.zeros(len(x))
    except:
        print("Unknown Error Occured during derivative!")
        der = np.zeros(len(x))

    return der


if __name__ == '__main__':
    print(loadPV())
