#!/usr/bin/env python

import sys
import os
sys.path.append(os.path.dirname(sys.argv[0]))  # Add module's actual directory to system path.
import time
import numpy as np  # Needed for integer arrays
from gpufancnvgui import *
from subprocess import call, check_output

class FCForm(QtGui.QMainWindow):
   def __init__(self, parent=None):
      QtGui.QWidget.__init__(self, parent)
      self.ui = Ui_MainWindow()
      self.ui.setupUi(self)

      global gpucnt,selectedGPU
      vernum = "0.5.1"
      os.chdir(os.path.dirname(sys.argv[0]))  # Point to directory where modules and config files reside.
      self.setWindowTitle("Fan Control for nVidia GPUs (v"+vernum+")")

# Newer NVIDIA drivers use the "GPUTargetFanSpeed" attribute, but older ones used "GPUCurrentFanSpeed".
# This test should determine which one is active. An error message might be generated if "GPUTargetFanSpeed"
# isn't found, but it is ignored. Only the return code matters.
      fanspeedattr = "GPUTargetFanSpeed"
      if call("nvidia-settings -q "+fanspeedattr, shell=True)!=0:
         fanspeedattr = "GPUCurrentFanSpeed"

# Determine the current number of NVIDIA GPUs on the system
      gpucnt = int((check_output("nvidia-settings -t -q gpus", shell=True).decode("utf-8").split())[0])
      self.ui.gpuselected.setMaximum(gpucnt-1)
      self.ui.totnvgpus.setText(str(gpucnt))
      
# Initialize several variables and arrays
      selectedGPU = 0
      initpass = True
      sstrigger = True
      ctrlvals = np.zeros((gpucnt,5,2), dtype=np.int8)
      ctrlsw = np.zeros((gpucnt), dtype=np.int8)
      currvals = np.zeros((gpucnt,2), dtype=np.int8)
      timer = QtCore.QTimer(self)  # Define the timer used for the adjustment interval
      self.loadconfig(ctrlvals, ctrlsw)  # Load any saved settings
      self.appstartup(currvals, ctrlvals, ctrlsw, fanspeedattr)
      self.timesup(ctrlvals, currvals, ctrlsw, fanspeedattr) # Trigger an initial control check
      timer.start(self.ui.ctrlinterval.value()*1000) # Now set the interval to be used for future control checks
          
# Create the necessary signal/slot connections
      QtCore.QObject.connect(self.ui.fancontrolon, QtCore.SIGNAL('clicked()'), lambda: self.fancontrolon(ctrlsw))
      QtCore.QObject.connect(self.ui.fancontroloff, QtCore.SIGNAL('clicked()'), lambda: self.fancontroloff(ctrlsw))
      self.ui.gpuselected.valueChanged.connect(lambda: self.GPUChanged(currvals, ctrlvals, ctrlsw, fanspeedattr))
      self.ui.ctrlinterval.valueChanged.connect(lambda: self.ctrlintervalchanged(timer, self.ui.ctrlinterval.value()))
      self.ui.tempslide0.valueChanged.connect(lambda: self.tempslide0changed(ctrlvals, self.ui.tempslide0.value()))
      self.ui.tempslide1.valueChanged.connect(lambda: self.tempslide1changed(ctrlvals, self.ui.tempslide1.value()))
      self.ui.tempslide2.valueChanged.connect(lambda: self.tempslide2changed(ctrlvals, self.ui.tempslide2.value()))
      self.ui.tempslide3.valueChanged.connect(lambda: self.tempslide3changed(ctrlvals, self.ui.tempslide3.value()))
      self.ui.speedslide0.valueChanged.connect(lambda: self.speedslidechanged(ctrlvals, self.ui.speedslide0.value(), 0))
      self.ui.speedslide1.valueChanged.connect(lambda: self.speedslidechanged(ctrlvals, self.ui.speedslide1.value(), 1))
      self.ui.speedslide2.valueChanged.connect(lambda: self.speedslidechanged(ctrlvals, self.ui.speedslide2.value(), 2))
      self.ui.speedslide3.valueChanged.connect(lambda: self.speedslidechanged(ctrlvals, self.ui.speedslide3.value(), 3))
      self.ui.speedslide4.valueChanged.connect(lambda: self.speedslidechanged(ctrlvals, self.ui.speedslide4.value(), 4))
      self.ui.savesettings.clicked.connect(lambda: self.saveconfig(ctrlvals, ctrlsw))
      self.ui.revertsettings.clicked.connect(lambda: self.revertsettings(currvals, ctrlvals, ctrlsw, fanspeedattr))
      timer.timeout.connect(lambda: self.timesup(ctrlvals, currvals, ctrlsw, fanspeedattr))

# Assign the initial values to the GUI controls
   def appstartup(self, currvals, ctrlvals, ctrlsw, fanspeedattr):
       global selectedGPU
       self.GPUChanged(currvals, ctrlvals, ctrlsw, fanspeedattr)
       self.tempslide0changed(ctrlvals, self.ui.tempslide0.value())
       self.tempslide1changed(ctrlvals, self.ui.tempslide1.value())
       self.tempslide2changed(ctrlvals, self.ui.tempslide2.value())
       self.tempslide3changed(ctrlvals, self.ui.tempslide3.value())
       currselectedGPU = selectedGPU
       for i in range(gpucnt):
           selectedGPU = i
           if ctrlsw[i]==1: self.fancontrolon(ctrlsw)
           else: self.fancontroloff(ctrlsw)
       selectedGPU = currselectedGPU    
       self.ui.savesettings.setStyleSheet("background-color:light gray")
       self.ui.revertsettings.hide()

# Load any saved settings, if a configuration file exists
# If no config file found, the defaults built into the GUI are displayed
   def loadconfig(self, ctrlvals, ctrlsw):
       if os.path.isfile('gpufancnv.cfg'):
          configfile = open('gpufancnv.cfg')
          while True:
             linein = (configfile.readline()).lower()
             linein = linein.replace("\n","")
             if len(linein)==0:
                break
             configstr = linein.partition('=')
             configpfx = configstr[0]
             if configpfx.startswith("gpu"):
                configvals = configstr[2].split(",")         
                if "active" in configpfx:
                   for i in range(gpucnt):
                       ctrlsw[i] = int(configvals[i])
                elif "steps" in configpfx:
                   gpuidx = int(configpfx[3])
                   if gpuidx < gpucnt:
                      for i in range(5):
                          ctrlvals[gpuidx, i, 0] = int(configvals[i])
                elif "speeds" in configpfx:
                   gpuidx = int(configpfx[3])
                   if gpuidx < gpucnt:
                      for i in range(5):
                          ctrlvals[gpuidx, i, 1] = int(configvals[i])
             elif configpfx.startswith("interval"):
                self.ui.ctrlinterval.setValue(int(configstr[2]))
          configfile.close
       else:
          for i in range(gpucnt):
             ctrlvals[i, 4, 0] = 100
             ctrlvals[i, 4, 1] = 100

# Save user settings to a configuration file, for use each time program is launched
   def saveconfig(self, ctrlvals, ctrlsw):
       configfile = open('gpufancnv.cfg', 'w')
       outline = 'Interval='+str(self.ui.ctrlinterval.value())+'\n'
       configfile.write(outline)
       outline = 'GPU Active='+str(ctrlsw[0])
       for i in range(1,gpucnt):
          outline = outline+','+str(ctrlsw[i])
       outline = outline+'\n'   
       configfile.write(outline)
       for i in range(gpucnt):
          outline = 'GPU'+str(i)+'steps='+str(ctrlvals[i,0,0])+','+str(ctrlvals[i,1,0])+','+str(ctrlvals[i,2,0])+','+str(ctrlvals[i,3,0])+','+str(100)+'\n'
          configfile.write(outline)
          outline = 'GPU'+str(i)+'speeds='+str(ctrlvals[i,0,1])+','+str(ctrlvals[i,1,1])+','+str(ctrlvals[i,2,1])+','+str(ctrlvals[i,3,1])+','+str(ctrlvals[i,4,1])+'\n'
          configfile.write(outline)
       configfile.close
       self.ui.savesettings.setStyleSheet("background-color:light gray")
       self.ui.revertsettings.hide()

# Revert to last saved settings and then hide the "Revert" butoon
   def revertsettings(self, currvals, ctrlvals, ctrlsw, fanspeedattr):
       global selectedGPU
       self.loadconfig(ctrlvals, ctrlsw)
       self.GPUChanged(currvals, ctrlvals, ctrlsw, fanspeedattr)
       self.ui.savesettings.setStyleSheet("background-color:light gray")
       self.ui.revertsettings.hide()

# Whenever ANY displayed setting is changed by user, flag is set, "Save Settings" button is highlighted,
# and "Revert" button is displayed.
   def settingschanged(self):
       global sstrigger
       if sstrigger==True:
          self.ui.savesettings.setStyleSheet("background-color:rgb(176,240,176)")
          self.ui.revertsettings.show()

# Change the timer interval any time the user changes the value onscreen
   def ctrlintervalchanged(self, timer, value):
       timer.start(value*1000)
       self.settingschanged()

# Turn on Fan Control for the currently selected GPU
   def fancontrolon(self, ctrlsw):
       global selectedGPU
       ctrlsw[selectedGPU] = 1
       self.ui.currtemp.show()
       self.ui.currspeed.show()
       call("nvidia-settings -a [gpu:"+str(selectedGPU)+"]/GPUFanControlState=1", shell=True)
       self.settingschanged()

# Turn off Fan Control for the currently selected GPU
   def fancontroloff(self, ctrlsw):
       global selectedGPU
       ctrlsw[selectedGPU] = 0
       self.ui.currtemp.hide()
       self.ui.currspeed.hide()
       call("nvidia-settings -a [gpu:"+str(selectedGPU)+"]/GPUFanControlState=0", shell=True)
       self.settingschanged()

# The next 4 routines respond to changes to the temperature range sliders.
# A change to the max value in one range also alters the min value in the next higher range to match.
# This may have a cascading effect up the ranges, depending on the extent of the change.
# When the selected GPU changes, two passes through each routine are necessary so that a previously established
# min value in the next higher range doesn't inhibit the setting of a new minimum for that range.
   def tempslide0changed(self, ctrlvals, value):
       global selectedGPU, initpass
       self.ui.tempslide1.setGeometry(self.ui.tempslide0.x()+(value*2), self.ui.tempslide1.y(), self.ui.tempslide0.width()-(value*2), self.ui.tempslide1.height())
       self.ui.tempslide1.setMinimum(value)
       if initpass==False:
          ctrlvals[selectedGPU, 0, 0] = value
       self.settingschanged()

   def tempslide1changed(self, ctrlvals, value):
       global selectedGPU, initpass
       self.ui.tempslide2.setGeometry(self.ui.tempslide0.x()+(value*2), self.ui.tempslide2.y(), self.ui.tempslide0.width()-(value*2), self.ui.tempslide2.height())
       self.ui.tempslide2.setMinimum(value)
       if initpass==False:
          ctrlvals[(selectedGPU, 1, 0)] = value
       self.settingschanged()
   
   def tempslide2changed(self, ctrlvals, value):
       global selectedGPU, initpass
       self.ui.tempslide3.setGeometry(self.ui.tempslide0.x()+(value*2), self.ui.tempslide3.y(), self.ui.tempslide0.width()-(value*2), self.ui.tempslide3.height())
       self.ui.tempslide3.setMinimum(value)
       if initpass==False:
          ctrlvals[selectedGPU, 2, 0] = value
       self.settingschanged()
   
   def tempslide3changed(self, ctrlvals, value):
       global selectedGPU, initpass
       self.ui.tempslide4.setGeometry(self.ui.tempslide0.x()+(value*2), self.ui.tempslide4.y(), self.ui.tempslide0.width()-(value*2), self.ui.tempslide4.height())
       self.ui.tempslide4.setMinimum(value)
       if initpass==False:
          ctrlvals[selectedGPU, 3, 0] = value
       self.settingschanged()

# Respond to a change to the specified fan speed slider.
   def speedslidechanged(self, ctrlvals, value, slidenum):
       global selectedGPU
       ctrlvals[selectedGPU,slidenum,1] = value
       self.settingschanged()
   
# Respond to a change to the GPU selection.
# Change all displayed slider values to reflect those of the newly selected GPU
   def GPUChanged(self, currvals, ctrlvals, ctrlsw, fanspeedattr):
       global selectedGPU, initpass, sstrigger
       selectedGPU = self.ui.gpuselected.value()
       sstrigger = False  # Prevent these internal changes from looking like external ones 
       if ctrlsw[selectedGPU]==1:
          self.ui.fancontrolon.click()
          self.timesup(ctrlvals, currvals, ctrlsw, fanspeedattr)
       else:
          self.ui.fancontroloff.click()
       initpass = True  # Initial pass sets temp maxes to zero to zero
       self.ui.tempslide0.setValue(0)
       self.ui.tempslide1.setValue(0)
       self.ui.tempslide2.setValue(0)
       self.ui.tempslide3.setValue(0)
       initpass = False  # Second pass applies actual stored vales
       self.ui.tempslide3.setValue(ctrlvals[selectedGPU, 3, 0])
       self.ui.tempslide2.setValue(ctrlvals[selectedGPU, 2, 0])
       self.ui.tempslide1.setValue(ctrlvals[selectedGPU, 1, 0])
       self.ui.tempslide0.setValue(ctrlvals[selectedGPU, 0, 0])
       self.ui.speedslide0.setValue(ctrlvals[selectedGPU, 0, 1])
       self.ui.speedslide1.setValue(ctrlvals[selectedGPU, 1, 1])
       self.ui.speedslide2.setValue(ctrlvals[selectedGPU, 2, 1])
       self.ui.speedslide3.setValue(ctrlvals[selectedGPU, 3, 1])
       self.ui.speedslide4.setValue(ctrlvals[selectedGPU, 4, 1])
       sstrigger = True
       self.ui.lblselgpu.setFocus()
       self.ui.gpuselected.setFocus()
       
# This routine is performed each time the timer reaches the specified control interval.
# Fan speed for all GPUs are adjusted according to user's specifications and current GPU temperatures.
# Current temperature and fan speed for the currently selected GPU are updated in the display.
   def timesup(self, ctrlvals, currvals, ctrlsw, fanspeedattr):
       global selectedGPU
       for i in range(gpucnt):
           if ctrlsw[i]==1:
              currtemp = int(check_output("nvidia-settings -t -q [gpu:"+str(i)+"]/GPUCoreTemp", shell=True))
              if currtemp <= ctrlvals[i,3,0]:
                 if currtemp <= ctrlvals[i,2,0]:
                    if currtemp <= ctrlvals[i,1,0]:
                       if currtemp <= ctrlvals[i,0,0]: speedtoset = ctrlvals[i,0,1]
                       else: speedtoset = ctrlvals[i,1,1]
                    else: speedtoset = ctrlvals[i,2,1]
                 else: speedtoset = ctrlvals[i,3,1]
              else: speedtoset = ctrlvals[i,4,1]
              call("nvidia-settings -a [fan:"+str(i)+"]/"+fanspeedattr+"="+str(speedtoset), shell=True)
              currvals[i, 0] = currtemp
              currvals[i, 1] = int(check_output("nvidia-settings -t -q [fan:"+str(selectedGPU)+"]/"+fanspeedattr, shell=True))
       self.ui.currtemp.setNum(currvals[selectedGPU, 0])
       self.ui.currspeed.setNum(currvals[selectedGPU, 1])
   
if __name__ == "__main__":
   app = QtGui.QApplication(sys.argv)
   fcapp = FCForm()
   fcapp.show()
   sys.exit(app.exec_())
