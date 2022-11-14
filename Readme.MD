# Python Send One-Cancels-Another (OCA) Orders to Interactive Brokers

It can be difficult to enter OCA orders into Interactive Broker's TWS software. It is fiddly to use, and if you are entering multiple symbols in, it can be time consuming.

Also - the IB API is difficult to use. It is multithreaded and event driven, making the level of coding standard needed to code an order transmitting app higher.

This handy python script allows you to enter a list of stocks, and enter a stop loss and take profit (% value). The latest price for each stock is downloaded from Yahoo Finance (free site for financial data), and the stop loss/take profit level is calculated automatically from this.

The orders will then be transmitted to TWS live.

They are transmitted as OCA orders - ie. whichever comes first, SL or TP, this then cancels the other order, and exits the position.

eg:

AAPL - current price = $150, stop loss of 50% = $75, take profit of 100% = $300

## Requirements:

pip install yfinance

pip install ibapi


## Usage:

Enter your TWS port number (usually 7497) and Client ID into "TWS_Includes_Blank.py".

Enter a file path to your home folder into "LogOutputFolder" in "TWS_Includes_Blank.py".

Then...

python main.py


TWS will need to be open for orders to be sent live.

*NOTE: Please check the "API" and "Pending" tabs that will open with your orders on TWS to ensure that the orders have been sent through correctly.*

**These scripts send live orders to the stock exchange. If you use these scripts, it is totally at your own risk. I accept NO responsibility for any losses or errors (financial or otherwise) that may occur from the use of these scripts. If you are unsure, do not use them.**
