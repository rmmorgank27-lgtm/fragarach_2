# Global Prime index-CFD ingestion

Fragarach admits the Windows MT5 `divergence.market_data` package as a distinct
`BROKER_INDEX_CFDS` authority. The commissioned scope is exactly:

- `US30`, `US500`, and `NAS100`;
- native `D1`, `H1`, `M30`, `M15`, and `M5` completed bars;
- provider `GLOBAL_PRIME_MT5`;
- provider contract `GLOBAL_PRIME_MT5_PYTHON_RATES_V1`; and
- timestamp policy `MT5_PYTHON_COPY_RATES_UNIX_UTC_V1`.

Official calculated indices and ETF proxies are separate instruments. The
importer rejects packages that substitute `DJI`, `SPY`, `QQQ`, or any other
alias for an exact broker symbol, omit a native timeframe, lack complete-bar
proof, fail an embedded checksum, or leave timestamp authority unresolved.

The per-user LaunchAgent is:

`~/Library/LaunchAgents/com.raymorgan.fragarach-ii.global-prime-index-cfd-importer.plist`

It starts at login, remains alive, polls the immutable Datagather receipts, and
admits only new or corrected rows. Fragarach's registered-writer lock remains
authoritative: a busy authority produces a retry state and the package remains
unprocessed until a later successful pass.

Inspect service state:

```sh
PYTHONPATH=src python3 -m fragarach_ii.index_cfd_service status
```

Install or repair the service:

```sh
PYTHONPATH=src python3 -m fragarach_ii.index_cfd_service install \
  --repository /Users/raymorgan/VSC/Fragarach_2 \
  --python /opt/homebrew/bin/python3
```

The durable importer state is
`data/runtime/global-prime-index-cfd-importer.json`. Transport health remains a
separate Datagather responsibility; a current receiver does not by itself prove
that Fragarach admission or publication is current.
