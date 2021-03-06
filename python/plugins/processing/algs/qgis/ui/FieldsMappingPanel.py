# -*- coding: utf-8 -*-

"""
***************************************************************************
    FieldsMappingWidget.py
    ---------------------
    Date                 : October 2014
    Copyright            : (C) 2014 by Arnaud Morvan
    Email                : arnaud dot morvan at camptocamp dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
from builtins import range

__author__ = 'Arnaud Morvan'
__date__ = 'October 2014'
__copyright__ = '(C) 2014, Arnaud Morvan'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os

from collections import OrderedDict

from qgis.PyQt import uic
from qgis.PyQt.QtGui import QBrush
from qgis.PyQt.QtWidgets import QComboBox, QHeaderView, QLineEdit, QSpacerItem, QMessageBox, QSpinBox, QStyledItemDelegate
from qgis.PyQt.QtCore import QItemSelectionModel, QAbstractTableModel, QModelIndex, QVariant, Qt, pyqtSlot

from qgis.core import (QgsExpression,
                       QgsProject,
                       QgsApplication,
                       QgsProcessingUtils)
from qgis.gui import QgsFieldExpressionWidget

from processing.gui.wrappers import WidgetWrapper, DIALOG_STANDARD, DIALOG_MODELER

pluginPath = os.path.dirname(__file__)
WIDGET, BASE = uic.loadUiType(
    os.path.join(pluginPath, 'widgetFieldsMapping.ui'))


class FieldsMappingModel(QAbstractTableModel):

    fieldTypes = OrderedDict([
        (QVariant.Int, "Integer"),
        (QVariant.Double, "Double"),
        (QVariant.String, "String"),
        (QVariant.DateTime, "Date"),
        (QVariant.LongLong, "Double"),
        (QVariant.Date, "Date")])

    columns = [
        {'name': 'name', 'type': QVariant.String},
        {'name': 'type', 'type': QVariant.Type},
        {'name': 'length', 'type': QVariant.Int},
        {'name': 'precision', 'type': QVariant.Int},
        # {'name': 'comment', 'type': QVariant.String},
        {'name': 'expression', 'type': QgsExpression}]

    def __init__(self, parent=None):
        super(FieldsMappingModel, self).__init__(parent)
        self._mapping = []
        self._errors = []
        self._layer = None

    def mapping(self):
        return self._mapping

    def setMapping(self, value):
        self.beginResetModel()
        self._mapping = value
        self.testAllExpressions()
        self.endResetModel()

    def testAllExpressions(self):
        self._errors = [None for i in range(len(self._mapping))]
        for row in range(len(self._mapping)):
            self.testExpression(row)

    def testExpression(self, row):
        self._errors[row] = None
        field = self._mapping[row]
        exp_context = self.contextGenerator().createExpressionContext()

        expression = QgsExpression(field['expression'])
        expression.prepare(exp_context)
        if expression.hasParserError():
            self._errors[row] = expression.parserErrorString()
            return

        # test evaluation on the first feature
        if self._layer is None:
            return
        for feature in self._layer.getFeatures():
            exp_context.setFeature(feature)
            exp_context.lastScope().setVariable("row_number", 1)
            expression.evaluate(exp_context)
            if expression.hasEvalError():
                self._errors[row] = expression.evalErrorString()
            break

    def contextGenerator(self):
        if self._layer:
            return self._layer
        return QgsProject.instance()

    def layer(self):
        return self._layer

    def setLayer(self, layer):
        self._layer = layer
        self.testAllExpressions()

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.columns)

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return self._mapping.__len__()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self.columns[section]['name'].title()
            if orientation == Qt.Vertical:
                return section

    def flags(self, index):
        flags = (Qt.ItemIsSelectable |
                 Qt.ItemIsEditable |
                 Qt.ItemIsEnabled)

        return Qt.ItemFlags(flags)

    def data(self, index, role=Qt.DisplayRole):
        column = index.column()

        if role == Qt.DisplayRole:
            field = self._mapping[index.row()]
            column_def = self.columns[column]
            value = field[column_def['name']]

            fieldType = column_def['type']
            if fieldType == QVariant.Type:
                if value == QVariant.Invalid:
                    return ''
                return self.fieldTypes[value]
            return value

        if role == Qt.EditRole:
            field = self._mapping[index.row()]
            column_def = self.columns[column]
            value = field[column_def['name']]
            return value

        if role == Qt.TextAlignmentRole:
            fieldType = self.columns[column]['type']
            if fieldType in [QVariant.Int]:
                hAlign = Qt.AlignRight
            else:
                hAlign = Qt.AlignLeft
            return hAlign + Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            column_def = self.columns[column]
            if column_def['name'] == 'expression':
                brush = QBrush()
                if self._errors[index.row()]:
                    brush.setColor(Qt.red)
                else:
                    brush.setColor(Qt.black)
                return brush

        if role == Qt.ToolTipRole:
            column_def = self.columns[column]
            if column_def['name'] == 'expression':
                return self._errors[index.row()]

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole:
            field = self._mapping[index.row()]
            column = index.column()
            column_def = self.columns[column]
            field[column_def['name']] = value
            if column_def['name'] == 'expression':
                self.testExpression(index.row())
            self.dataChanged.emit(index, index)
        return True

    def insertRows(self, row, count, index=QModelIndex()):
        self.beginInsertRows(index, row, row + count - 1)

        for i in range(count):
            field = self.newField()
            self._mapping.insert(row + i, field)
            self._errors.insert(row + i, None)
            self.testExpression(row)

        self.endInsertRows()
        return True

    def removeRows(self, row, count, index=QModelIndex()):
        self.beginRemoveRows(index, row, row + count - 1)

        for i in range(row + count - 1, row + 1):
            self._mapping.pop(i)
            self._errors.pop(i)

        self.endRemoveRows()
        return True

    def newField(self, field=None):
        if field is None:
            return {'name': '',
                    'type': QVariant.Invalid,
                    'length': 0,
                    'precision': 0,
                    'expression': ''}

        return {'name': field.name(),
                'type': field.type(),
                'length': field.length(),
                'precision': field.precision(),
                'expression': QgsExpression.quotedColumnRef(field.name())}

    def loadLayerFields(self, layer):
        self.beginResetModel()

        self._mapping = []
        if layer is not None:
            dp = layer.dataProvider()
            for field in dp.fields():
                self._mapping.append(self.newField(field))
        self.testAllExpressions()

        self.endResetModel()


class FieldDelegate(QStyledItemDelegate):

    def __init__(self, parent=None):
        super(FieldDelegate, self).__init__(parent)

    def createEditor(self, parent, option, index):
        column = index.column()

        fieldType = FieldsMappingModel.columns[column]['type']
        if fieldType == QVariant.Type:
            editor = QComboBox(parent)
            for key, text in list(FieldsMappingModel.fieldTypes.items()):
                editor.addItem(text, key)

        elif fieldType == QgsExpression:
            editor = QgsFieldExpressionWidget(parent)
            editor.setLayer(index.model().layer())
            editor.registerExpressionContextGenerator(index.model().contextGenerator())
            editor.fieldChanged.connect(self.on_expression_fieldChange)

        else:
            editor = QStyledItemDelegate.createEditor(self, parent, option, index)

        editor.setAutoFillBackground(True)
        return editor

    def setEditorData(self, editor, index):
        if not editor:
            return

        column = index.column()
        value = index.model().data(index, Qt.EditRole)

        fieldType = FieldsMappingModel.columns[column]['type']
        if fieldType == QVariant.Type:
            editor.setCurrentIndex(editor.findData(value))

        elif fieldType == QgsExpression:
            editor.setField(value)

        else:
            QStyledItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if not editor:
            return

        column = index.column()

        fieldType = FieldsMappingModel.columns[column]['type']
        if fieldType == QVariant.Type:
            value = editor.currentData()
            if value is None:
                value = QVariant.Invalid
            model.setData(index, value)

        elif fieldType == QgsExpression:
            (value, isExpression, isValid) = editor.currentField()
            if isExpression is True:
                model.setData(index, value)
            else:
                model.setData(index, QgsExpression.quotedColumnRef(value))

        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def on_expression_fieldChange(self, fieldName):
        self.commitData.emit(self.sender())


class FieldsMappingPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(FieldsMappingPanel, self).__init__(parent)
        self.setupUi(self)

        self.addButton.setIcon(QgsApplication.getThemeIcon("/mActionNewAttribute.svg"))
        self.deleteButton.setIcon(QgsApplication.getThemeIcon('/mActionDeleteAttribute.svg'))
        self.upButton.setIcon(QgsApplication.getThemeIcon('/mActionArrowUp.svg'))
        self.downButton.setIcon(QgsApplication.getThemeIcon('/mActionArrowDown.svg'))
        self.resetButton.setIcon(QgsApplication.getThemeIcon('/mIconClearText.svg'))

        self.model = FieldsMappingModel()
        self.fieldsView.setModel(self.model)

        self.model.rowsInserted.connect(self.on_model_rowsInserted)
        self.fieldsView.setItemDelegate(FieldDelegate())

        self.updateLayerCombo()

    def setLayer(self, layer):
        self.model.setLayer(layer)
        if self.model.rowCount() == 0:
            self.on_resetButton_clicked()
        else:
            dlg = QMessageBox(self)
            dlg.setText("Do you want to reset the field mapping?")
            dlg.setStandardButtons(
                QMessageBox.StandardButtons(QMessageBox.Yes |
                                            QMessageBox.No))
            dlg.setDefaultButton(QMessageBox.No)
            if dlg.exec_() == QMessageBox.Yes:
                self.on_resetButton_clicked()

    def value(self):
        return self.model.mapping()

    def setValue(self, value):
        self.model.setMapping(value)

    @pyqtSlot(bool, name='on_addButton_clicked')
    def on_addButton_clicked(self, checked=False):
        rowCount = self.model.rowCount()
        self.model.insertRows(rowCount, 1)
        index = self.model.index(rowCount, 0)
        self.fieldsView.selectionModel().select(index,
                                                QItemSelectionModel.SelectionFlags(QItemSelectionModel.Clear |
                                                                                   QItemSelectionModel.Select |
                                                                                   QItemSelectionModel.Current |
                                                                                   QItemSelectionModel.Rows))
        self.fieldsView.scrollTo(index)
        self.fieldsView.scrollTo(index)

    @pyqtSlot(bool, name='on_deleteButton_clicked')
    def on_deleteButton_clicked(self, checked=False):
        sel = self.fieldsView.selectionModel()
        if not sel.hasSelection():
            return

        indexes = sel.selectedRows()
        for index in indexes:
            self.model.removeRows(index.row(), 1)

    @pyqtSlot(bool, name='on_upButton_clicked')
    def on_upButton_clicked(self, checked=False):
        sel = self.fieldsView.selectionModel()
        if not sel.hasSelection():
            return

        row = sel.selectedRows()[0].row()
        if row == 0:
            return

        self.model.insertRows(row - 1, 1)

        for column in range(self.model.columnCount()):
            srcIndex = self.model.index(row + 1, column)
            dstIndex = self.model.index(row - 1, column)
            value = self.model.data(srcIndex, Qt.EditRole)
            self.model.setData(dstIndex, value, Qt.EditRole)

        self.model.removeRows(row + 1, 1)

        sel.select(self.model.index(row - 1, 0),
                   QItemSelectionModel.SelectionFlags(QItemSelectionModel.Clear |
                                                      QItemSelectionModel.Select |
                                                      QItemSelectionModel.Current |
                                                      QItemSelectionModel.Rows))

    @pyqtSlot(bool, name='on_downButton_clicked')
    def on_downButton_clicked(self, checked=False):
        sel = self.fieldsView.selectionModel()
        if not sel.hasSelection():
            return

        row = sel.selectedRows()[0].row()
        if row == self.model.rowCount() - 1:
            return

        self.model.insertRows(row + 2, 1)

        for column in range(self.model.columnCount()):
            srcIndex = self.model.index(row, column)
            dstIndex = self.model.index(row + 2, column)
            value = self.model.data(srcIndex, Qt.EditRole)
            self.model.setData(dstIndex, value, Qt.EditRole)

        self.model.removeRows(row, 1)

        sel.select(self.model.index(row + 1, 0),
                   QItemSelectionModel.SelectionFlags(QItemSelectionModel.Clear |
                                                      QItemSelectionModel.Select |
                                                      QItemSelectionModel.Current |
                                                      QItemSelectionModel.Rows))

    @pyqtSlot(bool, name='on_resetButton_clicked')
    def on_resetButton_clicked(self, checked=False):
        self.model.loadLayerFields(self.model.layer())
        self.openPersistentEditor(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1,
                             self.model.columnCount() - 1))
        self.resizeColumns()

    def resizeColumns(self):
        header = self.fieldsView.horizontalHeader()
        header.resizeSections(QHeaderView.ResizeToContents)
        for section in range(header.count()):
            size = header.sectionSize(section)
            fieldType = FieldsMappingModel.columns[section]['type']
            if fieldType == QgsExpression:
                header.resizeSection(section, size + 100)
            else:
                header.resizeSection(section, size + 20)

    def openPersistentEditor(self, topLeft, bottomRight):
        return
        for row in range(topLeft.row(), bottomRight.row() + 1):
            for column in range(topLeft.column(), bottomRight.column() + 1):
                self.fieldsView.openPersistentEditor(self.model.index(row, column))
                editor = self.fieldsView.indexWidget(self.model.index(row, column))
                if isinstance(editor, QLineEdit):
                    editor.deselect()
                if isinstance(editor, QSpinBox):
                    lineEdit = editor.findChild(QLineEdit)
                    lineEdit.setAlignment(Qt.AlignRight or Qt.AlignVCenter)
                    lineEdit.deselect()

    def on_model_rowsInserted(self, parent, start, end):
        self.openPersistentEditor(
            self.model.index(start, 0),
            self.model.index(end, self.model.columnCount() - 1))

    def updateLayerCombo(self):
        layers = QgsProcessingUtils.compatibleVectorLayers(QgsProject.instance())
        for layer in layers:
            self.layerCombo.addItem(layer.name(), layer)

    @pyqtSlot(bool, name='on_loadLayerFieldsButton_clicked')
    def on_loadLayerFieldsButton_clicked(self, checked=False):
        layer = self.layerCombo.currentData()
        if layer is None:
            return
        self.model.loadLayerFields(layer)


class FieldsMappingWidgetWrapper(WidgetWrapper):

    def createWidget(self):
        return FieldsMappingPanel()

    def postInitialize(self, wrappers):
        for wrapper in wrappers:
            if wrapper.param.name == self.param.parent:
                wrapper.widgetValueHasChanged.connect(self.parentLayerChanged)
                break
        layers = QgsProcessingUtils.compatibleVectorLayers(QgsProject.instance())
        if len(layers) > 0:
            # as first item in combobox is already selected
            self.widget.setLayer(layers[0])

        # remove exiting spacers to get FieldsMappingPanel fully expanded
        if self.dialogType in (DIALOG_STANDARD, DIALOG_MODELER):
            layout = self.widget.parent().layout()
            spacer = layout.itemAt(layout.count() - 1)
            if isinstance(spacer, QSpacerItem):
                layout.removeItem(spacer)

    def parentLayerChanged(self):
        self.widget.setLayer(self.sender().value())

    def setValue(self, value):
        self.widget.setValue(value)

    def value(self):
        return self.widget.value()
