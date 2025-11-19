import cv2
from cv2_enumerate_cameras import enumerate_cameras
import numpy as np

from experiencebuffers.core.BufferDevice import BufferDevice
from experiencebuffers.util.Tools import Tools


class Camera(BufferDevice):

    def __init__(self,machineID,deviceID):
        BufferDevice.__init__(self,machineID,deviceID)
        self.setPropertyDefault("Name","Camera")
        self.setPropertyDefault("Description","Camera Device")

        self.addService("video")

        self.setPropertyDefault("FileExtension",".mpg")
        self.setPropertyDefault("SaveFormat","h264")
        self.setPropertyDefault("BufferFormat","XVID")
        self.setPropertyDefault("CaptureFormat","MJPG")
        self.setPropertyDefault("Width",1920)
        self.setPropertyDefault("Height",1080)
        self.setPropertyDefault("FPS",15)
        self.intermediateFileExt=".avi"
        self.captureDevice=None
        self.captureFormat=None
        self.saveFormat=None
        self.platforms=[cv2.CAP_ANY,cv2.CAP_VFW,cv2.CAP_DSHOW,cv2.CAP_MSMF,cv2.CAP_V4L2]
        self.hostAPI=self.platforms[2] if self.platform.lower()=="windows" else self.platforms[0]

    #-----------------------------------------------------------------
    #Required methods
    #-----------------------------------------------------------------
    def initialize(self):
        result=False

        mediaIndex=self.parseMediaID()
        if not mediaIndex:
            if not (mediaIndex:=self.getCameraIndexByName(self.getMediaID())):
                mediaIndex=0

        self.mediaIndex=mediaIndex
        try:
            # Open the webcam
            if str(self.mediaIndex).isnumeric():
                self.captureDevice=cv2.VideoCapture(self.mediaIndex,self.hostAPI)
            else:
                #likely an http, rtsp, or rtmp url
                self.captureDevice=cv2.VideoCapture(self.mediaIndex)

            if result:=self.captureDevice.isOpened():
                if w:=self.getProperty("Width"):
                    self.captureDevice.set(cv2.CAP_PROP_FRAME_WIDTH,int(w))
                if h:=self.getProperty("Height"):
                    self.captureDevice.set(cv2.CAP_PROP_FRAME_HEIGHT,int(h))

                #if fps:=self.getProperty("FPS"):
                    #self.captureDevice.set(cv2.CAP_PROP_FPS,int(fps))
                if captureFormat:=self.getProperty("CaptureFormat"):
                    self.captureDevice.set(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*captureFormat))

                if str(self.mediaIndex).isnumeric():
                    self.setMediaID(str(self.mediaIndex)+": "+str(self.getCameraNameByIndex(self.mediaIndex)))

                self.fps=int(self.captureDevice.get(cv2.CAP_PROP_FPS) if self.captureDevice.get(cv2.CAP_PROP_FPS) else self.getProperty("FPS"))

                self.width=int(self.captureDevice.get(cv2.CAP_PROP_FRAME_WIDTH))
                if self.width:
                    self.setProperty("Width",self.width)

                self.height=int(self.captureDevice.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if self.height:
                    self.setProperty("Height",self.height)

                self.pixelDepth=int(self.captureDevice.get(cv2.CAP_PROP_FORMAT))
                self.pixelDepth=self.pixelDepth if self.pixelDepth>=0 else None

                self.captureFormat=int(self.captureDevice.get(cv2.CAP_PROP_FOURCC))
                if self.captureFormat>100:
                    self.setCaptureFormat(Tools.decodeFOURCC(self.captureFormat))

                self.bufferFormat=cv2.VideoWriter_fourcc(*self.getBufferFormat())
                #self.saveFormat=cv2.VideoWriter_fourcc(*self.getSaveFormat())

                self.printConfiguration()
        except:
            self.captureDevice=None
            result=False
            Tools.printStackTrace()

        if not result:
            print("Error initializing "+str(self.getDeviceName())+" using "+str(self.getMediaID()))
            print("Try using one of these "+str(self.getBufferClass())+" devices:")
            for d in self.listDevices():
                print("\t"+str(d))

        self.initialized=result

    #-----------------------------------------------------------------
    def listDevices(self):
        return [f"{(dev.index-self.hostAPI)}: {dev.name}" for dev in enumerate_cameras() if (dev.index&self.hostAPI)==self.hostAPI]

    #-----------------------------------------------------------------
    def getCaptureBufferSize(self):
        return self.width*self.height*3*(self.pixelDepth//8)

    #-----------------------------------------------------------------
    def getBytesPerPeriod(self):
        return int(self.fps*self.getCaptureBufferSize()*self.getCaptureFrequency()/1000)

    #-----------------------------------------------------------------
    def getFiller(self):
        if not self.filler:
            self.filler=[np.zeros((self.height,self.width,3),dtype=np.uint8 if (self.pixelDepth//8)==1 else np.uint16)]*int(self.fps*self.getCaptureFrequency()/1000)

        return self.filler

    #-----------------------------------------------------------------
    def deviceStartCapture(self):
        if self.showOutput() and self.hasDisplay:
            windowName=self.getCameraNameByIndex(self.mediaIndex)
            windowName=windowName if windowName else self.getDeviceName()
            cv2.namedWindow(windowName,cv2.WINDOW_NORMAL)

            cv2.resizeWindow(windowName,self.width,self.height)
        else:
            print(f"{self.getDeviceName()} operating in headless capture mode.")

        self.capturing=True
        while self.isCapturing():
            if not self.isPaused():
                try:
                    ret,frame=self.captureDevice.read()  # Capture frame
                    if ret:
                        if not self.pixelDepth:
                            self.pixelDepth=self.determinePixelDepth(frame.dtype)
                        self.addData(frame,Tools.currentTimeMillis())
                    else:
                        print("Error in buffer capture "+self.getDeviceName()+": "+str(ret))
                        break

                    if self.showOutput() and self.hasDisplay:
                        cv2.imshow(windowName,frame)  # Display the frame

                        cv2.waitKey(1)
                        if cv2.getWindowProperty(windowName,cv2.WND_PROP_AUTOSIZE)>0:
                            self.deviceStopCapture()
                except Exception as e:
                    print("Buffer Capture exception "+self.getDeviceName()+": "+str(e))
            else:
                Tools.sleep(100)

        self.captureDevice.release()  # Release the webcam
        if self.showOutput() and self.hasDisplay:
            cv2.waitKey(1)
            cv2.destroyWindow(windowName)  # Close OpenCV windows
        self.captureDevice=None

    #-----------------------------------------------------------------
    def deviceStopCapture(self):
        result=True

        if self.captureDevice:
            self.capturing=False
            self.initialized=False

        return result

    #-----------------------------------------------------------------
    def forceClose(self):
        self.deviceStopCapture()
        self.captureDevice=None

    #-----------------------------------------------------------------
    def testDataSource(self):
        return (self.captureDevice.isOpened() if self.captureDevice else False) or not self.initialized

    #-----------------------------------------------------------------
    def validateBufferFilename(self,filename):
        if self.getBufferFormat()in ["XVID","MJPG"]:
            self.intermediateFileExt=".avi"
            filename+=self.intermediateFileExt

        return filename

    #-----------------------------------------------------------------
    def deviceWriteBufferData(self,filename,data):
        result=True

        try:
            bufferWriter=self.getWriter(filename,self.bufferFormat)

            for frame in data:
                bufferWriter.write(frame)

            bufferWriter.release()
        except Exception as e:
            result=False
            print("Error writing buffer file for "+self.getDeviceName()+": "+str(e))

        return result

    #-----------------------------------------------------------------
    def deviceMakeClip(self,requestID,clipFilename,files,_start,_duration):
        intermediateFile=clipFilename[:-4]+self.intermediateFileExt
        parts=intermediateFile.rpartition("/")
        intermediateFile=parts[0]+parts[1]+"temp_"+parts[2]

        print(self.getDeviceName()+": "+str(len(files)))
        try:
            clipWriter=self.getWriter(intermediateFile,self.bufferFormat)

            for i,file in enumerate(files):
                cap=cv2.VideoCapture(file)

                while cap.isOpened():
                    ret,frame=cap.read()
                    if not ret:
                        break
                    clipWriter.write(frame)

                cap.release()

                self.recordConcatenationProgress(requestID,self.getDeviceID(),intermediateFile,file,i+1,len(files))
                self.concatenationProgressCallback(requestID,self.getDeviceID(),intermediateFile,file,i+1,len(files))

            clipWriter.release()
        except Exception as e:
            print("Error writing clip file for "+self.getDeviceName()+": "+str(e))
            Tools.printStackTrace()

        return intermediateFile

    #-----------------------------------------------------------------
    #Helper methods
    #-----------------------------------------------------------------
    def printConfiguration(self):
        print(self.getDeviceName()+" Format")
        print("\tDeviceID:\t"+str(self.getDeviceID()))
        print("\tPlatform:\t"+str(self.hostAPI))
        print("\tDevice:\t\t"+str(self.getMediaID()))
        print("\tCapture Format:\t"+str(self.getCaptureFormat()))
        print("\tBuffer Format:\t"+str(self.getBufferFormat()))
        print("\tClip Format:\t"+str(self.getSaveFormat()))
        print("\tResolution:\t"+str(self.width)+"x"+str(self.height))
        print("\tColor Depth:\t"+str(self.pixelDepth if self.pixelDepth else "TBD"))
        print("\tFPS:\t\t"+str(self.fps))

    #-----------------------------------------------------------------
    def printDevices(self):
        for d in self.listDevices():
            print(d)

    #-----------------------------------------------------------------
    def getCameraNameByIndex(self,ind):
        result=None

        if str(ind).isnumeric():
            for cam in enumerate_cameras():
                if cam.index==(self.hostAPI+ind):
                    result=cam.name

        return result

    #-----------------------------------------------------------------
    def getCameraIndexByName(self,name):
        result=None

        for cam in enumerate_cameras():
            if name in cam.name:
                result=cam.index

        return result

    #-----------------------------------------------------------------
    def getWriter(self,filename,vFormat):
        return cv2.VideoWriter(filename,vFormat,self.fps,(self.width,self.height))

    #-----------------------------------------------------------------
    def determinePixelDepth(self,depth):
        result=None

        if "uint8" in str(depth).lower():
            result=8
        elif "uint16" in str(depth).lower():
            result=16

        return result
