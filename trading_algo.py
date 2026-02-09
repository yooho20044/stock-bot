import pandas as pd
from datetime import datetime, timedelta
import logging # For logging
from pykis.api.stock.daily_chart import KisDomesticDailyChart
from pykis.scope.stock import KisStockScope # Import manually to bypass domain issues
from notifier import send_slack_message # Import Slack notifier

logger = logging.getLogger(__name__)

# This will be passed from main.py
# from pykis.kis import PyKis

def fetch_historical_data(api, symbol: str, start_date: str, end_date: str):
    """
    Fetches historical daily price data for a given symbol from the Kis API.

    Args:
        api: An initialized PyKis API object.
        symbol (str): The stock symbol (e.g., "005930").
        start_date (str): Start date in "YYYYMMDD" format.
        end_date (str): End date in "YYYYMMDD" format.

    Returns:
        pd.DataFrame: DataFrame containing historical prices, or None if fetching fails.
    """
    try:
        # TR_ID for historical daily prices
        # "국내주식시세 -> 주식일별가[v1_국내주식-002]" (FHKST01010200)
        # Path: /uapi/domestic-stock/v1/quotations/daily-price

        response = api.fetch(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            api="FHKST03010100", # TR_ID for domestic stock daily chart
            params={
                "FID_COND_MRKT_DIV_CODE": "J", # Condition market division code (e.g., J for stock)
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": end_date,
                "FID_PERIOD_DIV_CODE": "D", # D: 일, W: 주, M: 월
                "FID_ORG_ADJ_PRC": "1" # 0: 수정주가 미반영, 1: 수정주가 반영
            },
            domain="virtual",
            response_type=KisDomesticDailyChart(symbol=symbol)
        )

        if response and response.bars and len(response.bars) > 0:
            data = []
            for bar in response.bars:
                data.append({
                    '날짜': bar.time.strftime("%Y%m%d"),
                    '종가': bar.close,
                    '고가': bar.high,
                    '저가': bar.low
                })
            df = pd.DataFrame(data)
            df['날짜'] = pd.to_datetime(df['날짜'])
            df[['종가', '고가', '저가']] = df[['종가', '고가', '저가']].apply(pd.to_numeric)
            df = df.sort_values(by='날짜').set_index('날짜')
            return df[['종가', '고가', '저가']]
        else:
            error_msg = f"❌ *Data Fetch Failed* for {symbol}: No historical data found."
            logger.warning(error_msg)
            send_slack_message(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        if "Data Fetch Failed" not in str(e):
            error_msg = f"❌ *Data Fetch Failed* for {symbol}: {e}"
            logger.error(error_msg)
            send_slack_message(error_msg)
        raise e

def calculate_moving_averages(df: pd.DataFrame, short_window: int = 5, long_window: int = 20):
    """
    Calculates short-term and long-term moving averages.

    Args:
        df (pd.DataFrame): DataFrame with a '종가' (closing price) column.
        short_window (int): Window size for the short-term moving average.
        long_window (int): Window size for the long-term moving average.

    Returns:
        pd.DataFrame: DataFrame with 'SMA' and 'LMA' columns.
    """
    if df is None or df.empty:
        return None

    df['SMA'] = df['종가'].rolling(window=short_window).mean()
    df['LMA'] = df['종가'].rolling(window=long_window).mean()
    return df

def generate_buy_sell_signal(df: pd.DataFrame):
    """
    Generates buy and sell signals based on moving average crossover.

    Args:
        df (pd.DataFrame): DataFrame with 'SMA' and 'LMA' columns.

    Returns:
        pd.DataFrame: DataFrame with 'Signal' (0: hold, 1: buy, -1: sell) and 'Position' columns.
    """
    if df is None or df.empty:
        return None

    df['Signal'] = 0
    df['Position'] = 0

    # Generate signals
    # Buy signal: When SMA crosses above LMA AND RSI is not overbought (e.g., < 70)
    df.loc[(df['SMA'] > df['LMA']) & (df['RSI'] < 70), 'Signal'] = 1

    # Sell signal: When SMA crosses below LMA AND RSI is not oversold (e.g., > 30)
    df.loc[(df['SMA'] < df['LMA']) & (df['RSI'] > 30), 'Signal'] = -1

    # Determine position
    # Iterate to avoid look-ahead bias and simulate real-time trading
    # Using .at to avoid ChainedAssignmentError
    for i in range(1, len(df)):
        if df['Signal'].iloc[i] == 1: # Buy signal
            df.at[df.index[i], 'Position'] = 1
        elif df['Signal'].iloc[i] == -1: # Sell signal
            df.at[df.index[i], 'Position'] = 0
        else:
            df.at[df.index[i], 'Position'] = df['Position'].iloc[i-1] # Hold position

    return df

def calculate_rsi(df: pd.DataFrame, window: int = 14):
    """
    Calculates the Relative Strength Index (RSI).

    Args:
        df (pd.DataFrame): DataFrame with a '종가' (closing price) column.
        window (int): The period for RSI calculation.

    Returns:
        pd.DataFrame: DataFrame with an 'RSI' column.
    """
    if df is None or df.empty:
        return None

    delta = df['종가'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()

    # Calculate Relative Strength (RS)
    # Handle division by zero: if avg_loss is 0, RS is effectively infinite.
    # If both avg_gain and avg_loss are 0, RS is NaN.
    rs = avg_gain / avg_loss
    
    # Calculate RSI
    df['RSI'] = 100 - (100 / (1 + rs))

    # Fill NaN values (e.g., when initial periods don't have enough data or avg_loss is 0)
    # If avg_loss is 0 and avg_gain > 0, RSI should be 100.
    # If avg_gain is 0 and avg_loss > 0, RSI should be 0.
    # If both are 0, RSI is 50 (neutral).
    df['RSI'] = df['RSI'].fillna(0) # Default to 0, then handle specific cases
    df.loc[avg_loss == 0, 'RSI'] = 100
    df.loc[(avg_gain == 0) & (avg_loss == 0), 'RSI'] = 50 # When both are zero, it's neutral

    return df

def calculate_atr(df: pd.DataFrame, window: int = 14):
    """
    Calculates the Average True Range (ATR).
    """
    if df is None or df.empty:
        return None

    high = df['고가']
    low = df['저가']
    close = df['종가']

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=window).mean()
    
    return df

def get_balance(api):
    """
    Fetches the current cash balance (orderable cash).
    """
    try:
        # Get account object
        acc = api.account()
        # Using KisStockScope to get account balance info
        # "국내주식주문 -> 주식잔고조회" (VTTC8434R for virtual, TTTC8434R for real)
        response = api.fetch(
            "/uapi/domestic-stock/v1/trading/inquire-psbl-order",
            api="VTTC8434R",
            params={
                "CANO": acc.account_number.number,
                "ACNT_PRDT_CD": acc.account_number.code,
                "PDNO": "", # Empty for all
                "ORD_UNPR": "0", # 0 for market price
                "ORD_DVSN": "01", # 01: Market price
                "CMA_EVLU_AMT_ICLD_YN": "Y",
                "OVRS_ICLD_YN": "N"
            },
            domain="virtual"
        )
        if response and 'output' in response:
            return float(response['output']['nrcv_buy_amt']) # nrcv_buy_amt: 미수없는 매수 가능 금액
        return 0.0
    except Exception as e:
        logger.error(f"Failed to fetch balance: {e}")
        return 0.0

def calculate_position_size(strategy: str, balance: float, current_price: float, **kwargs):
    """
    Calculates the order quantity based on the chosen strategy.
    
    Strategies:
    - 'fixed': Fixed fractional (e.g., 10% of balance)
    - 'volatility': Volatility sizing (ATR based)
    - 'kelly': Half-Kelly formula
    """
    try:
        rsi = kwargs.get('rsi', 50)
        
        if strategy == 'fixed':
            ratio = kwargs.get('ratio', 0.1) # Default 10%
            invest_amount = balance * ratio
            qty = int(invest_amount / current_price)
        
        elif strategy == 'volatility':
            atr = kwargs.get('atr')
            risk_amount = kwargs.get('risk_amount', balance * 0.01) # Default 1% risk of total balance
            if atr and atr > 0:
                qty = int(risk_amount / atr)
            else:
                qty = 0
                
        elif strategy == 'kelly':
            win_rate = kwargs.get('win_rate', 0.5)
            profit_loss_ratio = kwargs.get('pl_ratio', 2.0)
            
            f_star = (profit_loss_ratio * win_rate - (1 - win_rate)) / profit_loss_ratio
            f_star = max(0, f_star * 0.5)
            
            invest_amount = balance * f_star
            qty = int(invest_amount / current_price)
        
        else:
            qty = 1 # Fallback
            
        # Split Entry Logic based on RSI strength (for BUY signals)
        # If RSI is lower (more oversold), we can entry with a larger portion
        if rsi < 30:
            split_ratio = 1.0 # 100%
        elif rsi < 45:
            split_ratio = 0.7 # 70%
        elif rsi < 60:
            split_ratio = 0.4 # 40%
        else:
            split_ratio = 0.2 # 20%
            
        final_qty = int(qty * split_ratio)
            
        return max(0, final_qty)
    except Exception as e:
        logger.error(f"Error calculating position size: {e}")
        return 0

def execute_trade(api, stock_code: str, signal: int, current_price: float, order_qty: int = 1):
    """
    Executes a buy or sell trade based on the generated signal and calculated quantity.

    Args:
        api: An initialized PyKis API object.
        stock_code (str): The stock symbol (e.g., "005930").
        signal (int): 1 for buy, -1 for sell.
        current_price (float): The current price of the stock.
        order_qty (int): Quantity to trade.
    """
    try:
        # Instantiate KisStockScope manually
        stock_object = KisStockScope(kis=api, symbol=stock_code, market='KRX', account=api.primary)

        if signal == 1: # Buy signal
            if order_qty <= 0:
                logger.info(f"Calculated BUY quantity is {order_qty}. Skipping order.")
                return None
                
            logger.info(f"Attempting to BUY {order_qty} shares of {stock_code} at market price...")
            order_result = stock_object.buy(qty=order_qty, price=None, condition=None, execution=None)
            logger.info(f"Buy order placed for {stock_code}: {order_result}")
            return {"time": datetime.now().strftime("%H:%M:%S"), "type": "BUY", "symbol": stock_code, "qty": order_qty, "price": current_price, "status": "Success"}

        elif signal == -1: # Sell signal
            current_holding_qty = stock_object.quantity.as_int()
            
            # If order_qty is not specified or 0, sell all
            if order_qty <= 0:
                order_qty = current_holding_qty

            if current_holding_qty > 0:
                actual_sell_qty = min(current_holding_qty, order_qty)
                logger.info(f"Attempting to SELL {actual_sell_qty} shares of {stock_code} at market price...")
                order_result = stock_object.sell(qty=actual_sell_qty, price=None, condition=None, execution=None)
                logger.info(f"Sell order placed for {stock_code}: {order_result}")
                return {"time": datetime.now().strftime("%H:%M:%S"), "type": "SELL", "symbol": stock_code, "qty": actual_sell_qty, "price": current_price, "status": "Success"}
            else:
                msg = f"Cannot SELL {stock_code}: No holdings."
                logger.info(msg)
                return {"time": datetime.now().strftime("%H:%M:%S"), "type": "SELL", "symbol": stock_code, "qty": 0, "price": current_price, "status": "Failed (No Holdings)"}
        
        return None

    except Exception as e:
        error_msg = f"❌ *Trade Execution Failed* for {stock_code}\nReason: {e}"
        logger.error(error_msg)
        send_slack_message(error_msg)
        raise e
