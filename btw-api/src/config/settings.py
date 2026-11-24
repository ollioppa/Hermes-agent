import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _project_path(value: str, default: str) -> str:
    """Resolve relative project paths to absolute paths.

    launchd can be picky about working directories. Keep .env ergonomic while
    ensuring runtime paths are deterministic.
    """
    raw = value or default
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)

# ── Google Sheets ──────────────────────────────────────────────
# Offline computation imports need no account. Live access validates this later.
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = _project_path(
    os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", ""),
    "service_account.json",
)

# ── Windowed Sheets (30/90/180d rolling windows) ────────────────
WINDOWED_SHEETS_ENABLED = os.getenv("WINDOWED_SHEETS_ENABLED", "false").lower() == "true"
MACRO_DATA_DAILY_ENABLED = os.getenv("MACRO_DATA_DAILY_ENABLED", "false").lower() == "true"
MACRO_DATA_CONSUMER_ENABLED = os.getenv("MACRO_DATA_CONSUMER_ENABLED", "false").lower() == "true"
SPREADSHEET_ID_30D = os.getenv("SPREADSHEET_ID_30D", "")
SPREADSHEET_ID_90D = os.getenv("SPREADSHEET_ID_90D", "")
SPREADSHEET_ID_180D = os.getenv("SPREADSHEET_ID_180D", "")

WINDOWED_SHEET_CONFIG = {
    "30d": {"days": 30, "spreadsheet_id": SPREADSHEET_ID_30D},
    "90d": {"days": 90, "spreadsheet_id": SPREADSHEET_ID_90D},
    "180d": {"days": 180, "spreadsheet_id": SPREADSHEET_ID_180D},
}

# ── Coinalyze ─────────────────────────────────────────────────
COINALYZE_API_KEY = os.getenv("COINALYZE_API_KEY", "")

# Coinalyze daily-history endpoints are fetched as full-range calls.
# These legacy knobs are kept as environment overrides/backward-compatible
# constants, but current backfill.py uses BACKFILL_START["coinalyze"].
COINALYZE_OI_BACKFILL_DAYS = int(os.getenv("COINALYZE_OI_BACKFILL_DAYS", "730"))
COINALYZE_FUNDING_BACKFILL_DAYS = int(os.getenv("COINALYZE_FUNDING_BACKFILL_DAYS", "365"))
COINALYZE_LIQ_BACKFILL_DAYS = int(os.getenv("COINALYZE_LIQ_BACKFILL_DAYS", "180"))

# Legacy chunk knobs; current daily-history fetchers no longer chunk Coinalyze.
COINALYZE_OI_CHUNK_DAYS = int(os.getenv("COINALYZE_OI_CHUNK_DAYS", "90"))
COINALYZE_FUNDING_CHUNK_DAYS = int(os.getenv("COINALYZE_FUNDING_CHUNK_DAYS", "90"))
COINALYZE_LIQ_CHUNK_DAYS = int(os.getenv("COINALYZE_LIQ_CHUNK_DAYS", "30"))
COINALYZE_INTER_CHUNK_DELAY_SECONDS = float(os.getenv("COINALYZE_INTER_CHUNK_DELAY_SECONDS", "5"))

# We want the data, not silent missing rows. Retry on 429 by default.
COINALYZE_MAX_RETRIES = int(os.getenv("COINALYZE_MAX_RETRIES", "2"))

# ── Logging ───────────────────────────────────────────────────
LOG_DIR = _project_path(os.getenv("LOG_DIR", ""), "logs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ── Coinalyze symbol sets (verified against real API responses) ─
# BTC_USDT.Y (Gate.io) returns no data for OI
# Immutable identity for composite_thermometer_v1.  A basket change requires
# a new ID and must never be smuggled in through an environment override.
# BitMEX closed and settled XBTUSD on 2026-09-16.  The replacement is the
# independent, coin-margined Deribit BTC perpetual; this is a new immutable
# basket identity, not a silent continuation of the prior series.
OI_BASKET_ID = "coinalyze_btc_perp_basket_20260924_v2"
OI_SYMBOLS = [
    "BTCUSDT_PERP.A",  # Binance USDT
    "BTCUSD_PERP.A",   # Binance COIN
    "BTCUSDT.6",       # Bybit USDT
    "BTCUSD.6",        # Bybit COIN
    "BTCUSDT_PERP.3",  # OKX USDT
    "BTCUSD_PERP.3",   # OKX COIN
    "BTC-PERPETUAL.2", # Deribit BTC/USD COIN (replaces closed BitMEX)
    "BTC.H",           # Hyperliquid
    "BTCUSDT_PERP.4",  # Huobi/HTX
]

# USDT-perps only; BTC.H is non-USDT but Coinalyze normalises it
FUNDING_SYMBOLS = [
    "BTCUSDT_PERP.A",  # Binance
    "BTCUSDT.6",       # Bybit
    "BTCUSDT_PERP.3",  # OKX
    "BTC.H",           # Hyperliquid
    "BTCUSDT_PERP.4",  # Huobi/HTX
    "BTC_USDT.Y",      # Gate.io
]

# BTC.H returns no liquidation data
LIQ_SYMBOLS = [
    "BTCUSDT_PERP.A",  # Binance USDT
    "BTCUSD_PERP.A",   # Binance COIN
    "BTCUSDT.6",       # Bybit USDT
    "BTCUSD.6",        # Bybit COIN
    "BTCUSDT_PERP.3",  # OKX USDT
    "BTCUSD_PERP.3",   # OKX COIN
    "BTCUSD_PERP.0",   # BitMEX
]

# ── Chunk sizes (max candles/records per API request) ──────────
BINANCE_CHUNK_DAYS = 1000      # Binance /klines limit=1000
COINBASE_CHUNK_DAYS = 300      # Coinbase /candles max 300/request
# Legacy fallback only; Coinalyze fetchers use full-range daily-history calls.
COINALYZE_CHUNK_DAYS = COINALYZE_FUNDING_CHUNK_DAYS

# ── Per-source backfill start dates ───────────────────────────
BACKFILL_START = {
    "coinbase":    "2015-07-20",  # oldest available Coinbase BTC-USD candles
    "fear_greed":  "2018-02-01",  # Alternative.me API history start
    "coinmetrics": "2010-07-18",  # first on-chain BTC data
    "coinalyze":   "2015-01-01",  # max-history attempt; API returns rows only where symbols exist
    "binance":     "2019-09-08",  # BTCUSDT spot launch
    "mstr":        "2020-08-11",  # MicroStrategy first BTC purchase
    "etf_flows":   "2024-01-11",  # US BTC ETF launch date
}

# ── DB column order (= sheet write order) ─────────────────────
DB_COLUMNS = [
    "date",
    # Raw prices
    "btc_binance_close", "btc_coinbase_close", "mstr_close",
    # Coinbase Premium
    "cb_premium_usd", "cb_premium_pct",
    "cb_premium_7d_usd", "cb_premium_30d_usd",
    # On-chain raw
    "fear_greed", "mvrv",
    # On-chain computed
    "fng_7d_median", "fng_30d_median", "mvrv_30d_median",
    # Open Interest
    "perp_oi_usd", "perp_oi_7d_change_pct", "perp_oi_30d_change_pct",
    "oi_coverage_pct",
    # Funding (legacy field held: no documented daily settlement contract)
    "funding_daily_pct", "funding_7d_pct", "funding_30d_pct",
    # Liquidations
    "liq_daily_long_usd", "liq_daily_short_usd", "liq_daily_total_usd",
    "liq_7d_total_usd", "liq_7d_long_pct",
    "liq_30d_total_usd", "liq_30d_long_pct",
    "liq_coverage_pct",
    # Regime signals
    "btc_200w_ma_usd", "btc_200w_ma_ratio_pct", "flex_signal",
    "mstr_btc_ratio", "mstr_btc_90d_trend_pct",
    # Meta
    "btc_etf_total_flow_usd_m",
    "etf_flow_source_status",
    "source_status_json",
    "updated_at_utc",
]

# ── MACRO_DATA sheet ──────────────────────────────────────────
# One wide dated table, mirroring the proven DB/MARKET_DATA pattern. Schema
# changes are migrations: daily positional upserts must match this list exactly.
MACRO_DATA_COLUMNS = [
    "date",
    "finra_margin_date", "finra_margin_debt_usd", "finra_margin_source_status",
    "cpi_index", "sp500_close", "sp500_12m_high",
    "finra_real_margin", "finra_real_margin_growth_3m_annualized",
    "finra_growth_percentile_60m", "finra_had_recent_blowoff",
    "finra_current_growth_negative", "finra_sp500_near_high",
    "finra_rollover_warning", "finra_signal_authority",
    "nfci_leverage", "nfci_leverage_delta_3m", "nfci_leverage_percentile",
    "nfci_leverage_warning",
    "fed_walcl", "fed_tga_wtregen", "fed_rrp_rpontsyd",
    "walcl_delta_3m", "wtregen_delta_3m", "rrp_delta_3m",
    "liquidity_tightening_component_count_3m", "liquidity_2of3_3m_warning",
    "hy_oas", "hy_oas_source_regime", "hy_oas_percentile_60m",
    "hy_oas_trough_value", "hy_oas_months_since_trough",
    "hy_oas_widening_from_trough", "hy_oas_still_tight",
    "hy_oas_sp500_near_high", "hy_oas_warning", "hy_oas_quality_status",
    "bdc_as_of_date", "bdc_stage1_credit_quality",
    "bdc_stage2_wrapper_repricing", "bdc_stage3_funding_stress",
    "bdc_stage4_credit_supply", "bdc_stage5_macro_effects",
    "bdc_stage6_feedback", "bdc_regime_a_probability",
    "bdc_regime_b_probability", "bdc_regime_c_probability",
    "bdc_status_code", "bdc_source_status",
    "source_status_json", "calculation_version_json", "updated_at_utc",
]

if len(MACRO_DATA_COLUMNS) > 64:
    raise RuntimeError("MACRO_DATA schema exceeds reviewed 64-column limit")

_MACRO_DATE_COLUMNS = {"date", "finra_margin_date", "bdc_as_of_date"}
_MACRO_BOOLEAN_COLUMNS = {
    "finra_had_recent_blowoff",
    "finra_current_growth_negative",
    "finra_sp500_near_high",
    "finra_rollover_warning",
    "nfci_leverage_warning",
    "liquidity_2of3_3m_warning",
    "hy_oas_still_tight",
    "hy_oas_sp500_near_high",
    "hy_oas_warning",
}
_MACRO_INTEGER_COLUMNS = {
    "liquidity_tightening_component_count_3m",
    "hy_oas_months_since_trough",
    "bdc_stage1_credit_quality",
    "bdc_stage2_wrapper_repricing",
    "bdc_stage3_funding_stress",
    "bdc_stage4_credit_supply",
    "bdc_stage5_macro_effects",
    "bdc_stage6_feedback",
}
_MACRO_TEXT_COLUMNS = {
    "finra_margin_source_status",
    "finra_signal_authority",
    "hy_oas_source_regime",
    "hy_oas_quality_status",
    "bdc_status_code",
    "bdc_source_status",
}
_MACRO_JSON_COLUMNS = {"source_status_json", "calculation_version_json"}


def _macro_column_type(column: str) -> str:
    if column in _MACRO_DATE_COLUMNS:
        return "date"
    if column == "updated_at_utc":
        return "datetime"
    if column in _MACRO_BOOLEAN_COLUMNS:
        return "boolean"
    if column in _MACRO_INTEGER_COLUMNS:
        return "integer"
    if column in _MACRO_TEXT_COLUMNS:
        return "text"
    if column in _MACRO_JSON_COLUMNS:
        return "json"
    return "number"


MACRO_DATA_COLUMN_TYPES = {
    column: _macro_column_type(column) for column in MACRO_DATA_COLUMNS
}

# ── MARKET_DATA sheet ─────────────────────────────────────────
MARKET_DATA_SYMBOL_MAP = {
    "BTC-USD":   "BTC",
    "MSTR":      "MSTR",
    "STRK":      "STRK",
    "STRF":      "STRF",
    "STRD":      "STRD",
    "STRC":      "STRC",
    "^GSPC":     "SP500",
    "GC=F":      "GOLD",
    "^NDX":      "NASDAQ100",
    "DX-Y.NYB":  "DXY",
    "GRID":      "Smartgrid_ETF",
    "WNUC.DE":   "WNUC_Euro",
    "5MVW.DE":   "5MVW_Euro",
    "PTC":       "PTC",
    "URTH":      "MSCI_World_Core",
}

# Explicit ETF proxies; columns are the actual tickers, never sector-index labels.
SECTOR_SYMBOL_MAP = {symbol:symbol for symbol in (
    'XLE','XLB','XLI','XLY','XLP','XLV','XLF','XLK','XLC','XLU','XLRE'
)}

MARKET_DATA_COLUMN_ORDER = [
    "BTC", "MSTR", "STRK", "STRF", "STRD", "STRC",
    "SP500", "GOLD", "NASDAQ100", "DXY",
    "Smartgrid_ETF", "WNUC_Euro", "5MVW_Euro", "PTC", "MSCI_World_Core",
]
