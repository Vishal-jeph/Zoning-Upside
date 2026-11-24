"""Whole pipeline in one command: python -m pipeline [--refresh]  (fetch → clean → potential)."""
import argparse

from . import clean, fetch, potential

ap = argparse.ArgumentParser(description="Download (cached), clean, and score Hoboken sites.")
ap.add_argument("--refresh", action="store_true", help="re-download source layers instead of using the cache")
args = ap.parse_args()
fetch.fetch_all(refresh=args.refresh)
clean.main()
potential.main()
