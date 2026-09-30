"""Run separately from the API: python -m app.webhook_worker [--once]."""
import argparse
import time

from .db import SessionLocal
from .webhooks import drain


def main():
    parser = argparse.ArgumentParser(description="Deliver queued Tavo webhooks")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        with SessionLocal() as db:
            drain(db)
        if args.once:
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
