'''
Created on May 16, 2025

@author: lmgar
'''
import sys
import threading

sys.path.append("/mnt/c/Users/lmgar/OneDrive/Documents/My Projects/ExperienceBuffers/python source/")
from experiencebuffers.util.Tools import Tools
from experiencebuffers.util.TimeSpan import TimeSpan


class TimeLock:
#===================================================================================================
# The TimeLock class uses clipLock, deleteLock, clipUnlock, and deleteUnlock to protect blocks of code
# and spans of time from from add or delete operations from interfering with each other. For example.
# it is often used to prevent buffer files from being deleted if they are being gathered for
# inclusion in an archiving request. Likewise, files over a given span of time can be locked out
# of being selected if they are already locked for deletion. The time objects use the TimeSpan class.
#===================================================================================================

    def __init__(self):
        self.deleteSync=list()
        self.deleteThreadLock=threading.Lock()

        self.clipSync=list()
        self.clipThreadLock=threading.Lock()

    #-----------------------------------------------------------------
    def clipLock(self,t1,t2=None,wait=True):
        count=0
        if t2 is None:
            t2=t1

        while (waiting:=self.checkLocks(self.deleteSync,t1,t2)) and wait:
            Tools.sleep(10)

        if not waiting:
            with self.clipThreadLock:
                if ts:=self.find(self.clipSync,t1,t2):
                    ts.increment()
                else:
                    self.clipSync.append(TimeSpan(t1,t2))
        else:
            count=self.numberOfLocks(self.deleteSync,t1,t2)

        return count

    #-----------------------------------------------------------------
    def clipUnlock(self,t1,t2=None):
        count=0
        if t2 is None:
            t2=t1

        with self.clipThreadLock:
            if ts:=self.find(self.clipSync,t1,t2):
                ts.decrement()
                if ts.getCount()==0:
                    self.clipSync.remove(ts)

                count=ts.getCount()

        return count

    #-----------------------------------------------------------------
    def deleteLock(self,t1,t2=None,wait=True):
        count=0
        if t2 is None:
            t2=t1

        while (waiting:=self.checkLocks(self.clipSync,t1,t2)) and wait:
            Tools.sleep(10)

        if not waiting:
            with self.deleteThreadLock:
                if ts:=self.find(self.deleteSync,t1,t2):
                    ts.increment()
                else:
                    self.deleteSync.append(TimeSpan(t1,t2))
        else:
            count=self.numberOfLocks(self.clipSync,t1,t2)

        return count

    #-----------------------------------------------------------------
    def deleteUnlock(self,t1,t2=None):
        count=0
        if t2 is None:
            t2=t1

        with self.deleteThreadLock:
            if ts:=self.find(self.deleteSync,t1,t2):
                ts.decrement()
                if ts.getCount()==0:
                    self.deleteSync.remove(ts)

                count=ts.getCount()

        return count

    #-----------------------------------------------------------------
    def numberOfLocks(self,lockList,t1,t2):
        return sum(1 for ts in lockList if ts.within(t1,t2))

    #-----------------------------------------------------------------
    def checkLocks(self,timeSpans,t1,t2):
        result=False

        for ts in timeSpans:
            if ts.within(t1,t2):
                result=True
                break

        return result

    #-----------------------------------------------------------------
    def find(self,timeSpans,t1,t2):
        result=None

        for ts in timeSpans:
            if ts.match(t1,t2):
                result=ts
                break

        return result

    #-----------------------------------------------------------------
    def clearAll(self):
        with self.deleteThreadLock,self.clipThreadLock:
            for ts in self.deleteSync:
                ts.clear()
            for ts in self.clipSync:
                ts.clear()
