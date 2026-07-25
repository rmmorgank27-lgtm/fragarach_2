"""Inspect or update the canonical Credential Authority."""

from __future__ import annotations

import argparse
import json
import os

from fragarach_ii.credentials import CredentialAuthority


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("status", "store", "migrate", "validate"), default="status")
    parser.add_argument("--provider", default="TWELVE_DATA")
    parser.add_argument("--json", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    authority = CredentialAuthority()
    try:
        if arguments.mode == "status":
            result = authority.snapshot()
        elif arguments.mode == "migrate":
            result = authority.migrate_legacy_twelve_data()
        elif arguments.mode == "validate":
            result = authority.validate(arguments.provider)
        else:
            value = os.environ.pop("FRAGARACH_CREDENTIAL_INPUT", "")
            result = authority.store_credential(arguments.provider, value).public_dict()
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"contract": "fragarach_ii.credential_authority_error.v1", "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
