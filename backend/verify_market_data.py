import sys

import httpx

from app.services.binance_client import BinanceClientError, BinanceMarketDataClient


def verify():
    # We use the official Futures Demo URL
    base_url = "https://demo-fapi.binance.com"
    print(f"Connecting to Binance Futures Demo REST endpoint: {base_url}")
    client = BinanceMarketDataClient(
        base_url=base_url,
        timeout_seconds=5.0,
        max_retries=1,
        backoff_seconds=0.1,
    )

    try:
        info = client.exchange_info()
        symbols = [s["symbol"] for s in info.get("symbols", [])]
        print("Successfully fetched exchange info!")
        print(f"Found {len(symbols)} total symbols.")
        usdt_symbols = [s for s in symbols if s.endswith("USDT")][:5]
        print(f"Sample USDT Futures symbols: {usdt_symbols}")

        # Now try to fetch 15m klines for BTCUSDT
        print("Fetching 15m klines for BTCUSDT...")
        klines = client.klines("BTCUSDT", "15m", limit=5)
        print(f"Successfully fetched {len(klines)} klines!")
        print(f"Latest candle: {klines[-1]}")
        print("VERIFICATION SUCCESSFUL")
        return True
    except BinanceClientError as e:
        print(f"BinanceClientError occurred: {e}", file=sys.stderr)
    except httpx.HTTPError as e:
        print(f"HTTPError occurred: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)

    print("VERIFICATION FAILED/BLOCKED (Possibly due to restricted location)")
    return False

if __name__ == "__main__":
    verify()
