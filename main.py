
import os
import time # For time.sleep
import logging # For logging
from pykis.kis import PyKis
from dotenv import load_dotenv
from trading_algo import fetch_historical_data, calculate_moving_averages, calculate_rsi, calculate_atr, get_balance, calculate_position_size, generate_buy_sell_signal, execute_trade
from datetime import datetime, date, timedelta
import schedule # For scheduling tasks
from notifier import send_slack_message # Import Slack notifier

# Configure logging
logging.basicConfig(
    level=logging.INFO, # Set to INFO for general messages, DEBUG for more detailed messages
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"), # Log to a file
        logging.StreamHandler() # Also log to console
    ]
)
logger = logging.getLogger(__name__)

# Store trade history for hourly summary
trade_history = []

def send_hourly_summary():
    """
    Sends a summary of all trades executed in the last hour to Slack.
    """
    global trade_history
    if not trade_history:
        # Optional: Send a "No trades this hour" message, or just skip
        # send_slack_message("📊 *Hourly Summary*: No trades executed in the last hour.")
        logger.info("Hourly summary: No trades to report.")
        return

    summary_msg = "📊 *Hourly Trading Summary*\n"
    summary_msg += "--------------------------------------------\n"
    
    for trade in trade_history:
        status_icon = "✅" if trade['status'] == "Success" else "⚠️"
        summary_msg += f"{status_icon} [{trade['time']}] *{trade['type']}* {trade['symbol']} | {trade['qty']} shares @ {trade['price']:,} KRW ({trade['status']})\n"
    
    summary_msg += "--------------------------------------------\n"
    summary_msg += f"Total trades: {len(trade_history)}"

    send_slack_message(summary_msg)
    logger.info("Hourly summary sent to Slack.")
    trade_history = [] # Clear history for the next hour

def is_market_open():
    """
    Checks if the Korean stock market is currently open.
    Mon-Fri, 09:00 - 15:30
    """
    now = datetime.now()
    # Weekday check (0: Monday, 4: Friday)
    if now.weekday() > 4:
        return False
    
    # Time check (09:00 - 15:30)
    current_time = now.strftime("%H%M")
    if "0900" <= current_time <= "1530":
        return True
    
    return False

# Function to read API key and secret from environment variables
def read_api_keys():
    app_key = os.getenv("APP_KEY")
    app_secret = os.getenv("APP_SECRET")
    hts_id = os.getenv("HTS_ID")
    account_number = os.getenv("ACCOUNT_NUMBER")

    if not app_key or not app_secret or not hts_id or not account_number:
        print("Error: APP_KEY, APP_SECRET, HTS_ID, or ACCOUNT_NUMBER environment variables not set.")
        return None, None, None, None
    return app_key, app_secret, hts_id, account_number

# Initialize API outside the scheduled job to avoid re-initializing on each run
load_dotenv() # Load environment variables from .env file
app_key, app_secret, hts_id, account_number = read_api_keys()

if not app_key or not app_secret or not hts_id or not account_number:
    logger.error("Failed to load API keys or HTS ID/Account Number. Exiting.")
    exit(1)

api = PyKis(
    id=hts_id,
    account=account_number,
    appkey=app_key,
    secretkey=app_secret,
    virtual_appkey=app_key,
    virtual_secretkey=app_secret,
    use_websocket=True,
    keep_token=True # Set to True to keep token across runs
)
logger.info("PyKis API initialized successfully.")

def run_trading_strategy(api_client):
    if not is_market_open():
        logger.info(f"Market is closed at {time.ctime()}. Skipping strategy execution.")
        return

    logger.info(f"--- Running trading strategy at {time.ctime()} ---")
    try:
        stock_code = "005930" # Samsung Electronics example stock code
        end_date = date.today().strftime("%Y%m%d")
        start_date = (date.today() - timedelta(days=60)).strftime("%Y%m%d") # Last 60 days for moving averages

        logger.info(f"Fetching historical data for {stock_code} from {start_date} to {end_date}...")
        historical_data = fetch_historical_data(api_client, stock_code, start_date, end_date)

        if historical_data is not None:
            logger.info("Calculating technical indicators and signals...")
            df = calculate_moving_averages(historical_data, short_window=5, long_window=20)
            df = calculate_rsi(df)
            df = calculate_atr(df)
            df_with_signals = generate_buy_sell_signal(df)
            
            if df_with_signals is not None:
                logger.info("\nTrading Signals (last 5 days):")
                logger.info(df_with_signals.tail().to_string())

                latest_signal = df_with_signals['Signal'].iloc[-1]
                latest_atr = df_with_signals['ATR'].iloc[-1]
                latest_rsi = df_with_signals['RSI'].iloc[-1]

                if latest_signal != 0:
                    # Fetch current price
                    current_price_response = api_client.fetch(
                        "/uapi/domestic-stock/v1/quotations/inquire-price",
                        api="FHKST01010100",
                        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code},
                        domain="virtual"
                    )
                    current_stock_price = float(current_price_response.output.stck_prpr) if current_price_response and current_price_response.output else None
                    
                    if current_stock_price:
                        # Fetch balance for position sizing
                        balance = get_balance(api_client)
                        logger.info(f"Current Orderable Balance: {balance:,.0f} KRW")

                        # Strategy selection (can be moved to .env later)
                        # Options: 'fixed', 'volatility', 'kelly'
                        strategy_type = os.getenv("TRADING_STRATEGY", "fixed")
                        
                        calc_qty = calculate_position_size(
                            strategy=strategy_type,
                            balance=balance,
                            current_price=current_stock_price,
                            atr=latest_atr,
                            rsi=latest_rsi,
                            ratio=0.1,      # 10% for fixed
                            risk_amount=balance * 0.01, # 1% risk for volatility
                            win_rate=0.5,   # For Kelly
                            pl_ratio=2.0    # For Kelly
                        )
                        
                        logger.info(f"Calculated Order Quantity ({strategy_type}): {calc_qty}")

                        if latest_signal == 1:
                            logger.info(f"Latest Signal for {stock_code}: BUY")
                            result = execute_trade(api_client, stock_code, latest_signal, current_stock_price, order_qty=calc_qty)
                        elif latest_signal == -1:
                            logger.info(f"Latest Signal for {stock_code}: SELL")
                            # For sell, we can pass 0 to sell all or use calc_qty for partial sell
                            result = execute_trade(api_client, stock_code, latest_signal, current_stock_price, order_qty=0)
                        
                        if result: trade_history.append(result)
                    else:
                        logger.error(f"Could not fetch current price for {stock_code}.")
                else:
                    logger.info(f"Latest Signal for {stock_code}: HOLD")
            else:
                logger.warning("Failed to generate signals.")
        else:
            logger.error("Failed to fetch historical data.")

    except Exception as e:
            error_msg = f"❌ *Critical Error - Stopping Bot*: {e}"
            logger.error(error_msg)
            send_slack_message(error_msg)
            import sys
            sys.exit(1) # Stop the entire program
if __name__ == "__main__":
    # Schedule the trading strategy to run every 1 minute
    schedule.every(1).minutes.do(run_trading_strategy, api)
    # Schedule the hourly summary report
    schedule.every(1).hours.do(send_hourly_summary)

    logger.info("Scheduler started. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1) # Sleep for 1 second to avoid high CPU usage
