'''
Created on May 16, 2025

@author: lmgar
'''

import sys,math
import threading
import logging

sys.path.append("/mnt/c/Users/lmgar/OneDrive/Documents/My Projects/ExperienceBuffers/python source/")
from experiencebuffers.util.Tools import Tools

logger=logging.getLogger(__name__)


class PeriodicBufferSaver:

    def __init__(self,device):
        self.isAlive=True
        self.paused=False
        self.loop=False
        self.ready=True
        self.sampleSizes=list()

        self.device=device
        self.startTimes=list()

        self.checker=None
        self.archiver=None
        self.scheduler=None

    #-----------------------------------------------------------------
    def pause(self):
        self.paused=True

    #-----------------------------------------------------------------
    def unpause(self):
        self.paused=False

    #-----------------------------------------------------------------
    def isPaused(self):
        return self.paused

    #-----------------------------------------------------------------
    def terminate(self):
        self.loop=False
        self.startTimes.clear()
        self.unpause()
        self.isAlive=False

    #-----------------------------------------------------------------
    def kill(self):
        self.terminate()

        Tools.sleep(1000)

        self.checker=None
        self.archiver=None
        self.scheduler=None

    #-----------------------------------------------------------------
    def addStartTime(self,start):
        self.startTimes.append(start)

    #-----------------------------------------------------------------
    def start(self):
        self.loop=True

        self.checker=threading.Thread(target=self.deviceChecker,daemon=True)
        self.checker.start()

        self.archiver=threading.Thread(target=self.archiveSaver,daemon=True)
        self.archiver.start()

        self.scheduler=threading.Thread(target=self.archiveScheduler,daemon=True)
        self.scheduler.start()

    #-----------------------------------------------------------------
    def archiveScheduler(self):
        while self.loop:
            try:
                if self.device.isCapturing():
                    startTime=Tools.currentTimeMillis()
                    Tools.sleep(self.device.getCaptureFrequency())

                    if self.device.getDataSize()>0:
                        self.addStartTime(startTime)
                else:
                    Tools.sleep(10)
            except:
                Tools.printStackTrace()

    #-----------------------------------------------------------------
    def archiveSaver(self):
        while self.loop:
            try:
                if self.startTimes:
                    start=math.floor(self.startTimes.pop(0)/self.device.getCaptureFrequency())*self.device.getCaptureFrequency()
                    #start=round(self.startTimes.pop(0)/self.device.getCaptureFrequency())*self.device.getCaptureFrequency()
                    end=start+self.device.getCaptureFrequency()

                    if self.device.isArchivable():
                        data=self.device.getDataTimeRange(start,end)
                        self.device.removeDataTimeRange(0,end)
                        self.ready=True
                    else:
                        data=None

                    self.device.checkForProblems(len(data) if data else None)

                    if data:
                        if not self.isPaused():
                            self.calculateAverage(data)
                            data=self.device.normalizeSize(data)

                            self.device.writeBufferData(start,data)

                        data.clear()

                Tools.sleep(10)
            except:
                Tools.printStackTrace()

    #-----------------------------------------------------------------
    def deviceChecker(self):
        self.waitForCaptureDevice()

        while self.loop:
            try:
                if self.device.isCapturing():
                    if self.device.getDataSize()>0 or self.isPaused or self.device.isPaused() or self.ready:
                        self.ready=False

                    if self.device.warningIssued():
                        self.device.pauseArchiving()
                    else:
                        self.device.unpauseArchiving()

                    Tools.sleep(self.device.getCaptureFrequency())
                else:
                    if self.device.testDataSource():
                        Tools.sleep(3000)
                        print(f"Trying to revive {self.device.getBufferClass()}...")
                        if self.device.startCapture():
                            print(f"{self.device.getBufferClass()} was successfully revived.")
                            self.device.healthCallback(self.device.getDeviceID(),"Buffer revived",str(self.device.getAverageRatePerPeriod()))

                    else:
                        Tools.sleep(1000)

                if self.device.problemDetected() and self.device.isCapturing():
                    print(f"{self.device.getDeviceName()} is now being closed but will periodically try to reopen.")
                    self.device.stopCapture()
                    Tools.sleep(5000)
            except:
                Tools.printStackTrace()

    #-----------------------------------------------------------------
    def calculateAverage(self,data):
        maxBufferElements=self.device.getBufferLength()/self.device.getCaptureFrequency()

        self.sampleSizes.append(len(data))

        while len(self.sampleSizes)>maxBufferElements:
            self.sampleSizes.pop(0)

        self.device.averageBytes=round(sum([s for s in self.sampleSizes])*self.device.getCaptureBufferSize()/len(self.sampleSizes),1)

    #-----------------------------------------------------------------
    def waitForCaptureDevice(self):
        while self.isAlive and self.device.isBufferAlive() and (not self.device.isCapturing() or self.device.getDataSize()==0):
            Tools.sleep(10)
