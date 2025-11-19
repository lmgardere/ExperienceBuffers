'''
Created on May 18, 2025

@author: lmgar
'''

import os,sys,math,random
import time,ast
import threading
import logging

from abc import ABC,abstractmethod

sys.path.append("/mnt/c/Users/lmgar/OneDrive/Documents/My Projects/ExperienceBuffers/python source/")
from experiencebuffers.util.Converter import Converter
from experiencebuffers.util.TimeLock import TimeLock
from experiencebuffers.util.PeriodicBufferSaver import PeriodicBufferSaver
from experiencebuffers.core.DeviceListener import DeviceListener
from experiencebuffers.util.Standards import Standards
from experiencebuffers.util.Tools import Tools

logger=logging.getLogger(__name__)


class BufferDevice(DeviceListener,ABC):
    DEFAULT_NAME="Base"
    DEFAULT_DESCRIPTION="Base buffer device"

    def __init__(self,machineID,deviceID):
        self.machineID=machineID  #Unique identifier for the machine the device is on
        self.deviceID=deviceID
        self.deviceType="Buffer"
        self.bufferAlive=True
        self.parent=None
        self.platform=None
        self.hasDisplay=False

        self.averageBytes=0
        self.startTime=0
        self.startTimeDiff=0
        self.lastCaptureStartTime=0
        self.lastClipTime=0
        self.problemCount=0
        self.freeDiskSpacePercThreshold=10
        self.lowBatteryPercThreshold=10
        self.currentFilename=None
        self.userFormat=None
        self.filler=None

        self.initialized=False
        self.paused=False
        self.capturing=False
        self.problem=False
        self.warning=False

        self.homeDir=None
        self.dataDir=None
        self.bufferDir=None
        self.clipDir=None
        self.logsDir=None
        self.config=dict()

        self.listeners=list()
        self.bufferDeviceRecords=dict()
        self.devices=dict()  # Used if this device uses other devices that match its service offerings to capture data.
                            # Requires a valid parent (Buffer Server) that holds all available devices.

        self.timeLock=TimeLock()
        self.fileSync=threading.Lock()
        self.fileTimeStamps=list()
        self.files=list()

        self.framesSync=threading.Lock()
        self.timeStamps=list()
        self.frames=list()

        self.captureCondition=threading.Condition()
        self.maintenanceCondition=threading.Condition()
        self.clipSync=threading.Lock()
        self.clipTimeStamps=list()
        self.clips=list()
        self.converter=Converter()

        self.deleteSync=threading.Lock()

        self.archiveSync=threading.Lock()

        self.platform=Tools.getPlatform()
        self.hasDisplay=True if "Windows" in self.platform or "DISPLAY" in os.environ else False

        self.addListener(self)
        self.loadConfig()
        self.setFrameBaseName(self.getBufferClass())

        self.captureThread=None
        self.archivingThread=PeriodicBufferSaver(self)
        self.maintenanceThread=threading.Thread(target=self.maintainBuffer,daemon=True)

    #-----------------------------------------------------------------
    @abstractmethod
    def initialize(self): pass

    @abstractmethod
    def listDevices(self): pass

    @abstractmethod
    def testDataSource(self): pass

    @abstractmethod
    def getCaptureBufferSize(self): pass

    @abstractmethod
    def getBytesPerPeriod(self): pass

    @abstractmethod
    def validateBufferFilename(self,filename): pass

    @abstractmethod
    def getFiller(self): pass

    @abstractmethod
    def deviceStartCapture(self): pass

    @abstractmethod
    def deviceStopCapture(self): pass

    @abstractmethod
    def forceClose(self): pass

    @abstractmethod
    def deviceWriteBufferData(self,filename,data): pass

    @abstractmethod
    def deviceMakeClip(self,requestID,clipFilename,files,start,duration): pass

    #-----------------------------------------------------------------
    def startMaintenanceServices(self):
        self.archivingThread.start()
        self.maintenanceThread.start()

    #-----------------------------------------------------------------
    def loadConfig(self):
        self.config=Tools.loadConfig(self.getConfigFilename())
        rewrite=self.validateConfig()
        self.homeDir=self.getHomeDir()

        if rewrite:
            self.saveConfig();

    #-----------------------------------------------------------------
    def validateConfig(self):
        rewrite=False

        if (v:="DeviceID") not in self.config:
            self.config[v]=self.getDeviceID()
            rewrite=True

        if (v:="Description") not in self.config:
            self.config[v]=BufferDevice.DEFAULT_DESCRIPTION
            rewrite=True

        if (v:="Name") not in self.config:
            self.config[v]=BufferDevice.DEFAULT_NAME
            rewrite=True

        #Device types may have multiple media resources on a machine (ex: a laptop with multiple webcams). This identifies the corrent media.
        #Can be a url or a media identifying, normally a number.
        if (v:="MediaID") not in self.config:
            self.config[v]="0"
            rewrite=True
        if self.config[v].isnumeric():
            self.config[v]=ast.literal_eval(self.config[v])

        if (v:="Services") not in self.config:
            self.config[v]="[]"
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="Groups") not in self.config:
            self.config[v]="[]"
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="Enable") not in self.config:
            self.config[v]="False"
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="ShowOutput") not in self.config:
            self.config[v]="True"
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        #length of buffer segment. Also, how often the buffer must save. Ex: Every one second save a one second clip
        if (v:="CaptureFrequency") not in self.config:
            self.config[v]=str(Standards.CAPTURE_FREQUENCY)
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="BufferLength") not in self.config:
            self.config[v]=str(Standards.BUFFER_LENGTH)
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="CaptureFormat") not in self.config:
            self.config[v]=""
            rewrite=True

        if (v:="BufferFormat") not in self.config:
            self.config[v]=""
            rewrite=True

        if (v:="SaveFormat") not in self.config:
            self.config[v]=""
            rewrite=True

        if (v:="FileExtension") not in self.config:
            self.config[v]=""
            rewrite=True

        return rewrite

    #-----------------------------------------------------------------
    def saveConfig(self):
        Tools.saveConfig(self.config,self.getConfigFilename(),self.getBufferClass())

    #-----------------------------------------------------------------
    def getConfigFilename(self):
        return self.getBufferClass()+"-"+self.getDeviceID()[-5:]+Standards.CONFIG_EXTENSION

    #-----------------------------------------------------------------
    def startCapture(self):
        self.resetWarningsAndProblems()

        if self.captureThread:
            self.deviceStopCapture()

        if not self.initialized:
            self.initialize()

        if self.initialized:
            if self.getStartTime()==0:
                self.setStartTime(Tools.currentTimeMillis())

            self.unpause()
            self.captureThread=threading.Thread(target=self.deviceStartCapture,daemon=True)
            self.captureThread.start()

            self.waitForCaptureToStart()
            self.setLastCaptureStartTime(Tools.currentTimeMillis())

        return self.isCapturing()

    #-----------------------------------------------------------------
    def stopCapture(self):
        flag=True

        self.resetWarningsAndProblems()
        if self.isCapturing():
            flag=self.deviceStopCapture()
            self.captureThread=None

        return flag

    #-----------------------------------------------------------------
    def restartCapture(self):
        result=False

        if self.stopCapture():
            with self.captureCondition:
                self.captureCondition.notify(5)
            result=self.startCapture()

        return result

    #-----------------------------------------------------------------
    def shutdown(self):
        if self.archivingThread:
            self.archivingThread.terminate()
            self.archivingThread=None

        self.stopCapture()

        self.bufferAlive=False
        self.deleteBufferFiles()

        with self.captureCondition:
            self.captureCondition.notify()
        with self.maintenanceCondition:
            self.maintenanceCondition.notify()

    #-----------------------------------------------------------------
    def forceShutdown(self):
        if self.archivingThread:
            self.archivingThread.kill()
            self.archivingThread=None

        self.forceClose()

        self.bufferAlive=False
        self.deleteBufferFiles()

        with self.captureCondition:
            self.captureCondition.notify()
        with self.maintenanceCondition:
            self.maintenanceCondition.notify()
        self.maintenanceThread=None

    #-----------------------------------------------------------------
    def waitForCaptureToStart(self):
        while self.isBufferAlive() and not self.isCapturing():
            Tools.sleep(10)

    #-----------------------------------------------------------------
    def addListener(self,listener):
        self.listeners.append(listener)

    #-----------------------------------------------------------------
    def removeListener(self,listener):
        self.listener.remove(listener)

    #-----------------------------------------------------------------
    def getListeners(self):
        return self.listeners

    #-----------------------------------------------------------------
    def writeBufferData(self,time,data):
        filename=self.getBufferDir()+self.makeBufferClipName(time,self.getCaptureFrequency())
        filename=self.validateBufferFilename(filename)

        if result:=self.deviceWriteBufferData(filename,data):
            with self.getFileSyncObject():
                self.addFile(filename,time)

            BufferDevice.bufferFileCreatedCallback(self,self.getDeviceID(),filename,time)
            for listener in self.getListeners():
                Tools.callback(listener.bufferFileCreatedCallback,self.getDeviceID(),filename,time)

        return result

    #-----------------------------------------------------------------
    def removeFile(self,i):
        result=None

        try:
            result=self.getFiles().pop(i)
            result=result if self.getFileTimeStamps().pop(i) else None
        except:
            pass

        return result

    #-----------------------------------------------------------------
    # Should only be used on start up and shutdown. It deletes the buffer but does not manage any of the structures
    # that manage the buffer. It assumes the device is closing and all resources will be released on exit.
    def deleteBufferFiles(self):
        prefix=self.getFrameName()

        for i,filename in enumerate(os.listdir(self.getBufferDir())):
            if filename.startswith(prefix):
                try:
                    if Tools.exists(self.getBufferDir()+filename):
                        os.remove(self.getBufferDir()+filename)

                    if i%600==0:
                        Tools.sleep(10)
                except Exception as e:
                    print("Error deleting "+str(filename)+" from the "+self.getDeviceName()+" buffer: "+str(e))

    #-----------------------------------------------------------------
    # Loads buffer files from a directory and reintegrates them into the system if they appear to belong
    # to this buffer. Extra files in the buffer that need to be reintegratred is a sign the buffer was restarted,
    # the program ended abruptly, or was improperly terminated.
    def reestablishBufferFiles(self):
        prefix=self.getFrameName()

        files=[os.path.join(self.getBufferDir(),f) for f in os.listdir(self.getBufferDir())]
        files.sort(key=os.path.getctime)
        for i,filename in enumerate(files):
            if prefix in filename:
                try:
                    time=int(filename.rsplit('_',2)[1])

                    with self.getFileSyncObject():
                        self.addFile(filename,time)

                    BufferDevice.bufferFileCreatedCallback(self,self.getDeviceID(),filename,time)
                    for listener in self.getListeners():
                        Tools.callback(listener.bufferFileCreatedCallback,self.getDeviceID(),filename,time)

                    if i%600==0:
                        Tools.sleep(10)
                except Exception as e:
                    print("Error reintegrating "+str(filename)+" into "+self.getDeviceName()+" buffer: "+str(e))

        self.reestablishServiceDeviceBufferFiles()

        logging.debug(f"Reestablished file buffer for {self.getDeviceName()}. {self.getBufferSize()} files reintegrated.")

    #-----------------------------------------------------------------
    def validBufferFile(self,filename):
        allFrameNames=[device.getFrameName() for _,device in self.devices.items()]
        allFrameNames.append(self.getFrameName())

        return any([frameName in filename for frameName in allFrameNames])

    #-----------------------------------------------------------------
    # Deletes obsolete sections of the buffer, prunes the buffer to protect disk space, and sends an alert for
    # low disk space and slow battery.
    def maintainBuffer(self):
        spaceMultiple=1

        while self.isBufferAlive():
            self.delete(0,Tools.currentTimeMillis()-(spaceMultiple*self.getBufferLength()))

            if self.bufferPercFreeDiskSpace()<self.freeDiskSpacePercThreshold and self.getBufferFillLevel()>self.captureFrequencyBufferPerc():
                spaceMultiple+=1
                self.healthCallback(self.getDeviceID(),"Buffer low disk space",str(self.bufferPercFreeDiskSpace()))
            else:
                spaceMultiple=1

            if Tools.getBatteryLevel()<self.lowBatteryPercThreshold:
                self.healthCallback(self.getDeviceID(),"Low battery",str(Tools.getBatteryLevel()))

            with self.maintenanceCondition:
                self.maintenanceCondition.wait(Standards.GC_FREQUENCY/1000.0)

    #-----------------------------------------------------------------
    def clipFreeDiskSpace(self):
        return Tools.freeDiskSpace(self.getClipDir())

    #-----------------------------------------------------------------
    def clipTotalDiskSpace(self):
        return Tools.totalDiskSpace(self.getClipDir())

    #-----------------------------------------------------------------
    def clipPercFreeDiskSpace(self):
        return Tools.percFreeDiskSpace(self.getClipDir())

    #-----------------------------------------------------------------
    def bufferFreeDiskSpace(self):
        return Tools.freeDiskSpace(self.getBufferDir())

    #-----------------------------------------------------------------
    def bufferTotalDiskSpace(self):
        return Tools.totalDiskSpace(self.getBufferDir())

    #-----------------------------------------------------------------
    def bufferPercFreeDiskSpace(self):
        return Tools.percFreeDiskSpace(self.getBufferDir())

    #-----------------------------------------------------------------
    def deleteBuffer(self):
        self.delete(0,Tools.currentTimeMillis())

    #-----------------------------------------------------------------
    #pads the data, if necessary, so that it is always a complete data frame
    def normalizeSize(self,data):
        #print(f"{self.getBufferClass()} {len(data)} {self.getAverageBytesPerPeriod()} vs {self.getBytesPerPeriod()}")
        if data:
            if dataFrames:=((self.getBytesPerPeriod()//self.getCaptureBufferSize()) if self.getCaptureBufferSize() else 0):
                while (dataSize:=len(data))!=dataFrames:
                    if dataSize>dataFrames:
                        if (dataSize%dataFrames) in [0]:
                            # If the data is twice as big as it should be (ie - 30fps instead of 15fps), it
                            # just removes every other element for smoother frame rate adjustment. Does the
                            # same if it is twice as big +1.
                            data=data[::dataSize//dataFrames]
                        else:
                            data.pop(random.randrange(0,dataSize))
                    elif dataSize<dataFrames:
                        ind=random.randrange(0,dataSize)
                        data.insert(ind,data[ind])
            else:
                data.clear()

        return data

    #-----------------------------------------------------------------
    def deleteDeviceFile(self,filename):
        result=False

        try:
            if Tools.exists(filename):
                result=True
            elif Tools.exists(self.getBufferDir()+filename):
                filename=self.getBufferDir()+filename
                result=True
            elif Tools.exists(self.getDataDir()+filename):
                filename=self.getDataDir()+filename
                result=True
            elif Tools.exists(self.getLogsDir()+filename):
                filename=self.getLogsDir()+filename
                result=True
            elif Tools.exists(self.getClipDir()+filename):
                filename=self.getClipDir()+filename
                result=True

            if result:
                os.remove(filename)

            result=True
        except:
            result=False

        return result

    #-----------------------------------------------------------------
    #delete buffer files within given time range
    def delete(self,startTime,endTime):
        result=True

        if self.getTimeLock().deleteLock(startTime,endTime,False)==0:
            with self.getDeleteSyncObject():
                if startTime==endTime:
                    try:
                        ind=self.getFileTimeStampAt(startTime)
                        if ind>=0:
                            filename=self.removeFile(ind)
                            os.remove(filename)
                    except ValueError:
                        print("Problem deleting "+str(filename))
                        result=not Tools.exists(filename)
                else:
                    i=0
                    while i<len(self.getFileTimeStamps()):
                        temp=self.getFileTimeStampAt(i)

                        if startTime<=temp<=endTime:
                            try:
                                filename=self.getFileAt(i)
                                if self.deleteDeviceFile(filename):
                                    if self.removeFile(i):
                                        i-=1
                                    else:
                                        result=False
                                        break
                                elif temp>endTime:
                                    result=False
                                    break
                                elif result:=not Tools.exists(filename):
                                    if self.removeFile(i):
                                        i-=1
                                    else:
                                        result=False
                                        break
                                else:
                                    print("Failed to delete "+str(self.getFileAt(i)))
                            except Exception as e:
                                if temp>endTime:
                                    result=False
                                    break
                                print("Problem deleting "+str(filename))
                                print("Start time: "+str(startTime)+" Target time: "+str(temp)+" End time: "+str(endTime))
                                print(e)
                            Tools.sleep(10)
                        i+=1
            self.getTimeLock().deleteUnlock(startTime,endTime)
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def removeClip(self,i):
        result=None

        try:
            result=self.getClips().pop(i)
            self.getClipTimeStamps().pop(i)
        except:
            pass

        return result

    #-----------------------------------------------------------------
    def deleteClip(self,file):
        result=False

        with self.getClipSyncObject():
            for i,clip in enumerate(self.getClips()):
                if clip.lower().endswith(file.lower()):
                    if self.deleteDeviceFile(clip):
                        self.removeClip(i)
                        result=True
                    break

        return result

    #-----------------------------------------------------------------
    def addFile(self,filename,start):
        result=False

        if not filename in self.getFiles():
            self.getFiles().append(filename)
            self.getFileTimeStamps().append(start)
            result=True

        return result

    #-----------------------------------------------------------------
    def addClip(self,filename,start):
        result=False

        if not filename in self.getClips():
            self.getClips().append(filename)
            self.getClipTimeStamps().append(start)
            result=True

        return result

    #-----------------------------------------------------------------
    def makeClip(self,requestID,triggerTime,past,future):
        result=dict()

        if self.isCapturing():
            duration=past+future
            newStartTime=self.findRealStartTime(triggerTime,past,future)
            newEndTime=newStartTime+((triggerTime+future-newStartTime)//self.getCaptureFrequency())*self.getCaptureFrequency()

            if duration>self.getCaptureFrequency():
                filename=str(self.makeClipName(newStartTime,newEndTime,duration))+str(self.getFileExtension())
                threading.Thread(target=self.clipMaker,args=(requestID,self.getClipDir()+filename,newStartTime,newEndTime)).start()

                self.lastClipTime=newStartTime

                result["clip"]=filename
                result["trigger_time"]=triggerTime
                result["start_time"]=newStartTime
                result["end_time"]=newEndTime
                result["duration"]=newEndTime-newStartTime
                result["buffer_id"]=self.getDeviceID()

        return result

    #-----------------------------------------------------------------
    # If files have been pre-gathered for this clip, they can be provided directly.
    # Otherwise, they will be retrieved from the system as needed.
    def clipMaker(self,requestID,filename,startTime,endTime,files=None):
        #helps avoid any concurrency issues if this buffer is being used by multiple services
        with self.getArchiveSyncObject():
            self.validateRecordEntry(requestID,self.getDeviceID(),filename)

            # ServiceCall tells the buffer whether or not the request to make a clip is
            # coming from the buffer itself or another buffer that is using it as a service.
            # If it receives files as a parameter in the function call it's a service call,
            # if it finds its own files it's not a service call.
            if files:
                self.setServiceCall(requestID)

            if not self.isServiceCall(requestID):
                self.bufferDeviceRecords[requestID]["clipStartTime"]=Tools.currentTimeMillis()
            duration=endTime-startTime

            self.getTimeLock().clipLock(startTime,endTime)

            print("Creating "+Tools.removeDir(filename))
            files=self.getFilesTimeRange(startTime,endTime) if not files else files

            if not self.isServiceCall(requestID):
                self.bufferDeviceRecords[requestID]["concatenationStartTime"]=Tools.currentTimeMillis()
                self.bufferDeviceRecords[requestID]["status"]="CONCATENATING"

            #Concatenation produces an intermediate file to avoid filename conflicts
            intermediateFile=self.deviceMakeClip(requestID,filename,files,startTime,duration)
            result=Tools.exists(intermediateFile) and Tools.getFileSize(intermediateFile)>0

            if not self.isServiceCall(requestID):
                self.bufferDeviceRecords[requestID]["concatenationEndTime"]=Tools.currentTimeMillis()

            self.recordConcatenationCompleted(requestID,self.getDeviceID(),intermediateFile,startTime,duration if result else 0)
            self.concatenationCompletedCallback(requestID,self.getDeviceID(),intermediateFile,startTime,duration if result else 0)

            self.getTimeLock().clipUnlock(startTime,endTime)

            if self.getBufferFormat() and self.getSaveFormat():
                if self.getBufferFormat().lower()==self.getSaveFormat().lower():
                    #check to see if the intermediate file is the final file. If so replace it with the real filename.
                    if result and intermediateFile.lower()!=filename.lower():
                        os.replace(intermediateFile,filename)
                        result=Tools.exists(filename) and Tools.getFileSize(filename)>0
                else:
                    #convert the intermediate file to the final file
                    print(f"{self.getDeviceName()} converting {intermediateFile} to {filename}...")
                    result=self.convert(intermediateFile,filename,vCodec=self.getSaveFormat())
                    os.remove(intermediateFile)

                    self.recordConcatenationCompleted(requestID,self.getDeviceID(),filename,startTime,duration if result else 0)
                    self.concatenationCompletedCallback(requestID,self.getDeviceID(),filename,startTime,duration if result else 0)

            if not self.isServiceCall(requestID):
                self.bufferDeviceRecords[requestID]["clipEndTime"]=Tools.currentTimeMillis()

            if result:
                with self.getClipSyncObject():
                    self.addClip(filename,startTime)
                print("Request for "+Tools.removeDir(filename)+" successfully finished:")
            else:
                print("Request for "+Tools.removeDir(filename)+" failed:")

            self.recordClipCompleted(requestID,self.getDeviceID(),filename,startTime,duration if result else 0)
            self.clipCompletedCallback(requestID,self.getDeviceID(),filename,startTime,duration if result else 0)

            # Clear standalone in the event that this same request includes a request from the buffer to make its own clip
            self.clearServiceCall(requestID)

        return result

    #-----------------------------------------------------------------
    def findRealStartTime(self,startTime,past,future):
        realStart=(startTime-past)//self.getCaptureFrequency()*self.getCaptureFrequency()

        while realStart+self.getCaptureFrequency()<=startTime+future:
            filename=str(self.getBufferDir())+str(self.makeBufferClipName(realStart,self.getCaptureFrequency()))+str(self.getFileExtension())
            if filename in self.getFiles() or self.getFirstSaveTime()<=realStart:
                break
            realStart+=self.getCaptureFrequency()

        return realStart

    #-----------------------------------------------------------------
    def makeBufferClipName(self,startTime,duration):
        return str(self.getFrameName())+"_"+str(startTime)+"_"+str(duration)

    #-----------------------------------------------------------------
    def makeClipName(self,startTime,endTime,duration):
        return str(self.getFrameName())+"_"+str(startTime)+"_"+str(endTime)+"_"+str(duration)

    #-----------------------------------------------------------------
    def makeDeviceID(self):
        return Tools.makeDeviceID(self.getMachineID())

    #-----------------------------------------------------------------
    def makeGroupID(self):
        return Tools.makeGroupID(self.getMachineID())

    #-----------------------------------------------------------------
    def parseMediaID(self):
        mediaStr=str(self.getMediaID()).partition(":")

        if mediaStr[1] and mediaStr[0]:
            if "http" in mediaStr[0].lower() or "rtsp" in mediaStr[0].lower() or "rtmp" in mediaStr[0].lower():
                mediaStr=self.getMediaID()
            elif str(mediaStr[0]).isnumeric():
                mediaStr=int(mediaStr[0])
            else:
                mediaStr=None
        elif str(self.getMediaID()).isnumeric():
            mediaStr=int(self.getMediaID())
        else:
            mediaStr=None

        return mediaStr

    #-----------------------------------------------------------------
    def pause(self):
        self.paused=True

    #-----------------------------------------------------------------
    def unpause(self):
        self.paused=False

    #-----------------------------------------------------------------
    def pauseArchiving(self):
        self.archivingThread.pause()

    #-----------------------------------------------------------------
    def unpauseArchiving(self):
        self.archivingThread.unpause()

    #-----------------------------------------------------------------
    def isSelf(self,machineID):
        return self.getDeviceID()==machineID

    #-----------------------------------------------------------------
    def isEnabled(self):
        return self.getProperty("Enable")

    #-----------------------------------------------------------------
    def isServiceCall(self,requestID):
        return self.bufferDeviceRecords[requestID]["serviceCall"] if requestID in self.bufferDeviceRecords and "serviceCall" in self.bufferDeviceRecords[requestID] else False

    #-----------------------------------------------------------------
    def isCapturing(self):
        return self.capturing

    #-----------------------------------------------------------------
    def isArchivable(self):
        return self.isBufferAlive() and self.isCapturing() and not self.isPaused()

    #-----------------------------------------------------------------
    def isPaused(self):
        return self.paused

    #-----------------------------------------------------------------
    def isArchivingPaused(self):
        return self.archivingThread.isPaused()

    #-----------------------------------------------------------------
    def isInitDone(self):
        return self.initialized

    #-----------------------------------------------------------------
    def isBufferAlive(self):
        return self.bufferAlive

    #-----------------------------------------------------------------
    def isVerbose(self):
        return self.verbose

    #-----------------------------------------------------------------
    def problemDetected(self):
        return self.problem

    #-----------------------------------------------------------------
    def warningIssued(self):
        return self.warning

    #-----------------------------------------------------------------
    def resetWarningsAndProblems(self):
        self.problemCount=0
        self.problem=False
        self.warning=False

    #-----------------------------------------------------------------
    def checkForProblems(self,length=None):
        if not self.isCapturing() or self.isPaused():
            self.problemCount=0
        elif length!=None:
            if self.getCaptureBufferSize() and self.getBytesPerPeriod()>0:
                if (capturePct:=length/(self.getBytesPerPeriod()//self.getCaptureBufferSize()))<0.9:
                    self.problemCount+=1
                elif capturePct>=1:
                    self.problemCount=0

        avg=self.getAverageRatePerPeriod()
        if self.problemCount==0:
            if self.warning or self.problem:
                print(f"{self.getDeviceName()} restored to proper functioning.")
                self.healthCallback(self.getDeviceID(),"Buffer restored",str(avg))

            self.problem=False
            self.warning=False

        elif self.problemCount>=5:
            if not self.warning:
                print(f"A warning was issued for {self.getDeviceName()}. Average capture rate is {avg}%")
                self.healthCallback(self.getDeviceID(),"Buffer warning",str(avg))
            self.warning=True

            if self.problemCount>=15:
                if not self.problem:
                    print(f"A problem was detected with {self.getDeviceName()}. Average capture rate is {avg}%")
                    self.healthCallback(self.getDeviceID(),"Buffer problem",str(avg))
                self.problem=True

    #-----------------------------------------------------------------
    def hasVideo(self):
        return "video" in self.getServices()

    #-----------------------------------------------------------------
    def hasAudio(self):
        return "audio" in self.getServices()

    #-----------------------------------------------------------------
    def showOutput(self):
        return self.getProperty("ShowOutput")

    #-----------------------------------------------------------------
    def enable(self):
        self.setProperty("Enable",True)

    #-----------------------------------------------------------------
    def disable(self):
        self.setProperty("Enable",False)

    #-----------------------------------------------------------------
    def setServiceCall(self,requestID):
        if not requestID in self.bufferDeviceRecords:
            self.bufferDeviceRecords[requestID]=dict()

        self.bufferDeviceRecords[requestID]["serviceCall"]=True

    #-----------------------------------------------------------------
    def clearServiceCall(self,requestID):
        if not requestID in self.bufferDeviceRecords:
            self.bufferDeviceRecords[requestID]=dict()

        self.bufferDeviceRecords[requestID]["serviceCall"]=False

    #-----------------------------------------------------------------
    def getConfig(self):
        return self.config

    #-----------------------------------------------------------------
    def getProperty(self,k):
        return self.config[k] if k in self.config else None

    #-----------------------------------------------------------------
    def getDeviceType(self):
        return self.deviceType

    #-----------------------------------------------------------------
    def getDeviceID(self):
        if not (ID:=self.getProperty("DeviceID")):
            ID=self.deviceID if self.deviceID else self.makeDeviceID()
        self.deviceID=ID

        return self.deviceID

    #-----------------------------------------------------------------
    def getDeviceDescription(self):
        return self.getProperty("Description")

    #-----------------------------------------------------------------
    def getDeviceName(self):
        return self.getProperty("Name")

    #-----------------------------------------------------------------
    def getMachineID(self):
        return self.machineID

    #-----------------------------------------------------------------
    def getFormat(self):
        return self.userFormat

    #-----------------------------------------------------------------
    def getFileExtension(self):
        return self.getProperty("FileExtension")

    #-----------------------------------------------------------------
    def getFrameName(self):
        filename=str(self.getFrameBaseName())+"_"+str(self.getDeviceID())

        return filename.replace(":","-")

    #-----------------------------------------------------------------
    def getStatus(self):
        if self.isCapturing():
            status="active"
        elif self.isPaused():
            status="paused"
        elif self.isBufferAlive():
            status="alive"
        elif self.isEnabled():
            status="enabled"
        else:
            status="offline"

        return status

    #-----------------------------------------------------------------
    def getBufferClass(self):
        return self.__class__.__name__

    #-----------------------------------------------------------------
    def getServices(self):
        return self.getProperty("Services")

    #-----------------------------------------------------------------
    def getGroups(self):
        return self.getProperty("Groups")

    #-----------------------------------------------------------------
    def getBufferFormat(self):
        return self.getProperty("BufferFormat")

    #-----------------------------------------------------------------
    def getCaptureFormat(self):
        return self.getProperty("CaptureFormat")

    #-----------------------------------------------------------------
    def getSaveFormat(self):
        return self.getProperty("SaveFormat")

    #-----------------------------------------------------------------
    def getBufferRecords(self):
        return self.bufferDeviceRecords

    #-----------------------------------------------------------------
    def getBufferRecord(self,requestID):
        return self.bufferDeviceRecords[requestID] if requestID in self.bufferDeviceRecords else None

    #-----------------------------------------------------------------
    def getCaptureFrequency(self):
        return self.getProperty("CaptureFrequency")

    #-----------------------------------------------------------------
    def getBufferLength(self):
        return self.getProperty("BufferLength")

    #-----------------------------------------------------------------
    def getHomeDir(self):
        self.homeDir=self.homeDir if self.homeDir else Tools.findHomeDir()
        return self.homeDir

    #-----------------------------------------------------------------
    def getDataDir(self):
        return self.dataDir

    #-----------------------------------------------------------------
    def getBufferDir(self):
        return self.bufferDir

    #-----------------------------------------------------------------
    def getLogsDir(self):
        return self.logsDir

    #-----------------------------------------------------------------
    def getClipDir(self):
        return self.clipDir

    #-----------------------------------------------------------------
    def getMediaID(self):
        return self.getProperty("MediaID")

    #-----------------------------------------------------------------
    def getSyncObject(self):
        return self.framesSync

    #-----------------------------------------------------------------
    def getFileSyncObject(self):
        return self.fileSync

    #-----------------------------------------------------------------
    def getClipSyncObject(self):
        return self.clipSync

    #-----------------------------------------------------------------
    def getDeleteSyncObject(self):
        return self.deleteSync

    #-----------------------------------------------------------------
    def getArchiveSyncObject(self):
        return self.archiveSync

    #-----------------------------------------------------------------
    def addData(self,data,time):
        self.getData().append(data)
        self.getTimeStamps().append(time)

        return len(self.getData())

    #-----------------------------------------------------------------
    def getData(self):
        return self.frames

    #-----------------------------------------------------------------
    def getDataSize(self):
        return len(self.getData())

    #-----------------------------------------------------------------
    def removeData(self,i):
        result=None

        try:
            result=self.getData().pop(i)
            self.getTimeStamps().pop(i)
        except:
            pass

        return result

    #-----------------------------------------------------------------
    def getDataTimeRange(self,start,end):
        with self.getSyncObject():
            data=[self.getData()[i] for i,timeStamp in enumerate(self.getTimeStamps()) if start<=timeStamp<end]

        return data

    #-----------------------------------------------------------------
    def removeDataTimeRange(self,start,end):
        with self.getSyncObject():
            indexes=[i for i,timeStamp in enumerate(self.getTimeStamps()) if start<=timeStamp<end]
            data=[self.removeData(i) for i in reversed(indexes)]

        return data

    #-----------------------------------------------------------------
    def getTimeStamps(self):
        return self.timeStamps

    #-----------------------------------------------------------------
    def getTimeStampAt(self,i):
        return self.getTimeStamps()[i] if self.getTimeStamps() else None

    #-----------------------------------------------------------------
    def getFileTimeStamps(self):
        return self.fileTimeStamps

    #-----------------------------------------------------------------
    def getFileTimeStampAt(self,i):
        return self.getFileTimeStamps()[i] if self.getFileTimeStamps() else None

    #-----------------------------------------------------------------
    def getFiles(self):
        return self.files

    #-----------------------------------------------------------------
    def getFileAt(self,i):
        return self.getFiles()[i] if self.getFiles() else None

    #-----------------------------------------------------------------
    def bufferFileReady(self,time):
        result=list()

        try:
            while any([self.getLastSaveTime()<=time]+[dev.getLastSaveTime()<=time for _,dev in self.devices.items()]):
                if self.isCapturing():
                    if self.getLastSaveTime()>time and not self.getFilesAtTime(time):
                        print(f"Can't find file at {Tools.formatTime(time)}, making filler for {self.getDeviceName()}")
                        if self.getFiller():
                            self.writeBufferData(time,self.getFiller())

                    for _,dev in self.devices.items():
                        if dev.getLastSaveTime()>time and not dev.getFilesAtTime(time):
                            print(f"Can't find file at {Tools.formatTime(time)}, making filler for {dev.getDeviceName()}")
                            if dev.getFiller():
                                dev.writeBufferData(time,dev.getFiller())
                else:
                    print("Device is no longer capturing data. Creating clips with the data currently available.")
                    break

                with self.captureCondition:
                    self.captureCondition.wait(self.getCaptureFrequency()/1000.0)

            files=self.getFilesAtTime(time)
            result=[file for file in files if Tools.exists(file)]
            #result=all([Tools.exists(file) for file in files]) if files else False
        except:
            Tools.printStackTrace()

        return result

    #-----------------------------------------------------------------
    def getBufferSize(self):
        return len(self.getFiles())

    #-----------------------------------------------------------------
    def getFilesTimeRange(self,start,end):
        return [file for timeStamp in range(start,end,self.getCaptureFrequency()) for file in self.bufferFileReady(timeStamp)]
        #return [file for timeStamp in range(start,end,self.getCaptureFrequency()) if self.bufferFileReady(timeStamp) for file in self.getFilesAtTime(timeStamp)]

    #-----------------------------------------------------------------
    def getFilesAtTime(self,time):
        result=list()

        self.getTimeLock().clipLock(time)
        with self.getFileSyncObject():
            try:
                for i,timeStamp in enumerate(self.getFileTimeStamps()):
                    if timeStamp==time and (file:=self.getFileAt(i)) and file not in result:
                        result.append(file)
            except ValueError:
                pass  # Handle case where time isn't found
        self.getTimeLock().clipUnlock(time)

        return result

    #-----------------------------------------------------------------
    def getClipTimeStamps(self):
        return self.clipTimeStamps

    #-----------------------------------------------------------------
    def getClipTimeStampsAt(self,i):
        return self.getClipTimeStamps()[i] if self.getClipTimeStamps() else None

    #-----------------------------------------------------------------
    def getClips(self):
        return self.clips

    #-----------------------------------------------------------------
    def getTimeLock(self):
        return self.timeLock

    #-----------------------------------------------------------------
    def getStartTime(self):
        return self.startTime

    #-----------------------------------------------------------------
    def getStartDiff(self):
        return self.startTimeDiff

    #-----------------------------------------------------------------
    def getLastCaptureStartTime(self):
        return self.lastCaptureStartTime

    #-----------------------------------------------------------------
    def getLastClipTime(self):
        return self.lastClipTime

    #-----------------------------------------------------------------
    def getAverageBytesPerPeriod(self):
        return self.averageBytes

    #-----------------------------------------------------------------
    def getAverageRatePerPeriod(self):
        return round(100*self.getAverageBytesPerPeriod()/self.getBytesPerPeriod(),1) if self.getBytesPerPeriod() else 0

    #-----------------------------------------------------------------
    def getFrameBaseName(self):
        return self.currentFilename

    #-----------------------------------------------------------------
    def getFirstSaveTime(self):
        return self.getFileTimeStampAt(0)

    #-----------------------------------------------------------------
    def getLastSaveTime(self):
        return self.getFileTimeStamps()[-1] if self.getFileTimeStamps() else None

    #-----------------------------------------------------------------
    def getBufferFillLevel(self):
        if self.getFirstSaveTime()==0 or not self.isCapturing():
            perc=0
        else:
            perc=round(100*((Tools.currentTimeMillis()-self.getFirstSaveTime())/float(self.getBufferLength())),2)

        return min(100,perc)

    #-----------------------------------------------------------------
    def captureFrequencyBufferPerc(self):
        return round(100*(self.getCaptureFrequency()/float(self.getBufferLength())),2)

    #-----------------------------------------------------------------
    def getFormattedBufferFillLevel(self):
        return f"{self.getBufferFillLevel():.1f}%"

    #-----------------------------------------------------------------
    def setProperty(self,k,v):
        rewrite=False

        if k in self.config:
            if str(self.config[k])!=str(v):
                rewrite=True
        else:
            rewrite=True

        if rewrite:
            self.config[k]=v
            self.saveConfig()

        return v

    #-----------------------------------------------------------------
    def setPropertyDefault(self,k,default):
        if not (v:=self.getProperty(k)):
            v=self.setProperty(k,default)

        return v

    #-----------------------------------------------------------------
    def setMachineId(self,machineID):
        self.machineID=machineID

    #-----------------------------------------------------------------
    def setDeviceID(self,deviceID):
        self.deviceID=deviceID
        self.setProperty("DeviceID",deviceID)

    #-----------------------------------------------------------------
    def setParent(self,parent):
        self.parent=parent

    #-----------------------------------------------------------------
    def addService(self,service):
        k="Services"

        if k in self.config:
            temp=self.config[k].copy()
            if service not in temp:
                temp.append(service)
        else:
            temp=[service]

        self.setProperty(k,temp)

    #-----------------------------------------------------------------
    def addGroup(self,group):
        k="Groups"

        if k in self.config:
            temp=self.config[k].copy()
            if group not in temp:
                temp.append(group)
        else:
            temp=[group]

        self.setProperty(k,temp)

    #-----------------------------------------------------------------
    def setFileExtension(self,ext):
        self.setProperty("FileExtension",("." if not str(ext).startswith(".") else "")+str(ext))

    #-----------------------------------------------------------------
    def setDeviceDescription(self,description):
        self.setProperty("Description",description)

    #-----------------------------------------------------------------
    def setDeviceName(self,name):
        self.setProperty("Name",name)

    #-----------------------------------------------------------------
    def setShowOutput(self,output):
        self.setProperty("ShowOutput",output)

    #-----------------------------------------------------------------
    def setFrameBaseName(self,filename):
        self.currentFilename=filename

    #-----------------------------------------------------------------
    def setBufferFormat(self,bufferFormat):
        self.setProperty("BufferFormat",bufferFormat)

    #-----------------------------------------------------------------
    def setCaptureFormat(self,saveFormat):
        self.setProperty("CaptureFormat",saveFormat)

    #-----------------------------------------------------------------
    def setSaveFormat(self,saveFormat):
        self.setProperty("SaveFormat",saveFormat)

    #-----------------------------------------------------------------
    def setFrequency(self,freq):
        self.setProperty("CaptureFrequency",freq)

    #-----------------------------------------------------------------
    def setBufferLength(self,length):
        self.setProperty("BufferLength",length)

    #-----------------------------------------------------------------
    def setBufferDir(self,dirPath):
        self.bufferDir=Tools.validateDir(dirPath)

    #-----------------------------------------------------------------
    def setClipDir(self,dirPath):
        self.clipDir=Tools.validateDir(dirPath)

    #-----------------------------------------------------------------
    def setDataDir(self,dirPath):
        self.dataDir=Tools.validateDir(dirPath)

    #-----------------------------------------------------------------
    def setLogsDir(self,dirPath):
        self.logsDir=Tools.validateDir(dirPath)

    #-----------------------------------------------------------------
    def setMediaID(self,media):
        self.setProperty("MediaID",media)

    #-----------------------------------------------------------------
    def setLastCaptureStartTime(self,t):
        startCandidate=self.getFirstSaveTime()
        self.lastCaptureStartTime=min(t,startCandidate) if startCandidate else t

        self.startTimeDiff=self.lastCaptureStartTime-self.getStartTime()

    #-----------------------------------------------------------------
    def setStartTime(self,startTime):
        self.startTime=int(math.ceil(startTime/self.getCaptureFrequency()))*self.getCaptureFrequency()

    #-----------------------------------------------------------------
    def initializeServiceDevices(self):
        self.devices.clear()

        if self.parent:
            for service in self.getServices():
                prop=str(service).lower().capitalize()+"Device"
                device=None

                if ID:=self.getProperty(prop):
                    device=self.parent.findBufferByID(ID)

                if device:
                    self.setPropertyDefault(prop,device.getDeviceID())
                    device.addListener(self)

                    if not device.initialized:
                        device.initialize()
                    if device.initialized:
                        self.devices[service]=device
                else:
                    print(f"No {service} device configured for {self.getDeviceName()}. Try using one of these devices:")
                    for device in self.findDevicesByService(service):
                        print(f"\t{device.getDeviceName()}, {device.getBufferClass()}, {device.getDeviceID()}")

        return (len(self.devices)==len(self.getServices()))

    #-----------------------------------------------------------------
    def reestablishServiceDeviceBufferFiles(self):
        for _,device in self.devices.items():
            device.reestablishBufferFiles()

    #-----------------------------------------------------------------
    def startServiceDevices(self):
        for _,device in self.devices.items():
            if not device.isCapturing():
                device.setStartTime(self.getStartTime())
                device.startCapture()

        return all(device.isCapturing() for _,device in self.devices.items())

    #-----------------------------------------------------------------
    def stopServiceDevices(self):
        result=True

        for _,device in self.devices.items():
            result&=device.stopCapture()

        return result

    #-----------------------------------------------------------------
    def forceServiceClose(self):
        for _,device in self.devices.items():
            device.forceClose()

    #-----------------------------------------------------------------
    def findDevicesByService(self,service):
        devices=list()

        if self.parent:
            devices=[dev for dev in self.parent.getBuffers() if dev!=self and service in dev.getServices()]

        return devices

    #-----------------------------------------------------------------
    def findDevicesByID(self,ID):
        devices=list()

        if self.parent:
            devices=[dev for dev in self.parent.getBuffers() if dev!=self and ID==dev.getDeviceID()]

        return devices

    #-----------------------------------------------------------------
    def listServiceDevices(self):
        devices=list()

        for _,device in self.devices.items():
            devices.extend(device.listDevices())

        return devices

    #-----------------------------------------------------------------
    def testServiceDeviceDataSources(self):
        result=True

        for _,device in self.devices.items():
            result&=device.testDataSource()

        return result

    #-----------------------------------------------------------------
    def convert(self,inputFile,outputFile,vCodec=None,aCodec=None):
        return self.converter.convert(inputFile,outputFile,vCodec,aCodec)

    #-----------------------------------------------------------------
    def mergeAudioVideo(self,inputFiles,outputFile,vCodec=None,aCodec=None):
        return self.converter.mergeAudioVideo(inputFiles,outputFile,vCodec,aCodec)

    #-----------------------------------------------------------------
    def validateRecordEntry(self,requestID,machineID,filename):
        if not requestID in self.bufferDeviceRecords:
            self.bufferDeviceRecords[requestID]=dict()
            self.bufferDeviceRecords[requestID]["machineID"]=list()
        if not filename in self.bufferDeviceRecords[requestID]:
            self.bufferDeviceRecords[requestID][filename]=dict()

        if not machineID in self.bufferDeviceRecords[requestID]["machineID"]:
            self.bufferDeviceRecords[requestID]["machineID"].append(machineID)

    #-----------------------------------------------------------------
    def recordClipCompleted(self,requestID,machineID,filename,start,duration):
        if not self.isServiceCall(requestID):
            self.validateRecordEntry(requestID,machineID,filename)

            self.bufferDeviceRecords[requestID]["clipDevice"]=machineID
            self.bufferDeviceRecords[requestID]["clip"]=filename
            self.bufferDeviceRecords[requestID]["type"]=str(self.getServices())
            self.bufferDeviceRecords[requestID][filename]["bufferFileType"]="clip"
            self.bufferDeviceRecords[requestID][filename]["fileStartTime"]=start
            self.bufferDeviceRecords[requestID][filename]["duration"]=duration
            self.bufferDeviceRecords[requestID][filename]["fileLength"]=Tools.getFileSize(filename) if duration>0 else 0
            self.bufferDeviceRecords[requestID][filename]["status"]="COMPLETED" if duration>0 else "FAILED"
            self.bufferDeviceRecords[requestID]["status"]="COMPLETED" if duration>0 else "FAILED"

    #-----------------------------------------------------------------
    def recordConcatenationProgress(self,requestID,machineID,filename,_filePiece,current,total):
        if not self.isServiceCall(requestID):
            self.validateRecordEntry(requestID,machineID,filename)

            self.bufferDeviceRecords[requestID][filename]["bufferFileType"]="intermediate"
            self.bufferDeviceRecords[requestID][filename]["status"]="CONCATENATING"
            self.bufferDeviceRecords[requestID][filename]["progress"]=round(100*(current/float(total)),2)

    #-----------------------------------------------------------------
    def recordConcatenationCompleted(self,requestID,machineID,filename,start,duration):
        if not self.isServiceCall(requestID):
            self.validateRecordEntry(requestID,machineID,filename)

            self.bufferDeviceRecords[requestID][filename]["bufferFileType"]="intermediate"
            self.bufferDeviceRecords[requestID][filename]["fileStartTime"]=start
            self.bufferDeviceRecords[requestID][filename]["duration"]=duration
            self.bufferDeviceRecords[requestID][filename]["status"]="COMPLETED" if duration>0 else "FAILED"

    #-----------------------------------------------------------------
    def healthCallback(self,machineID,prop,value):
        for listener in self.getListeners():
            Tools.callback(listener.bufferHealthCallback,machineID,prop,value)

    #-----------------------------------------------------------------
    def clipCompletedCallback(self,requestID,machineID,filename,start,duration):
        if not self.isServiceCall(requestID):
            for listener in self.getListeners():
                Tools.callback(listener.clipCreatedCallback,requestID,machineID,filename,start,duration)

    #-----------------------------------------------------------------
    def concatenationProgressCallback(self,requestID,machineID,filename,filePiece,current,total):
        if not self.isServiceCall(requestID):
            for listener in self.getListeners():
                Tools.callback(listener.fileConcatenatedCallback,requestID,machineID,filename,filePiece,current,total)

    #-----------------------------------------------------------------
    def concatenationCompletedCallback(self,requestID,machineID,filename,start,duration):
        if not self.isServiceCall(requestID):
            for listener in self.getListeners():
                Tools.callback(listener.fileConcatenationCompletedCallback,requestID,machineID,filename,start,duration)

    #-----------------------------------------------------------------
    #DeviceListener methods
    #-----------------------------------------------------------------
    def bufferHealthCallback(self,machineID,prop,value):
        pass

    #-----------------------------------------------------------------
    def bufferFileCreatedCallback(self,machineID,filename,start):
        pass

    #-----------------------------------------------------------------
    def clipCreatedCallback(self,requestID,_machineID,filename,start,duration):
        result=Tools.exists(filename)
        timerStart=self.bufferDeviceRecords[requestID]["clipStartTime"]
        timerEnd=self.bufferDeviceRecords[requestID]["clipEndTime"]

        print("\tClip start time:\t"+Tools.formatTime(start))
        print("\tclip length:\t\t"+str(duration//60000)+"m "+str(duration//1000%60)+"s")
        print("\tclipMaker start time:\t"+Tools.formatTime(timerStart))
        print("\tclipMaker end time:\t"+Tools.formatTime(timerEnd))
        print("\tfile size:\t\t"+str(Tools.getFileSize(filename) if result else 0))
        print("\twait time:\t\t"+Tools.timeLength(timerStart,self.bufferDeviceRecords[requestID]["concatenationStartTime"]))
        print("\tbuffer gather time:\t"+Tools.timeLength(self.bufferDeviceRecords[requestID]["concatenationStartTime"],self.bufferDeviceRecords[requestID]["concatenationEndTime"]))
        print("\ttotal time:\t\t"+Tools.timeLength(timerStart,timerEnd))

    #-----------------------------------------------------------------
    def fileConcatenatedCallback(self,requestID,machineID,filename,_filePiece,current,total):
        pass

    #-----------------------------------------------------------------
    def fileConcatenationCompletedCallback(self,requestID,machineID,filename,start,duration):
        pass
