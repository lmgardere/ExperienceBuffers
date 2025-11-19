import pyaudio
import wave
import traceback

from experiencebuffers.core.BufferDevice import BufferDevice
from experiencebuffers.util.Tools import Tools


class Mic(BufferDevice):

    def __init__(self,machineID,deviceID):
        BufferDevice.__init__(self,machineID,deviceID)
        self.setPropertyDefault("Name","Mic")
        self.setPropertyDefault("Description","Mic Device")

        self.addService("audio")

        self.setPropertyDefault("FileExtension",".mp3")
        self.setPropertyDefault("SaveFormat","mp3")
        self.setPropertyDefault("BufferFormat","PCM")
        self.setPropertyDefault("CaptureFormat","PCM")
        self.setPropertyDefault("SoundDepth","16")
        self.setPropertyDefault("AudioMode","stereo")
        self.setPropertyDefault("AudioRate","44100")
        self.intermediateFileExt=".wav"

        self.audioDevice=None
        self.audioStream=None
        self.channels=None
        self.chunk=0
        self.hostAPI=0 if self.platform.lower()=="windows" else 0

    #-----------------------------------------------------------------
    #Required methods
    #-----------------------------------------------------------------
    def initialize(self):
        result=False

        self.mediaIndex=self.parseMediaID()

        try:
            self.audioDevice=pyaudio.PyAudio()

            if not self.mediaIndex:
                self.mediaIndex=self.audioDevice.get_default_input_device_info()["index"]

            self.setChunkSize(1225)
            self.audioStream=self.audioDevice.open(format=self.getFormat(),channels=self.getChannels(),rate=self.getRate(),
                        input=True,frames_per_buffer=self.chunk,input_device_index=self.mediaIndex)

            if result:=self.audioStream.is_active():
                if str(self.mediaIndex).isnumeric():
                    self.setMediaID(str(self.mediaIndex)+": "+str(self.getMediaNameByIndex(self.mediaIndex)))

                self.setProperty("SoundDepth",self.determineSoundDepth(self.audioStream._format))
                self.setProperty("AudioMode","mono" if self.audioStream._channels==1 else "stereo" if self.audioStream._channels else None)
                self.setProperty("AudioRate",self.audioStream._rate)
                self.setChunkSize(self.audioStream._frames_per_buffer)

                self.printConfiguration()
        except:
            self.audioStream=None
            result=False
            traceback.print_exc()

        if not result:
            print("Error initializing "+str(self.getDeviceName())+" using "+str(self.getMediaID()))
            print("Trying using one of these "+str(self.getBufferClass())+" devices:")
            for d in self.listDevices():
                print("\t"+str(d))

        self.initialized=result

    #-----------------------------------------------------------------
    def listDevices(self):
        dev=list()

        for i in range(self.audioDevice.get_device_count()):
            d=self.audioDevice.get_device_info_by_index(i)
            if d["hostApi"]==self.hostAPI and d["defaultSampleRate"]==self.getRate() and d["maxInputChannels"]>=self.getChannels():
                dev.append(f"{i}:{d['name']}")

        return dev

    #-----------------------------------------------------------------
    def getCaptureBufferSize(self):
        return 4*self.chunk

    #-----------------------------------------------------------------
    def getBytesPerPeriod(self):
        return int(self.getRate()*self.getChannels()*(self.getSoundDepth()//8)*self.getCaptureFrequency()/1000)

    #-----------------------------------------------------------------
    def getFiller(self):
        if not self.filler:
            self.filler=[(b'\x00')*self.getCaptureBufferSize()]*int(self.getBytesPerPeriod()//self.getCaptureBufferSize())

        return self.filler

    #-----------------------------------------------------------------
    def deviceStartCapture(self):
        self.capturing=True
        while self.isCapturing():
            if not self.isPaused():
                try:
                    data=self.audioStream.read(self.chunk)
                    self.addData(data,Tools.currentTimeMillis())
                except Exception as e:
                    Tools.printStackTrace()
                    print("Error in buffer capture "+self.getDeviceName()+": "+str(e))
            else:
                Tools.sleep(100)

    #-----------------------------------------------------------------
    def deviceStopCapture(self):
        self.capturing=False

        self.audioStream.stop_stream()
        self.audioStream.close()
        self.audioDevice.terminate()

        self.initialized=False

        return self.capturing

    #-----------------------------------------------------------------
    def forceClose(self):
        self.deviceStopCapture()
        self.audioStream=None
        self.audioDevice=None

    #-----------------------------------------------------------------
    def testDataSource(self):
        return (self.audioStream.is_active() if self.audioStream else False) or not self.initialized

    #-----------------------------------------------------------------
    def validateBufferFilename(self,filename):
        if self.getBufferFormat()=="PCM":
            filename+=self.intermediateFileExt

        return filename

    #-----------------------------------------------------------------
    def deviceWriteBufferData(self,filename,data):
        result=True

        try:
            with wave.open(filename,'wb') as waveform:
                waveform.setnchannels(self.getChannels())
                waveform.setsampwidth(self.audioDevice.get_sample_size(self.getFormat()))
                waveform.setframerate(self.getRate())
                waveform.writeframes(b''.join(data))
        except:
            result=False

        return result

    #-----------------------------------------------------------------
    def deviceMakeClip(self,requestID,clipFilename,files,_start,_duration):
        intermediateFile=clipFilename[:-4]+self.intermediateFileExt
        parts=intermediateFile.rpartition("/")
        intermediateFile=parts[0]+parts[1]+"temp_"+parts[2]

        print(self.getDeviceName()+": "+str(len(files)))
        try:
            with wave.open(intermediateFile,'wb') as outputFile:
                outputFile.setnchannels(self.getChannels())
                outputFile.setsampwidth(self.audioDevice.get_sample_size(self.getFormat()))
                outputFile.setframerate(self.getRate())

                for i,file in enumerate(files):
                    try:
                        with wave.open(file,'rb') as inputFile:
                            outputFile.writeframes(inputFile.readframes(inputFile.getnframes()))

                        self.recordConcatenationProgress(requestID,self.getDeviceID(),intermediateFile,file,i+1,len(files))
                        self.concatenationProgressCallback(requestID,self.getDeviceID(),intermediateFile,file,i+1,len(files))
                    except:
                        Tools.printStackTrace()
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
        print("\tMode:\t\t"+str(self.getAudioMode()).capitalize())
        print("\tSound Depth:\t"+str(self.getSoundDepth())+"-bit")
        print("\tSampleRate:\t"+str(self.getRate()))

    #-----------------------------------------------------------------
    def printAPIs(self):
        for d in self.listAPIs():
            print(d)

    #-----------------------------------------------------------------
    def printDevices(self):
        for d in self.listDevices():
            print(d)

    #-----------------------------------------------------------------
    def getAudioMode(self):
        return self.getProperty("AudioMode")

    #-----------------------------------------------------------------
    def getRate(self):
        return int(self.getProperty("AudioRate"))

    #-----------------------------------------------------------------
    def getSoundDepth(self):
        return int(self.getProperty("SoundDepth"))

    #-----------------------------------------------------------------
    def getChannels(self):
        return 2 if self.getAudioMode().lower()=="stereo" else 1

    #-----------------------------------------------------------------
    def determineSoundDepth(self,sformat):
        formats={pyaudio.paInt8:8,pyaudio.paInt16:16,pyaudio.paInt24:24,pyaudio.paInt32:32}

        return formats[sformat]

    #-----------------------------------------------------------------
    def getFormat(self):
        formats={"8":pyaudio.paInt8,"16":pyaudio.paInt16,"24":pyaudio.paInt24,"32":pyaudio.paInt32}

        return formats[str(self.getSoundDepth())]

    #-----------------------------------------------------------------
    def listAPIs(self):
        APIs=list()

        for i in range(self.audioDevice.get_host_api_count()):
            APIs.append(self.audioDevice.get_host_api_info_by_index(i))

        return APIs

    #-----------------------------------------------------------------
    def getMediaNameByIndex(self,ind):
        return self.audioDevice.get_device_info_by_index(ind)["name"] if str(ind).isnumeric() else None

    #-----------------------------------------------------------------
    def setChunkSize(self,chunk):
        #Trying to get to a good chunk size that allows for consistent capture of 1 sec of audioDevice. pyaudio tends to capture in 4
        #chunks so, 4*1225=4900.
        #36 frames of data at 4 chunks of 1225 equals 176,400 bytes or 44100hz * 2 channels * 16 bits.
        #40 frames of data at 4 chunks of 1200 equals 192,000 bytes or 48000hz * 2 channels * 16 bits.

        self.chunk=chunk
