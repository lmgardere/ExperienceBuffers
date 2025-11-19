'''
Created on May 16, 2025

@author: lmgar
'''


class TimeSpan:

    def __init__(self,start,end):
        self.start=start
        self.end=end
        self.count=1
        self.relatedObject=None

    #-----------------------------------------------------------------
    def increment(self):
        self.count+=1
        return self.count

    #-----------------------------------------------------------------
    def decrement(self):
        self.count=max(0,self.count-1)
        return self.count

    #-----------------------------------------------------------------
    def getStart(self):
        return self.start

    #-----------------------------------------------------------------
    def getEnd(self):
        return self.end

    #-----------------------------------------------------------------
    def getCount(self):
        return self.count

    #-----------------------------------------------------------------
    def getRelatedObject(self):
        return self.relatedObject

    #-----------------------------------------------------------------
    def setRelatedObject(self,ro):
        self.relatedObject=ro

    #-----------------------------------------------------------------
    def clear(self):
        self.count=0

    #-----------------------------------------------------------------
    def match(self,t1,t2):
        return self.getStart()==t1 and self.getEnd()==t2

    #-----------------------------------------------------------------
    def within(self,t1,t2):
        return self.getStart()<=t1<=self.getEnd() or self.getStart()<=t2<=self.getEnd() or t1<=self.getStart()<=t2 or t1<=self.getEnd()<=t2
