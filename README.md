# Solana Wallet Tracker

A Python-based Solana monitoring and Telegram notification toolkit.

## Features

- Telegram notification monitoring using Telethon
- Wallet trade event parsing
- Buy and sell event extraction
- Token contract address and market-cap parsing
- SQLite-based event storage
- CSV event export
- Solana live swap monitoring
- Transaction-level token and SOL balance analysis
- Failed swap tracking
- Jupiter paper quote integration
- Token price monitoring utilities

## Technology Stack

- Python 3.10+
- Telethon
- SQLite
- Requests
- Python-dotenv
- Solana RPC
- Jupiter API

## Project Structure

- `main.py` - Telegram monitoring entry point
- `parser.py` - Notification parsing
- `storage.py` - SQLite storage
- `config.py` - Configuration management
- `export_csv.py` - CSV export utility
- `solana_live_swap_monitor.py` - Live swap monitoring
- `solana_live_swap_monitor_v2.py` - Updated swap monitor
- `jupiter_paper_quote.py` - Jupiter paper quote testing
- `test_*.py` - Test and monitoring utilities

## Requirements

- Python 3.10+
- Telegram API credentials
- Jupiter API key (for Jupiter integration)
- Solana RPC endpoint (for live monitoring)

## Installation

Clone the repository:

```bash
git clone https://github.com/akshay-vadhan/solana_wallet_tracker.git
cd solana_wallet_tracker
