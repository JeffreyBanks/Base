import requests
from bs4 import BeautifulSoup
from web3 import Web3
import time
import json
from decimal import Decimal
import os  # Import os module for environment variables

# Configuration
BASE_CHAIN_URL = "https://base.blockpi.network/v1/rpc/7922ee7d50270adaed240e792075235e8034de56"  # Base chain RPC URL
PRIVATE_KEY = os.getenv('PRIVATE_KEY')  # Retrieve private key from environment variable
WALLET_ADDRESS = "0x67BF9289B0519eBF4c5050fa8069aBE8980C74E7"  # Wallet address
SLIPPAGE = 0.2  # 20% slippage
PRICE_INCREASE_THRESHOLD = 1.5  # 150%

# Uniswap V2 Router address and ABI (for Base chain)
UNISWAP_ROUTER_ADDRESS = '0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD'  # Replace with actual router address on Base chain
UNISWAP_ROUTER_ABI = json.loads('''
[
  {
    "constant": false,
    "inputs": [
      {
        "name": "amountOutMin",
        "type": "uint256"
      },
      {
        "name": "path",
        "type": "address[]"
      },
      {
        "name": "to",
        "type": "address"
      },
      {
        "name": "deadline",
        "type": "uint256"
      }
    ],
    "name": "swapExactETHForTokens",
    "outputs": [
      {
        "name": "amounts",
        "type": "uint256[]"
      }
    ],
    "payable": true,
    "stateMutability": "payable",
    "type": "function"
  },
  {
    "constant": false,
    "inputs": [
      {
        "name": "amountIn",
        "type": "uint256"
      },
      {
        "name": "amountOutMin",
        "type": "uint256"
      },
      {
        "name": "path",
        "type": "address[]"
      },
      {
        "name": "to",
        "type": "address"
      },
      {
        "name": "deadline",
        "type": "uint256"
      }
    ],
    "name": "swapExactTokensForETH",
    "outputs": [
      {
        "name": "amounts",
        "type": "uint256[]"
      }
    ],
    "payable": false,
    "stateMutability": "nonpayable",
    "type": "function"
  }
]
''')

# Tokensniffer URL
TOKENSNIFFER_URL = "https://tokensniffer.com/api/tokens"

# Connect to Web3
web3 = Web3(Web3.HTTPProvider(BASE_CHAIN_URL))

# Ensure connected to Web3 provider
if not web3.is_connected():
    raise Exception("Failed to connect to Web3 provider")

def get_new_pairs():
    url = "https://dexscreener.com/new-pairs?rankBy=trendingScoreH24&order=desc&chainIds=base&minLiq=5000&maxLiq=120000&maxAge=24"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    pairs = []
    for pair in soup.find_all('div', class_='pair-container'):
        # Check if the token has a Twitter or X link
        if pair.find('a', href=lambda href: href and ('twitter.com' in href or 'medium.com' in href)):
            token_address = pair['data-token-address']
            score = get_token_score(token_address)
            if score == 100:
                pairs.append({
                    'token_address': token_address,
                    'pair_address': pair['data-pair-address']
                })
    return pairs

def get_wallet_balance():
    balance = web3.eth.get_balance(WALLET_ADDRESS)
    return balance

def calculate_purchase_amount(balance):
    # Calculate purchase amount as 10% of total wallet holdings
    purchase_amount = balance * 0.1
    return purchase_amount

def buy_token(token_address, purchase_amount, slippage):
    router = web3.eth.contract(address=UNISWAP_ROUTER_ADDRESS, abi=UNISWAP_ROUTER_ABI)
    nonce = web3.eth.getTransactionCount(WALLET_ADDRESS)

    # Ensure token approval (not fully implemented here, example only)
    token = web3.eth.contract(address=token_address, abi=[{"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "payable": False, "stateMutability": "nonpayable", "type": "function"}])
    approve_txn = token.functions.approve(UNISWAP_ROUTER_ADDRESS, purchase_amount).buildTransaction({
        'from': WALLET_ADDRESS,
        'gas': 100000,
        'gasPrice': web3.toWei('50', 'gwei'),
        'nonce': nonce
    })
    signed_approve_txn = web3.eth.account.signTransaction(approve_txn, PRIVATE_KEY)
    web3.eth.sendRawTransaction(signed_approve_txn.rawTransaction)
    print("Approval transaction sent")

    time.sleep(30)

    txn = router.functions.swapExactETHForTokens(
        0,
        [web3.toChecksumAddress(web3.eth.default_account), web3.toChecksumAddress(token_address)],
        WALLET_ADDRESS,
        int(time.time()) + 60
    ).buildTransaction({
        'from': WALLET_ADDRESS,
        'value': purchase_amount,
        'gas': 2000000,
        'gasPrice': web3.toWei('50', 'gwei'),
        'nonce': nonce
    })

    signed_txn = web3.eth.account.signTransaction(txn, private_key=PRIVATE_KEY)
    tx_hash = web3.eth.sendRawTransaction(signed_txn.rawTransaction)
    print(f"Buy transaction sent with hash: {web3.toHex(tx_hash)}")
    return tx_hash

def get_token_price(pair_address):
    url = f"https://api.dexscreener.com/latest/dex/pairs/base/{pair_address}"
    response = requests.get(url)
    data = response.json()
    price = Decimal(data['pair']['priceUsd'])
    return price

def get_token_score(token_address):
    response = requests.get(f"{TOKENSNIFFER_URL}/base/{token_address}")
    if response.status_code == 200:
        data = response.json()
        score = data.get('score', 0)
        return score
    else:
        return 0

def sell_token(token_address, amount):
    router = web3.eth.contract(address=UNISWAP_ROUTER_ADDRESS, abi=UNISWAP_ROUTER_ABI)
    nonce = web3.eth.getTransactionCount(WALLET_ADDRESS)

    token = web3.eth.contract(address=token_address, abi=[{"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "payable": False, "stateMutability": "nonpayable", "type": "function"}])
    approve_txn = token.functions.approve(UNISWAP_ROUTER_ADDRESS, amount).buildTransaction({
        'from': WALLET_ADDRESS,
        'gas': 100000,
        'gasPrice': web3.toWei('50', 'gwei'),
        'nonce': nonce
    })
    signed_approve_txn = web3.eth.account.signTransaction(approve_txn, PRIVATE_KEY)
    web3.eth.sendRawTransaction(signed_approve_txn.rawTransaction)
    print("Approval transaction sent")

    time.sleep(30)

    txn = router.functions.swapExactTokensForETH(
        amount,
        0,
        [web3.toChecksumAddress(token_address), web3.toChecksumAddress(web3.eth.default_account)],
        WALLET_ADDRESS,
        int(time.time()) + 60
    ).buildTransaction({
        'from': WALLET_ADDRESS,
        'gas': 2000000,
        'gasPrice': web3.toWei('50', 'gwei'),
        'nonce': web3.eth.getTransactionCount(WALLET_ADDRESS)
    })

    signed_txn = web3.eth.account.signTransaction(txn, PRIVATE_KEY)
    tx_hash = web3.eth.sendRawTransaction(signed_txn.rawTransaction)
    print(f"Sell transaction sent with hash: {web3.toHex(tx_hash)}")
    return tx_hash

def main():
    new_pairs = get_new_pairs()
    for pair in new_pairs:
        token_address = pair['token_address']
        pair_address = pair['pair_address']

        # Get wallet balance and calculate purchase amount
        balance = get_wallet_balance()
        purchase_amount = calculate_purchase_amount(balance)

        buy_token(token_address, purchase_amount, SLIPPAGE)

        initial_price = get_token_price(pair_address)
        target_price = initial_price * PRICE_INCREASE_THRESHOLD
        print(f"Initial price: {initial_price}, Target price: {target_price}")

        while True:
            current_price = get_token_price(pair_address)
            print(f"Current price: {current_price}")
            if current_price >= target_price:
                sell_token(token_address, purchase_amount)
                break
            time.sleep(10)

if __name__ == "__main__":
    main()
