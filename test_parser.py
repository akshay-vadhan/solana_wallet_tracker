from parser import parse_notification


CA = "E6exteuDy1u6u3FfQV7SvPyU4XPdcBGi4cBnqrusocat"

BUY_MESSAGE = f"""
✅ @FreshUpperHyena bought $CAT
└ contract address token · Solana

🟣 $CAT · MC: $19.76K
├ Size: $700.00
└ Price: $0.00002044
{CA}
DexScreener · Pump.fun
"""

SELL_MESSAGE = f"""
🔻 @FreshUpperHyena sold all $CAT
└ contract address token · Solana

🟣 $CAT · MC: $23.31K
├ Size: $826.05
├ Price: $0.00002412
└ PnL: ⬆️ +$126.05 (+18.0%)
{CA}
DexScreener · Pump.fun
"""

NEGATIVE_SELL_MESSAGE = f"""
🔻 @SpareFineBass sold all $MAGNET
└ Magnet · Solana

🟣 $MAGNET · MC: $6.81K
├ Size: $290.35
├ Price: $0.0(5)7113
└ PnL: ⬇️ -$9.65 (-3.2%)
3cP1eyQXMwmBsnsY9BDzWJTLCH7NdJ6MkGrDt76pump
DexScreener · Pump.fun
"""

def test_cat_buy():
    result = parse_notification(BUY_MESSAGE)

    assert result["trader_label"] == "FreshUpperHyena"
    assert result["side"] == "BUY"
    assert result["token_symbol"] == "CAT"
    assert result["token_ca"] == CA
    assert result["market_cap_usd"] == 19760.0
    assert result["buy_mc_usd"] == 19760.0
    assert result["sell_mc_usd"] is None
    assert result["size_usd"] == 700.0
    assert result["price_raw"] == "0.00002044"
    assert result["pnl_usd"] is None
    assert result["parser_status"] == "parsed"

def test_cat_sell():
    result = parse_notification(SELL_MESSAGE)

    assert result["trader_label"] == "FreshUpperHyena"
    assert result["side"] == "SELL"
    assert result["token_symbol"] == "CAT"
    assert result["token_ca"] == CA
    assert result["market_cap_usd"] == 23310.0
    assert result["sell_mc_usd"] == 23310.0
    assert result["size_usd"] == 826.05
    assert result["price_raw"] == "0.00002412"
    assert result["pnl_usd"] == 126.05
    assert result["pnl_percent"] == 18.0
    assert result["parser_status"] == "parsed"

def test_negative_pnl_and_shorthand_price():
    result = parse_notification(NEGATIVE_SELL_MESSAGE)

    assert result["trader_label"] == "SpareFineBass"
    assert result["side"] == "SELL"
    assert result["market_cap_usd"] == 6810.0
    assert result["size_usd"] == 290.35
    assert result["price_raw"] == "0.0(5)7113"
    assert result["pnl_usd"] == -9.65
    assert result["pnl_percent"] == -3.2

def test_label_is_not_a_wallet_address():
    result = parse_notification(BUY_MESSAGE)

    assert result["trader_label"] == "FreshUpperHyena"
    assert result["wallet_address"] is None
    assert result["wallet_label"] is None

def test_unknown_message_is_not_misclassified():
    result = parse_notification("Hello, this is an ordinary message")

    assert result["side"] is None
    assert result["token_ca"] is None
    assert result["parser_status"] == "needs_review"

if __name__ == "main":
    tests = [
        test_cat_buy,
        test_cat_sell,
        test_negative_pnl_and_shorthand_price,
        test_label_is_not_a_wallet_address,
        test_unknown_message_is_not_misclassified,
        ]

for test in tests:
    test()
    print(f"PASS: {test.name}")

    print(f"\nAll {len(tests)} parser tests passed.")