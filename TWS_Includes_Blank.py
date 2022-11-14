
# Blank includes needed by any TWS file - populated by any main apps

# this must match TWS > Edit > GlobalConfig > API > Settings > MasterAPI Client ID field
MASTERCLIENTID = 100 
MASTERPORT = 7497


IBClass = None              # main IB class called in mainApp

doMainAppClass = None       # this is the doMainApp() class needed in main.py, to be referenced from TWSFuncs

CurrentOrderID = -999            # master orderID used by TWS. All orders are after this sequentially. -999 is init value
CurrentOrderIDLock = 0          # set to 1 to lock --- coz many SendOrder processes at once may mess up incrementing of the CurrentOrderID
CurrentOrderIDLockObject = None

# Threads

ThreadList = []                         # list object for holding Threads  -  NOT used as a queue, just a thread tracker list
TerminateAppSignal = 0       # set to 1 on CTRL+C to terminate all threads as well

# ================
# Logs and locations

LogsCheckFreq = 2               # in seconds to check the lists below for new messages
LogsDumpSymObjects = 1              # 0 = off
nextTimeCheckInt = 0           # next time period

LogOutputType = 1               # 0 = just file ; 1 = print as well
LogOutputFiles = 2                 # 0 = errors, msgs separate ; 1 = Also with CombinedFile ; 2 = CombinedFileOnly
LogOutputFolder = "/home/{{USER}}/Desktop/"             # slash on end ; basefolder for all log outputs

ErrorsFileName = "TWS-Errors"
MessagesFileName = "TWS-AppEvents"
CombFileName = "TWS-All-Combined"

ErrorsQueue = None
OtherMessagesQueue = None

SMTradesFilenameAndFolder = ""
OrderIDFilenameAndFolder = ""

# =======================
# Class objects form symbols
# =======================

GlobalSymList = []                 # a global list for holding the below objects
GlobalSymListCount = -1           # zero based, so zero ==1 symbol()

class IndividualSymbol:
    
    def __init__(self):
        
        self.symname = ""
        self.symListRefNumber = -1            # number symbol in list (0-x)
        self.orderID = -1
        self.tpPercent = 0
        self.slPercent = 0
        self.accountSizeThisSymOnly = 0
        self.numshares = -1                            # populated later on
        
        # 0 = just created
        # 1 = requested data (eg- from .processSymbolInTurn() -- reqMktData or reqHistoricalData)
        # 2 = data recieved
        # 3 = bracket order sent
        self.statusA = 0

        self.PriceDataNowRecieved = -1               # a flag (0 or 1) from TWSFuncs.reqData functions to signal to mainApp() thread

        # Price data for certain requests : keep at -1, coz if not populated by TWS they will show as not populated
        
        self.o = -1
        self.h = -1
        self.l = -1
        self.c = -1
        self.v = -1
        self.bid = -1
        self.ask = -1

   # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def outputstatus(self):

        r = "Symname: "+self.symname \
        +"\nStatusA: "+str(self.statusA) \
        +"\nSymListRefNumber: "+str(self.symListRefNumber) \
        +"\nTP%: "+str(self.tpPercent) \
        +"\nSL%: "+str(self.slPercent) \
        +"\nAccountSizeThisSymOnly: "+str(self.accountSizeThisSymOnly) \
        +"\nNumshares: "+str(self.numshares) \
        +"\nOpen: "+str(self.o) \
        +"\nHigh: "+str(self.h) \
        +"\nLow: "+str(self.l) \
        +"\nClose: "+str(self.c) \
        +"\nVolume: "+str(self.v) \
        +"\nBid - Ask: "+str(self.bid)+"  -  "+str(self.ask) \
        +"\nPriceDataNowRecieved: "+str(self.PriceDataNowRecieved) \
        +"\nOrderID: "+str(self.orderID) \
        +"\n"
        
        return r
