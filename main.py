# ========================================================
# ========================================================
# Sends a list of orders to TWS
# ========================================================
# ========================================================
import sys
import os
import shutil
import time
import threading
import signal
import generalFuncs as gnrl
import yfinance as yf

import TWS_Includes_Blank as TWSInclude
import TWS_Funcs as TWSFuncs
from TWS_Funcs import IBApiOverride

import ibapi
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract


# ========================================================
# Some gloabl vars
# ========================================================

accountSize = 0
saveResultsToFile = ""
doneFirstTradeOK = 0
datasource = ""

# ========================================================
# ========================================================

def main():

    global accountSize
    global saveResultsToFile
    global datasource

    os.system('clear')

    print ("\n\033[4mV1 - Send OCA Orders To TWS\033[0m\n")

    stocksString = gnrl.prefilledInput("\nStocks List:  ", "(enter your list of stocks here, comma seperated)")
    #stocksString="AAPL,BIDU"

    sls = float(gnrl.prefilledInput("\ncataSL (%):  ", "40"))                 # % stop loss
    tps = float(gnrl.prefilledInput("\nTP (%):  ", "40"))                        # % take profit

    accountSize = float(gnrl.prefilledInput("\nEnter Total Account Size (x stocks will be divided into this equally):  ", "(enter account size here)"))
    #accountSize = 1000

    # Now create GlobalSymList of objects
        # 1st create a dictionary 
        # 2nd create the objects from this dictionary
    err, d = TWSFuncs.CreateDictForGlobalSymlists(stocksString, accountSize, tps, sls, 1)
    
    if err == 1:
        print("\n\nFATAL ERROR! Problems with stocks list.\n\n")
    else:
        print("\n\nOK, working....\n\n")
    
        TWSFuncs.transformDictToGlobalSymbolList(d)

        # Some precursor things to do
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # This handles the CTRL+C program termination correctly
        # Else ports left open and TWS cant open anymore    

        signal.signal(signal.SIGINT, TWSFuncs.IBTWSCTRLCHandler)

        # This starts the message queues and handling

        TWSFuncs.MessageQueueStart()

        # Call the classes to start the app
    
        TWSInclude.IBClass = TWSFuncs.IBApiOverride()

        TWSInclude.doMainAppClass = doMainApp()


# ========================================================
# ========================================================
class doMainApp():

    def run_loop(self):
        # This creates a loop that listens to the IB server
        TWSInclude.IBClass.run()

    # =============================================================

    def __init__(self):

        global datasource

        TWSInclude.IBClass.connect("127.0.0.1", TWSInclude.MASTERPORT, TWSInclude.MASTERCLIENTID)

        # Start IB app thread
        th1 = threading.Thread(target=self.run_loop, daemon=True)
        TWSInclude.ThreadList.append(th1)
        th1.start()
     
        # give time to startup and avoid IB messages flash up
        time.sleep(3)

        # Now start
        # 1st thing to do - get a valid orderID

        TWSFuncs.requestCurrentOrderID()


        # 2nd is start Thread_ListenForPriceDataRecieved thread()

        th2 = threading.Thread(target=self.Thread_ListenForPriceDataRecieved)
        TWSInclude.ThreadList.append(th2)
        th2.start()


        # =======================================================
        # Request latest price from Yahoo Finance 
        # =======================================================

        for o in TWSInclude.GlobalSymList:

            TWSFuncs.LogAddMessage("Requesting prices from Yahoo for: "+o.symname+"...", 1)

            tick = yf.Ticker(o.symname)
            df = tick.history(period="1mo", interval="1d", prepost=False, auto_adjust=True, back_adjust=False, actions=False)

            if df.empty:
                TWSFuncs.LogAddMessage("***ERROR!*** No data found for: "+o.symname+". Excluded!", 0)
            else:
                # float to get rid of index that came with it    
                o.o = round(float(df[-1:]["Open"]),2)
                o.h = round(float(df[-1:]["High"]),2)
                o.l = round(float(df[-1:]["Low"]),2)
                o.c = round(float(df[-1:]["Close"]),2)
                o.v = round(float(df[-1:]["Volume"]),2)
                
                o.PriceDataNowRecieved = 1
                o.statusA = 1
      
    # =============================================================
    def Thread_ListenForPriceDataRecieved(self):

        # This is a THREAD that runs and listens for price recieved events
        #     
        global accountSize
        global saveResultsToFile
        global doneFirstTradeOK
        global datasource

        while TWSInclude.TerminateAppSignal == 0:           # global thread end signal

            for obj in TWSInclude.GlobalSymList:
                
                # 2nd check, is this the correct cycle for this symbol?
                if obj.statusA==1:

                    if obj.PriceDataNowRecieved == 1:

                        buypricefield = -1
                        price = obj.c

                        # OK to carry on?
                        # if not, wait for correct data type of price to be returned.

                        if price > -1:

                            obj.PriceDataNowRecieved = 0
                            obj.statusA = 2

                            contract = TWSInclude.IBClass.GetSMARTStockContract(obj.symname, "USD")

                            accounttouse = obj.accountSizeThisSymOnly
                            obj.numshares = int(accounttouse / price)

                            
                            # Create Bracket Order
                                # 1st LOCK CurrentOrderID

                            lockerr = TWSFuncs.tryToLockCurrentOrderID(obj)                            

                            if lockerr==0:

                                obj.orderID = TWSInclude.CurrentOrderID

                                # OrderIDs are logged in this function
                                tpval, slval, btx, bracket = TWSInclude.IBClass.CreateBracketOrder(obj, "BUY", "MKT", 0, price, accounttouse, "GTC", TWSInclude.OrderIDFilenameAndFolder)

                                # Clear the LOCK now CurrentOrderID has been updated in CreateBracketOrder()

                                TWSFuncs.ClearLockForCurrentOrderID()
 
                                # Actually send the order

                                for xyz in bracket:
                                    TWSInclude.IBClass.placeOrder(xyz.orderId, contract, xyz)      # NB- xyz.orderId not obj!
           
                                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                                # Live trading app --- would check order has gone through OK
                                # None done here!

                                # Orders can be partially filled. For every fill, you'll get a fillEvent. The filledEvent is when the order is completely filled
                                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

                                obj.statusA = 3

                                # Do the logs

                                if datasource=="2":
                                    ttextx = "Open"
                                else:
                                    ttextx = "Close"

                                tt = obj.symname+", "+ttextx+" Price of "+str(price)

                                # update logs        
                                for x in btx:
                                    tt += ", "+x        
                                TWSFuncs.LogAddMessage(tt, 1)

                            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                            # All done - and can I end the app?

                            fl = 0
                            for x in TWSInclude.GlobalSymList:
                                if x.statusA < 3:
                                    fl = 1

                            if fl==0:
                                # App is now ended, exit properly
                                TWSFuncs.LogAddMessage("ALL SYMBOLS DONE NOW!", 1)                    
                                TWSFuncs.ExitTWS()

        # Thread ended
        TWSFuncs.LogAddMessage("'Thread_ListenForPriceDataRecieved()' Thread Ending", 1)                    


# ========================================================
# ========================================================

if __name__=="__main__":
    main()
