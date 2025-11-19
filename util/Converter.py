'''
Created on Nov 12, 2025

@author: Lamar Gardere
'''
import os
import shutil
import subprocess

from experiencebuffers.util.Tools import Tools
from experiencebuffers.util.Standards import Standards


class Converter:

    def __init__(self,path=None):
        self.ffmpegPath=Tools.validateDir(path if path else Standards.BIN_DIR)+"ffmpeg.exe"
        self.verbose=False

    #-----------------------------------------------------------------
    def setVerbose(self,verbose):
        self.verbose=verbose

    #-----------------------------------------------------------------
    def run(self,cmd):
        subprocess.run(cmd,
                       creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS,
                       stdout=None if self.verbose else subprocess.DEVNULL,
                       stderr=None if self.verbose else subprocess.DEVNULL
                       )

    #-----------------------------------------------------------------
    # Uses FFMPEG to merge audio and video tracks.
    # inputFiles: dict of services and associated file names an codecs
    # outputName: name of resulting file after merge operation
    # returns boolean
    def mergeAudioVideo(self,inputFiles,outputFile,vCodec=None,aCodec=None):
        af=inputFiles["audio"]
        vf=inputFiles["video"]
        tmpOutputFile="/temp_".join(outputFile.rsplit("/",1))

        cmd="ffmpeg" if shutil.which("ffmpeg") else f"{self.ffmpegPath}"
        cmd+=f" -y -i {vf} -i {af}"
        cmd+=(f" -c:v {str(vCodec).lower()}") if vCodec else ""
        cmd+=(f" -c:a {str(aCodec).lower()}") if aCodec else ""
        cmd+=f" {tmpOutputFile}"

        self.run(cmd)
        if result:=Tools.exists(tmpOutputFile) and Tools.getFileSize(tmpOutputFile)>0:
            os.replace(tmpOutputFile,outputFile)

        return result

    #-----------------------------------------------------------------
    # Uses FFMPEG to convert media
    # sourceFiles: dict of services and associated file names an codecs
    # outputName: name of resulting file after merge operation
    # returns boolean
    def convert(self,inputFile,outputFile,vCodec=None,aCodec=None):
        tmpOutputFile="/temp_".join(outputFile.rsplit("/",1))

        cmd="ffmpeg" if shutil.which("ffmpeg") else f"{self.ffmpegPath}"
        cmd+=f" -y -i {inputFile}"
        cmd+=(f" -c:v {str(vCodec).lower()}") if vCodec else ""
        cmd+=(f" -c:a {str(aCodec).lower()}") if aCodec else ""
        cmd+=f" {tmpOutputFile}"

        self.run(cmd)
        if result:=Tools.exists(tmpOutputFile) and Tools.getFileSize(tmpOutputFile)>0:
            os.replace(tmpOutputFile,outputFile)

        return result
