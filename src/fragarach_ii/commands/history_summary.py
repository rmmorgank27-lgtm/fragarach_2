"""Read the history inventory for one symbol without changing evidence."""
import argparse
import json
import sqlite3
from fragarach_ii.history_summary import history_summary
from fragarach_ii.market_history_service import MarketHistoryServiceError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--json', action='store_true', required=True)
    args = parser.parse_args()
    try:
        result = history_summary(args.database, args.symbol)
    except (MarketHistoryServiceError, FileNotFoundError, RuntimeError, sqlite3.Error) as error:
        print(json.dumps({'error': str(error)}))
        return 1
    print(json.dumps(result, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
