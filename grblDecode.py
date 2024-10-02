# -*- coding: UTF-8 -*-

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
'                                                                         '
' Copyright 2018-2024 Gauthier Brière (gauthier.briere "at" gmail.com)    '
'                                                                         '
' This file is part of cn5X++                                             '
'                                                                         '
' cn5X++ is free software: you can redistribute it and/or modify it       '
' under the terms of the GNU General Public License as published by       '
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

from PyQt6 import QtGui
from PyQt6 import QtWidgets, QtCore #, QtGui,
from PyQt6.QtCore import QCoreApplication, QObject, QEventLoop, pyqtSignal, pyqtSlot

from grblError import grblError
from speedOverrides import *
from grblCom import grblCom
from cn5X_beep import cn5XBeeper


class grblDecode(QObject):
  '''
  Classe de decodage des reponses de GRBL :
  - Decode les reponses de Grbl,
  - Met a jour l'interface graphique.
  - Stocke des valeurs des parametres decodes.
  '''

  sig_log     = pyqtSignal(int, str) # Message de fonctionnement du composant

  def __init__(self, ui, log, grbl: grblCom, beeper: cn5XBeeper, arretUrgence):
    super().__init__()
    self.ui = ui
    self.log = log
    self.__grblCom   = grbl
    self.__nbAxis    = DEFAULT_NB_AXIS
    self.__axisNames = DEFAULT_AXIS_NAMES
    self.__validMachineState = [
      GRBL_STATUS_IDLE,
      GRBL_STATUS_RUN,
      GRBL_STATUS_HOLD0,
      GRBL_STATUS_HOLD1,
      GRBL_STATUS_JOG,
      GRBL_STATUS_ALARM,
      GRBL_STATUS_DOOR0,
      GRBL_STATUS_DOOR1,
      GRBL_STATUS_DOOR2,
      GRBL_STATUS_DOOR3,
      GRBL_STATUS_CHECK,
      GRBL_STATUS_HOME,
      GRBL_STATUS_SLEEP
    ]
    self.__validG5x = ["G28", "G30", "G54","G55","G56","G57","G58","G59", "G92"]
    self.__G5actif = 54
    self.__G5x={
      28: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
      30: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
      54: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
      55: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
      56: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
      57: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
      58: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
      59: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
      92: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    }
    self.__toolLengthOffset = 0
    self.__probeCoord = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    self.__wco        = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    self.__wpos       = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    self.__mpos       = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    self.__offsetG92  = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    self.__offsetG5x  = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    self.__etatArrosage = "M9"
    self.__etatSpindle  = "M5"
    self.__etatMachine = None
    self.__digitalStatus = [False, False, False, False, False, False, False, False]
    self.__getNextStatusOutput = False
    self.__getNextGCodeParams = False
    self.__getNextGCodeState = False
    self.__getNextProbe = False
    self.__grblAlarm = [
      [0, self.tr("No Alarm."), ""],
      [1, self.tr("Hard limit"),         self.tr("Hard limit has been triggered. Machine position is likely lost due to sudden halt. Re-homing is highly recommended.")],
      [2, self.tr("Soft limit"),         self.tr("Soft limit alarm. G-code motion target exceeds machine travel. Machine position retained. Alarm may be safely unlocked.")],
      [3, self.tr("Abort during cycle"), self.tr("Reset while in motion. Machine position is likely lost due to sudden halt. Re-homing is highly recommended.")],
      [4, self.tr("Probe fail"),         self.tr("Probe fail. Probe is not in the expected initial state before starting probe cycle when G38.2 and G38.3 is not triggered and G38.4 and G38.5 is triggered.")],
      [5, self.tr("Probe fail"),         self.tr("Probe fail. Probe did not contact the workpiece within the programmed travel for G38.2 and G38.4.")],
      [6, self.tr("Homing fail"),        self.tr("Homing fail. The active homing cycle was reset.")],
      [7, self.tr("Homing fail"),        self.tr("Homing fail. Safety door was opened during homing cycle.")],
      [8, self.tr("Homing fail"),        self.tr("Homing fail. Pull off travel failed to clear limit switch. Try increasing pull-off setting or check wiring.")],
      [9, self.tr("Homing fail"),        self.tr("Homing fail. Could not find limit switch within search distances. Try increasing max travel, decreasing pull-off distance, or check wiring.")]
    ]
    self.__distanceMode = "G90" # G90 ou G91 par défaut, Grbl est en G90
    self.__settings = {} # Utilisation d'un dictionnaire pour stocker les
                         # settings de Grbl sous la forme { Num: "Valeur" }
    
    self.beeper = beeper
    self.probeStatus = False
    self.arretUrgence = arretUrgence
    
  def getG5actif(self):
    return "G{}".format(self.__G5actif)


  def setNbAxis(self, val: int):
    if val < 3 or val > 6:
      raise RuntimeError(self.tr("The number of axis should be between 3 and 6!"))
    self.__nbAxis = val


  def getNextStatus(self):
    self.__getNextStatusOutput = True


  def getNextGCodeParams(self):
    self.__getNextGCodeParams = True


  def getNextGCodeState(self):
    self.__getNextGCodeState = True


  def getNextProbe(self):
    self.__getNextProbe = True


  def decodeGrblStatus(self, grblOutput):

    if grblOutput[0] != "<" or grblOutput[-1] != ">":
      return self.tr("grblDecode.py.decodeGrblStatus():error ! \n[{}] Incorrect status.").format(grblOutput)

    # Affiche la chaine complette dans la barrs de status self.__statusText
    self.ui.statusBar.showMessage("{} + {}".format(self.__grblCom.grblVersion(), grblOutput))

    flagPn = False
    flagOv = False
    flagDigital = False
    tblDecode = grblOutput[1:-1].split("|")
    for D in tblDecode:
      if D in self.__validMachineState:
        if D != self.__etatMachine:
          self.ui.lblEtat.setText(D)
          self.__etatMachine = D
          if D == GRBL_STATUS_IDLE:
            if self.ui.btnStart.getButtonStatus():    self.ui.btnStart.setButtonStatus(False)
            if self.ui.btnPause.getButtonStatus():    self.ui.btnPause.setButtonStatus(False)
            if not self.ui.btnStop.getButtonStatus(): self.ui.btnStop.setButtonStatus(True)
            self.ui.lblEtat.setToolTip(self.tr("Grbl is waiting for work."))
            if self.ui.btnG28.getButtonStatus():      self.ui.btnG28.setButtonStatus(False)
            if self.ui.btnG30.getButtonStatus():      self.ui.btnG30.setButtonStatus(False)
          elif D ==GRBL_STATUS_HOLD0:
            if self.ui.btnStart.getButtonStatus():    self.ui.btnStart.setButtonStatus(False)
            if not self.ui.btnPause.getButtonStatus():    self.ui.btnPause.setButtonStatus(True)
            if self.ui.btnStop.getButtonStatus(): self.ui.btnStop.setButtonStatus(False)
            self.ui.lblEtat.setToolTip(self.tr("Hold complete. Ready to resume."))
          elif D ==GRBL_STATUS_HOLD1:
            if self.ui.btnStart.getButtonStatus():    self.ui.btnStart.setButtonStatus(False)
            if not self.ui.btnPause.getButtonStatus():    self.ui.btnPause.setButtonStatus(True)
            if self.ui.btnStop.getButtonStatus(): self.ui.btnStop.setButtonStatus(False)
            self.ui.lblEtat.setToolTip(self.tr("Hold in-progress. Reset will throw an alarm."))
          elif D =="Door:0":
            self.ui.lblEtat.setToolTip(self.tr("Door closed. Ready to resume."))
          elif D =="Door:1":
            self.ui.lblEtat.setToolTip(self.tr("Machine stopped. Door still ajar. Can't resume until closed."))
          elif D =="Door:2":
            self.ui.lblEtat.setToolTip(self.tr("Door opened. Hold (or parking retract) in-progress. Reset will throw an alarm."))
          elif D =="Door:3":
            self.ui.lblEtat.setToolTip(self.tr("Door closed and resuming. Restoring from park, if applicable. Reset will throw an alarm."))
          elif D == GRBL_STATUS_RUN:
            if not self.ui.btnStart.getButtonStatus():    self.ui.btnStart.setButtonStatus(True)
            if self.ui.btnPause.getButtonStatus():    self.ui.btnPause.setButtonStatus(False)
            if self.ui.btnStop.getButtonStatus(): self.ui.btnStop.setButtonStatus(False)
            self.ui.lblEtat.setToolTip(self.tr("Grbl running..."))
          elif D == GRBL_STATUS_JOG:
            self.ui.lblEtat.setToolTip(self.tr("Grbl jogging..."))
          elif D == GRBL_STATUS_ALARM:
            self.ui.lblEtat.setToolTip(self.tr("Grbl Alarm! see Grbl communication."))
          elif D == GRBL_STATUS_HOME:
            self.ui.lblEtat.setToolTip(self.tr("Grbl homing, wait for finish..."))
          else:
            self.ui.lblEtat.setToolTip("")

      # Machine position MPos ($10=0 ou 2) ou WPos ($10=1 ou 3)?
      elif D[:5] == "MPos:":
        # Mémorise la dernière position machine reçue
        tblPos = D[5:].split(",")
        try:
          for I in range(len(tblPos)):
            self.__mpos[I] = float(tblPos[I])
            self.__wpos[I] = float(tblPos[I]) - self.__wco[I]
        except  ValueError as e:
          self.sig_log.emit(logSeverity.error.value, self.tr("grblDecode.decodeGrblStatus(MPos): ValueError: {}, grblOutput = {}".format(str(e), grblOutput)))
        else:
          if not self.ui.mnu_MPos.isChecked():
            self.ui.mnu_MPos.setChecked(True)
          if self.ui.mnu_WPos.isChecked():
            self.ui.mnu_WPos.setChecked(False)
          tblPos = D[5:].split(",")
          self.ui.lblPosX.setText('{:+0.3f}'.format(float(tblPos[0]))); self.ui.lblPosX.setToolTip(self.tr("Machine Position (MPos)."))
          self.ui.lblPosY.setText('{:+0.3f}'.format(float(tblPos[1]))); self.ui.lblPosY.setToolTip(self.tr("Machine Position (MPos)."))
          self.ui.lblPosZ.setText('{:+0.3f}'.format(float(tblPos[2]))); self.ui.lblPosZ.setToolTip(self.tr("Machine Position (MPos)."))
          if self.__nbAxis > 3:
            self.ui.lblPosA.setText('{:+0.3f}'.format(float(tblPos[3]))); self.ui.lblPosA.setToolTip(self.tr("Machine Position (MPos)."))
          else:
            self.ui.lblPosA.setText("-")
          if self.__nbAxis > 4:
            self.ui.lblPosB.setText('{:+0.3f}'.format(float(tblPos[4]))); self.ui.lblPosB.setToolTip(self.tr("Machine Position (MPos)."))
          else:
            self.ui.lblPosB.setText("-")
          if self.__nbAxis > 5:
            self.ui.lblPosC.setText('{:+0.3f}'.format(float(tblPos[5]))); self.ui.lblPosB.setToolTip(self.tr("Machine Position (MPos)."))
          else:
            self.ui.lblPosC.setText("-")

      elif D[:5] == "WPos:":
        # Mémorise la dernière position de travail reçue
        tblPos = D[5:].split(",")
        try:
          for I in range(len(tblPos)):
            self.__wpos[I] = float(tblPos[I])
            self.__mpos[I] = float(tblPos[I]) + self.__wco[I]
        except  ValueError as e:
          self.sig_log.emit(logSeverity.error.value, self.tr("grblDecode.decodeGrblStatus(WPos): ValueError: {}, grblOutput = {}".format(str(e), grblOutput)))
        else:
        # Met à jour l'interface
          if not self.ui.mnu_WPos.isChecked():
            self.ui.mnu_WPos.setChecked(True)
          if self.ui.mnu_MPos.isChecked():
            self.ui.mnu_MPos.setChecked(False)
          tblPos = D[5:].split(",")
          self.ui.lblPosX.setText('{:+0.3f}'.format(float(tblPos[0]))); self.ui.lblPosX.setToolTip(self.tr("Working Position (WPos)."))
          self.ui.lblPosY.setText('{:+0.3f}'.format(float(tblPos[1]))); self.ui.lblPosY.setToolTip(self.tr("Working Position (WPos)."))
          self.ui.lblPosZ.setText('{:+0.3f}'.format(float(tblPos[2]))); self.ui.lblPosZ.setToolTip(self.tr("Working Position (WPos)."))
          if self.__nbAxis > 3:
            self.ui.lblPosA.setText('{:+0.3f}'.format(float(tblPos[3]))); self.ui.lblPosA.setToolTip(self.tr("Working Position (WPos)."))
          else:
            self.ui.lblPosA.setText("-")
          if self.__nbAxis > 4:
            self.ui.lblPosB.setText('{:+0.3f}'.format(float(tblPos[4]))); self.ui.lblPosB.setToolTip(self.tr("Working Position (WPos)."))
          else:
            self.ui.lblPosB.setText("-")
          if self.__nbAxis > 5:
            self.ui.lblPosC.setText('{:+0.3f}'.format(float(tblPos[5]))); self.ui.lblPosB.setToolTip(self.tr("Working Position (WPos)."))
          else:
            self.ui.lblPosC.setText("-")

      elif D[:4] == "WCO:": # Work Coordinate Offset
        tblPos = D[4:].split(",")
        try:
          for I in range(len(tblPos)):
            self.__wco[I] = float(tblPos[I])
        except  ValueError as e:
          self.sig_log.emit(logSeverity.error.value, self.tr("grblDecode.decodeGrblStatus(WCO): ValueError: {}, grblOutput = {}".format(str(e), grblOutput)))
        else:
          self.ui.lblWcoX.setText('{:+0.3f}'.format(self.__wco[0]))
          self.ui.lblWcoY.setText('{:+0.3f}'.format(self.__wco[1]))
          self.ui.lblWcoZ.setText('{:+0.3f}'.format(self.__wco[2]))
          if self.__nbAxis > 3:
            self.ui.lblWcoA.setText('{:+0.3f}'.format(self.__wco[3]))
          else:
            self.ui.lblWcoA.setText("-")
          if self.__nbAxis > 4:
            self.ui.lblWcoB.setText('{:+0.3f}'.format(self.__wco[4]))
          else:
            self.ui.lblWcoB.setText("-")
          if self.__nbAxis > 5:
            self.ui.lblWcoC.setText('{:+0.3f}'.format(self.__wco[5]))
          else:
            self.ui.lblWcoC.setText("-")

      elif D[:3] == "Bf:": # Buffer State (Bf:15,128)
        tblValue = D[3:].split(",")
        self.ui.progressBufferState.setValue(int(tblValue[0]))
        self.ui.progressBufferState.setMaximum(int(tblValue[1]))
        self.ui.progressBufferState.setToolTip("Buffer stat : " + tblValue[0] + "/" + tblValue[1])

      elif D[:3] == "Ov:": # Override Values for feed, rapids, and spindle
        flagOv = True
        values = D.split(':')[1].split(',')
        # Avance de travail
        if int(self.ui.lblAvancePourcent.text()[:-1]) != int(values[0]):
          adjustFeedOverride(int(values[0]), int(self.ui.lblAvancePourcent.text()[:-1]), self.__grblCom)
        # Avance rapide
        if values[1] == 25:
          self.ui.rbRapid025.setChecked(True)
        if values[1] == 50:
          self.ui.rbRapid050.setChecked(True)
        if values[1] == 25:
          self.ui.rbRapid100.setChecked(True)
        # Ajuste la vitesse de broche
        if int(self.ui.lblBrochePourcent.text()[:-1]) != int(values[2]):
          adjustSpindleOverride(int(values[2]), int(self.ui.lblBrochePourcent.text()[:-1]), self.__grblCom)

      elif D[:3] == "Pn:": # Input Pin State
        flagPn = True
        triggered = D[3:]
        # Affichage voyants d'interface
        for L in ['X', 'Y', 'Z', 'A', 'B', 'C', 'P', 'D', 'H', 'R', 'S']:
          if L in triggered:
            exec("self.ui.cnLed" + L + ".setLedStatus(True)")
          else:
            exec("self.ui.cnLed" + L + ".setLedStatus(False)")
        # Beep lorsque le probe entre en contact
        if 'P' in triggered:
          if not self.probeStatus:
            self.beeper.beep(0.5)#1760, 0.25, 16000)
            self.probeStatus = True
        else:
          if self.probeStatus:
            self.probeStatus = False
        # Si pin reset active, on déclenche l'arrêt d'urgence dans l'interface.
        if 'R' in triggered:
          if not self.arretUrgence():
            self.ui.btnUrgence.click()

      elif D[:2] == "A:": # OverrideAccessory State
        accessoryState = D[2:]
        digitalFind = accessoryState.find("D")
        if digitalFind >=0:
          flagDigital = True
          digitalState = accessoryState[digitalFind+1:]
          # Avec la version 1.2f, ajout du status digital input sur les 4 bits de gauche
          if len(digitalState) == 4:
            # Seulement 4 bits pour les outputs
            if digitalState[3] == "1":
              if not self.__digitalStatus[0]:
                self.ui.btnM64P0.setButtonStatus(True)
                self.__digitalStatus[0] = True
            else:
              if self.__digitalStatus[0]:
                self.ui.btnM64P0.setButtonStatus(False)
                self.__digitalStatus[0] = False
            if digitalState[2] == "1":
              if not self.__digitalStatus[1]:
                self.ui.btnM64P1.setButtonStatus(True)
                self.__digitalStatus[1] = True
            else:
              if self.__digitalStatus[1]:
                self.ui.btnM64P1.setButtonStatus(False)
                self.__digitalStatus[1] = False
            if digitalState[1] == "1":
              if not self.__digitalStatus[2]:
                self.ui.btnM64P2.setButtonStatus(True)
                self.__digitalStatus[2] = True
            else:
              if self.__digitalStatus[2]:
                self.ui.btnM64P2.setButtonStatus(False)
                self.__digitalStatus[2] = False
            if digitalState[0] == "1":
              if not self.__digitalStatus[3]:
                self.ui.btnM64P3.setButtonStatus(True)
                self.__digitalStatus[3] = True
            else:
              if self.__digitalStatus[3]:
                self.ui.btnM64P3.setButtonStatus(False)
                self.__digitalStatus[3] = False
          else: # output + input => 8 bits
            if digitalState[7] == "1":
              if not self.__digitalStatus[0]:
                self.ui.btnM64P0.setButtonStatus(True)
                self.__digitalStatus[0] = True
            else:
              if self.__digitalStatus[0]:
                self.ui.btnM64P0.setButtonStatus(False)
                self.__digitalStatus[0] = False
            if digitalState[6] == "1":
              if not self.__digitalStatus[1]:
                self.ui.btnM64P1.setButtonStatus(True)
                self.__digitalStatus[1] = True
            else:
              if self.__digitalStatus[1]:
                self.ui.btnM64P1.setButtonStatus(False)
                self.__digitalStatus[1] = False
            if digitalState[5] == "1":
              if not self.__digitalStatus[2]:
                self.ui.btnM64P2.setButtonStatus(True)
                self.__digitalStatus[2] = True
            else:
              if self.__digitalStatus[2]:
                self.ui.btnM64P2.setButtonStatus(False)
                self.__digitalStatus[2] = False
            if digitalState[4] == "1":
              if not self.__digitalStatus[3]:
                self.ui.btnM64P3.setButtonStatus(True)
                self.__digitalStatus[3] = True
            else:
              if self.__digitalStatus[3]:
                self.ui.btnM64P3.setButtonStatus(False)
                self.__digitalStatus[3] = False
            if digitalState[3] == "1":
              if not self.__digitalStatus[4]:
                self.ui.cnLedD0.setLedStatus(True)
                self.__digitalStatus[4] = True
            else:
              if self.__digitalStatus[4]:
                self.ui.cnLedD0.setLedStatus(False)
                self.__digitalStatus[4] = False
            if digitalState[2] == "1":
              if not self.__digitalStatus[5]:
                self.ui.cnLedD1.setLedStatus(True)
                self.__digitalStatus[5] = True
            else:
              if self.__digitalStatus[5]:
                self.ui.cnLedD1.setLedStatus(False)
                self.__digitalStatus[5] = False
            if digitalState[1] == "1":
              if not self.__digitalStatus[6]:
                self.ui.cnLedD2.setLedStatus(True)
                self.__digitalStatus[6] = True
            else:
              if self.__digitalStatus[6]:
                self.ui.cnLedD2.setLedStatus(False)
                self.__digitalStatus[6] = False
            if digitalState[0] == "1":
              if not self.__digitalStatus[7]:
                self.ui.cnLedD3.setLedStatus(True)
                self.__digitalStatus[7] = True
            else:
              if self.__digitalStatus[7]:
                self.ui.cnLedD3.setLedStatus(False)
                self.__digitalStatus[7] = False


      '''
      elif D[:3] == "Ln:": # Line Number
        return D

      elif D[2:] == "F:": # Current Feed and Speed
        return D

      elif D[3:] == "FS:": # Current Feed and Speed
        return D
      '''

    # l'information Accessory State est toujours affichée avec l'info d'Overlay
    # si pas dinformation digitale avec Ov:, c'est qu'ils sont tous off.
    if flagOv and not flagDigital:
      if self.__digitalStatus[0]:
        self.ui.btnM64P0.setButtonStatus(False)
        self.__digitalStatus[0] = False
      if self.__digitalStatus[1]:
        self.ui.btnM64P1.setButtonStatus(False)
        self.__digitalStatus[1] = False
      if self.__digitalStatus[2]:
        self.ui.btnM64P2.setButtonStatus(False)
        self.__digitalStatus[2] = False
      if self.__digitalStatus[3]:
        self.ui.btnM64P3.setButtonStatus(False)
        self.__digitalStatus[3] = False
      if self.__digitalStatus[4]:
        self.ui.cnLedD0.setLedStatus(False)
        self.__digitalStatus[4] = False
      if self.__digitalStatus[5]:
        self.ui.cnLedD1.setLedStatus(False)
        self.__digitalStatus[5] = False
      if self.__digitalStatus[6]:
        self.ui.cnLedD2.setLedStatus(False)
        self.__digitalStatus[6] = False
      if self.__digitalStatus[7]:
        self.ui.cnLedD3.setLedStatus(False)
        self.__digitalStatus[7] = False

    if not flagPn:
      # Eteint toute les leds. Si on a pas trouve la chaine Pn:, c'est que toute les leds sont eteintes.
      for L in ['X', 'Y', 'Z', 'A', 'B', 'C', 'P', 'D', 'H', 'R', 'S']:
        exec("self.ui.cnLed" + L + ".setLedStatus(False)")
      if self.probeStatus:
        self.probeStatus = False


    if self.__getNextStatusOutput:
      self.__getNextStatusOutput = False
      return grblOutput
    else:
      return ""

  def decodeGrblResponse(self, grblOutput):

    if grblOutput == "ok":
      return grblOutput

    elif grblOutput[:6] == "error:":
      errNum = int(float(grblOutput[6:]))
      return self.tr("Grbl error number {}: {},\n{}").format(str(errNum), grblError[errNum][1], grblError[errNum][2])

    elif grblOutput[:6] == "ALARM:":
      alarmNum = int(float(grblOutput[6:]))
      return self.tr("Grbl Alarm number {}: {},\n{}").format(str(alarmNum), self.__grblAlarm[alarmNum][1], self.__grblAlarm[alarmNum][2])

    else:
      return self.tr("Unknown Grbl reply: [{}]").format(grblOutput)


  def errorMessage(self, errNum: int):
    return "error:{}: {},\n{}".format(str(errNum), grblError[errNum][1], grblError[errNum][2])


  def alarmMessage(self, alarmNum: int):
    return "ALARM:{}: {},\n{}".format(str(alarmNum), self.__grblAlarm[alarmNum][1], self.__grblAlarm[alarmNum][2])


  def decodeGrblData(self, grblOutput):

    if grblOutput[:1] == "$": # Setting output
      if grblOutput[:2] == "$N": # startup blocks
        return grblOutput
      else: # Pure setting output
        try:
          settingNum = int(float(grblOutput[1:].split('=')[0]))
          settingVal = grblOutput[1:].split('=')[1]
          self.__settings[settingNum] = settingVal
        except ValueError:
          return grblOutput
        settingInfo = self.grblSetting(settingNum)
        return (grblOutput + " >> " + settingInfo)

    elif grblOutput[:1] == "[" and grblOutput[-1:] == "]":
      ''' Push Messages: '''
      if grblOutput[1:4] in self.__validG5x: # ["G28", "G30", "G54","G55","G56","G57","G58","G59", "G92"]
        '''
        messages indicate the parameter data output from a "$#" (CMD_GRBL_GET_GCODE_PARAMATERS) user query.
        '''
        num=int(grblOutput[2:4])
        values=grblOutput[5:-1].split(",")
        for i in range(6):
          if i < self.__nbAxis:
            self.__G5x[num][i] = float(values[i])
          else:
            self.__G5x[num][i] = float("0")
        if num == self.__G5actif:
          for i in range(len(values)):
            self.__offsetG5x[i] = float(values[i])
          self.ui.lblG5xX.setText('{:+0.3f}'.format(self.__G5x[num][0]))
          self.ui.lblG5xY.setText('{:+0.3f}'.format(self.__G5x[num][1]))
          self.ui.lblG5xZ.setText('{:+0.3f}'.format(self.__G5x[num][2]))
          if self.__nbAxis > 3:
            self.ui.lblG5xA.setText('{:+0.3f}'.format(self.__G5x[num][3]))
          else:
            self.ui.lblG5xA.setText("-")
          if self.__nbAxis > 4:
            self.ui.lblG5xB.setText('{:+0.3f}'.format(self.__G5x[num][4]))
          else:
            self.ui.lblG5xB.setText("-")
          if self.__nbAxis > 5:
            self.ui.lblG5xC.setText('{:+0.3f}'.format(self.__G5x[num][5]))
          else:
            self.ui.lblG5xC.setText("-")
        if num == 92:
          for i in range(len(values)):
            self.__offsetG92[i] = float(values[i])
          self.ui.lblG92X.setText('{:+0.3f}'.format(self.__G5x[num][0]))
          self.ui.lblG92Y.setText('{:+0.3f}'.format(self.__G5x[num][1]))
          self.ui.lblG92Z.setText('{:+0.3f}'.format(self.__G5x[num][2]))
          if self.__nbAxis > 3:
            self.ui.lblG92A.setText('{:+0.3f}'.format(self.__G5x[num][3]))
          else:
            self.ui.lblG92A.setText("-")
          if self.__nbAxis > 4:
            self.ui.lblG92B.setText('{:+0.3f}'.format(self.__G5x[num][4]))
          else:
            self.ui.lblG92B.setText("-")
          if self.__nbAxis > 5:
            self.ui.lblG92C.setText('{:+0.3f}'.format(self.__G5x[num][5]))
          else:
            self.ui.lblG92C.setText("-")
        # renvoie le résultat si $# demandé dans par l'utilisateur
        if self.__getNextGCodeParams:
          return grblOutput

      elif grblOutput[1:5] == "TLO:":
        ''' Tool length offset (for the default z-axis) '''
        self.__toolLengthOffset = float(grblOutput[5:-1])
        self.ui.lblTlo.setText('{:+0.3f}'.format(self.__toolLengthOffset))
        # renvoie le résultat si $# demandé dans par l'utilisateur
        if self.__getNextGCodeParams:
          return grblOutput

      elif grblOutput[1:5] == "PRB:":
        ''' Coordinates of the last probing cycle, suffix :1 => Success '''
        self.__probeCoord = grblOutput[5:-1].split(",")
        # renvoie le résultat si $# demandé dans par l'utilisateur
        if self.__getNextGCodeParams or self.__getNextProbe:
          self.__getNextGCodeParams = False # L'envoi du résultat de $# est complet
          self.__getNextProbe = False
          return grblOutput

      elif grblOutput[:4] == "[GC:":
        '''
        traitement interogation $G : G-code Parser State Message
        [GC:G0 G54 G17 G21 G90 G94 M5 M9 T0 F0 S0]
        '''
        tblGcodeParser = grblOutput[4:-1].split(" ")
        for S in tblGcodeParser:
          if S in ["G54", "G55", "G56", "G57", "G58", "G59"]:
            # Preparation font pour modifier dynamiquement Bold/Normal
            font = QtGui.QFont()
            font.setFamily("LED Calculator")
            font.setPointSize(16)
            font.setWeight(75)
            self.ui.lblOffsetActif.setText("Offset {}".format(S))
            num=int(S[1:])
            if num != self.__G5actif:
              self.__G5actif = num
            for N, lbl in [
              [54, self.ui.lblG54],
              [55, self.ui.lblG55],
              [56, self.ui.lblG56],
              [57, self.ui.lblG57],
              [58, self.ui.lblG58],
              [59, self.ui.lblG59]
            ]:
              if N == num:
                lbl.setStyleSheet("background-color:  rgb(0, 0, 63); color:rgb(248, 255, 192);")
                font.setBold(True)
                lbl.setFont(font)
              else:
                lbl.setStyleSheet("background-color: rgb(248, 255, 192); color: rgb(0, 0, 63);")
                font.setBold(False)
                lbl.setFont(font)
            # Mise à jour des labels dépendant du système de coordonnées actif
            self.updateAxisDefinition()
          
          elif S in ["G17", "G18", "G19"]:
            self.ui.lblPlan.setText(S)
            if S == 'G17': self.ui.lblPlan.setToolTip(self.tr(" Working plane = XY "))
            if S == 'G18': self.ui.lblPlan.setToolTip(self.tr(" Working plane = ZX "))
            if S == 'G19': self.ui.lblPlan.setToolTip(self.tr(" Working plane = YZ "))
          elif S in ["G20", "G21"]:
            self.ui.lblUnites.setText(S)
            if S == 'G20': self.ui.lblUnites.setToolTip(self.tr(" Units = inches "))
            if S == 'G21': self.ui.lblUnites.setToolTip(self.tr(" Units = millimeters "))
          elif S in ["G90", "G91"]:
            self.__distanceMode = S
            self.ui.lblCoord.setText(S)
            if S == 'G90': self.ui.lblCoord.setToolTip(self.tr(" Absolute coordinates move "))
            if S == 'G91': self.ui.lblCoord.setToolTip(self.tr(" Relative coordinates move "))
          elif S in ['G0', 'G1', 'G2', 'G3', 'G38.2', 'G38.3', 'G38.4', 'G38.5']:
            self.ui.lblDeplacements.setText(S)
            if S == 'G0': self.ui.lblDeplacements.setToolTip(self.tr(" Rapid speed move. "))
            if S == 'G1': self.ui.lblDeplacements.setToolTip(self.tr(" Linear (straight line) motion at programed feed rate. "))
            if S == 'G2': self.ui.lblDeplacements.setToolTip(self.tr(" Circular interpolation motion clockwise at programed feed rate. "))
            if S == 'G3': self.ui.lblDeplacements.setToolTip(self.tr(" Circular interpolation motion counter-clockwise at programed feed rate. "))
            if S == 'G38.2': self.ui.lblDeplacements.setToolTip(self.tr(" Probe: probe toward workpiece, stop on contact, signal error if failure. "))
            if S == 'G38.3': self.ui.lblDeplacements.setToolTip(self.tr(" Probe: probe toward workpiece, stop on contact."))
            if S == 'G38.4': self.ui.lblDeplacements.setToolTip(self.tr(" Probe: probe away from workpiece, stop on loss of contact, signal error if failure. "))
            if S == 'G38.5': self.ui.lblDeplacements.setToolTip(self.tr(" Probe: probe away from workpiece, stop on loss of contact. "))
          elif S in ['G93', 'G94']:
            self.ui.lblVitesse.setText(S)
            if S == 'G93': self.ui.lblVitesse.setToolTip(self.tr(" Inverse Time feed mode "))
            if S == 'G94': self.ui.lblVitesse.setToolTip(self.tr(" Units per minute feed mode "))
          elif S in ['M3', 'M4', 'M5']:
            self.ui.lblBroche.setText(S)
            if S == 'M3':
              self.ui.lblBroche.setToolTip(self.tr(" Spindle clockwise at the S speed "))
              if not self.ui.btnSpinM3.getButtonStatus(): self.ui.btnSpinM3.setButtonStatus(True)
              if self.ui.btnSpinM4.getButtonStatus():     self.ui.btnSpinM4.setButtonStatus(False)
              if self.ui.btnSpinM5.getButtonStatus():     self.ui.btnSpinM5.setButtonStatus(False)
              if not self.ui.btnSpinM3.isEnabled(): self.ui.btnSpinM3.setEnabled(True)  # Activation bouton M3
              if self.ui.btnSpinM4.isEnabled(): self.ui.btnSpinM4.setEnabled(False)     # Interdit un changement de sens de rotation direct
              self.__etatSpindle  = "M3"
            if S == 'M4':
              self.ui.lblBroche.setToolTip(self.tr(" Spindle counter-clockwise at the S speed "))
              if self.ui.btnSpinM3.getButtonStatus():     self.ui.btnSpinM3.setButtonStatus(False)
              if not self.ui.btnSpinM4.getButtonStatus(): self.ui.btnSpinM4.setButtonStatus(True)
              if self.ui.btnSpinM5.getButtonStatus():     self.ui.btnSpinM5.setButtonStatus(False)
              if self.ui.btnSpinM3.isEnabled(): self.ui.btnSpinM3.setEnabled(False)     # Interdit un changement de sens de rotation direct
              if not self.ui.btnSpinM4.isEnabled(): self.ui.btnSpinM4.setEnabled(True)  # Activation bouton M4
              self.__etatSpindle  = "M4"
            if S == 'M5':
              self.ui.lblBroche.setToolTip(self.tr(" Spindle stoped "))
              if self.ui.btnSpinM3.getButtonStatus():     self.ui.btnSpinM3.setButtonStatus(False)
              if self.ui.btnSpinM4.getButtonStatus():     self.ui.btnSpinM4.setButtonStatus(False)
              if not self.ui.btnSpinM5.getButtonStatus(): self.ui.btnSpinM5.setButtonStatus(True)
              if not self.ui.btnSpinM3.isEnabled(): self.ui.btnSpinM3.setEnabled(True)  # Activation bouton M3
              if not self.ui.btnSpinM4.isEnabled(): self.ui.btnSpinM4.setEnabled(True)  # Activation bouton M4
              self.__etatSpindle  = "M5"
          elif S in ['M7', 'M8', 'M78', 'M9']:
            self.ui.lblArrosage.setText(S)
            if S == 'M7':
              self.ui.lblArrosage.setToolTip(self.tr(" Mist coolant on "))
              if not self.ui.btnFloodM7.getButtonStatus(): self.ui.btnFloodM7.setButtonStatus(True)
              if self.ui.btnFloodM8.getButtonStatus():     self.ui.btnFloodM8.setButtonStatus(False)
              if self.ui.btnFloodM9.getButtonStatus():     self.ui.btnFloodM9.setButtonStatus(False)
              self.__etatArrosage = "M7"
            if S == 'M8':
              self.ui.lblArrosage.setToolTip(self.tr(" Flood coolant on "))
              if self.ui.btnFloodM7.getButtonStatus():     self.ui.btnFloodM7.setButtonStatus(False)
              if not self.ui.btnFloodM8.getButtonStatus(): self.ui.btnFloodM8.setButtonStatus(True)
              if self.ui.btnFloodM9.getButtonStatus():     self.ui.btnFloodM9.setButtonStatus(False)
              self.__etatArrosage = "M8"
            if S == 'M78':
              self.ui.lblArrosage.setToolTip(self.tr(" Mist + Flood coolant on "))
              if not self.ui.btnFloodM7.getButtonStatus(): self.ui.btnFloodM7.setButtonStatus(True)
              if not self.ui.btnFloodM8.getButtonStatus(): self.ui.btnFloodM8.setButtonStatus(True)
              if self.ui.btnFloodM9.getButtonStatus():     self.ui.btnFloodM9.setButtonStatus(False)
              self.__etatArrosage = "M78"
            if S == 'M9':
              self.ui.lblArrosage.setToolTip(self.tr(" Coolant off "))
              if self.ui.btnFloodM7.getButtonStatus():     self.ui.btnFloodM7.setButtonStatus(False)
              if self.ui.btnFloodM8.getButtonStatus():     self.ui.btnFloodM8.setButtonStatus(False)
              if not self.ui.btnFloodM9.getButtonStatus(): self.ui.btnFloodM9.setButtonStatus(True)
              self.__etatArrosage = "M9"
          elif S[:1] == "T":
            self.ui.lblOutil.setText(S)
            self.ui.lblOutil.setToolTip(self.tr(" Tool number {}").format(S[1:]))
          elif S[:1] == "S":
            self.ui.lblRotation.setText(S)
            self.ui.lblRotation.setToolTip(self.tr(" Spindle speed = {} revolutions per minute").format(S[1:]))
          elif S[:1] == "F":
            self.ui.lblAvance.setText(S)
            self.ui.lblAvance.setToolTip(self.tr(" Feed rate  = ").format(S[1:]))
          else:
            return (self.tr("Unknown G-code Parser status in {} : {}").format(grblOutput, S))
        # renvoie le résultat si $G demandé dans par l'utilisateur
        if self.__getNextGCodeState:
          self.__getNextGCodeState = False
          return grblOutput
      
      elif grblOutput[:5] == "[AXS:":
        # Recupère le nombre d'axes et leurs noms
        self.__nbAxis           = int(grblOutput[1:-1].split(':')[1])
        self.__axisNames        = list(grblOutput[1:-1].split(':')[2])
        if len(self.__axisNames) < self.__nbAxis:
          # Il est posible qu'il y ait moins de lettres que le nombre d'axes si Grbl
          # implémente l'option REPORT_VALUE_FOR_AXIS_NAME_ONCE
          self.__nbAxis = len(self.__axisNames);
        self.updateAxisDefinition()
        return grblOutput
      
      elif grblOutput[:4] == "[D:":
        # Digital status
        return grblOutput

      elif grblOutput[:5] == "[OPT:":
        compilOptions = grblOutput[1:-1].split(':')[1].split(',')[0]
        if 'D' in compilOptions:
          # Digital input actives
          self.ui.frmDigitalIntput.setEnabled(True)
        else:
          # Digital input non actives
          self.ui.frmDigitalIntput.setEnabled(False)

      else:
        # Autre reponse [] ?
        return grblOutput
        
    else:
      # Autre reponse ?
      if grblOutput != "": self.log(logSeverity.info.value, self.tr("Not decoded Grbl reply : [{}]").format(grblOutput))
      return grblOutput


  def get_etatArrosage(self):
    return self.__etatArrosage


  def get_etatSpindle(self):
    return self.__etatSpindle


  def set_etatMachine(self, etat):
      if etat in self.__validMachineState:
        if etat != self.__etatMachine:
          self.ui.lblEtat.setText(etat)
          self.__etatMachine = etat

  def get_etatMachine(self):
    return self.__etatMachine


  def getDigitalStatus(self, digitNum):
    if digitNum >= 0 and digitNum <= 3:
      return self.__digitalStatus[digitNum]


  def getWco(self, axis=None):
    if axis is not None:
      if axis in self.__axisNames:
        return self.__wco[self.__axisNames.index(axis)]
      elif isinstance(axis, int):
        if axis >= 0 and axis < self.__nbAxis:
          return self.__wco[axis]
    else:
      return self.__wco


  def getWpos(self, axis=None):
    if axis is not None:
      if axis in self.__axisNames:
        return self.__wpos[self.__axisNames.index(axis)]
      elif isinstance(axis, int):
        if axis >= 0 and axis < self.__nbAxis:
          return self.__wpos[axis]
    else:
      return self.__wpos


  def getMpos(self, axis=None):
    if axis is not None:
      if axis in self.__axisNames:
        return self.__mpos[self.__axisNames.index(axis)]
      elif isinstance(axis, int):
        if axis >= 0 and axis < self.__nbAxis:
          return self.__mpos[axis]
    else:
      return self.__mpos


  def getOffsetG5x(self, axis=None):
    if axis is not None:
      if axis in self.__axisNames:
        return self.__offsetG5x[self.__axisNames.index(axis)]
      elif isinstance(axis, int):
        if axis >= 0 and axis < self.__nbAxis:
          return self.__offsetG5x[axis]
    else:
      return self.__offsetG5x


  def getOffsetG92(self, axis=None):
    if axis is not None:
      if axis in self.__axisNames:
        return self.__offsetG92[self.__axisNames.index(axis)]
      elif isinstance(axis, int):
        if axis >= 0 and axis < self.__nbAxis:
          return self.__offsetG92[axis]
    else:
      return self.__offsetG92


  def getG28(self, axis=None):
    if axis is not None:
      if axis in self.__axisNames:
        return self.__G5x[28][self.__axisNames.index(axis)]
      elif isinstance(axis, int):
        if axis >= 0 and axis < self.__nbAxis:
          return self.__G5x[28][axis]
    else:
      return self.__G5x[28]


  def getG30(self, axis=None):
    if axis is not None:
      if axis in self.__axisNames:
        return self.__G5x[30][self.__axisNames.index(axis)]
      elif isinstance(axis, int):
        if axis >= 0 and axis < self.__nbAxis:
          return self.__G5x[30][axis]
    else:
      return self.__G5x[30]


  def getDistanceMode(self):
    return self.__distanceMode


  def getGrblSetting(self, num: int):
    ''' Renvoi la valeur du setting Grbl s'il existe, sinon, renvoi None '''
    try:
      return self.__settings[num]
    except KeyError:
      return None
    
  def grblSetting(self, num):
    ''' Renvoi la description d'un setting de Grbl en fonction de son numéro '''
    # "$-Code"," Setting"," Units"," Setting Description"
    grblSettingsCodes = {
      0: [self.tr("Step pulse time"), self.tr("microseconds"), self.tr("Sets time length per step (Minimum 3usec).")],
      1: [self.tr("Step idle delay"), self.tr("milliseconds"), self.tr("Sets a short hold delay when stopping to let dynamics settle before disabling steppers. Value 255 keeps motors enabled with no delay.")],
      2: [self.tr("Step pulse invert"), self.tr("mask"), self.tr("Inverts the step signal. Set axis bit to invert (00000ZYX).")],
      3: [self.tr("Step direction invert"), self.tr("mask"), self.tr("Inverts the direction signal. Set axis bit to invert (00000ZYX).")],
      4: [self.tr("Invert step enable pin"), self.tr("boolean"), self.tr("Inverts the stepper driver enable pin signal.")],
      5: [self.tr("Invert limit pins"), self.tr("boolean"), self.tr("Inverts the all of the limit input pins.")],
      6: [self.tr("Invert probe pin"), self.tr("boolean"), self.tr("Inverts the probe input pin signal.")],
      10: [self.tr("Status report options"), self.tr("mask"), self.tr("Alters data included in status reports.")],
      11: [self.tr("Junction deviation"), self.tr("millimeters"), self.tr("Sets how fast Grbl travels through consecutive motions. Lower value slows it down.")],
      12: [self.tr("Arc tolerance"), self.tr("millimeters"), self.tr("Sets the G2 and G3 arc tracing accuracy based on radial error. Beware: A very small value may effect performance.")],
      13: [self.tr("Report in inches"), self.tr("boolean"), self.tr("Enables inch units when returning any position and rate value that is not a settings value.")],
      20: [self.tr("Soft limits enable"), self.tr("boolean"), self.tr("Enables soft limits checks within machine travel and sets alarm when exceeded. Requires homing.")],
      21: [self.tr("Hard limits enable"), self.tr("boolean"), self.tr("Enables hard limits. Immediately halts motion and throws an alarm when switch is triggered.")],
      22: [self.tr("Homing cycle enable"), self.tr("boolean"), self.tr("Enables homing cycle. Requires limit switches on all axes.")],
      23: [self.tr("Homing direction invert"), self.tr("mask"), self.tr("Homing searches for a switch in the positive direction. Set axis bit (00000ZYX) to search in negative direction.")],
      24: [self.tr("Homing locate feed rate"), self.tr("units (millimeters or degres)/min"), self.tr("Feed rate to slowly engage limit switch to determine its location accurately.")],
      25: [self.tr("Homing search seek rate"), self.tr("units (millimeters or degres)/min"), self.tr("Seek rate to quickly find the limit switch before the slower locating phase.")],
      26: [self.tr("Homing switch debounce delay"), self.tr("milliseconds"), self.tr("Sets a short delay between phases of homing cycle to let a switch debounce.")],
      27: [self.tr("Homing switch pull-off distance"), self.tr("millimeters"), self.tr("Retract distance after triggering switch to disengage it. Homing will fail if switch isn't cleared.")],
      30: [self.tr("Maximum spindle speed"), self.tr("RPM"), self.tr("Maximum spindle speed. Sets PWM to 100% duty cycle.")],
      31: [self.tr("Minimum spindle speed"), self.tr("RPM"), self.tr("Minimum spindle speed. Sets PWM to 0.4% or lowest duty cycle.")],
      32: [self.tr("Laser-mode enable"), self.tr("boolean"), self.tr("Enables laser mode. Consecutive G1/2/3 commands will not halt when spindle speed is changed.")],
      100: [self.tr("1st axis travel resolution"), self.tr("step/unit"), self.tr("1st axis travel resolution in steps per unit (millimeter or degre).")],
      101: [self.tr("2nd axis travel resolution"), self.tr("step/unit"), self.tr("2nd axis travel resolution in steps per unit (millimeter or degre).")],
      102: [self.tr("3rd axis travel resolution"), self.tr("step/unit"), self.tr("3rd axis travel resolution in steps per unit (millimeter or degre).")],
      103: [self.tr("4th axis travel resolution"), self.tr("step/unit"), self.tr("4th axis travel resolution in steps per unit (millimeter or degre).")],
      104: [self.tr("5th axis travel resolution"), self.tr("step/unit"), self.tr("5th axis travel resolution in steps per unit (millimeter or degre).")],
      105: [self.tr("6th axis travel resolution"), self.tr("step/unit"), self.tr("6th axis travel resolution in steps per unit (millimeter or degre).")],
      110: [self.tr("1st axis maximum rate"), self.tr("unit/min"), self.tr("1st axis maximum rate. Used as G0 rapid rate.")],
      111: [self.tr("2nd axis maximum rate"), self.tr("unit/min"), self.tr("2nd axis maximum rate. Used as G0 rapid rate.")],
      112: [self.tr("3rd axis maximum rate"), self.tr("unit/min"), self.tr("3rd axis maximum rate. Used as G0 rapid rate.")],
      113: [self.tr("4th axis maximum rate"), self.tr("unit/min"), self.tr("4th axis maximum rate. Used as G0 rapid rate")],
      114: [self.tr("5th axis maximum rate"), self.tr("unit/min"), self.tr("5th axis maximum rate. Used as G0 rapid rate")],
      115: [self.tr("6th axis maximum rate"), self.tr("unit/min"), self.tr("6th axis maximum rate. Used as G0 rapid rate")],
      120: [self.tr("1st axis acceleration"), self.tr("unit/sec^2"), self.tr("1st axis acceleration. Used for motion planning to not exceed motor torque and lose steps.")],
      121: [self.tr("2nd axis acceleration"), self.tr("unit/sec^2"), self.tr("2nd axis acceleration. Used for motion planning to not exceed motor torque and lose steps.")],
      122: [self.tr("3rd axis acceleration"), self.tr("unit/sec^2"), self.tr("3rd axis acceleration. Used for motion planning to not exceed motor torque and lose steps.")],
      123: [self.tr("4th axis acceleration"), self.tr("unit/sec^2"), self.tr("4th axis acceleration. Used for motion planning to not exceed motor torque and lose steps.")],
      124: [self.tr("5th axis acceleration"), self.tr("unit/sec^2"), self.tr("5th axis acceleration. Used for motion planning to not exceed motor torque and lose steps.")],
      125: [self.tr("6th axis acceleration"), self.tr("unit/sec^2"), self.tr("6th axis acceleration. Used for motion planning to not exceed motor torque and lose steps.")],
      130: [self.tr("1st axis maximum travel"), self.tr("unit (millimeters or degres)"), self.tr("Maximum 1st axis travel distance from homing switch. Determines valid machine space for soft-limits and homing search distances.")],
      131: [self.tr("2nd axis maximum travel"), self.tr("unit (millimeters or degres)"), self.tr("Maximum 2nd axis travel distance from homing switch. Determines valid machine space for soft-limits and homing search distances.")],
      132: [self.tr("3rd axis maximum travel"), self.tr("unit (millimeters or degres)"), self.tr("Maximum 3rd axis travel distance from homing switch. Determines valid machine space for soft-limits and homing search distances.")],
      133: [self.tr("4th axis maximum travel"), self.tr("unit (millimeters or degres)"), self.tr("Maximum 4th axis travel distance from homing switch. Determines valid machine space for soft-limits and homing search distances.")],
      134: [self.tr("5th axis maximum travel"), self.tr("unit (millimeters or degres)"), self.tr("Maximum 5th axis travel distance from homing switch. Determines valid machine space for soft-limits and homing search distances.")],
      135: [self.tr("6th axis maximum travel"), self.tr("unit (millimeters or degres)"), self.tr("Maximum 6th axis travel distance from homing switch. Determines valid machine space for soft-limits and homing search distances.")]
    }

    try:
      champ_0 = grblSettingsCodes[num][0]
    except KeyError as e:
      champ_0 = ""
    try:
      champ_1 = grblSettingsCodes[num][1]
    except KeyError as e:
      champ_1 = ""
    try:
      champ_2 = grblSettingsCodes[num][2]
    except KeyError as e:
      champ_2 = ""
    
    return (champ_0 + " (" + champ_1 + ")" + " : " + champ_2)


  def updateAxisDefinition(self):
    ''' Mise à jour des lagels dépendant du système de coordonnées actif et du nombre d'axes '''
    
    self.ui.lblLblPosX.setText(self.__axisNames[0])
    self.ui.lblLblPosY.setText(self.__axisNames[1])
    self.ui.lblLblPosZ.setText(self.__axisNames[2])
    self.ui.rbtDefineOriginXY_G54.setText("G{} offset".format(self.__G5actif))
    self.ui.rbtDefineOriginZ_G54.setText("G{} offset".format(self.__G5actif))
    self.ui.mnuG5X_reset.setText("Turn off and reset G{} offsets of all axis".format(self.__G5actif))
    self.ui.mnuG5X_origine_0.setText("Place the G{} origin of all axis here".format(self.__G5actif))
    self.ui.mnuG5X_origine_1.setText("Place the G{} origin of axis {} here".format(self.__G5actif, self.__axisNames[0]))
    self.ui.mnuG5X_origine_2.setText("Place the G{} origin of axis {} here".format(self.__G5actif, self.__axisNames[1]))
    self.ui.mnuG5X_origine_3.setText("Place the G{} origin of axis {} here".format(self.__G5actif, self.__axisNames[2]))

    if self.__nbAxis > 3:
      self.ui.lblLblPosA.setText(self.__axisNames[3])
      self.ui.lblLblPosA.setEnabled(True)
      self.ui.lblLblPosA.setStyleSheet("")
      self.ui.lblPosA.setEnabled(True)
      self.ui.lblPosA.setStyleSheet("")
      self.ui.lblG5xA.setStyleSheet("")
      self.ui.lblG92A.setStyleSheet("")
      self.ui.lblWcoA.setStyleSheet("")
      self.ui.mnuG5X_origine_4.setText("Place the G{} origin of axis {} here".format(self.__G5actif, self.__axisNames[3]))
      self.ui.mnuG5X_origine_4.setEnabled(True)
    else:
      self.ui.lblLblPosA.setText("")
      self.ui.lblLblPosA.setEnabled(False)
      self.ui.lblLblPosA.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblPosA.setEnabled(False)
      self.ui.lblPosA.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblG5xA.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblG92A.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblWcoA.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.mnuG5X_origine_4.setText("Place the G{} origin of axis - here".format(self.__G5actif))
      self.ui.mnuG5X_origine_4.setEnabled(False)
    if self.__nbAxis > 4:
      self.ui.lblLblPosB.setText(self.__axisNames[4])
      self.ui.lblLblPosB.setEnabled(True)
      self.ui.lblLblPosB.setStyleSheet("")
      self.ui.lblPosB.setEnabled(True)
      self.ui.lblPosB.setStyleSheet("")
      self.ui.lblG5xB.setStyleSheet("")
      self.ui.lblG92B.setStyleSheet("")
      self.ui.lblWcoB.setStyleSheet("")
      self.ui.mnuG5X_origine_5.setText("Place the G{} origin of axis {} here".format(self.__G5actif, self.__axisNames[4]))
      self.ui.mnuG5X_origine_5.setEnabled(True)
    else:
      self.ui.lblLblPosB.setText("")
      self.ui.lblLblPosB.setEnabled(False)
      self.ui.lblLblPosB.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblPosB.setEnabled(False)
      self.ui.lblPosB.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblG5xB.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblG92B.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblWcoB.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.mnuG5X_origine_5.setText("Place the G{} origin of axis - here".format(self.__G5actif))
      self.ui.mnuG5X_origine_5.setEnabled(False)
    if self.__nbAxis > 5:
      self.ui.lblLblPosC.setText(self.__axisNames[5])
      self.ui.lblLblPosC.setEnabled(True)
      self.ui.lblLblPosC.setStyleSheet("")
      self.ui.lblPosC.setEnabled(True)
      self.ui.lblPosC.setStyleSheet("")
      self.ui.lblG5xC.setStyleSheet("")
      self.ui.lblG92C.setStyleSheet("")
      self.ui.lblWcoC.setStyleSheet("")
      self.ui.mnuG5X_origine_6.setText("Place the G{} origin of axis {} here".format(self.__G5actif, self.__axisNames[5]))
      self.ui.mnuG5X_origine_6.setEnabled(True)
    else:
      self.ui.lblLblPosC.setText("")
      self.ui.lblLblPosC.setEnabled(False)
      self.ui.lblLblPosC.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblPosC.setEnabled(False)
      self.ui.lblPosC.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblG5xC.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblG92C.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.lblWcoC.setStyleSheet("color: rgb(224, 224, 230);")
      self.ui.mnuG5X_origine_6.setText("Place the G{} origin of axis - here".format(self.__G5actif))
      self.ui.mnuG5X_origine_6.setEnabled(False)

    if 'A' in self.__axisNames:
      self.ui.btnJogMoinsA.setEnabled(True)
      self.ui.btnJogPlusA.setEnabled(True)
    else:
      self.ui.btnJogMoinsA.setEnabled(False)
      self.ui.btnJogPlusA.setEnabled(False)

    if 'B' in self.__axisNames:
      self.ui.btnJogMoinsB.setEnabled(True)
      self.ui.btnJogPlusB.setEnabled(True)
    else:
      self.ui.btnJogMoinsB.setEnabled(False)
      self.ui.btnJogPlusB.setEnabled(False)

    if 'C' in self.__axisNames:
      self.ui.btnJogMoinsC.setEnabled(True)
      self.ui.btnJogPlusC.setEnabled(True)
    else:
      self.ui.btnJogMoinsC.setEnabled(False)
      self.ui.btnJogPlusC.setEnabled(False)


  @pyqtSlot()
  def waitForGrblReply(self):
    ''' Attente d'une réponse de Grbl, OK ou error ou Alarm '''
    recu = None
    def quitOnOk():
      recu = SIG_OK
      loop.quit()
    def quitOnError():
      recu = SIG_ERROR
      loop.quit()
    def quitOnAlarm():
      recu = SIG_ALARM
      loop.quit()
    loop = QEventLoop()
    self.__grblCom.sig_ok.connect(quitOnOk)
    self.__grblCom.sig_error.connect(quitOnError)
    self.__grblCom.sig_alarm.connect(quitOnAlarm)
    loop.exec()
    self.__grblCom.sig_ok.disconnect(quitOnOk)
    self.__grblCom.sig_error.disconnect(quitOnError)
    self.__grblCom.sig_alarm.disconnect(quitOnAlarm)
    return recu


  @pyqtSlot()
  def waitForGrblProbe(self):
    ''' Attente d'une réponse de Grbl, Probe ou error ou Alarm '''
    self.__probeRecu = None
    
    def quitOnProbe(data: str):
      resultatProbe = []
      tblData   = data.split(":")
      tblValues = tblData[1].split(",")
      resultatProbe.append(tblData[2] == "1]")
      resultatProbe.append([])
      for v in tblValues:
        resultatProbe[1].append(float(v))
      resultatProbe.append(SIG_PROBE)
      self.__probeRecu = resultatProbe
      loop.quit()

    def quitOnError():
      self.__probeRecu = [False, [], SIG_ERROR]
      loop.quit()

    def quitOnAlarm():
      self.__probeRecu = [False, [], SIG_ALARM]
      loop.quit()

    loop = QEventLoop()
    self.__grblCom.sig_probe.connect(quitOnProbe)
    self.__grblCom.sig_error.connect(quitOnError)
    self.__grblCom.sig_alarm.connect(quitOnAlarm)
    loop.exec()
    self.__grblCom.sig_probe.disconnect(quitOnProbe)
    self.__grblCom.sig_error.disconnect(quitOnError)
    self.__grblCom.sig_alarm.disconnect(quitOnAlarm)
    
    return self.__probeRecu

