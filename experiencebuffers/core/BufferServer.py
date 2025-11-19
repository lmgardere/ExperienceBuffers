import os,sys
import ast
import threading
import socket
import json
import importlib.util,inspect
import signal
import logging

sys.path.append("/mnt/c/Users/lmgar/OneDrive/Documents/My Projects/ExperienceBuffers/python source/")
from experiencebuffers.core.AbstractHandler import AbstractHandler
from experiencebuffers.core.ServerListener import ServerListener
from experiencebuffers.core.DeviceListener import DeviceListener
from experiencebuffers.core.BufferDevice import BufferDevice
from experiencebuffers.util.Standards import Standards
from experiencebuffers.util.Tools import Tools

logger=logging.getLogger(__name__)


class BufferServer(ServerListener,DeviceListener):
    DEFAULT_NAME="EB"
    DEFAULT_DESCRIPTION="EB Server"

    def __init__(self):
        self.serverClass="ebs"
        self.deviceType="Server"

        self.homeDir=None
        self.devicesDir=None
        self.config=None

        self.listeners=list()
        self.allBuffers=list()
        self.deviceTemplates=list()
        self.monitors=list()
        self.bufferDeviceRecords=None

        self.platform=Tools.getPlatform()

        self.initialize()

    #-----------------------------------------------------------------
    def initialize(self):
        self.addListener(self)
        self.loadConfig()
        self.loadBufferRecords()

        self.setupLogging()

        self.allBuffers=self.loadDevicesFromDirectory()

        self.maintenanceMan=self.MaintenanceThread(self)
        self.broadcaster=self.BroadcastThread(self)
        self.networkHandler=self.NetworkThread(self)

        #register shutdown hooks
        signal.signal(signal.SIGINT,self.shutdown)
        signal.signal(signal.SIGTERM,self.shutdown)

    #-----------------------------------------------------------------
    def loadConfig(self):
        self.config=Tools.loadConfig(self.getConfigFilename())
        rewrite=self.validateConfig()
        self.homeDir=self.getHomeDir()
        self.devicesDir=Tools.validateDir(Standards.DEVICES_DIR)

        if rewrite:
            self.saveConfig();

    #-----------------------------------------------------------------
    def validateConfig(self):
        rewrite=False

        if (v:="MachineID") not in self.config:
            self.config[v]=Tools.makeMachineID()
            rewrite=True

        if (v:="ServerGroupID") not in self.config:
            self.config[v]=self.makeGroupID()
            rewrite=True

        if (v:="Description") not in self.config:
            self.config[v]=BufferServer.DEFAULT_DESCRIPTION
            rewrite=True

        if (v:="Name") not in self.config:
            self.config[v]=BufferServer.DEFAULT_NAME
            rewrite=True

        if (v:="Groups") not in self.config:
            self.config[v]=str([self.getServerGroupID()])
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])
        if self.getServerGroupID() not in self.getGroups():
            self.addGroup(self.getServerGroupID())
            rewrite=True

        #list of external coordinators that can't otherwise be reached through broadcast
        if (v:="ConfiguredCoordinators") not in self.config:
            self.config[v]="[]"
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="BufferPort") not in self.config:
            self.config[v]=str(Standards.BUFFER_PORT)
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="CoordinatorPort") not in self.config:
            self.config[v]=str(Standards.COORDINATOR_PORT)
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="BroadcastFrequency") not in self.config:
            self.config[v]=str(Standards.BROADCAST_FREQUENCY)
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        #allows for boradcasts to be made over a given address. Default is "any"
        if (v:="BroadcastAddress") not in self.config:
            self.config[v]="any"
            rewrite=True

        if (v:="UseBroadcast") not in self.config:
            self.config[v]=str(Standards.USE_BROADCAST)
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        #allows for the server to operate without a coordinator, instead directly taking requests on the coordinator port
        if (v:="StandaloneMode") not in self.config:
            self.config[v]="False"
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="Verbose") not in self.config:
            self.config[v]="False"
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        #report LAN IP address or the external IP address in the broadcast message
        if (v:="UseLocalIP") not in self.config:
            self.config[v]=str(Standards.USE_LOCAL_IP)
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

        if (v:="DefaultBefore") not in self.config:
            self.config[v]=str(Standards.DEFAULT_BEFORE)
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="DefaultAfter") not in self.config:
            self.config[v]=str(Standards.DEFAULT_AFTER)
            rewrite=True
        self.config[v]=ast.literal_eval(self.config[v])

        if (v:="DataDir") not in self.config:
            self.config[v]=Standards.DATA_DIR
            rewrite=True
        temp=Tools.validateDir(self.config[v])
        if self.config[v]!=temp:
            self.config[v]=temp
            rewrite=True

        if (v:="ExportDir") not in self.config:
            self.config[v]=Standards.EXPORT_DIR
            rewrite=True
        temp=Tools.validateDir(self.config[v])
        if self.config[v]!=temp:
            self.config[v]=temp
            rewrite=True

        if (v:="ArchiveDir") not in self.config:
            self.config[v]=Standards.TMP_DIR
            rewrite=True
        temp=Tools.validateDir(self.config[v])
        if self.config[v]!=temp:
            self.config[v]=temp
            rewrite=True

        if (v:="LogsDir") not in self.config:
            self.config[v]=Standards.LOGS_DIR
            rewrite=True
        temp=Tools.validateDir(self.config[v])
        if self.config[v]!=temp:
            self.config[v]=temp
            rewrite=True

        return rewrite

    #-----------------------------------------------------------------
    def saveConfig(self):
        Tools.saveConfig(self.config,self.getConfigFilename(),self.getServerClass())

    #-----------------------------------------------------------------
    def setupLogging(self):
        logger.setLevel(logging.DEBUG)  # Capture everything internally

        # File handler: logs everything
        fileHandler=logging.FileHandler(self.getLogsDir()+"activity.log")
        fileHandler.setLevel(logging.DEBUG)

        # File handler: logs everything
        errorHandler=logging.FileHandler(self.getLogsDir()+"error.log")
        errorHandler.setLevel(logging.ERROR)

        # Console handler: logs only warnings and above
        consoleHandler=logging.StreamHandler()
        consoleHandler.setLevel(logging.DEBUG if self.getVerbose() else logging.INFO)

        # Formatter: consistent format for both
        fileFormatter=logging.Formatter(
            "%(asctime)s|%(levelname)s|%(module)s|%%(message)s"
        )
        fileHandler.setFormatter(fileFormatter)
        errorHandler.setFormatter(fileFormatter)

        consoleFormatter=logging.Formatter(
            "%(message)s"
        )
        consoleHandler.setFormatter(consoleFormatter)

        logger.addHandler(fileHandler)
        logger.addHandler(errorHandler)
        logger.addHandler(consoleHandler)

    #-----------------------------------------------------------------
    def startExperienceBufferServer(self):
        print("Starting Experience Buffers Server at "+Tools.printCurrentTime())
        print("Server ID:\t\t\t"+self.getMachineID())
        print("Working directory:\t\t"+Tools.getWorkingDir())
        print("Device directory:\t\t"+self.getDevicesDir())
        print("Data directory:\t\t\t"+self.getDataDir())
        print("Clip directory:\t\t\t"+self.getClipDir())
        print("Archive-Buffer directory:\t"+self.getBufferDir())
        print("Export directory:\t\t"+self.getExportDir())
        print("Logs directory:\t\t\t"+self.getLogsDir())
        print()

        self.startBuffers()
        self.startNetwork()
        self.WaitForNetworkStartup()
        self.maintenanceMan.start()

        for listener in self.getListeners():
            Tools.callback(listener.serverStartedCallback(self.getDeviceID()))

    #-----------------------------------------------------------------
    def shutdown(self):
        print("Shutting down BufferServer")

        self.shutdownBuffers()
        self.shutdownNetwork()
        self.maintenanceMan.terminate()
        self.saveBufferRecords()

        for listener in self.getListeners():
            Tools.callback(listener.serverStoppedCallback(self.getDeviceID()))

    #-----------------------------------------------------------------
    #  Starts network thread that responds to requests
    def startNetwork(self):
        print("Starting BufferServer network...")
        self.networkHandler.start()
        self.broadcaster.start()
        print("Starting BufferServer network...done")

    #-----------------------------------------------------------------
    #  Stops network thread that responds to requests
    def shutdownNetwork(self):
        print("Stopping BufferServer network...")

        self.broadcaster.terminate()
        self.broadcaster.join(10)

        self.networkHandler.terminate()
        self.networkHandler.join(10)

        self.closeMonitors()

        print("Stopping BufferServer network...done")

    #-----------------------------------------------------------------
    def isBroadcasting(self):
        return self.broadcaster.isBroadcasting()

    #-----------------------------------------------------------------
    def WaitForNetworkStartup(self):
        while not self.networkIsReady() and not self.networkHandler.failedToStart():
            Tools.sleep(10)

        return self.networkIsReady()

    #-----------------------------------------------------------------
    def waitInNetworkLoop(self):
        while self.networkIsRunning():
            Tools.sleep(10)

    #-----------------------------------------------------------------
    def networkIsReady(self):
        return self.networkHandler.isReady()

    #-----------------------------------------------------------------
    def networkIsRunning(self):
        return self.networkHandler.isRunning()

    #-----------------------------------------------------------------
    # Device management methods
    #-----------------------------------------------------------------
    def loadDevicesFromDirectory(self):
        buffers=list()

        templates=self.findDeviceTemplates()
        self.setDeviceTemplates(templates)
        configs=self.findBufferConfigs()

        try:
            for template in templates:
                classObj=getattr(template["class"],template["className"])
                if inspect.isclass(classObj) and issubclass(classObj,BufferDevice):
                    dev="empty"
                    for config in configs:
                        if config["DeviceType"]==template["className"]:
                            if dev:=self.initializeDevice(classObj,config["DeviceID"] if "DeviceID" in config else None):  # Instantiate the class
                                buffers.append(dev)

                    if dev=="empty":
                        if dev:=self.initializeDevice(classObj):  # Instantiate the class
                            buffers.append(dev)
                else:
                    if not inspect.isclass(classObj):
                        print(str(template["className"])+" class not found in "+str(template["class"]))
                    if not issubclass(classObj,BufferDevice):
                        print(str(template["className"])+" does not appear to inherit from BufferDevice")
        except Exception as e:
            Tools.printStackTrace()
            print("Error loading devices: "+str(e))

        return buffers

    #-----------------------------------------------------------------
    def findDeviceTemplates(self):
        devices=list()
        devicesDir=self.getDevicesDir()

        try:
            for filename in os.listdir(devicesDir):
                if filename.lower().endswith(".py") and filename!="__init__.py":
                    className=filename[:-3]  # Remove .py extension
                    classPath=os.path.join(devicesDir,filename)

                    spec=importlib.util.spec_from_file_location(className,classPath)
                    classDef=importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(classDef)

                    if hasattr(classDef,className):
                        devices.append({"class":classDef,"className":className})
                    else:
                        print("Can't load "+filename+": cannot find class "+str(className)+" in "+str(classPath))
        except Exception as e:
            Tools.printStackTrace()
            print("Error finding device templates: "+str(e))

        return devices

    #-----------------------------------------------------------------
    def findBufferConfigs(self):
        configs=list()
        ownConfig=self.getConfigFilename()

        try:
            for filename in os.listdir(Tools.getWorkingDir()):
                if filename.lower().endswith(Standards.CONFIG_EXTENSION) and filename!=ownConfig:
                    config=Tools.loadConfig(filename)
                    if "DeviceType" in config:
                        con=config["DeviceID"] if "DeviceID" in config else Tools.makeDeviceID(self.getMachineID())
                        configs.append({"DeviceType":config["DeviceType"],"DeviceID":con})
                        self.validateDeviceConfigFilename(filename,config["DeviceType"],con)
        except Exception as e:
            Tools.printStackTrace()
            print("Error finding device configs: "+str(e))

        return configs

    #-----------------------------------------------------------------
    # Renames config files so they match the deviceType and deviceID in the config file,
    # otherwise the configs and templates won't be able to configure themselves. When
    # the template is instantiated it wouldn't be able to find the correct config file.
    def validateDeviceConfigFilename(self,filename,deviceType,deviceID):
        idTail=str(deviceID[-5:]) if deviceID else None

        if idTail and filename.find("-"+idTail+".")<0:
            newFilename=deviceType+"-"+idTail+Standards.CONFIG_EXTENSION
            os.rename(filename,newFilename)

    #-----------------------------------------------------------------
    def initializeDevice(self,classObj,deviceID=None):
        try:
            dev=classObj(self.getMachineID(),deviceID)
            dev.addListener(self)
            dev.setParent(self)
            dev.setBufferDir(self.getBufferDir())
            dev.setDataDir(self.getDataDir())
            dev.setClipDir(self.getDataDir()+"clips/")
            dev.setLogsDir(self.getLogsDir())
            dev.setFrequency(self.getCaptureFrequency())
            dev.setBufferLength(self.getBufferLength())
            dev.addGroup(self.getServerGroupID())
            dev.startMaintenanceServices()
        except Exception as e:
            dev=None
            Tools.printStackTrace()
            print("Error initializing device: "+str(e))

        return dev

    #-----------------------------------------------------------------
    # Abstract Handler routines
    #-----------------------------------------------------------------
    def startBuffers(self):
        bufs=[buf for buf in self.getBuffers() if buf.isEnabled()]
        startTime=Tools.currentTimeMillis()

        print("Starting "+str(len(bufs))+" buffer(s)...")
        for buf in bufs:
            self.startBufferCapture(buf,startTime)

        print("Done starting buffers")

    #-----------------------------------------------------------------
    def startBufferCapture(self,buffer,startTime):
        result=True

        if (buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None) and buffer.isEnabled():
            try:
                buffer.setStartTime(startTime)
                if buffer.startCapture():
                    buffer.reestablishBufferFiles()
                    print("Started "+str(buffer.getDeviceName()))

                    for listener in self.getListeners():
                        Tools.callback(listener.startCaptureCallback,buffer.getDeviceID())
                else:
                    print("Failed to start "+str(buffer.getDeviceName()))
            except Exception as e:
                print("Failed to start "+str(buffer.getDeviceName())+" using template "+str(buffer.getBufferClass())+": "+str(e))
                result=False
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def stopBuffers(self):
        bufs=[buf for buf in self.getBuffers() if buf.isEnabled()]

        print("Stopping "+str(len(bufs))+" buffers...")
        for buf in bufs:
            self.stopBufferCapture(buf)

        print("Done stopping buffers")

    #-----------------------------------------------------------------
    def stopBufferCapture(self,buffer):
        result=True

        if (buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None) and buffer.isEnabled():
            try:
                buffer.stopCapture()

                for listener in self.getListeners():
                    Tools.callback(listener.stopCaptureCallback,buffer.getDeviceID())
            except Exception as e:
                print("Failed to stop "+str(buffer.getDeviceName())+": "+str(e))
                result=False
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def pauseBuffers(self):
        bufs=[buf for buf in self.getBuffers() if buf.isEnabled()]

        print("Pausing "+str(len(bufs))+" buffers...")
        for buf in bufs:
            self.pauseBufferCapture(buf)

        print("Done pausing buffers")

    #-----------------------------------------------------------------
    def pauseBufferCapture(self,buffer):
        result=True

        if (buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None) and buffer.isEnabled():
            try:
                buffer.pause()

                for listener in self.getListeners():
                    Tools.callback(listener.pauseCaptureCallback,buffer.getDeviceID())
            except Exception as e:
                print("Failed to pause "+str(buffer.getDeviceName())+": "+str(e))
                result=False
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def unpauseBuffers(self):
        bufs=[buf for buf in self.getBuffers() if buf.isEnabled()]

        print("Unpausing "+str(len(bufs))+" buffers...")
        for buf in bufs:
            self.unpauseBufferCapture(buf)

        print("Done unpausing buffers")

    #-----------------------------------------------------------------
    def unpauseBufferCapture(self,buffer):
        result=True

        if (buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None) and buffer.isEnabled():
            try:
                buffer.unpause()

                for listener in self.getListeners():
                    Tools.callback(listener.unpauseCaptureCallback,buffer.getDeviceID())
            except Exception as e:
                print("Failed to unpause "+str(buffer.getDeviceName())+": "+str(e))
                result=False
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def restartBuffers(self):
        bufs=[buf for buf in self.getBuffers() if buf.isEnabled()]

        print("Restarting "+str(len(bufs))+" buffers...")
        for buf in bufs:
            self.restartBufferCapture(buf)

        print("Done restarting buffers")

    #-----------------------------------------------------------------
    def restartBufferCapture(self,buffer):
        result=True

        if (buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None) and buffer.isEnabled():
            try:
                buffer.restartCapture()

                for listener in self.getListeners():
                    Tools.callback(listener.restartCaptureCallback,buffer.getDeviceID())
            except Exception as e:
                print("Failed to restart "+str(buffer.getDeviceName())+": "+str(e))
                result=False
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def shutdownBuffers(self):
        print("Shutting down "+str(len(self.getBuffers()))+" buffers...")
        for buf in self.getBuffers():
            self.shutdownBufferCapture(buf)

        print("Done shutting down buffers")

    #-----------------------------------------------------------------
    def shutdownBufferCapture(self,buffer):
        result=True

        if buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None:
            try:
                buffer.shutdown()

                for listener in self.getListeners():
                    Tools.callback(listener.shutdownCaptureCallback,buffer.getDeviceID())
            except Exception as e:
                print("Failed to shutdown "+str(buffer.getDeviceName())+": "+str(e))
                result=False
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def killBuffers(self):
        print("Force shutting down "+str(len(self.getBuffers()))+" buffers...")
        for buf in self.getBuffers():
            self.killBufferCapture(buf)

        print("Done force shutting down buffers")

    #-----------------------------------------------------------------
    def killBufferCapture(self,buffer):
        result=True

        if buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None:
            try:
                buffer.forceShutdown()

                for listener in self.getListeners():
                    Tools.callback(listener.killCaptureCallback(buffer.getDeviceID()))
            except Exception as e:
                print("Failed to force shutdown "+str(buffer.getDeviceName())+": "+str(e))
                result=False
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def deleteBuffers(self):
        bufs=[buf for buf in self.getBuffers() if buf.isEnabled()]

        print("Deleting "+str(len(bufs))+" buffers...")
        for buf in bufs:
            self.deleteBuffer(buf)

        print("Done deleting buffers")

    #-----------------------------------------------------------------
    def deleteBuffer(self,buffer):
        result=True

        if (buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None) and buffer.isEnabled():
            try:
                success=buffer.deleteBuffer()

                for listener in self.getListeners():
                    Tools.callback(listener.deleteBufferCallback,buffer.getDeviceID(),success)
            except Exception as e:
                print("Failed to delete "+str(buffer.getDeviceName())+": "+str(e))
                result=False
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def deleteFileFromBuffers(self,file,fileType):
        bufs=[buf for buf in self.getBuffers() if buf.isEnabled()]

        print(f"Trying to delete {file} from {len(self.getBuffers())} buffers...")
        for buf in bufs:
            self.deleteFileFromBuffer(buf,file,fileType)

        print("Done deleting buffers")

    #-----------------------------------------------------------------
    def deleteFileFromBuffer(self,buffer,file,fileType):
        result=True

        if (buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None) and buffer.isEnabled():
            try:
                match fileType.lower():
                    case "clip":
                        success=buffer.deleteClip(file)
                    case "data":
                        success=buffer.deleteDeviceFile(file)
                    case "log":
                        success=buffer.deleteDeviceFile(file)
                    case "config":
                        pass
                    case _:
                        success=False

                for listener in self.getListeners():
                    Tools.callback(listener.deleteFileCallback,buffer.getDeviceID(),file,success)
            except Exception as e:
                print(f"Failed to delete {file} from {buffer.getDeviceName()}: {e}")
                result=False
        else:
            result=False

        return result

    #-----------------------------------------------------------------
    def archiveRequestForBuffers(self,requestID,requestTime,startTime,past,future):
        bufs=[buf for buf in self.getBuffers() if buf.isEnabled()]

        print(f"Submitting archive request for {len(bufs)} buffers...")

        #clips=[clip for buf in bufs if (clip:=buf.makeClip(requestID,startTime,past,future))]
        clips=[clip for i,buf in enumerate(bufs) if (clip:=self.archiveRequestForBuffer(f"{requestID}-{i}",requestTime,buf,startTime,past,future))]

        print("Done requesting archive")

        return clips

    #-----------------------------------------------------------------
    def archiveRequestForBuffer(self,requestID,requestTime,buffer,startTime,past,future):
        result=None

        if (buffer:=self.findBufferByID(buffer) if isinstance(buffer,str) else buffer if isinstance(buffer,BufferDevice) else None) and buffer.isArchivable():
            try:
                result=buffer.makeClip(requestID,startTime,past,future)
                result["machine_id"]=self.getDeviceID()

                for listener in self.getListeners():
                    Tools.callback(listener.archiveRequestCallback,requestID,requestTime,buffer.getDeviceID(),startTime,past,future)
            except Exception as e:
                Tools.printStackTrace()
                print(f"Failed to archive buffer from {Tools.formatTime(startTime-past)} to {Tools.formatTime(startTime+future)} for {buffer.getDeviceName()}: {e}")

        return result

    #-----------------------------------------------------------------
    def bufferLevelUpdate(self):
        reply=dict()

        reply["free_disk_space"]=Tools.EBFreeDiskSpace()
        reply["free_disk_space_perc"]=Tools.EBPercFreeDiskSpace()
        reply["power_source"]=Tools.getPowerSource()
        reply["battery_level"]=Tools.getBatteryLevel()
        reply["buffer_level"]=[{buf.getDeviceID():buf.getBufferFillLevel()} for buf in self.getActiveBuffers()]

        return reply

    #-----------------------------------------------------------------
    def getDeviceProperty(self,device,prop):
        result=None

        if device:=self.findByID(device) if isinstance(device,str) else device if isinstance(device,BufferDevice) or isinstance(device,BufferServer) else None:
            #"options" - all the configuration options for the device (eg fps, resolution, etc)
            match prop.lower():
                case "CaptureOptions":
                    pass
                case "DeviceOptions":
                    result=[str(dev) for dev in device.listDevices()] if device else None
                case "Config":
                    result=device.getConfig() if device else None
                case _:
                    result=device.getProperty(prop)

        return result

    #-----------------------------------------------------------------
    def setDeviceProperty(self,device,prop,value):
        result=None

        if device:=self.findByID(device) if isinstance(device,str) else device if isinstance(device,BufferDevice) or isinstance(device,BufferServer) else None:
            result=device.setProperty(prop,value)

        return result

    #-----------------------------------------------------------------
    def exportInfo(self,queryType=None,value=None):
        match queryType.lower():
            case "item":
                info={value:self.getBufferRecords()[value]} if self.getBufferRecords() and value in self.getBufferRecords() else {}
            case "server":
                info={k:v for k,v in self.getBufferRecords().items() if v["ParentID"]==value} if self.getBufferRecords() else {}
            case "buffer":
                info={k:v for k,v in self.getBufferRecords().items() if v["MachineID"]==value} if self.getBufferRecords() else {}
            case "file":
                info={k:v for k,v in self.getBufferRecords().items() if value in v["Filename"]} if self.getBufferRecords() else {}
            case "text":
                info={k:v for k,v in self.getBufferRecords().items() if value in str(v)} if self.getBufferRecords() else {}
            case "service":
                info={k:v for k,v in self.getBufferRecords().items() if value in v["Type"]} if self.getBufferRecords() else {}
            case _:
                info={k:v for k,v in self.getBufferRecords().items()} if self.getBufferRecords() else {}

        return info

    #-----------------------------------------------------------------
    # Get and Set methods
    #-----------------------------------------------------------------
    def getDeviceType(self):
        return self.deviceType

    #-----------------------------------------------------------------
    def getDeviceID(self):
        return self.getMachineID()

    #-----------------------------------------------------------------
    def getMachineID(self):
        return self.getProperty("MachineID")

    #-----------------------------------------------------------------
    def getServerGroupID(self):
        return self.getProperty("ServerGroupID")

    #-----------------------------------------------------------------
    def getGroups(self):
        return self.getProperty("Groups")

    #-----------------------------------------------------------------
    def getConfiguredCoordinators(self):
        return self.getProperty("ConfiguredCoordinators")

    #-----------------------------------------------------------------
    def getServerName(self):
        return self.getProperty("Name")

    #-----------------------------------------------------------------
    def getServerDescription(self):
        return self.getProperty("Description")

    #-----------------------------------------------------------------
    def getCoordinatorPort(self):
        return self.getProperty("CoordinatorPort")

    #-----------------------------------------------------------------
    def getBufferPort(self):
        return self.getCoordinatorPort() if self.getStandaloneMode() else self.getProperty("BufferPort")

    #-----------------------------------------------------------------
    def getHomeDir(self):
        self.homeDir=self.homeDir if self.homeDir else Tools.findHomeDir()
        return self.homeDir

    #-----------------------------------------------------------------
    def getDevicesDir(self):
        return self.devicesDir

    #-----------------------------------------------------------------
    def getDataDir(self):
        return self.getProperty("DataDir")

    #-----------------------------------------------------------------
    def getClipDir(self):
        return Tools.validateDir(self.getDataDir()+"clips/")

    #-----------------------------------------------------------------
    def getLogsDir(self):
        return self.getProperty("LogsDir")

    #-----------------------------------------------------------------
    def getBufferDir(self):
        return self.getProperty("ArchiveDir")

    #-----------------------------------------------------------------
    def getExportDir(self):
        return self.getProperty("ExportDir")

    #-----------------------------------------------------------------
    def getVerbose(self):
        return self.getProperty("Verbose")

    #-----------------------------------------------------------------
    def getCaptureFrequency(self):
        return self.getProperty("CaptureFrequency")

    #-----------------------------------------------------------------
    def getBufferLength(self):
        return self.getProperty("BufferLength")

    #-----------------------------------------------------------------
    def getDefaultBefore(self):
        return self.getProperty("DefaultBefore")

    #-----------------------------------------------------------------
    def getDefaultAfter(self):
        return self.getProperty("DefaultAfter")

    #-----------------------------------------------------------------
    def getBroadcastFrequency(self):
        return self.getProperty("BroadcastFrequency")

    #-----------------------------------------------------------------
    def getBroadcastAddress(self):
        return self.getProperty("BroadcastAddress")

    #-----------------------------------------------------------------
    def getStandaloneMode(self):
        return self.getProperty("StandaloneMode")

    #-----------------------------------------------------------------
    def getUseBroadcast(self):
        return self.getProperty("UseBroadcast")

    #-----------------------------------------------------------------
    def getUseLocalIP(self):
        return self.getProperty("UseLocalIP")

    #-----------------------------------------------------------------
    def getConfigFilename(self):
        return self.getServerClass()+Standards.CONFIG_EXTENSION

    #-----------------------------------------------------------------
    def getServerClass(self):
        return self.serverClass

    #-----------------------------------------------------------------
    def getProperty(self,k):
        return self.config[k] if k in self.config else None

    #-----------------------------------------------------------------
    def getHostName(self):
        return Tools.getHostName()

    #-----------------------------------------------------------------
    def getLocalIP(self):
        return Tools.getLocalIP()

    #-----------------------------------------------------------------
    def getExternalIP(self):
        return Tools.getExternalIP()

    #-----------------------------------------------------------------
    def getDeviceTemplates(self):
        return self.deviceTemplates

    #-----------------------------------------------------------------
    def getStatus(self):
        return "active" if self.networkIsRunning() else "paused"

    #-----------------------------------------------------------------
    def getBufferRecords(self):
        return self.bufferDeviceRecords

    #-----------------------------------------------------------------
    def getBuffers(self):
        return self.allBuffers

    #-----------------------------------------------------------------
    def getActiveBuffers(self):
        bufs=list()

        for buf in self.getBuffers():
            if buf.isEnabled():
                for service in buf.getServices():
                    bufs.append({"type":service,
                                 "device_name":buf.getDeviceName(),
                                 "buffer_id":buf.getDeviceID(),
                                 "groups":buf.getGroups(),
                                 "description":buf.getDeviceDescription(),
                                 "status":buf.getStatus()})

        return bufs

    #-----------------------------------------------------------------
    def anyActiveBuffers(self):
        return len(self.getActiveBuffers())>0

    #-----------------------------------------------------------------
    def setProperty(self,k,v):
        rewrite=False

        if k in self.config:
            if self.config[k]!=v:
                rewrite=True
        else:
            rewrite=True

        if rewrite:
            self.config[k]=v
            self.saveConfig()

        return v

    #-----------------------------------------------------------------
    def setMachineID(self,machineID):
        self.setProperty("MachineID",machineID)

    #-----------------------------------------------------------------
    def setServerGroupID(self,groupID):
        self.setProperty("ServerGroupID",groupID)

    #-----------------------------------------------------------------
    def setServerName(self,name):
        self.setProperty("Name",name)

    #-----------------------------------------------------------------
    def setServerDescription(self,description):
        self.setProperty("Description",description)

    #-----------------------------------------------------------------
    def setCoordinatorPort(self,port):
        self.setProperty("CoordinatorPort",port)

    #-----------------------------------------------------------------
    def setDataDir(self,pathDir):
        self.setProperty("DataDir",pathDir)

    #-----------------------------------------------------------------
    def setBufferDir(self,pathDir):
        self.setProperty("ArchiveDir",pathDir)

    #-----------------------------------------------------------------
    def setLogsDir(self,pathDir):
        self.setProperty("LogsDir",pathDir)

    #-----------------------------------------------------------------
    def setExportDir(self,pathDir):
        self.setProperty("ExportDir",pathDir)

    #-----------------------------------------------------------------
    def setVerbose(self,v):
        self.setProperty("Verbose",v)

    #-----------------------------------------------------------------
    def setCaptureFrequency(self,freq):
        self.setProperty("CaptureFrequency",freq)

    #-----------------------------------------------------------------
    def setBufferLength(self,length):
        self.setProperty("BufferLength",length)

    #-----------------------------------------------------------------
    def setBroadcastFrequency(self,freq):
        self.setProperty("BroadcastFrequency",freq)

    #-----------------------------------------------------------------
    def setBroadcastAddress(self,addr):
        self.setProperty("BroadcastAddress",addr)

    #-----------------------------------------------------------------
    def setStandaloneMode(self,mode):
        self.setProperty("StandaloneMode",mode)

    #-----------------------------------------------------------------
    def setUseBroadcast(self,b):
        self.setProperty("UseBroadcast",b)

    #-----------------------------------------------------------------
    def setUseLocalIP(self,l):
        self.setProperty("UseLocalIP",l)

    #-----------------------------------------------------------------
    def setDeviceTemplates(self,templates):
        self.deviceTemplates=templates

    #-----------------------------------------------------------------
    def makeGroupID(self):
        return Tools.makeGroupID(self.getMachineID())

    #-----------------------------------------------------------------
    def addToListProperty(self,prop,value):
        if prop in self.config:
            temp=self.config[prop].copy()
            if value not in temp:
                temp.append(value)
        else:
            temp=[value]

        self.setProperty(prop,temp)

    #-----------------------------------------------------------------
    def addMonitor(self,sock):
        self.monitors.append(sock)

    #-----------------------------------------------------------------
    def closeMonitors(self):
        for sock in self.monitors:
            try:
                if Tools.isConnected(sock):
                    sock.close()
            except Exception as e:
                print(f"Error closing socket: {e}")

    #-----------------------------------------------------------------
    def addListener(self,listener):
        self.listeners.append(listener)

    #-----------------------------------------------------------------
    def removeListener(self,listener):
        self.listeners.remove(listener)

    #-----------------------------------------------------------------
    def getListeners(self):
        return self.listeners

    #-----------------------------------------------------------------
    def addGroup(self,group):
        self.addToListProperty("Groups",group)

    #-----------------------------------------------------------------
    def addExternalCoordinator(self,extCoor):
        self.addToListProperty("ExternalCoordinator",extCoor)

    #-----------------------------------------------------------------
    def getGroupParticipants(self,group):
        participants=[device.getDeviceID() for device in self.getBuffers() if group in device.getGroups()]

        if group in self.getGroups():
            participants.append(self.getDeviceID())

        return participants

    #-----------------------------------------------------------------
    def findFileMaker(self,filename):
        result=None

        for buf in self.getBuffers():
            if buf.getDeviceID() in filename:
                result=buf
                break

        return result

    #-----------------------------------------------------------------
    def findBufferByID(self,ID):
        result=None

        for dev in self.getBuffers():
            if dev.getDeviceID()==ID:
                result=dev
                break

        return result

    #-----------------------------------------------------------------
    def findBufferByService(self,service):
        return [dev for dev in self.getBuffers() if service in dev.getServices()]

    #-----------------------------------------------------------------
    def findByID(self,ID):
        return self if ID==self.getDeviceID() else self.findBufferByID(ID)

    #-----------------------------------------------------------------
    def loadBufferRecords(self):
        recordFile=self.getDataDir()+Standards.RECORDS_FILENAME

        try:
            if not Tools.exists(recordFile):
                with open(recordFile,'w',encoding='utf-8') as file:
                    json.dump({},file)

            with open(recordFile,'r') as file:
                self.bufferDeviceRecords=json.load(file)

            self.bufferDeviceRecords={str(k): v for k,v in self.bufferDeviceRecords.items() if not "Filename" in v or Tools.exists(self.getClipDir()+v["Filename"])}
            self.bufferDeviceRecords=dict(sorted(self.bufferDeviceRecords.items(),key=lambda item:item[1]["RequestTime"] if "RequestTime" in item[1] else 0))
        except:
            self.bufferDeviceRecords=dict()
            Tools.printStackTrace()

    #-----------------------------------------------------------------
    def saveBufferRecords(self):
        recordFile=self.getDataDir()+Standards.RECORDS_FILENAME

        try:
            self.bufferDeviceRecords=dict(sorted(self.bufferDeviceRecords.items(),key=lambda item:item[1]["RequestTime"] if "RequestTime" in item[1] else 0))

            with open(recordFile,'w',encoding='utf-8') as file:
                json.dump(self.bufferDeviceRecords,file,indent=2,ensure_ascii=False)
        except:
            Tools.printStackTrace()

    #-----------------------------------------------------------------
    def updateBufferRecords(self,requestID,machineID):
        record=self.findBufferByID(machineID).getBufferRecord(requestID)
        fullFilename=record["clip"]

        if not requestID in self.bufferDeviceRecords:
            self.bufferDeviceRecords[requestID]=dict()

        self.bufferDeviceRecords[requestID]["RequestID"]=requestID
        self.bufferDeviceRecords[requestID]["Filename"]=Tools.removeDir(fullFilename)
        self.bufferDeviceRecords[requestID]["FileLength"]=record[fullFilename]["fileLength"]
        self.bufferDeviceRecords[requestID]["Type"]=record["type"]
        self.bufferDeviceRecords[requestID]["Status"]=record["status"]
        self.bufferDeviceRecords[requestID]["MachineID"]=machineID
        self.bufferDeviceRecords[requestID]["ParentID"]=self.getDeviceID()
        self.bufferDeviceRecords[requestID]["FileStartTime"]=record[fullFilename]["fileStartTime"]
        self.bufferDeviceRecords[requestID]["FormattedFileStartTime"]=Tools.formatTime(record[fullFilename]["fileStartTime"])

        triggerTimeInClip=self.bufferDeviceRecords[requestID]["TriggerTime"]-self.bufferDeviceRecords[requestID]["FileStartTime"]
        formattedTriggerTimeInClip=Tools.timeLength(self.bufferDeviceRecords[requestID]["FileStartTime"],self.bufferDeviceRecords[requestID]["TriggerTime"])
        self.bufferDeviceRecords[requestID]["Mark"]={triggerTimeInClip:f"Triggered at {formattedTriggerTimeInClip}"}

        self.saveBufferRecords()

        for listener in self.getListeners():
            Tools.callback(listener.infoUpdatedCallback,machineID,"BufferRecord")

    #-----------------------------------------------------------------
    #ServerListner methods
    #-----------------------------------------------------------------
    def serverStartedCallback(self,machineID):
        logger.debug(f"Server started callback: {machineID}")

    #-----------------------------------------------------------------
    def serverStoppedCallback(self,machineID):
        logger.debug(f"Server stopped callback: {machineID}")

    #-----------------------------------------------------------------
    def dataReadyCallback(self,machineID,file,fileLength,success):
        logger.debug(f"Data ready callback: {machineID}, {file}, {fileLength}, {success}")

    #-----------------------------------------------------------------
    def infoUpdatedCallback(self,machineID,info):
        logger.debug(f"info updated callback: {machineID}, {info}")

    #-----------------------------------------------------------------
    def deleteFileCallback(self,machineID,file,success):
        logger.debug(f"Delete file callback: {machineID}, {file}, {success}")

    #-----------------------------------------------------------------
    def deleteBufferCallback(self,machineID,success):
        logger.debug(f"Delete buffer callback: {machineID}, {success}")

    #-----------------------------------------------------------------
    def startCaptureCallback(self,machineID):
        logger.debug(f"Start capture callback: {machineID}")

    #-----------------------------------------------------------------
    def stopCaptureCallback(self,machineID):
        logger.debug(f"Stop capture callback: {machineID}")

    #-----------------------------------------------------------------
    def pauseCaptureCallback(self,machineID):
        logger.debug(f"Pause capture callback: {machineID}")

    #-----------------------------------------------------------------
    def unpauseCaptureCallback(self,machineID):
        logger.debug(f"Unpause capture callback: {machineID}")

    #-----------------------------------------------------------------
    def restartCaptureCallback(self,machineID):
        logger.debug(f"Restart capture callback: {machineID}")

    #-----------------------------------------------------------------
    def shutdownCaptureCallback(self,machineID):
        logger.debug(f"Shutdown capture callback: {machineID}")

    #-----------------------------------------------------------------
    def killCaptureCallback(self,machineID):
        logger.debug(f"Kill capture callback: {machineID}")

    #-----------------------------------------------------------------
    def archiveRequestCallback(self,requestID,requestTime,machineID,startTime,_past,_future):
        if not requestID in self.bufferDeviceRecords:
            self.bufferDeviceRecords[requestID]=dict()

        self.bufferDeviceRecords[requestID]["RequestID"]=requestID
        self.bufferDeviceRecords[requestID]["MachineID"]=machineID
        self.bufferDeviceRecords[requestID]["ParentID"]=self.getDeviceID()
        self.bufferDeviceRecords[requestID]["RequestTime"]=requestTime
        self.bufferDeviceRecords[requestID]["FormattedRequestTime"]=Tools.formatTime(requestTime)
        self.bufferDeviceRecords[requestID]["TriggerTime"]=startTime
        self.bufferDeviceRecords[requestID]["FormattedTriggerTime"]=Tools.formatTime(startTime)
        self.bufferDeviceRecords[requestID]["Status"]="REQUESTED"

        self.saveBufferRecords()

        for listener in self.getListeners():
            Tools.callback(listener.infoUpdatedCallback,machineID,"BufferRecord")

    #-----------------------------------------------------------------
    def saveFileCallback(self,machineID,file,success):
        logger.debug(f"Save file callback: {machineID}, {file}, {success}")

    #-----------------------------------------------------------------
    def convertCallback(self,machineID,inputFile,outputFile,success):
        logger.debug(f"Convert callback: {machineID}, {inputFile}, {outputFile}, {success}")

    #-----------------------------------------------------------------
    #DeviceListener methods
    #-----------------------------------------------------------------
    def bufferHealthCallback(self,machineID,prop,value):
        pass

    #-----------------------------------------------------------------
    def bufferFileCreatedCallback(self,machineID,filename,start):
        pass

    #-----------------------------------------------------------------
    def clipCreatedCallback(self,requestID,machineID,filename,_start,_duration):
        self.updateBufferRecords(requestID,machineID)

        fileLength=Tools.getFileSize(filename) if Tools.exists(filename) else 0
        for listener in self.getListeners():
            Tools.callback(listener.dataReadyCallback,machineID,filename,fileLength,True if fileLength>0 else False)

    #-----------------------------------------------------------------
    def fileConcatenatedCallback(self,requestID,machineID,filename,filePiece,current,total):
        pass

    #-----------------------------------------------------------------
    def fileConcatenationCompletedCallback(self,requestID,machineID,filename,start,duration):
        pass

    #-----------------------------------------------------------------
    #NetworkThread inner class
    #-----------------------------------------------------------------
    class NetworkThread(threading.Thread):

        def __init__(self,ebs):
            super().__init__(name="BufferServer - NetworkThread")
            self.ebs=ebs
            self.loop=False
            self.ready=False
            self.success=False
            self.server=None
            self.workers=list()

        #-----------------------------------------------------------------
        def start(self):
            try:
                self.server=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                self.server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                self.server.bind(("0.0.0.0",self.ebs.getBufferPort()))
                self.server.listen(256)
                self.success=True
                print("Started Network Handler")
            except Exception as e:
                self.success=False
                print("Error failed to start Network Handler: "+str(e))

            self.loop=self.success

            if self.success:
                super().start()

        #-----------------------------------------------------------------
        def terminate(self):
            print("Shutting down Network Thread...")
            self.loop=False
            self.ready=False
            self.success=False

            Tools.closeSocket(self.server)

            for w in self.workers:
                w.terminate()

            print("Shutting down Network Thread...done")

        #-----------------------------------------------------------------
        def failedToStart(self):
            return not self.success

        #-----------------------------------------------------------------
        def isReady(self):
            return self.ready

        #-----------------------------------------------------------------
        def isRunning(self):
            return self.loop

        #-----------------------------------------------------------------
        def run(self):
            while self.loop:
                try:
                    self.ready=True

                    handler=BufferServer.Handler(self.ebs,self.server.accept())
                    if handler.isReady():
                        handler.start()
                        self.workers.append(handler)
                    else:
                        handler.terminate()
                except Exception as e:
                    self.ready=False
                    if self.loop:
                        Tools.printStackTrace()
                        print("Error running Network Handler: "+str(e))
                        Tools.sleep(10000)
                        print("Restarting socket")
                    else:
                        Tools.printStackTrace()
                        print("Closing Network Handler: "+str(e))

                self.workers=[w for w in self.workers if w.is_alive()]

            if self.success:
                self.terminate()

            print("Network Handler has stopped")

    #-----------------------------------------------------------------
    # Request Handler inner class
    #-----------------------------------------------------------------
    class Handler(AbstractHandler):

        def __init__(self,ebs,response):
            sock=response[0]
            addr=response[1][0]
            AbstractHandler.__init__(self,sock,addr)
            self.setServer(ebs)

        #-----------------------------------------------------------------
        def startBuffers(self):
            self.server.startBuffers()

        #-----------------------------------------------------------------
        def startBufferCapture(self,buffer,startTime):
            return self.server.startBufferCapture(buffer,startTime)

        #-----------------------------------------------------------------
        def shutdownBuffers(self):
            self.server.shutdownBuffers()

        #-----------------------------------------------------------------
        def shutdownBufferCapture(self,buffer):
            return self.server.shutdownBufferCapture(buffer)

        #-----------------------------------------------------------------
        def stopBuffers(self):
            self.server.stopBuffers()

        #-----------------------------------------------------------------
        def stopBufferCapture(self,buffer):
            return self.server.stopBufferCapture(buffer)

        #-----------------------------------------------------------------
        def pauseBuffers(self):
            self.server.pauseBuffers()

        #-----------------------------------------------------------------
        def pauseBufferCapture(self,buffer):
            return self.server.pauseBufferCapture(buffer)

        #-----------------------------------------------------------------
        def unpauseBuffers(self):
            self.server.unpauseBuffers()

        #-----------------------------------------------------------------
        def unpauseBufferCapture(self,buffer):
            return self.server.unpauseBufferCapture(buffer)

        #-----------------------------------------------------------------
        def restartBuffers(self):
            self.server.restartBuffers()

        #-----------------------------------------------------------------
        def restartBufferCapture(self,buffer):
            return self.server.restartBufferCapture(buffer)

        #-----------------------------------------------------------------
        def killBuffers(self):
            self.server.killBuffers()

        #-----------------------------------------------------------------
        def killBufferCapture(self,buffer):
            return self.server.killBufferCapture(buffer)

        #-----------------------------------------------------------------
        def deleteBuffers(self):
            self.server.deleteBuffers()

        #-----------------------------------------------------------------
        def deleteBuffer(self,buffer):
            return self.server.deleteBuffer(buffer)

        #-----------------------------------------------------------------
        def deleteFileFromBuffers(self,file):
            self.server.deleteFileFromBuffers(file)

        #-----------------------------------------------------------------
        def deleteFileFromBuffer(self,buffer,file):
            return self.server.deleteFileFromBuffer(buffer,file)

        #-----------------------------------------------------------------
        def archiveRequestForBuffers(self,requestID,requestTime,startTime,past,future):
            return self.server.archiveRequestForBuffers(requestID,requestTime,startTime,past,future)

        #-----------------------------------------------------------------
        def archiveRequestForBuffer(self,requestID,requestTime,buffer,startTime,past,future):
            return self.server.archiveRequestForBuffer(requestID,requestTime,buffer,startTime,past,future)

        #-----------------------------------------------------------------
        def announce(self):
            self.server.broadcaster.sendBroadcastMessage(None,self.clientAddress)

        #-----------------------------------------------------------------
        def bufferLevelUpdate(self):
            return self.server.bufferLevelUpdate()

        #-----------------------------------------------------------------
        def getDeviceProperty(self,device,prop):
            return self.server.getDeviceProperty(device,prop)

        #-----------------------------------------------------------------
        def setDeviceProperty(self,device,prop,value):
            return self.server.setDeviceProperty(device,prop,value)

        #-----------------------------------------------------------------
        def exportInfo(self,queryType=None,value=None):
            return self.server.exportInfo(queryType,value)

    #-----------------------------------------------------------------
    #BroadcastThread inner class
    #-----------------------------------------------------------------

    class BroadcastThread(threading.Thread):

        def __init__(self,ebs):
            super().__init__(name="BufferServer - BroadcastThread")
            self.ebs=ebs
            self.loop=False
            self.condition=threading.Condition()

        #-----------------------------------------------------------------
        def start(self):
            self.loop=True
            super().start()

        #-----------------------------------------------------------------
        def terminate(self):
            print("Shutting down Broadcast Thread...")
            self.loop=False
            with self.condition:
                self.condition.notify()
            print("Shutting down Broadcast Thread...done")

        #-----------------------------------------------------------------
        def getBroadcastMessage(self,ip=None):
            msg=dict()

            msg["type"]=self.ebs.getDeviceType()
            msg["device_name"]=self.ebs.getServerName()
            if ip:
                msg["client_address"]=ip
            else:
                msg["client_address"]=self.ebs.getLocalIP() if self.ebs.getUseLocalIP() else self.ebs.getExternalIP()
            msg["machine_id"]=self.ebs.getMachineID()
            msg["groups"]=self.ebs.getGroups()
            msg["description"]=self.ebs.getServerDescription()
            msg["status"]=self.ebs.getStatus()
            msg["parent_id"]="-1"
            msg["buffer_list"]=self.ebs.getActiveBuffers()

            return json.dumps(msg)

        #-----------------------------------------------------------------
        def sendBroadcastMessage(self,sock=None,address=None,returnIP=None):
            if not sock:
                sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)

            sock.sendto(self.getBroadcastMessage(returnIP).encode(),(address if address else self.makeBroadcastAddress(),self.ebs.getCoordinatorPort()))

        #-----------------------------------------------------------------
        def isBroadcasting(self):
            return self.loop and self.ebs.getUseBroadcast()

        #-----------------------------------------------------------------
        def makeBroadcastAddress(self):
            addr=self.ebs.getBroadcastAddress()

            if addr.lower() in ["any","localhost","loopback","127.0.0.1","0.0.0.0"]:
                addr="255.255.255.255"

            return addr

        #-----------------------------------------------------------------
        def run(self):
            try:
                sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)

                if self.loop:
                    print("Started Broadcaster")

                while self.loop:
                    if self.ebs.getUseBroadcast():
                        #Broadcast to the local network
                        self.sendBroadcastMessage(sock)

                    #Directed broadcast to configured external coordinators
                    extIP=self.ebs.getExternalIP()
                    for address in self.ebs.getConfiguredCoordinators():
                        self.sendBroadcastMessage(sock,address,extIP)

                    with self.condition:
                        self.condition.wait(self.ebs.getBroadcastFrequency()/1000.0)
            except Exception as e:
                self.loop=False
                print("Error running Broadcaster: "+str(e))

            Tools.closeSocket(sock)
            print("Broadcaster has stopped")

    #-----------------------------------------------------------------
    #MaintenanceThread inner class
    #-----------------------------------------------------------------
    class MaintenanceThread(threading.Thread):

        def __init__(self,ebs):
            super().__init__(name="BufferServer - MaintenanceThread")
            self.ebs=ebs
            self.loop=False
            self.condition=threading.Condition()

        #-----------------------------------------------------------------
        def start(self):
            self.loop=True
            super().start()

        #-----------------------------------------------------------------
        def run(self):
            if self.loop:
                print("Started MaintenanceMan")

            while self.loop:
                self.cleanBuffer()
                self.cleanClipDir()

                with self.condition:
                    self.condition.wait(Standards.GC_FREQUENCY/1000.0)

            print("MaintenanceMan has stopped")

        #-----------------------------------------------------------------
        def cleanBuffer(self):
            try:
                files=[os.path.join(self.ebs.getBufferDir(),f) for f in os.listdir(self.ebs.getBufferDir())]

                for filename in files:
                    if not any([buffer.validBufferFile(filename) for buffer in self.ebs.getBuffers() if buffer.isEnabled()]):
                        if Tools.exists(filename):
                            os.remove(filename)

            except Exception as e:
                print("Error deleting buffer file in BufferServer Maintenance Thread: "+str(e))

        #-----------------------------------------------------------------
        def cleanClipDir(self):
            try:
                files=[os.path.join(self.ebs.getClipDir(),f) for f in os.listdir(self.ebs.getClipDir())]

                for filename in files:
                    if "temp_" in filename and Tools.exists(filename) and buf:=self.ebs.findFileMaker(filename):
                        with buf.getArchiveSyncObject(),buf.getClipSyncObject():
                            os.remove(filename)

            except Exception as e:
                print("Error deleting clip in BufferServer Maintenance Thread: "+str(e))

        #-----------------------------------------------------------------
        def terminate(self):
            print("Shutting down Maintenance Thread...")
            self.loop=False
            with self.condition:
                self.condition.notify()
            print("Shutting down Maintenance Thread...done")


#-----------------------------------------------------------------
def main():
    experienceBuffers=BufferServer()
    experienceBuffers.startExperienceBufferServer()
    experienceBuffers.waitInNetworkLoop()
    Tools.sleep(5000)
    print()
    experienceBuffers.shutdown()


if __name__=='__main__':
    main()
