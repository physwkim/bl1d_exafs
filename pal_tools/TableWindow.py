import os
import numpy as np
import pandas as pd

from silx.gui import qt
from silx.gui.icons import getQIcon
from silx.gui.widgets.TableWidget import TableWidget

from utils import addWidgets, loadExcel, saveExcel, toArray

class TableWindow(qt.QWidget):
    """
    Customized ArrayTableWidget from silx.gui.data.ArrayTableWidget
    """
    def __init__(self, *args, **kwargs):
        super(TableWindow, self).__init__(*args, **kwargs)

        self.mainLayout = qt.QVBoxLayout(self)
        self.setLayout(self.mainLayout)

        self.lbl = np.array([])
        self.data = np.array([])
        self.df = None
        self.column_labels = None
        self.filename = None

        self.loadBtn = qt.QPushButton(self)
        self.loadBtn.setFixedWidth(30)
        self.loadBtn.setFixedHeight(30)
        self.loadBtn.setIcon(getQIcon('document-open'))
        self.loadBtn.clicked.connect(self.load)

        self.saveBtn = qt.QPushButton(self)
        self.saveBtn.setFixedWidth(30)
        self.saveBtn.setFixedHeight(30)
        self.saveBtn.setIcon(getQIcon('document-save'))
        self.saveBtn.clicked.connect(self.save)

        self.loadDefaultBtn = qt.QPushButton(self)
        self.loadDefaultBtn.setFixedWidth(130)
        self.loadDefaultBtn.setFixedHeight(30)
        self.loadDefaultBtn.setText('Load Default')
        self.loadDefaultBtn.clicked.connect(self.loadDefault)

        buttons = addWidgets([self.loadBtn,
                              self.saveBtn,
                              self.loadDefaultBtn], align='right')
        self.table = TableWidget(self)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(qt.QHeaderView.Stretch)
        # self.table.verticalHeader().setVisible(False)

        self.mainLayout.addWidget(buttons)
        self.mainLayout.addWidget(self.table)

    def loadDefault(self):
        filename = 'gap_and_taper_orig.xlsx'
        if os.path.exists(filename):
            try:
                self.df = loadExcel(filename)
                self.column_labels = list(self.df.columns)
                self.lbl, self.data = toArray(self.df)

                if len(self.lbl):
                    self.setData()
            except:
                print("not available")


    def load(self, filename=None):
        if filename:
            self.filename = filename

        # pandas dataFrame
        if os.path.exists(self.filename):
            try:
                self.df = loadExcel(self.filename)
                self.column_labels = list(self.df.columns)
                self.lbl, self.data = toArray(self.df)

                if len(self.lbl):
                    self.setData()
            except:
                print("not available")

    def save(self):
        self.getData()
        saveExcel(self.filename, self.df)

        self.load()

    def highlight(self, item):
        font=qt.QFont("Verdana")
        font.setBold(True)
        item.setFont(font)

        brush = qt.QBrush(qt.Qt.red)
        item.setForeground(brush)

    def setData(self):
        try:
            self.table.itemChanged.disconnect()
        except:
            pass

        # Delete data
        self.table.setRowCount(0)

        self.table.setColumnCount(len(self.column_labels))
        self.table.setHorizontalHeaderLabels(self.column_labels)

        for row, label in enumerate(self.lbl):
            self.table.insertRow(row)
            item = qt.QTableWidgetItem(label)
            item.setTextAlignment(qt.Qt.AlignCenter | qt.Qt.AlignVCenter)
            self.table.setItem(row, 0, item)

            for n, data in enumerate(self.data[row]):
                item = qt.QTableWidgetItem(str(data))
                item.setTextAlignment(qt.Qt.AlignCenter | qt.Qt.AlignVCenter)
                self.table.setItem(row, n+1, item)

        self.table.itemChanged.connect(self.highlight)

    def getData(self):
        rows = self.table.rowCount()
        cols = self.table.columnCount()

        self.lbl = []
        self.data = []
        for row in range(rows):
            temp = []
            for col in range(cols):
                if col == 0:
                    self.lbl.append(self.table.item(row, col).text())

                else:
                    temp.append(float(self.table.item(row, col).text()))
            self.data.append(temp)

        # To numpy array
        self.data = np.array(self.data)

        # To DataFrame
        df = pd.DataFrame()
        for n, label in enumerate(self.column_labels):
            if n == 0:
                df[label] = self.lbl
            else:
                df[label] = self.data[:, n-1]

        self.df = df

        return self.lbl, self.data


if __name__ == '__main__':
    app = qt.QApplication([])
    main = TableWindow()
    main.load('gap_and_taper.xlsx')
    main.show()
    app.exec_()

