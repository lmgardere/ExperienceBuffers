from experiencebuffers.core.BufferDevice import BufferDevice


class TestDevice(BufferDevice):

    def __init__(self,machineID,deviceID):
        BufferDevice.__init__(self,machineID,deviceID)
        self.setDeviceName("Test")
        self.setDeviceDescription("Empty Test Device")
        self.addService("test")
        self.setPropertyDefault("FileExtension",".txt")
        self.setPropertyDefault("SaveFormat","text")
        self.setPropertyDefault("CaptureFormat","text")
        self.filler=bytearray()

    #-----------------------------------------------------------------
    def initialize(self):
        self.initialized=True

    #-----------------------------------------------------------------
    def listDevices(self):
        pass

    #-----------------------------------------------------------------
    def getCaptureBufferSize(self):
        pass

    #-----------------------------------------------------------------
    def getBytesPerPeriod(self):
        pass

    #-----------------------------------------------------------------
    def getFiller(self):
        pass

    #-----------------------------------------------------------------
    def deviceStartCapture(self):
        self.capturing=True

    #-----------------------------------------------------------------
    def deviceStopCapture(self):
        pass

    #-----------------------------------------------------------------
    def forceClose(self):
        pass

    #-----------------------------------------------------------------
    def testDataSource(self):
        pass

    #-----------------------------------------------------------------
    def validateBufferFilename(self,filename):
        return filename

    #-----------------------------------------------------------------
    def deviceWriteBufferData(self,filename,data):
        pass

    #-----------------------------------------------------------------
    def deviceMakeClip(self,requestID,clipFilename,files,start,duration):
        pass
