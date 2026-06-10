"""Re-export Tushare client from derivkit.data (backward compatibility)."""

from derivkit.data.tushare_loader import (
    FUTURES_EXCHANGE_SUFFIX,
    TushareClient,
    get_tushare_token,
    resolve_exchange,
    resolve_option_opt_code,
    resolve_ts_code,
)

__all__ = [
    "FUTURES_EXCHANGE_SUFFIX",
    "TushareClient",
    "get_tushare_token",
    "resolve_exchange",
    "resolve_option_opt_code",
    "resolve_ts_code",
]
