'''
Created on Jun 15, 2025

@author: lmgar
'''

from abc import ABC,abstractmethod


class ServerListener(ABC):

    @abstractmethod
    def serverStartedCallback(self,machineID: str)->None: pass

    @abstractmethod
    def serverStoppedCallback(self,machineID: str)->None: pass

    @abstractmethod
    def deleteFileCallback(self,machineID: str,file: str,success: bool)->None: pass

    @abstractmethod
    def deleteBufferCallback(self,machineID: str,success: bool)->None: pass

    @abstractmethod
    def startCaptureCallback(self,machineID: str)->None: pass

    @abstractmethod
    def stopCaptureCallback(self,machineID: str)->None: pass

    @abstractmethod
    def pauseCaptureCallback(self,machineID: str)->None: pass

    @abstractmethod
    def unpauseCaptureCallback(self,machineID: str)->None: pass

    @abstractmethod
    def restartCaptureCallback(self,machineID: str)->None: pass

    @abstractmethod
    def shutdownCaptureCallback(self,machineID: str)->None: pass

    @abstractmethod
    def killCaptureCallback(self,machineID: str)->None: pass

    @abstractmethod
    def archiveRequestCallback(self,requestID: str,requestTime: int,machineID: str,startTime: int,past: int,future: int)->None: pass

    @abstractmethod
    def dataReadyCallback(self,machineID: str,file: str,fileLength: int,success: bool)->None: pass

    @abstractmethod
    def infoUpdatedCallback(self,machineID: str,info)->None: pass

    @abstractmethod
    def saveFileCallback(self,machineID: str,file: str,success: bool)->None: pass

    @abstractmethod
    def convertCallback(self,machineID: str,inputFile: str,outputFile: str,success: bool)->None: pass
