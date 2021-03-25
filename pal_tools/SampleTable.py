import os
import numpy as np
import pandas as pd
import re

from silx.gui import qt
from silx.gui.icons import getQIcon
from silx.gui.widgets.TableWidget import TableWidget

from utils import addWidgets, loadExcel, saveExcel, toArray

class SampleTable(qt.QWidget):
    """
    Customized ArrayTableWidget from silx.gui.data.ArrayTableWidget
    """
    def __init__(self, *args, **kwargs):
        super(SampleTable, self).__init__(*args, **kwargs)

        self.mainLayout = qt.QVBoxLayout(self)
        self.setLayout(self.mainLayout)

        self.lbl = np.array([])
        self.data = np.array([])
        self.df = None
        self.column_labels = None
        self.filename = None

        self.addBtn = qt.QPushButton(self)
        self.addBtn.setFixedWidth(30)
        self.addBtn.setFixedHeight(30)
        self.addBtn.setIcon(getQIcon('shape-cross'))
        self.addBtn.setToolTip("Add sample below")
        self.addBtn.clicked.connect(self.addRecord)

        self.minusBtn = qt.QPushButton(self)
        self.minusBtn.setFixedWidth(30)
        self.minusBtn.setFixedHeight(30)
        self.minusBtn.setIcon(getQIcon('close'))
        self.minusBtn.setToolTip("Remove current row")
        self.minusBtn.clicked.connect(self.removeRecord)

        self.loadBtn = qt.QPushButton(self)
        self.loadBtn.setFixedWidth(30)
        self.loadBtn.setFixedHeight(30)
        self.loadBtn.setIcon(getQIcon('document-open'))
        self.loadBtn.clicked.connect(self.load)
        self.loadBtn.setToolTip("Load from the excel file")

        self.saveBtn = qt.QPushButton(self)
        self.saveBtn.setFixedWidth(30)
        self.saveBtn.setFixedHeight(30)
        self.saveBtn.setIcon(getQIcon('document-save'))
        self.saveBtn.clicked.connect(self.save)
        self.saveBtn.setToolTip("Save to the excel file")

        buttons = addWidgets([self.addBtn,
                              self.minusBtn,
                              self.loadBtn,
                              self.saveBtn], align='right')

        self.table = TableWidget(self)
        self.table.setAlternatingRowColors(True)
        # self.table.horizontalHeader().setSectionResizeMode(qt.QHeaderView.Stretch)

        self.mainLayout.addWidget(buttons)
        self.mainLayout.addWidget(self.table)

    def addRecord(self):
        currentRow = self.table.currentRow()
        self.table.insertRow(currentRow+1)
        item = qt.QTableWidgetItem("SampleName")
        item.setTextAlignment(qt.Qt.AlignCenter | qt.Qt.AlignVCenter)
        self.table.setItem(currentRow+1, 0, item)

        for n, data in enumerate([1, 1]):
            item = qt.QTableWidgetItem(str(data))
            item.setTextAlignment(qt.Qt.AlignCenter | qt.Qt.AlignVCenter)
            self.table.setItem(currentRow+1, n+1, item)

        self.table.itemChanged.connect(self.check_validity)

    def removeRecord(self):
        currentRow = self.table.currentRow()
        self.table.removeRow(currentRow)

        self.table.itemChanged.connect(self.check_validity)

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

    def check_validity(self, item):
        text = item.text()
        if item.column() == 0:
            match = re.findall('[a-zA-Z0-9_]+', text)
        elif item.column() == 1:
            match = re.findall('[0-9]+', text)
            if len(match):
                if int(''.join(match)) > 390:
                    match = ['390']
            else:
                match = ['0']
        else:
            match = re.findall('[0-9]+', text)
            if not len(match):
                match = ['1']

        item.setText(''.join(match))

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

        self.table.itemChanged.connect(self.check_validity)


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
    main = SampleTable()
    main.load('sample.xlsx')
    main.show()
    app.exec_()

