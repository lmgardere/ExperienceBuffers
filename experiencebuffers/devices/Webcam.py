import os

from experiencebuffers.core.BufferDevice import BufferDevice


class Webcam(BufferDevice):

    def __init__(self,machineID,deviceID):
        BufferDevice.__init__(self,machineID,deviceID)
        self.setPropertyDefault("Name","WebcaM")
        self.setPropertyDefault("Description","Webcam with video and audio")

        self.addService("video")
        self.addService("audio")

        self.setPropertyDefault("FileExtension",".mpg")
        self.setPropertyDefault("CaptureFormat","text")
        self.setPropertyDefault("BufferFormat","h264")
        self.setPropertyDefault("SaveFormat","h264")

    #-----------------------------------------------------------------
    #Required methods
    #-----------------------------------------------------------------
    def initialize(self):
        self.initialized=self.initializeServiceDevices()

        print(self.getDeviceName()+" Format")
        print("\tDeviceID:\t"+str(self.getDeviceID()))
        print("\tDevice:\t\t"+str(self.getMediaID()))
        print("\tCapture Format:\t"+str(self.getCaptureFormat()))
        print("\tBuffer Format:\t"+str(self.getBufferFormat()))
        print("\tClip Format:\t"+str(self.getSaveFormat()))

    #-----------------------------------------------------------------
    def listDevices(self):
        return self.listServiceDevices()

    #-----------------------------------------------------------------
    def getCaptureBufferSize(self):
        return None

    #-----------------------------------------------------------------
    def getBytesPerPeriod(self):
        return None

    #-----------------------------------------------------------------
    def getFiller(self):
        return None

    #-----------------------------------------------------------------
    def deviceStartCapture(self):
        self.capturing=self.startServiceDevices()
        return self.capturing

    #-----------------------------------------------------------------
    def deviceStopCapture(self):
        self.capturing=self.stopServiceDevices()
        return self.capturing

    #-----------------------------------------------------------------
    def forceClose(self):
        self.forceServiceClose()

    #-----------------------------------------------------------------
    def testDataSource(self):
        return self.testServiceDeviceDataSources()

    #-----------------------------------------------------------------
    def validateBufferFilename(self,filename):
        return filename

    #-----------------------------------------------------------------
    def deviceWriteBufferData(self,_filename,_data):
        return len(self.getFiles())>0

    #-----------------------------------------------------------------
    def deviceMakeClip(self,requestID,clipFilename,files,start,duration):
        clips=dict()
        intermediateFile=clipFilename[:-4]

        print(self.getDeviceName()+": "+str(len(files)))
        for service,dev in self.devices.items():
            clips[service]={"files":[file for file in files if dev.getFrameName() in file]}
            clips[service]["filename"]=intermediateFile+dev.getFileExtension()
            clips[service]["result"]=dev.clipMaker(requestID,clips[service]["filename"],start,start+duration,clips[service]["files"])

        print(self.getDeviceName()+" merging audio and video streams...")
        if result:=all([clips[service]["result"] for service in self.devices.keys()]):
            mergeClips={service:clips[service]["filename"] for service,val in clips.items() if "filename" in val}
            result=self.mergeAudioVideo(mergeClips,clipFilename,self.getSaveFormat(),"mp3")

            for _,clip in mergeClips.items():
                if clip!=clipFilename:
                    os.remove(clip)

        return clipFilename

    #-----------------------------------------------------------------
    #DeviceListener methods
    #-----------------------------------------------------------------
    def bufferFileCreatedCallback(self,machineID,filename,start):
        deviceIDs=[device.getDeviceID() for _,device in self.devices.items()]
        deviceIDs.append(self.getDeviceID())

        if machineID in deviceIDs:
            with self.getFileSyncObject():
                self.addFile(filename,start)

    #-----------------------------------------------------------------
    def clipCreatedCallback(self,requestID,machineID,filename,start,duration):
        deviceIDs=[device.getDeviceID() for _,device in self.devices.items()]
        deviceIDs.append(self.getDeviceID())

        if machineID in deviceIDs:
            with self.getClipSyncObject():
                self.addClip(filename,start)

        BufferDevice.clipCreatedCallback(self,requestID,machineID,filename,start,duration)
