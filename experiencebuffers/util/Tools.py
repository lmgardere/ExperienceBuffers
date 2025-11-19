'''
Created on May 21, 2025

@author: lmgar
'''
import os,sys
import platform
import time,pytz
import uuid,psutil,shutil
import socket
import threading
import traceback
import mimetypes

from io import TextIOWrapper
from datetime import datetime,timezone

sys.path.append("/mnt/c/Users/lmgar/OneDrive/Documents/My Projects/ExperienceBuffers/python source/")
from experiencebuffers.util.Standards import Standards


class Tools:

    #-----------------------------------------------------------------
    @staticmethod
    def sleep(t):
        time.sleep(t/1000.0)

    #-----------------------------------------------------------------
    @staticmethod
    def printCurrentTime():
        return Tools.formatTime(Tools.currentTimeMillis())

    #-----------------------------------------------------------------
    @staticmethod
    def formatTime(utc):
        utcTime=datetime.fromtimestamp(utc/1000,tz=timezone.utc)

        timeZone=pytz.timezone("America/Chicago")
        localTime=utcTime.astimezone(timeZone)

        return str(localTime.strftime("%a, %b %d %H:%M:%S %Z %Y"))

    #-----------------------------------------------------------------
    @staticmethod
    def timeLength(start,end):
        t=(f"{(end-start)//60000}m ") if abs(end-start)>=60000 else ""
        t+=f"{((end-start)//1000)%60:02}.{(end-start)%100}s"

        return t

    #-----------------------------------------------------------------
    @staticmethod
    def currentTimeMillis():
        return int(time.time_ns()//1000000)

    #-----------------------------------------------------------------
    @staticmethod
    def makeRequestID():
        return str(hash(str(Tools.currentTimeMillis()))&0xFFFFFFFF)

    #-----------------------------------------------------------------
    @staticmethod
    def decodeFOURCC(code):
        return "".join([chr((int(code)>>(8*i))&0xFF) for i in range(4)])

    #-----------------------------------------------------------------
    @staticmethod
    def getLocalIP():
        ip="127.0.0.1"

        for interface in ["eth0","eth1","Wi-Fi","wifi0","wlan0","bnep0"]:
            try:
                for iface,addrs in psutil.net_if_addrs().items():
                    if interface in iface:
                        for addr in addrs:
                            if addr.broadcast:
                                ip=str(addr.address)
                                break
            except Exception:
                pass

        return ip

    #-----------------------------------------------------------------
    @staticmethod
    def getHostName():
        hostname="loopback"

        try:
            hostname=socket.gethostname()
        except Exception as e:
            print("Error getting hostname: "+str(e))

        return hostname

    #-----------------------------------------------------------------
    @staticmethod
    def getExternalIP():
        ip="127.0.0.1"
        try:
            # Create a socket connection to an external server
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8",80))  # Google's public DNS server
                ip=sock.getsockname()[0]
        except Exception as e:
            print("Error getting external ip address: "+str(e))

        return ip

    #-----------------------------------------------------------------
    @staticmethod
    def isConnected(sock):
        try:
            temp=sock.getblocking()
            sock.setblocking(False)
            data=sock.recv(1,socket.MSG_PEEK)
            sock.setblocking(temp)
            return bool(data)
        except BlockingIOError:
            return True  # No data, but still connected
        except (ConnectionResetError,OSError) as _:
            return False

    #-----------------------------------------------------------------
    @staticmethod
    def closeSocket(sock):
        if sock:
            if Tools.isConnected(sock):
                sock.shutdown(socket.SHUT_RDWR)
            sock.close()

    #-----------------------------------------------------------------
    @staticmethod
    def makeMachineID():
        return str(uuid.uuid4())

    #-----------------------------------------------------------------
    @staticmethod
    def makeGroupID(ID):
        return ID+":"+str(Tools.currentTimeMillis())[-4:]

    #-----------------------------------------------------------------
    @staticmethod
    def makeDeviceID(ID):
        return ID+":"+str(Tools.currentTimeMillis())[-5:]

    #-----------------------------------------------------------------
    @staticmethod
    def makeMACMachineID(tail=None):
        mac="00-00-00-00-00-00"
        tail=str(tail if tail else Tools.currentTimeMillis())

        try:
            # Try to get MAC address based on available network interfaces
            if macBytes:=(Tools.getMACAddress("Wi-Fi") or Tools.getMACAddress("wifi0") or Tools.getMACAddress("wlan0") or Tools.getMACAddress("eth0") or Tools.getAnyMACAddress()):
                mac="-".join("%02s"%byte for byte in macBytes)

        except Exception as e:
            print("Error retrieving MAC address: "+str(e))

        return mac+"-"+tail

    #-----------------------------------------------------------------
    @staticmethod
    def getMACAddress(interface):
        result=None

        try:
            for iface,addrs in psutil.net_if_addrs().items():
                if interface in iface:
                    for addr in addrs:
                        if addr.family==psutil.AF_LINK:
                            result=addr.address.split(":")
                            break
        except Exception:
            pass

        return result

    #-----------------------------------------------------------------
    @staticmethod
    def getAnyMACAddress():
        result=None

        try:
            result=uuid.getnode().to_bytes(6,'big')
        except Exception:
            pass

        return result

    #-----------------------------------------------------------------
    @staticmethod
    def loadConfig(configFile):
        config=dict()

        if os.path.exists(configFile):
            with open(configFile,"r") as file:
                for line in file:
                    if not line.startswith("#"):
                        param=line.partition("=")
                        key=param[0]
                        valid=param[1]
                        value=param[2]

                        if valid:
                            config[key]=str(value).strip()

        return config

    #-----------------------------------------------------------------
    @staticmethod
    def saveConfig(config,configFile,className):
        if os.path.exists(configFile):
            originalConfigFile=configFile
            configFile="tmp_"+configFile
        else:
            originalConfigFile=None

        try:
            with open(configFile,"w") as file:
                Tools.println(file,f"#{(className+' ') if className else ''}configuration file ({originalConfigFile if originalConfigFile else configFile})")
                Tools.println(file,"#"+Tools.printCurrentTime())

                config.setdefault("DeviceType",str(className))
                for k,v in config.items():
                    Tools.println(file,str(k)+"="+str(v))

            if originalConfigFile:
                os.replace(configFile,originalConfigFile)
        except:
            if originalConfigFile:
                os.remove(configFile)
            Tools.printStackTrace()

    #-----------------------------------------------------------------
    @staticmethod
    def printStackTrace():
        traceback.print_exc()
        #raceback.print_stack()

    #-----------------------------------------------------------------
    @staticmethod
    def println(file,s=""):
        Tools.print(file,str(s)+"\r\n")

    #-----------------------------------------------------------------
    @staticmethod
    def print(file,s=""):
        s=str(s)

        if isinstance(file,socket.socket):
            file.sendall(s.encode())
        else:
            file.write(s if isinstance(file,TextIOWrapper) else s.encode())
            file.flush()

    #-----------------------------------------------------------------
    @staticmethod
    def read(sock):
        result=b""

        sock.settimeout(0.1)

        try:
            while data:=sock.recv(Standards.SOCKET_BUFFER_SIZE):
                result+=data
        except:
            pass

        return result

    #-----------------------------------------------------------------
    @staticmethod
    def exists(filename):
        return os.path.exists(filename)

    #-----------------------------------------------------------------
    @staticmethod
    def getFileSize(filename):
        return os.path.getsize(filename)

    #-----------------------------------------------------------------
    @staticmethod
    def removeDir(filename):
        return filename.rpartition("/")[2]

    #-----------------------------------------------------------------
    @staticmethod
    def getWorkingDir():
        return Tools.validateDir(os.getcwd())

    #-----------------------------------------------------------------
    @staticmethod
    def findHomeDir():
        homeDir=os.path.expanduser("~").replace("\\","/")  # Standardize path format
        return str(homeDir)+"/ExperienceBuffers/"

    #-----------------------------------------------------------------
    @staticmethod
    def validateDir(dirPath,defaultDir=None,homeDir=None):
        if homeDir is None:
            homeDir=Tools.findHomeDir()

        if dirPath:
            dirPath=dirPath.replace("\\","/").strip()  # Normalize path

            if dirPath.startswith("~/"):
                dirPath=homeDir+dirPath[2:]
            elif dirPath.startswith("./"):
                dirPath=os.getcwd().replace("\\","/")+dirPath[1:]

            if not dirPath.endswith("/"):
                dirPath+="/"

            # Ensure directory exists
            if not os.path.exists(dirPath):
                try:
                    os.makedirs(dirPath)
                except OSError:
                    dirPath=""
        else:
            dirPath=""

        if not dirPath and defaultDir:
            defaultDir=defaultDir.replace("\\","/").strip()
            dirPath=defaultDir[2:] if defaultDir.startswith("~/") else defaultDir.lstrip("/")
            dirPath=homeDir+dirPath

        return dirPath

    #-----------------------------------------------------------------
    @staticmethod
    def determineContentType(filename):
        result,_=mimetypes.guess_type(filename)

        return result or "application/octet-stream"

    #-----------------------------------------------------------------
    @staticmethod
    def makeHTTPResponse(request,payloadSize=0,contentType=None):
        result=""

        match request["request"]:
            case "GET_HTTP":
                if request["success"]:
                    result+="HTTP/1.1 200 Ok\r\n"
                    result+=f"Content-Disposition: attachment; filename=\"{request['filename']}\"\r\n"
                else:
                    result+="HTTP/1.1 400 Bad Request\r\n"

                if payloadSize:
                    if contentType:
                        result+=f"Content-Type: {contentType}\r\n"
                    result+=f"Content-Length: {payloadSize}\r\n"

                result+=f"Date: {Tools.printCurrentTime()}\r\n"
                result+="Server: ExperienceBufferServer/1.0\r\n"

            case "POST_HTTP":
                if request["success"]:
                    result+="HTTP/1.1 201 Created\r\n"
                else:
                    result+="HTTP/1.1 400 Bad Request\r\n"

                result+="Location: ExperienceBufferServer\r\n"

                if payloadSize:
                    if contentType:
                        result+=f"Content-Type: {contentType}\r\n"
                    result+=f"Content-Length: {payloadSize}\r\n"

            case "ARCHIVE":
                result+="HTTP/1.1 202 Accepted\r\n"

                if payloadSize:
                    if contentType:
                        result+=f"Content-Type: {contentType}\r\n"
                    result+=f"Content-Length: {payloadSize}\r\n"

                result+="Location: ExperienceBufferServer\r\n"
                result+=f"Date: {Tools.printCurrentTime()}\r\n"

            case _:
                if payloadSize:
                    result+="HTTP/1.1 200 Ok\r\n"
                    if contentType:
                        result+=f"Content-Type: {contentType}\r\n"
                    result+=f"Content-Length: {payloadSize}\r\n"
                else:
                    result+="HTTP/1.1 204 No Content\r\n"
                    result+=f"Date: {Tools.printCurrentTime()}\r\n"
                    result+="Server: ExperienceBufferServer/1.0\r\n"

        result+="Connection: Keep-Alive\r\n"

        return result

    #-----------------------------------------------------------------
    @staticmethod
    def callback(listenerFunc,*args,**kwargs):
        listener=threading.Thread(target=listenerFunc,args=args,kwargs=kwargs,daemon=True,name=str(listenerFunc))
        listener.start()

        return listener

    #-----------------------------------------------------------------
    @staticmethod
    def downloadFile(socket,filename,fileDir=None,fileLength=None,boundary=None):
        size=0
        filename=Tools.validateDir(fileDir,Tools.getWorkingDir())+filename

        try:
            with open(filename,'wb') as file:
                if boundary:
                    while data:=socket.makefile.readline():
                        if boundary in str(data):
                            break

                while data:=socket.recv(Standards.FILE_BUFFER_SIZE):
                    file.write(data)
                    size+=len(data)

                    if (boundary and (boundary+"--") in str(data)) or (fileLength and size>=fileLength):
                        break
        except:
            Tools.printStackTrace()

        return size

    #-----------------------------------------------------------------
    @staticmethod
    def uploadFile(socket,filename):
        size=0

        try:
            with open(filename,'rb') as file:
                size=socket.sendfile(file)
        except:
            Tools.printStackTrace()

        return size

    #-----------------------------------------------------------------
    @staticmethod
    def getPlatform():
        return platform.system()

    #-----------------------------------------------------------------
    @staticmethod
    def getBatteryLevel():
        battery=psutil.sensors_battery()

        return battery.percent

    #-----------------------------------------------------------------
    @staticmethod
    def getPowerSource():
        battery=psutil.sensors_battery()

        return "plugged in" if battery.power_plugged else "battery"

    #-----------------------------------------------------------------
    @staticmethod
    def setPiLED(value):
        LEDPath="/sys/class/leds/led0/brightness"

        if Tools.exists(LEDPath):
            with open(LEDPath,"w") as file:
                file.write(str(value))

    #-----------------------------------------------------------------
    @staticmethod
    def piLEDOn():
        Tools.setPiLED(1)

    #-----------------------------------------------------------------
    @staticmethod
    def piLEDOff():
        Tools.setPiLED(0)

    #-----------------------------------------------------------------
    @staticmethod
    def freeDiskSpace(directory):
        #total, used, free
        _,_,free=shutil.disk_usage(directory)

        return free/float(2**20)

    #-----------------------------------------------------------------
    @staticmethod
    def totalDiskSpace(directory):
        total,_,_=shutil.disk_usage(directory)

        return total/float(2**20)

    #-----------------------------------------------------------------
    @staticmethod
    def percFreeDiskSpace(directory):
        return round(100*(Tools.freeDiskSpace(directory)/Tools.totalDiskSpace(directory)),2)

    #-----------------------------------------------------------------
    @staticmethod
    def EBFreeDiskSpace():
        return Tools.freeDiskSpace(Tools.findHomeDir())

    #-----------------------------------------------------------------
    @staticmethod
    def EBTotalDiskSpace():
        return Tools.totalDiskSpace(Tools.findHomeDir())

    #-----------------------------------------------------------------
    @staticmethod
    def EBPercFreeDiskSpace():
        return Tools.percFreeDiskSpace(Tools.findHomeDir())

    #-----------------------------------------------------------------
    @staticmethod
    def workingFreeDiskSpace():
        return Tools.freeDiskSpace(Tools.getWorkingDir())

    #-----------------------------------------------------------------
    @staticmethod
    def workingTotalDiskSpace():
        return Tools.totalDiskSpace(Tools.getWorkingDir())

    #-----------------------------------------------------------------
    @staticmethod
    def workingPercFreeDiskSpace():
        return Tools.percFreeDiskSpace(Tools.getWorkingDir())

