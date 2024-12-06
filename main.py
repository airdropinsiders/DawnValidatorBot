import requests
import json
import logging
import time
import asyncio
import telegram
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import colorlog
from colorama import init, Fore, Back, Style
from fake_useragent import UserAgent
import urllib3
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from asyncio import Queue
import itertools
import argparse
import multiprocessing
from multiprocessing import Pool, Manager 

banner = """
==================================================================
 █████╗ ██╗██████╗ ██████╗ ██████╗  ██████╗ ██████╗ 
██╔══██╗██║██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██╔══██╗
███████║██║██████╔╝██║  ██║██████╔╝██║   ██║██████╔╝
██╔══██║██║██╔══██╗██║  ██║██╔══██╗██║   ██║██╔═══╝ 
██║  ██║██║██║  ██║██████╔╝██║  ██║╚██████╔╝██║     
╚═╝  ╚═╝╚═╝╚═╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝     
                                                    
██╗███╗   ██╗███████╗██╗██████╗ ███████╗██████╗     
██║████╗  ██║██╔════╝██║██╔══██╗██╔════╝██╔══██╗    
██║██╔██╗ ██║███████╗██║██║  ██║█████╗  ██████╔╝    
██║██║╚██╗██║╚════██║██║██║  ██║██╔══╝  ██╔══██╗    
██║██║ ╚████║███████║██║██████╔╝███████╗██║  ██║    
╚═╝╚═╝  ╚═══╝╚══════╝╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝    

Join our Telegram channel for the latest updates: t.me/airdropinsiderid

DAWN AUTO BOT - Airdrop Insider
==================================================================
"""
print(banner)
time.sleep(1)

CONFIG_FILE = "config.json"
PROXY_FILE = "proxies.txt"

parser = argparse.ArgumentParser(description='DAWN AUTO BOT - Airdrop Insider')
parser.add_argument('-W', '-w', '--worker', type=int, default=3, help='Number of worker threads')
args = parser.parse_args()

# Setup logging with color
log_colors = {
    'DEBUG': 'cyan',
    'INFO': 'white',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'SUCCESS': 'green'
}

formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    log_colors=log_colors
)

handler = logging.StreamHandler()
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Adding a custom SUCCESS level between INFO and WARNING
SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")

def log_success(message, *args, **kwargs):
    if logger.isEnabledFor(SUCCESS_LEVEL):
        logger._log(SUCCESS_LEVEL, message, args, **kwargs)

logging.success = log_success

def read_config(filename=CONFIG_FILE):
    try:
        with open(filename, 'r') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        logging.error(f"Configuration file '{filename}' not found.")
        return {}
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON format in '{filename}'.")
        return {}

def read_proxies(filename=PROXY_FILE):
    proxies = []
    try:
        with open(filename, 'r') as file:
            for line in file:
                proxy = line.strip()
                if proxy:
                    proxies.append(proxy)
    except FileNotFoundError:
        logging.error(f"Proxy file '{filename}' not found.")
    return proxies

def parse_proxy(proxy):
    """Parse proxy string into format for requests."""
    proxy_url = urlparse(proxy)
    if proxy_url.scheme in ['http', 'https', 'socks5']:
        if proxy_url.username and proxy_url.password:
            return {
                'http': f"{proxy_url.scheme}://{proxy_url.username}:{proxy_url.password}@{proxy_url.hostname}:{proxy_url.port}",
                'https': f"{proxy_url.scheme}://{proxy_url.username}:{proxy_url.password}@{proxy_url.hostname}:{proxy_url.port}",
            }
        else:
            return {
                'http': f"{proxy_url.scheme}://{proxy_url.hostname}:{proxy_url.port}",
                'https': f"{proxy_url.scheme}://{proxy_url.hostname}:{proxy_url.port}",
            }
    return {}

def check_proxy(proxy):
    """Check if the proxy is active without logging."""
    proxies = parse_proxy(proxy)
    test_url = "http://httpbin.org/ip"
    try:
        response = requests.get(test_url, proxies=proxies, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def get_active_proxies():
    """Check all proxies and return a list of active proxies using multithreading."""
    proxies = read_proxies(PROXY_FILE)
    active_proxies = []

    # Create a ThreadPoolExecutor to run proxy checks concurrently
    with ThreadPoolExecutor(max_workers=200) as executor:  # You can adjust max_workers to control the level of concurrency
        futures = [executor.submit(check_proxy, proxy) for proxy in proxies]
        
        # Collect results as they complete
        for future, proxy in zip(futures, proxies):
            if future.result():
                active_proxies.append(proxy)

    if active_proxies:
        logging.success(f"Found {len(active_proxies)} active proxies.")
        return active_proxies
    else:
        logging.error("No active proxies found.")
        return []

def update_proxies_file(active_proxies):
    """Update proxies.txt file with only active proxies."""
    with open(PROXY_FILE, 'w') as file:
        for proxy in active_proxies:
            file.write(f"{proxy}\n")
    logging.success(f"Updated {PROXY_FILE} with {len(active_proxies)} active proxies.")

def create_session(proxy=None):
    session = requests.Session()
    session.mount('http://', HTTPAdapter(pool_connections=10, pool_maxsize=10))
    session.mount('https://', HTTPAdapter(pool_connections=10, pool_maxsize=10))
    if proxy:
        proxies = parse_proxy(proxy)
        logging.info(f"Using proxy: {proxy}")
        session.proxies.update(proxies)
    return session

config = read_config(CONFIG_FILE)
bot_token = config.get("telegram_bot_token")
chat_id = config.get("telegram_chat_id")
use_proxy = config.get("use_proxy", False)
use_telegram = config.get("use_telegram", False)
poll_interval = config.get("poll_interval", 120)  # Default to 120 seconds

if use_telegram and (not bot_token or not chat_id):
    logging.error("Missing 'bot_token' or 'chat_id' in 'config.json'.")
    exit(1)

bot = telegram.Bot(token=bot_token) if use_telegram else None
keepalive_url = "https://www.aeropres.in/chromeapi/dawn/v1/userreward/keepalive"
get_points_url = "https://www.aeropres.in/api/atom/v1/userreferral/getpoint"
extension_id = "fpdkjdnhkakefebpekbdhillbhonfjjp"
_v = "1.1.1"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ua = UserAgent()

def read_account(filename="config.json"):
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            accounts = data.get("accounts", [])
            return accounts 
    except FileNotFoundError:
        logging.error(f"Config file '{filename}' not found.")
        return []
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON format in '{filename}'.")
        return []

def total_points(headers, session):
    try:
        response = session.get(get_points_url, headers=headers, verify=False)
        response.raise_for_status()

        json_response = response.json()
        if json_response.get("status"):
            reward_point_data = json_response["data"]["rewardPoint"]
            referral_point_data = json_response["data"]["referralPoint"]
            total_points = (
                reward_point_data.get("points", 0) +
                reward_point_data.get("registerpoints", 0) +
                reward_point_data.get("signinpoints", 0) +
                reward_point_data.get("twitter_x_id_points", 0) +
                reward_point_data.get("discordid_points", 0) +
                reward_point_data.get("telegramid_points", 0) +
                reward_point_data.get("bonus_points", 0) +
                referral_point_data.get("commission", 0)
            )
            return total_points
        else:
            logging.warning(f"Warning: {json_response.get('message', 'Unknown error when fetching points')}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching points: {e}")
    return 0

def keep_alive(headers, email, session):
    keepalive_payload = {
        "username": email,
        "extensionid": extension_id,
        "numberoftabs": 0,
        "_v": _v
    }

    headers["User-Agent"] = ua.random

    try:
        response = session.post(keepalive_url, headers=headers, json=keepalive_payload, verify=False)
        response.raise_for_status()

        json_response = response.json()
        if 'message' in json_response:
            return True, json_response['message']
        else:
            return False, "Message not found in response"
    except requests.exceptions.RequestException as e:
        return False, str(e)

# Queue for Telegram messages
message_queue = Queue()

async def telegram_worker():
    while True:
        message = await message_queue.get()
        await telegram_message(message)
        message_queue.task_done()

async def queue_telegram_message(message):
    await message_queue.put(message)

async def telegram_message(message):
    if use_telegram:
        try:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
            await asyncio.sleep(1)  # Delay of 1 second after sending the message
        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")

def process_account(account, proxy_list, active_proxies):
    email = account["email"]
    token = account["token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": ua.random
    }

    session = None  # Inisialisasi session di luar loop
    
    try:
        for proxy in proxy_list:
            if session:
                session.close()  # Tutup session sebelumnya jika ada
            session = create_session(proxy)

            success, status_message = keep_alive(headers, email, session)

            if success:
                points = total_points(headers, session)
                message = (
                    "✅ *🌟 Success Notification 🌟* ✅\n\n"
                    f"👤 *Account:* {email}\n\n"
                    f"💰 *Points Earned:* {points}\n\n"
                    f"📢 *Message:* {status_message}\n\n"
                    f"🛠️ *Proxy Used:* {proxy}\n\n"
                    "🤖 *Bot made by https://t.me/AirdropInsiderID*"
                )
                logging.success(f"Success keep alive for {email} with proxy {proxy}. Reason: {status_message}")
                return email, True, message
            else:
                logging.error(f"Failed keep alive for {email} with proxy {proxy}. Reason: {status_message}")
        
        # Jika semua proxy gagal
        message = (
            "⚠️ *Failure Notification* ⚠️\n\n"
            f"👤 *Account:* {email}\n\n"
            "❌ *Status:* Keep Alive Failed for All Proxies\n\n"
            "⚙️ *Action Required:* Please check proxy list or account status.\n\n"
            "🤖 *Bot made by https://t.me/AirdropInsiderID*"
        )
        return email, False, message
    finally:
        if session:
            session.close()  # Pastikan session ditutup

async def main():
    accounts = read_account()
    active_proxies = get_active_proxies()
    update_proxies_file(active_proxies)

    # Start the Telegram message worker
    telegram_task = asyncio.create_task(telegram_worker())

    while True:
        pool = None
        try:
            # Buat pool untuk memproses akun secara parallel
            pool = Pool(processes=args.worker)
            
            # Siapkan parameter untuk setiap akun
            process_params = [(account, active_proxies, active_proxies) for account in accounts]
            
            # Proses akun secara parallel
            results = pool.starmap(process_account, process_params)

            # Kirim pesan Telegram untuk setiap hasil
            for email, success, message in results:
                await queue_telegram_message(message)
                logging.info(f"Account {email} completed with status: {'success' if success else 'failed'}")

            logging.info(f"All accounts processed. Waiting {poll_interval} seconds before next cycle.")
            await asyncio.sleep(poll_interval)

        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            await asyncio.sleep(10)
        finally:
            if pool:
                pool.close()
                pool.join()

if __name__ == "__main__":
    try:
        multiprocessing.freeze_support()
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Script stopped by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        logging.info("Cleaning up resources...")
