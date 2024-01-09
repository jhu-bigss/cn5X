# -*- coding: utf-8 -*-

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
'                                                                         '
' Copyright 2018-2022 Gauthier Brière (gauthier.briere "at" gmail.com)    '
'                                                                         '
' This file is part of cn5X++                                             '
'                                                                         '
' cn5X++ is free software: you can redistribute it and/or modify it       '
'  under the terms of the GNU General Public License as published by      '
' the Free Software Foundation, either version 3 of the License, or       '
' (at your option) any later version.                                     '
'                                                                         '
' cn5X++ is distributed in the hope that it will be useful, but           '
' WITHOUT ANY WARRANTY; without even the implied warranty of              '
' MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           '
' GNU General Public License for more details.                            '
'                                                                         '
' You should have received a copy of the GNU General Public License       '
' along with this program.  If not, see <http://www.gnu.org/licenses/>.   '
'                                                                         '
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

import sys, time, random
import threading
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt, QCoreApplication, QObject, pyqtSignal, pyqtSlot, QSettings, QEvent, QThread, QEventLoop
from PyQt5.QtGui import QKeyEvent
from gcodeQLineEdit import gcodeQLineEdit
###from PyQt5.QtTest import QTest
from cn5X_config import *

import qwHorloge

class horlogeUpdater(QObject):
  ''' Objet pour mise à jour horloge durant la mise en veille '''

  def __init__(self, horloge):
    QObject.__init__(self)
    self.horloge = horloge
    self.horlogeUi = horloge.ui
    self.deuxPoints = False
    self.updateTimer = QtCore.QTimer()
    self.updateTimer.setInterval(500) # 1/2 seconde
    self.updateTimer.timeout.connect(self.updateHeure)
    self.moveTimer = QtCore.QTimer()
    self.moveTimer.setInterval(17) # ~60 fois par seconde
    self.moveTimer.timeout.connect(self.moveHorloge)

    # Déplacements aléatoires entre minMove et maxMove pixels
    self.minMove = 2
    self.maxMove = 5
    random.seed()
    self.deplacementX = random.randint(self.minMove, self.maxMove)
    if random.randint(0, 1) == 0:
      self.deplacementX = -self.deplacementX
    self.deplacementY = random.randint(self.minMove, self.maxMove)
    if random.randint(0, 1) == 0:
      self.deplacementY = -self.deplacementY


  def start(self):
    self.updateTimer.start()
    self.moveTimer.start()


  def quit(self):
    self.updateTimer.stop()
    self.moveTimer.stop()


  def updateHeure(self):
    ''' Mise à l'heure de l'horloge '''
    H = time.strftime("%H")
    M = time.strftime("%M")
    S = time.strftime("%S")
    # Heures : Minutes avec clignottement des ':' 1 fois sur 2
    if self.deuxPoints:
      self.horlogeUi.lblHM.setText("{} {}".format(H, M))
      self.deuxPoints = False
    else:
      self.horlogeUi.lblHM.setText("{}:{}".format(H, M))
      self.deuxPoints = True
    # Secondes
    self.horlogeUi.lblS.setText("{}".format(S))


  def moveHorloge(self):
    ''' Déplacement de l'horloge sur l'écran '''
    
    newX = self.horloge.pos().x() + self.deplacementX
    if self.deplacementX > 0:
      if newX + self.horloge.width() > self.horloge.parentWidget().width():
        # On a atteind le bord de l'écran, on repart dans l'autre sens avec une autre vitesse
        self.deplacementX = -random.randint(self.minMove, self.maxMove)
        newX = self.horloge.pos().x() + self.deplacementX
    else: # self.deplacementX < 0
      if newX < 0:
        # On a atteind le bord de l'écran, on repart dans l'autre sens avec une autre vitesse
        self.deplacementX = random.randint(self.minMove, self.maxMove)
        newX = self.horloge.pos().x() + self.deplacementX

    newY = self.horloge.pos().y() + self.deplacementY
    if self.deplacementY> 0:
      if newY + self.horloge.height() > self.horloge.parentWidget().height():
        # On a atteind le bord de l'écran, on repart dans l'autre sens avec une autre vitesse
        self.deplacementY = -random.randint(self.minMove, self.maxMove)
        newY = self.horloge.pos().y() + self.deplacementY
    else: # self.deplacementY < 0
      if newY < 0:
        # On a atteind le bord de l'écran, on repart dans l'autre sens avec une autre vitesse
        self.deplacementY = random.randint(self.minMove, self.maxMove)
        newY = self.horloge.pos().y() + self.deplacementY

    self.horloge.move(newX, newY)    


class qwBlackScreen(QtWidgets.QWidget):
  ''' Widget personalise construisant un écran noir
  cet écran disparait en cas de click ou d'appuis sur une touche '''

  def __init__(self, parent=None):
    super().__init__()
    
    self.__settings = QSettings(QSettings.NativeFormat, QSettings.UserScope, ORG_NAME, APP_NAME)

    # Initialise le widget écran noir
    self.parent = parent
    self.blackScreen = QtWidgets.QWidget(parent)
    self.blackScreen.setStyleSheet("background-color: black")
    self.blackScreen.setCursor(Qt.BlankCursor)
    self.blackScreen.move(0, 0)
    self.blackScreen.resize(parent.width(), parent.height())
    
    # widget horloge
    self.blackScreen.horloge  = QtWidgets.QWidget(self.blackScreen)
    self.blackScreen.horloge.setStyleSheet("background-color: None")
    self.blackScreen.horloge.ui = qwHorloge.Ui_qwHorloge()
    self.blackScreen.horloge.ui.setupUi(self.blackScreen.horloge)
    # redimentionne l'horloge en fonction de la police de caractères
    fontSize = self.__settings.value("screenSaverClockFontSize", 72, type=int)
    print(fontSize)
    fontHM = self.blackScreen.horloge.ui.lblFondHM.font()
    fontS  = self.blackScreen.horloge.ui.lblFondS.font()
    fontHM.setPointSize(fontSize)
    fontS.setPointSize(int(fontSize/2))
    self.blackScreen.horloge.ui.lblFondHM.setFont(fontHM)
    self.blackScreen.horloge.ui.lblHM.setFont(fontHM)
    self.blackScreen.horloge.ui.lblFondS.setFont(fontS)
    self.blackScreen.horloge.ui.lblS.setFont(fontS)
    self.resizeClock()
    self.blackScreen.horloge.setVisible(False)
    self.updateHorloge = horlogeUpdater(self.blackScreen.horloge)
    
    # L'écran noir est masqué au départ
    self.blackScreen.setVisible(False)


  def blackScreen_show(self):
    # redimentionne le cache noir à la taille de la fenêtre
    self.blackScreen.resize(self.parent.width(), self.parent.height())
    if self.parent.screenSaverClock:
      # place l'horloge au millieu
      self.blackScreen.horloge.move(int((self.blackScreen.width()-self.blackScreen.horloge.width())/2), int((self.blackScreen.height()-self.blackScreen.horloge.height())/2))
      # horloge visible
      self.blackScreen.horloge.setVisible(True)
      # lance la mise à jour de l'horloge
      self.updateHorloge.start()
    else:
      # horloge invisible
      self.blackScreen.horloge.setVisible(False)
    # rend le tout visible
    self.blackScreen.setVisible(True)


  def resizeClock(self):
    ''' Ajuste la dimention de l'horloge en fonction de la police de caractères '''
    self.blackScreen.horloge.ui.lblFondHM.adjustSize()
    self.blackScreen.horloge.ui.lblHM.adjustSize()
    self.blackScreen.horloge.ui.lblFondS.adjustSize()
    self.blackScreen.horloge.ui.lblS.adjustSize()
    self.blackScreen.horloge.ui.lblFondS.move(self.blackScreen.horloge.ui.lblHM.width(), self.blackScreen.horloge.ui.lblHM.height() - self.blackScreen.horloge.ui.lblS.height())
    self.blackScreen.horloge.ui.lblS.move(self.blackScreen.horloge.ui.lblHM.width(), self.blackScreen.horloge.ui.lblHM.height() - self.blackScreen.horloge.ui.lblS.height())
    self.blackScreen.horloge.adjustSize()
    

  def blackScreen_hide(self):
    self.blackScreen.setVisible(False)
    if self.parent.screenSaverClock:
      self.updateHorloge.quit()


  def isVisible(self):
    return self.blackScreen.isVisible()

