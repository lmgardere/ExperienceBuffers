'''
Created on May 19, 2025

@author: lmgar
'''

from abc import ABC,abstractmethod


class DeviceListener(ABC):

    #Called whenever buffer health changes
    #include alerting for: Buffer low disk space, Low battery,
    #Buffer restored, Buffer warning, Buffer problem, Buffer revived
    @abstractmethod
    def bufferHealthCallback(self,machineID: str,prop: str,value: str)->None: pass

    #Called whenever a buffer file is saved
    @abstractmethod
    def bufferFileCreatedCallback(self,machineID: str,filename: str,start: int)->None: pass

    #Called whenever an archive clip is saved
    @abstractmethod
    def clipCreatedCallback(self,requestID: str,machineID: str,filename: str,start: int,duration: int)->None: pass

    #Called whenever a buffer file concatenated as part of the clip making procedure
    @abstractmethod
    def fileConcatenatedCallback(self,machineID: str,filename: str,filePiece: str,current: int,total: int)->None: pass

    #Called whenever a buffer file concatenation process ends
    @abstractmethod
    def fileConcatenationCompletedCallback(self,machineID: str,filename: str,start: int,duration: int)->None: pass
