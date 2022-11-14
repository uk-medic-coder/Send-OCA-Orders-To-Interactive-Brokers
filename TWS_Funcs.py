import ibapi
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import *
from ibapi.ticktype import TickTypeEnum

import time
from datetime import datetime, timedelta
import sys
import os
import threading
from collections import deque

import TWS_Includes_Blank as TWSInclude

# ==============================================================================================
# ==============================================================================================
class IBApiOverride(EWrapper,EClient):

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self):
        
        TWSInclude.CurrentOrderID = -999                          # set default
        EClient.__init__(self, self)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # standard error override
    def error(self, reqId, errorCode, errorString):
        
        a = ""
        if errorCode == 202:
            a = "Order cancelled. "
            
        LogAddMessage("API Message: "+a+"ReqID="+str(reqId)+", code="+str(errorCode)+", "+errorString, 0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Receives next valid order id. Will be invoked automatically upon successfull API client connection, or after call to EClient::reqIds 
    # Important: the next valid order ID is only valid at the time it is received. 
    
    def nextValidId(self, orderId):
        
        TWSInclude.CurrentOrderID = orderId             
        LogAddMessage("New orderID to use recieved = "+str(orderId), 1)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Create a stock contract
    def GetSMARTStockContract(self, ticker, currency):
        
        contract = Contract()
        contract.symbol = ticker.strip()
        contract.secType = "STK"
        contract.exchange = "SMART"        
        contract.currency = currency
        
        return contract
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def tickPrice(self, symbolListRefNumber, tickType, price, attrib):
        
        try:
            tt = TickTypeEnum.to_str(tickType)
            
            o = TWSInclude.GlobalSymList[symbolListRefNumber]
    
            if tt=="LAST" or tt=="CLOSE":
                o.c = price
            if tt=="LOW":
                o.l = price
            if tt=="HIGH":
                o.h = price
            if tt=="OPEN":
                o.o = price
            if tt=="BID":
                o.bid = price
            if tt=="ASK":
                o.ask = price                
                        
            # This now sets a flag in the object --- coz a class method in doMainApp() will be listening as a thread for a signal
            o.PriceDataNowRecieved = 1
    
        except Exception as e:
            LogAddMessage("ERROR: IBApiOverride(tickPrice) error = "+str(e), 0)
            ancExitTWS()
            
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def historicalData(self, symbolListRefNumber, bar):
        
        try:
            o = TWSInclude.GlobalSymList[symbolListRefNumber]
            
            o.o = bar.open
            o.h = bar.high
            o.l = bar.low
            o.c = bar.close
            o.v = bar.volume
            
            # This now sets a flag in the object --- coz a class method in doMainApp() will be listening as a thread for a signal
            o.PriceDataNowRecieved = 1

        except Exception as e:
            LogAddMessage("ERROR: IBApiOverride(historicalData) error = "+str(e), 0)
            ancExitTWS()
            
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def CreateBracketOrder(self, obj, actionaa, ordertypeIN, limitPriceTMP, currprice, accounttouse, tif, oidfn):

        # https://interactivebrokers.github.io/tws-api/classIBApi_1_1Order.html#ac2926db25ae147030a1cf519c07d86a6
        
        #tid: Valid orderID
        #action: BUY or SELL
        #ordertypeIN: MKT or LMT 
        #quanity: # of shares
        #limitPriceTMP: if LMT, put limit price here - else == 0
        #tif = GTC or DAY

        # btp / bsl --- these are in % of currprice (actual value calculated here). If zero, they are ommitted from bracket order

        # One key thing to keep in mind is to handle the order transmission accurately. Since a Bracket consists of three orders, there is always a risk that at least one of the orders gets filled before the entire bracket is sent. To avoid it, make use of the IBApi.Order.Transmit flag. When this flag is set to 'false', the TWS will receive the order but it will not send (transmit) it to the servers. In the example below, the first (parent) and second (takeProfit) orders will be send to the TWS but not transmitted to the servers. When the last child order (stopLoss) is sent however and given that its IBApi.Order.Transmit flag is set to true, the TWS will interpret this as a signal to transmit not only its parent order but also the rest of siblings, removing the risks of an accidental execution.

        tid = obj.orderID
        quantity = obj.numshares
        btp = obj.tpPercent
        bsl = obj.slPercent        
        action = actionaa.upper()               # just in-case!
        
        if ordertypeIN=="MKT":
            limitPrice = 0
            limitPTx = ""
        else:
            limitPrice = limitPriceTMP
            limitPTx = " (Limit Price="+str(limitPrice)+")"
        
        currentTID = tid
        
        #This will be our main or "parent" order
        parent = Order()
        parent.orderId = currentTID
        parent.action = action
        parent.orderType = ordertypeIN
        parent.totalQuantity = quantity
        parent.lmtPrice = limitPrice
        parent.tif = tif
        #The parent and children orders will need this attribute set to False to prevent accidental executions.
        #The LAST CHILD will have it set to True, 
        parent.transmit = False

        bracketOrder = [parent]
        
        tv = quantity * currprice
        btx = ["Bracket Order Created: "+action+", "+ordertypeIN+limitPTx+", Quantity="+str(quantity)+" (Total order value = "+str(tv)+" of account allowed for this trade of "+str(accounttouse)+"), "+tif+", OrderID = "+str(currentTID)]
        
        tp = sl = 0
        currentTID += 1                 # coz orderID needs to be +1 for brackets below
        
        if btp>0:
            tp = currprice + (currprice*(btp/100))
            takeProfit = Order()
            takeProfit.orderId = currentTID
            takeProfit.action = "SELL" if action == "BUY" else "BUY"
            takeProfit.orderType = "LMT"
            takeProfit.totalQuantity = quantity
            takeProfit.lmtPrice = round(tp, 2)
            takeProfit.parentId = tid
            takeProfit.tif = tif
            takeProfit.transmit = False
            bracketOrder.append(takeProfit)
            btx.append("TP of "+str(btp)+"% at "+str(takeProfit.lmtPrice))
            currentTID += 1                 # ensures next TID - used below or out of this func - is sequential

        if bsl>0:
            sl = currprice - (currprice*(bsl/100))            
            stopLoss = Order()
            stopLoss.orderId = currentTID
            stopLoss.action = "SELL" if action == "BUY" else "BUY"
            stopLoss.orderType = "STP"
            stopLoss.auxPrice = round(sl, 2)
            stopLoss.tif = tif
            stopLoss.totalQuantity = quantity
            stopLoss.parentId = tid
            stopLoss.transmit = True 
            bracketOrder.append(stopLoss)
            btx.append("SL of "+str(bsl)+"% at "+str(stopLoss.auxPrice))
            currentTID += 1                 # ensures next TID - used below or out of this func - is sequential

        
        # Update TWS.Include.CurrentOrderID to reflect the next OrderID that can be used by other symbols
        # This can be done here because the LOCK IS ON
        TWSInclude.CurrentOrderID = currentTID


        # **** REMEMBER TO REMOVE LOCK WHEN PASS BACK TO CALLING FUNCTION ***
        return tp, sl, btx, bracketOrder

# ==============================================================================================
# ==============================================================================================  
def ExitTWS():

    LogAddMessage("TWS main thread ending. Waiting for all other threads to end...", 1)

    # Terminate all other threads correctly
    TWSInclude.TerminateAppSignal = 1               # tell threads to finish up
    
    time.sleep(2)
    
    # This closes main IB thread - and impt to close opened socket, else have to restart TWS each time
    TWSInclude.IBClass.disconnect()
    
    # need this last one, as CTRL+C uses this also
    sys.exit(0)    

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def IBTWSCTRLCHandler(signum, frame):

    ExitTWS()


# ==============================================================================================  
# MESSAGE HANDLING
# ============================================================================================== 
def LogAddMessage(msg, typ):
    
    # typ:
        # 0 = add to errors list
        # 1 = add to general list
        
    e = datetime.now().strftime("%d/%m/%y - %H:%M:%S")+"  :  "+msg 
    
    if typ==0:
        TWSInclude.ErrorsQueue.append(e)
    
    if typ==1:
        TWSInclude.OtherMessagesQueue.append(e)

# ================================================

def messageLogsWriteOutAndClear():
    
    if TWSInclude.LogOutputFiles > 0:
        file5 = open(TWSInclude.LogOutputFolder + TWSInclude.CombFileName, "a")


    if TWSInclude.ErrorsQueue:
        file1 = open( TWSInclude.LogOutputFolder + TWSInclude.ErrorsFileName, "a")
        while TWSInclude.ErrorsQueue:
            mm = TWSInclude.ErrorsQueue.popleft()+"\n"
            if TWSInclude.LogOutputFiles > 0:
                file5.write(mm)
            if TWSInclude.LogOutputFiles <2:
                file1.write(mm)
            if TWSInclude.LogOutputType==1:
                print(mm)
        file1.close()     
        if TWSInclude.LogOutputFiles ==2:
           os.remove(TWSInclude.LogOutputFolder + TWSInclude.ErrorsFileName)
        
    if TWSInclude.OtherMessagesQueue:
        file1 = open( TWSInclude.LogOutputFolder + TWSInclude.MessagesFileName, "a")
        while TWSInclude.OtherMessagesQueue:
            mm = TWSInclude.OtherMessagesQueue.popleft()+"\n"
            if TWSInclude.LogOutputFiles > 0:
                file5.write(mm)
            if TWSInclude.LogOutputFiles <2:
                file1.write(mm)
            if TWSInclude.LogOutputType==1:
                print(mm)
        file1.close()     
        if TWSInclude.LogOutputFiles ==2:
           os.remove(TWSInclude.LogOutputFolder + TWSInclude.MessagesFileName)

    if TWSInclude.LogOutputFiles > 0:
        file5.close()


    # Now dump trading objects
    
    if TWSInclude.LogsDumpSymObjects==1:
        
        file1 = open(TWSInclude.LogOutputFolder + "SymObjectsStatus", "w")
        
        file1.write("===========================\nObjects as of: "+datetime.now().strftime("%d/%m/%y - %H:%M:%S")+"\n===========================\n")

        for j in TWSInclude.GlobalSymList:
            file1.write(j.outputstatus()+"--------------------------------------------------------\n\n")
        
        file1.close()
        
# ========================================================

def Thread_WatchForMessages():
    
    while True:

        if TWSInclude.TerminateAppSignal == 0:
            
            if datetime.now() > TWSInclude.nextTimeCheckInt:
                messageLogsWriteOutAndClear()        
                TWSInclude.nextTimeCheckInt = datetime.now() + timedelta(seconds=TWSInclude.LogsCheckFreq)        

        else:
            LogAddMessage("'Thread_WatchForMessages()' Thread Ending", 1)
            messageLogsWriteOutAndClear()
            time.sleep(TWSInclude.LogsCheckFreq*2)
            messageLogsWriteOutAndClear()
            break
        
# ========================================================

def MessageQueueStart():
    
    # Init all message checking and logging
    
    if os.path.exists(TWSInclude.LogOutputFolder + TWSInclude.ErrorsFileName):
        os.remove(TWSInclude.LogOutputFolder + TWSInclude.ErrorsFileName)       
       
    if os.path.exists(TWSInclude.LogOutputFolder + TWSInclude.MessagesFileName):
        os.remove(TWSInclude.LogOutputFolder + TWSInclude.MessagesFileName)       

    if os.path.exists(TWSInclude.LogOutputFolder + TWSInclude.CombFileName):
        os.remove(TWSInclude.LogOutputFolder + TWSInclude.CombFileName)       

    TWSInclude.ErrorsQueue = deque()
    TWSInclude.OtherMessagesQueue = deque()
    
    TWSInclude.nextTimeCheckInt = datetime.now() + timedelta(seconds=TWSInclude.LogsCheckFreq)        

    th = threading.Thread(target=Thread_WatchForMessages)
    TWSInclude.ThreadList.append(th)
    th.start()
    
    
# ==============================================================================================

def CreateDictForGlobalSymlists(ss, TotalAccountToDivideUp, tp, sl, flag):
    
    '''
    INPUTS:
        ss = csv string of stocks
        tp, sl = % values - these apply to all the stocks and are not individual
        TotalAccountToDivideUp = total account to use eg- $50K between 10 stocks = $5K per stock
        flag: 1 = symbols to upper 1st
    
    OUTPUTS:   "key" : [values...]
        {"AAPL" : [tp,sl,$account to use for aapl only],
         etc....}
    '''
    
    if flag==0:
        x = ss.split(",")
    else:
        x = ss.upper().split(",")

    dic = {}
    cnt = 0
    err = 0
    
    for s in x:
        xx = s.strip()
        if xx!="":
            if xx in dic.keys():
                print("\n\nERROR: "+xx+" symbol has been used twice in stocks list!")
                err = 1
            else:
                dic[xx] = [tp, sl, 0]                   # 0 is placeholder for accountsize
                cnt += 1

    if cnt == 0:
        err = 1
    else:
        r = TotalAccountToDivideUp / cnt
        for s in dic.keys():
            dic[s][2] = r

    return err, dic

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def transformDictToGlobalSymbolList(dic):
    
    # All upper() transformations and checks for duplicates need to be done prior to this
    
    TWSInclude.GlobalSymList = []
    cnt = 0
    
    for s in dic.keys():
        o = TWSInclude.IndividualSymbol()
        o.symname = s
        o.symListRefNumber = cnt
        o.tpPercent = dic[s][0]
        o.slPercent = dic[s][1]
        o.accountSizeThisSymOnly = dic[s][2]
                
        TWSInclude.GlobalSymList.append(o)
        TWSInclude.GlobalSymListCount = cnt 
            
        cnt+=1
            
# ==============================================================================================            
# ==============================================================================================            
def requestCurrentOrderID():

        requestFirstIDcount = 0
        
        while TWSInclude.CurrentOrderID == -999:

            if requestFirstIDcount > 10:
                
                LogAddMessage("ERROR: Too many attempts to request an ID. Aborting.", 0)
                ancExitTWS()
            
            else:
                ClearLockForCurrentOrderID()
                LogAddMessage("Requesting an initial TWS OrderID...", 1)
                TWSInclude.IBClass.reqIds(-1)                      # calls IB > nextValidId()
                requestFirstIDcount += 1             
                time.sleep(2)       
        
# ======================================================
def ClearLockForCurrentOrderID():
    
    TWSInclude.CurrentOrderIDLock=0
    TWSInclude.CurrentOrderIDLockObject = None

# ======================================================
def CurrentOrderIDLockError(symbolObject, tx):
    
        LogAddMessage("ERROR: CurrentOrderID is locked, cant "+tx+" for order for "+symbolObject.symname+", (locked CurrentOrderID value = "+str(TWSInclude.CurrentOrderID)+", locked by "+TWSInclude.CurrentOrderIDLockObject.symname+", symListRefNumber = "+str(TWSInclude.CurrentOrderIDLockObject.symListRefNumber)+")", 0)

# ======================================================
def tryToLockCurrentOrderID(symbolObject):
    
    if TWSInclude.CurrentOrderIDLock==0:
        
        TWSInclude.CurrentOrderIDLockObject = symbolObject
        TWSInclude.CurrentOrderIDLock = 1
        e = 0
        
    else:
        CurrentOrderIDLockError(symbolObject, "lock it")
        e = 1
        
    return e
