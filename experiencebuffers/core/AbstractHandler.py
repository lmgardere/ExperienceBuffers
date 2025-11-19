import sys
import json

from threading import Thread
from abc import ABC,abstractmethod
import logging

sys.path.append("/mnt/c/Users/lmgar/OneDrive/Documents/My Projects/ExperienceBuffers/python source/")
from experiencebuffers.util.Standards import Standards
from experiencebuffers.util.Tools import Tools

logger=logging.getLogger(__name__)


class AbstractHandler(Thread,ABC):

    def __init__(self,sock,addr):
        self.socket=sock
        self.socketFile=sock.makefile('rwb')
        self.clientAddress=addr
        self.requestTime=Tools.currentTimeMillis()
        Thread.__init__(self,name=f"BufferServer - Handler ({Tools.formatTime(self.requestTime)})",daemon=True)

        self.requestID=0
        self.request=None
        self.requestObject=dict()
        self.http=False
        self.overHTTP=False
        self.test=False
        self.ready=True
        self.server=None

        requestMap=dict()

        try:
            if requestStr:=Tools.read(self.socket):
                requestStr=requestStr.decode('utf-8',errors='ignore')

                if requestStr.lower().startswith("get") or requestStr.lower().startswith("post"):
                    requestMap=self.processHTTPRequest(requestStr)
                    self.overHTTP=True

                self.requestObject=requestMap if requestMap else json.loads(requestStr)

                print(self.requestObject)

                if self.requestObject:
                    self.request=self.requestObject["request"].upper()

                self.ready=self.request is not None
                self.http="HTTP" in self.request if self.ready else False

                if self.ready and self.request.startswith("~") and self.request!="~":
                    self.enableTestMode()
                    self.request=self.request[1:]
                else:
                    self.disableTestMode()

                self.requestID=self.requestObject["request_id"].upper() if "request_id" in self.requestObject else Tools.makeRequestID()
            else:
                self.ready=False
        except Exception:
            Tools.printStackTrace()
            self.ready=False

    #-----------------------------------------------------------------
    @abstractmethod
    def startBuffers(self)->None: pass

    @abstractmethod
    def startBufferCapture(self,buffer,startTime)->bool: pass

    @abstractmethod
    def stopBuffers(self)->None: pass

    @abstractmethod
    def stopBufferCapture(self,buffer)->bool: pass

    @abstractmethod
    def pauseBuffers(self)->None: pass

    @abstractmethod
    def pauseBufferCapture(self,buffer)->bool: pass

    @abstractmethod
    def unpauseBuffers(self)->None: pass

    @abstractmethod
    def unpauseBufferCapture(self,buffer)->bool: pass

    @abstractmethod
    def restartBuffers(self)->None: pass

    @abstractmethod
    def restartBufferCapture(self,buffer)->bool: pass

    @abstractmethod
    def shutdownBuffers(self)->None: pass

    @abstractmethod
    def shutdownBufferCapture(self,buffer)->bool: pass

    @abstractmethod
    def killBuffers(self)->None: pass

    @abstractmethod
    def killBufferCapture(self,buffer)->bool: pass

    @abstractmethod
    def deleteBuffers(self)->None: pass

    @abstractmethod
    def deleteBuffer(self,buffer)->bool: pass

    @abstractmethod
    def deleteFileFromBuffers(self,file,fileType)->None: pass

    @abstractmethod
    def deleteFileFromBuffer(self,buffer,file,fileType)->bool: pass

    @abstractmethod
    def archiveRequestForBuffers(self,requestID,requestTime,startTime,past,future)->list: pass

    @abstractmethod
    def archiveRequestForBuffer(self,requestID,requestTime,buffer,startTime,past,future)->str: pass

    @abstractmethod
    def announce(self)->None: pass

    @abstractmethod
    def bufferLevelUpdate(self)->None: pass

    @abstractmethod
    def getDeviceProperty(self,device,prop)->str: pass

    @abstractmethod
    def setDeviceProperty(self,device,prop,value)->str: pass

    @abstractmethod
    def exportInfo(self,queryType,value)->dict: pass

    #-----------------------------------------------------------------
    def processHTTPRequest(self,request):
        requestMap=dict()
        variables=""

        try:
            if request:
                requestParts=request.split("\r\n")
                requestStr=requestParts[0]
                requestStr=requestStr.replace("%22","\"").replace("%20"," ")
                if "?" in requestStr:
                    variables=requestStr[requestStr.index("?")+1:requestStr.index("HTTP")].strip()
                else:
                    variables=requestStr[requestStr.index(" /")+2:requestStr.index("HTTP")].strip()

            if "=" in variables:
                for term in variables.split("&"):
                    parts=term.partition("=")

                    if parts[1]:
                        requestMap[parts[0]]=parts[2]
            elif variables:
                requestMap["filename"]=variables

            if "request" not in requestMap:
                parts=requestStr.partition(" ")
                requestMap["request"]=parts[0]+"_HTTP"
                for r in requestParts:
                    if "content-type" in r.lower() or "content-length" in r.lower():
                        parts=requestStr.partition(":")
                        if parts[1]:
                            requestMap[parts[0].lower().strip()]=parts[2].strip()
                    if "boundary=" in r.lower():
                        parts=requestStr.partition("boundary=")
                        requestMap["boundary"]=parts[2].strip()

        except Exception as e:
            requestMap.clear()
            print("Exception:",e)

        return requestMap

    #-----------------------------------------------------------------
    def determineDirectory(self,fileType):
        match fileType.lower():
            case "clip":
                return self.server.getClipDir()
            case "data":
                return self.server.getDataDir()
            case "log":
                return self.server.getLogsDir()
            case "config":
                return Tools.getWorkingDir()
            case "export":
                return self.server.getExportDir()
            case "device":
                return self.server.getDeviceDir()
            case "resource":
                return self.server.getResourceDir()
            case _:
                return None

    #-----------------------------------------------------------------
    def isReady(self):
        return self.ready

    #-----------------------------------------------------------------
    # True if the incoming request is atually an http get or post file request
    def isHTTP(self):
        return self.http

    #-----------------------------------------------------------------
    def isRequestOverHTTP(self):
        return self.overHTTP

    #-----------------------------------------------------------------
    def getDefaultBefore(self):
        return self.server.getDefaultBefore() if self.server else Standards.DEFAULT_BEFORE

    #-----------------------------------------------------------------
    def getDefaultAfter(self):
        return self.server.getDefaultAfter() if self.server else Standards.DEFAULT_AFTER

    #-----------------------------------------------------------------
    def setServer(self,server):
        self.server=server

    #-----------------------------------------------------------------
    def setRequestTime(self,requestTime):
        self.requestTime=requestTime

    #-----------------------------------------------------------------
    def enableTestMode(self):
        self.test=True

    #-----------------------------------------------------------------
    def disableTestMode(self):
        self.test=False

    #-----------------------------------------------------------------
    def isSelf(self):
        return self.server and "machine_id" in self.requestObject and self.server.getDeviceID()==self.requestObject["machine_id"]

    #-----------------------------------------------------------------
    def closeSocket(self):
        try:
            Tools.closeSocket(self.socket)
            if self.socketFile:
                self.socketFile.close()
        except Exception as e:
            print(f"Error closing socket: {e}")

    #-----------------------------------------------------------------
    def run(self):
        reply=dict()
        contentType="application/json"
        monitorRequested=False

        if self.request!="BUFFER_LEVEL":
            print(f"{self.request} request received at {Tools.formatTime(self.requestTime)} from {self.clientAddress}")

        try:
            match self.request:
                case "MONITOR":
                    if self.server:
                        self.server.addMonitor(self.socketFile)
                    monitorRequested=True

                case "ARCHIVE"|"TRIGGER":
                    clientTime=int(self.requestObject["client_time"]) if "client_time" in self.requestObject else self.requestTime

                    diff=self.requestTime-clientTime
                    startTime=(int(self.requestObject["start_time"]) if "start_time" in self.requestObject else Tools.currentTimeMillis())+diff
                    past=int(self.requestObject["past"]) if "past" in self.requestObject else self.getDefaultBefore()
                    future=int(self.requestObject["future"]) if "future" in self.requestObject else self.getDefaultAfter()

                    if self.isSelf():
                        reply["clips"]=clips if (clips:=self.archiveRequestForBuffers(self.requestID,self.requestTime,startTime,past,future)) else []
                    else:
                        deviceID=self.requestObject["machine_id"]
                        reply["clips"]=[clip] if (clip:=self.archiveRequestForBuffer(self.requestID,self.requestTime,deviceID,startTime,past,future)) else []

                case "BUFFER_LEVEL":
                    reply=self.bufferLevelUpdate()

                case "ANNOUNCE":
                    self.announce()

                case "DELETE_FILE":
                    filename=self.requestObject["filename"]
                    fileType=self.requestObject["file_type"]

                    if self.isSelf():
                        self.deleteFileFromBuffers(filename,fileType)
                    else:
                        deviceID=self.requestObject["machine_id"]
                        self.deleteFileFromBuffer(deviceID,filename,fileType)

                case "DELETE_BUFFER":
                    if self.isSelf():
                        self.deleteBuffers()
                    else:
                        deviceID=self.requestObject["machine_id"]
                        self.deleteBuffer(deviceID)

                case "GET_FROM"|"GET_FROM_DEVICE":
                    deviceID=self.requestObject["buffer_id"] if "buffer_id" in self.requestObject else self.requestObject["machine_id"]
                    prop=self.requestObject["property_name"]
                    reply[prop]=self.getDeviceProperty(deviceID,prop)

                case "SET_AT"|"SET_AT_DEVICE":
                    deviceID=self.requestObject["buffer_id"] if "buffer_id" in self.requestObject else self.requestObject["machine_id"]
                    prop=self.requestObject["property_name"]
                    value=self.requestObject["property_value"]
                    self.setDeviceProperty(deviceID,prop,value)

                case "START_CAPTURE_AT":
                    if self.isSelf():
                        self.startBuffers()

                case "START_CAPTURE_AT_DEVICE":
                    if self.isSelf():
                        bufferID=self.requestObject["buffer_id"]
                        startTime=Tools.currentTimeMillis()
                        self.startBufferCapture(bufferID,startTime)

                case "STOP_CAPTURE_AT":
                    if self.isSelf():
                        self.stopBuffers()

                case "STOP_CAPTURE_AT_DEVICE":
                    if self.isSelf():
                        bufferID=self.requestObject["buffer_id"]
                        self.stopBufferCapture(bufferID)

                case "PAUSE_CAPTURE_AT":
                    if self.isSelf():
                        self.pauseBuffers()

                case "PAUSE_CAPTURE_AT_DEVICE":
                    if self.isSelf():
                        bufferID=self.requestObject["buffer_id"]
                        self.pauseBufferCapture(bufferID)

                case "UNPAUSE_CAPTURE_AT":
                    if self.isSelf():
                        self.unpauseBuffers()

                case "UNPAUSE_CAPTURE_AT_DEVICE":
                    if self.isSelf():
                        bufferID=self.requestObject["buffer_id"]
                        self.unpauseBufferCapture(bufferID)

                case "RESTART_CAPTURE_AT":
                    if self.isSelf():
                        self.restartBuffers()

                case "RESTART_CAPTURE_AT_DEVICE":
                    if self.isSelf():
                        bufferID=self.requestObject["buffer_id"]
                        self.restartBufferCapture(bufferID)

                case "SHUTDOWN_CAPTURE_AT":
                    if self.isSelf():
                        self.shutdownBuffers()

                case "SHUTDOWN_CAPTURE_AT_DEVICE":
                    if self.isSelf():
                        bufferID=self.requestObject["buffer_id"]
                        self.shutdownBufferCapture(bufferID)

                case "KILL_CAPTURE_AT":
                    if self.isSelf():
                        self.killBuffers()

                case "KILL_CAPTURE_AT_DEVICE":
                    if self.isSelf():
                        bufferID=self.requestObject["buffer_id"]
                        self.killBufferCapture(bufferID)

                case "DOWNLOAD":
                    filename=self.requestObject["filename"]
                    fileDir=self.determineDirectory(self.requestObject["file_type"])
                    fileSize=int(self.requestObject["file_length"]) if "file_length" in self.requestObject else None
                    reply["success"]=Tools.downloadFile(self.socket,filename,fileDir,fileSize)>0

                case "UPLOAD":
                    filename=self.requestObject["filename"]
                    fileDir=self.determineDirectory(self.requestObject["file_type"])

                    fullFilename=Tools.validateDir(fileDir,Tools.getWorkingDir())+filename

                    if Tools.exists(fullFilename):
                        reply["success"]=Tools.uploadFile(self.socket,fullFilename)>0
                    else:
                        reply["success"]=False

                case "POST_HTTP":
                    '''
                    post=savePostFile
                    getfile -> (Asks a buffer for a file) = savePostFile -> saves a file from an inputstream locally but can use a boundary to signal the end of the file)
                    save -> (uploads a file to the coordinator) = saveFile -> (saves a file from a socket locally but can use a boundary to signal the end of the file)
                    export=savefile -> (I don't think the server needs this. it moves a file out of the system. A server wouldn't be tasked with that.)
                    '''
                    if "filename" in self.requestObject:
                        filename=self.requestObject["filename"]
                        fileDir=self.determineDirectory("data")
                        fileSize=int(self.requestObject["content-length"])
                        boundary=self.requestObject["boundary"]

                        self.requestObject["success"]=True
                    else:
                        self.requestObject["success"]=False

                    if self.requestObject["success"]:
                        self.requestObject["success"]=Tools.downloadFile(self.socket,filename,fileDir,fileSize,boundary)>0
                    header=Tools.makeHTTPResponse(self.requestObject)
                    Tools.println(header)

                case "GET_HTTP":
                    '''
                    gethttp=uploadFile
                    upload->uploadFile
                    '''
                    if "filename" in self.requestObject:
                        filename=self.requestObject["filename"]
                        fileDir=self.determineDirectory("data")
                        contentType=self.requestObject["content-type"] if "content-type" in self.requestObject else Tools.determineContentType(filename)

                        fullFilename=Tools.validateDir(fileDir,Tools.getWorkingDir())+filename

                        if Tools.exists(fullFilename):
                            replyLength=Tools.getFileSize(fullFilename)
                            self.requestObject["success"]=True
                        else:
                            replyLength=0
                            self.requestObject["success"]=False
                    else:
                        replyLength=0
                        self.requestObject["success"]=True

                    header=Tools.makeHTTPResponse(self.requestObject,replyLength,contentType)
                    Tools.println(self.socket,header)

                    if self.requestObject["success"]:
                        replyLength=Tools.uploadFile(self.socket,fullFilename)

                case "EXPORT_INFO":
                    if "record_id" in self.requestObject:
                        info=self.exportInfo("item",self.requestObject["record_id"])
                    elif "machine_id" in self.requestObject:
                        #refers to parent_id
                        info=self.exportInfo("server",self.requestObject["machine_id"])
                    elif "buffer_id" in self.requestObject:
                        #refers to machine_id
                        info=self.exportInfo("buffer",self.requestObject["buffer_id"])
                    elif "filename" in self.requestObject:
                        info=self.exportInfo("file",self.requestObject["filename"])
                    elif "text" in self.requestObject:
                        info=self.exportInfo("text",self.requestObject["text"])
                    elif "service" in self.requestObject:
                        info=self.exportInfo("service",self.requestObject["service"])
                    else:
                        #return all records
                        info=self.exportInfo()

                    reply["info"]=info

            if not self.isHTTP():
                print(f"Request reply: {reply}")
                replyJSON=json.dumps(reply)
                replyLength=len(replyJSON.encode()) if reply else 0

                if self.isRequestOverHTTP():
                    header=Tools.makeHTTPResponse(self.requestObject,replyLength,contentType)
                    Tools.println(self.socket,header)

                if reply:
                    Tools.print(self.socket,replyJSON)
        except:
            Tools.printStackTrace()

        #print(f"Ended http={self.isHTTP()}, overhttp={self.isRequestOverHTTP()}\nheader={header}\nreply={reply}\n")
        if monitorRequested:
            while self.isReady():
                Tools.sleep(10)
        else:
            self.terminate()

        print(f"{self.request} request done.")

    #-----------------------------------------------------------------
    def terminate(self):
        self.closeSocket()
        self.ready=False

#http://127.0.0.1:9013/?request=~archive&machine_id=100&client_time=1000&start_time=700&past=150&future=50&stated_address=127.0.0.1
#http://127.0.0.1:9013/?request=archive&machine_id=aeec7a5c-0a15-483a-a73a-c4eca7820889:57201&stated_address=127.0.0.1
#http://127.0.0.1:9013/file/test.mpg
#http://127.0.0.1:9013/?request=GET_FROM_DEVICE&machine_id=aeec7a5c-0a15-483a-a73a-c4eca7820889&buffer_id=aeec7a5c-0a15-483a-a73a-c4eca7820889:57201&property_name=options
