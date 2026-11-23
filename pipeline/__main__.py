"""Phase 1 in one command: python -m pipeline [--refresh]  (fetch → clean)."""
import argparse

from . import clean, fetch

ap = argparse.ArgumentParser(description="Download (cached) and clean Hoboken parcel + zoning data.")
ap.add_argument("--refresh", action="store_true", help="re-download source layers instead of using the cache")
args = ap.parse_args()
fetch.fetch_all(refresh=args.refresh)
clean.main()
