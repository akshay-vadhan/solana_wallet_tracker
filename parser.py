
import re
from typing import Optional


# Solana addresses use the Base58 alphabet.
# This checks the address's shape only, not its on-chain validity.
BASE58 = r"1-9A-HJ-NP-Za-km-z"
ADDRESS_RE = re.compile(rf"(?<![{BASE58}])[{BASE58}]{{32,44}}(?![{BASE58}])")


def parse_number(value: Optional[str]) -> Optional[float]:
    """Parse a plain numeric string into a float."""
    if not value:
        return None

    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def parse_market_cap(raw: Optional[str]) -> Optional[float]:
    """
    Examples:
        '$19.76K' -> 19760.0
        '$1.2M'   -> 1200000.0
        '$850'    -> 850.0
    """
    if not raw:
        return None

    value = raw.strip().replace("$", "").replace(",", "").upper()
    multiplier = 1.0

    if value.endswith("K"):
        multiplier = 1_000.0
        value = value[:-1]
    elif value.endswith("M"):
        multiplier = 1_000_000.0
        value = value[:-1]
    elif value.endswith("B"):
        multiplier = 1_000_000_000.0
        value = value[:-1]

    number = parse_number(value)
    return number * multiplier if number is not None else None


def extract_trader_label(text: str) -> Optional[str]:
    """
    Extract the displayed FOMO trader label.
    It is NOT assumed to be a Telegram username or Solana wallet.
    The leading '@' is removed so labels can be stored consistently.
    """
    match = re.search(
        r"\b(?:bought|sold)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    # Only inspect the alert headline containing the action.
    headline = text[:match.end()]
    handles = re.findall(r"@([A-Za-z0-9_]+)", headline)

    return handles[-1] if handles else None


def extract_side(text: str) -> Optional[str]:
    if re.search(r"\bbought\b", text, re.IGNORECASE):
        return "BUY"

    if re.search(r"\bsold(?:\s+all)?\b", text, re.IGNORECASE):
        return "SELL"

    return None


def extract_token_symbol(text: str) -> Optional[str]:
    """
    Extract a normal ticker such as CAT from:
        @Trader bought $CAT
        @Trader sold all $CAT

    If the symbol is an emoji, token_symbol may remain None.
    """
    match = re.search(
        r"\b(?:bought|sold)(?:\s+all)?\s+\$([A-Za-z0-9_]{1,30})\b",
        text,
        re.IGNORECASE,
    )
    return match.group(1).upper() if match else None


def extract_token_name(text: str, token_symbol: Optional[str]) -> Optional[str]:
    """
    For normal tickers, use the ticker as the fallback token name.
    For emoji tickers, try the 'Token name · Solana' line.
    """
    if token_symbol:
        return token_symbol

    for line in text.splitlines():
        match = re.search(
            r"^\s*[└├│|\\\s]*([A-Za-z][A-Za-z0-9 _.-]{0,50}?)"
            r"\s*[·•]\s*Solana\b",
            line,
            re.IGNORECASE,
        )
        if match:
            name = match.group(1).strip()
            if name.lower() not in {
                "contract address token",
                "token",
                "solana",
            }:
                return name

    return None


def extract_token_ca(text: str) -> Optional[str]:
    """
    Prefer the CA from a DexScreener/Pump.fun link.
    Fall back to a standalone Base58 address line.
    """
    url_patterns = [
        r"dexscreener\.com/solana/([1-9A-HJ-NP-Za-km-z]{32,44})",
        r"pump\.fun/coin/([1-9A-HJ-NP-Za-km-z]{32,44})",
    ]

    for pattern in url_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    for line in text.splitlines():
        candidate = line.strip().strip("`").strip()
        if ADDRESS_RE.fullmatch(candidate):
            return candidate

    return None


def extract_market_cap_raw(text: str) -> Optional[str]:
    match = re.search(
        r"\bMC\s*:\s*\*\*?\s*(\$?\s*[\d,]+(?:\.\d+)?\s*[KMB]?)\s*\*?\*?",
        text,
        re.IGNORECASE,
    )
    if not match:
        # Also supports text copied without Markdown bold markers.
        match = re.search(
            r"\bMC\s*:\s*(\$?\s*[\d,]+(?:\.\d+)?\s*[KMB]?)",
            text,
            re.IGNORECASE,
        )

    return re.sub(r"\s+", "", match.group(1)) if match else None


def extract_size_usd(text: str) -> Optional[float]:
    match = re.search(
        r"\bSize\s*:\s*\*{0,2}\s*\$?\s*([\d,]+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    return parse_number(match.group(1)) if match else None


def extract_price_raw(text: str) -> Optional[str]:
    match = re.search(
        r"\bPrice\s*:\s*\*{0,2}\s*(\$?[^\r\n*]+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    return match.group(1).strip().rstrip("\\").strip()


def extract_pnl(text: str) -> tuple[Optional[float], Optional[float]]:
    """
    Handles:
        PnL: +$126.05 (+18.0%)
        PnL: -$9.65 (-3.2%)
        PnL: ⬆️ +$126.05 (+18.0%)
    """
    match = re.search(
        r"\bPnL\s*:\s*.*?([+-])\s*\$([\d,]+(?:\.\d+)?)"
        r"(?:\s*\(\s*([+-]?\d+(?:\.\d+)?)\s*%\s*\))?",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None, None

    sign = -1.0 if match.group(1) == "-" else 1.0
    pnl_usd = sign * float(match.group(2).replace(",", ""))

    pnl_percent = (
        float(match.group(3))
        if match.group(3) is not None
        else None
    )

    return pnl_usd, pnl_percent


def parse_notification(
    raw_text: str,
    tracked_wallets: Optional[dict] = None,
) -> dict:
    """
    Parse one FOMO trade notification.

    'trader_label' is the name shown in the FOMO notification.
    'wallet_address' is only filled if an actual configured Solana
    wallet address is present in the message.
    """
    text = raw_text or ""

    trader_label = extract_trader_label(text)
    side = extract_side(text)
    token_symbol = extract_token_symbol(text)
    token_name = extract_token_name(text, token_symbol)
    token_ca = extract_token_ca(text)

    market_cap_raw = extract_market_cap_raw(text)
    market_cap_usd = parse_market_cap(market_cap_raw)
    size_usd = extract_size_usd(text)
    price_raw = extract_price_raw(text)
    pnl_usd, pnl_percent = extract_pnl(text)

    wallet_address = None
    wallet_label = None

    for address, label in (tracked_wallets or {}).items():
        if address in text:
            wallet_address = address
            wallet_label = label
            break

    missing = []
    for field_name, value in (
        ("trader_label", trader_label),
        ("side", side),
        ("token_ca", token_ca),
        ("market_cap", market_cap_usd),
        ("size_usd", size_usd),
        ("price_raw", price_raw),
    ):
        if value is None:
            missing.append(field_name)

    return {
        "trader_label": trader_label,
        "token_name": token_name,
        "token_symbol": token_symbol,
        "token_ca": token_ca,
        "side": side,
        "market_cap_raw": market_cap_raw,
        "market_cap_usd": market_cap_usd,
        "buy_mc_usd": market_cap_usd if side == "BUY" else None,
        "sell_mc_usd": market_cap_usd if side == "SELL" else None,
        "size_usd": size_usd,
        "price_raw": price_raw,
        "pnl_usd": pnl_usd,
        "pnl_percent": pnl_percent,
        "wallet_address": wallet_address,
        "wallet_label": wallet_label,
        "parser_status": "parsed" if not missing else "needs_review",
        "missing_fields": missing,
        "raw_text": text,
    }
