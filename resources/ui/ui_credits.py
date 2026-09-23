# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'credits.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel, QScrollArea,
    QSizePolicy, QTextBrowser, QWidget)

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(743, 500)
        Form.setMinimumSize(QSize(500, 500))
        self.gridLayout = QGridLayout(Form)
        self.gridLayout.setObjectName(u"gridLayout")
        self.scrollArea = QScrollArea(Form)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaW = QWidget()
        self.scrollAreaW.setObjectName(u"scrollAreaW")
        self.scrollAreaW.setGeometry(QRect(0, 0, 723, 458))
        self.gridLayout_2 = QGridLayout(self.scrollAreaW)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.Creditos = QTextBrowser(self.scrollAreaW)
        self.Creditos.setObjectName(u"Creditos")
        self.Creditos.setOpenExternalLinks(True)

        self.gridLayout_2.addWidget(self.Creditos, 0, 0, 1, 1)

        self.scrollArea.setWidget(self.scrollAreaW)

        self.gridLayout.addWidget(self.scrollArea, 1, 0, 1, 1)

        self.Title = QLabel(Form)
        self.Title.setObjectName(u"Title")

        self.gridLayout.addWidget(self.Title, 0, 0, 1, 1)


        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.Title.setText(QCoreApplication.translate("Form", u"CREDITOS", None))
    # retranslateUi

