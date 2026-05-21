"""
Reporte de métricas del pipeline desde Langfuse.
Uso: conda run -n xertica python scripts/metrics_report.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]
"""
import argparse
import json
import os
import sys

from dotenv import load_dotenv

from metrics_lib import get_metrics


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="from_date", default=None)
    parser.add_argument("--to", dest="to_date", default=None)
    args = parser.parse_args()

    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        print(json.dumps({"error": "LANGFUSE_PUBLIC_KEY not set"}))
        sys.exit(1)

    report = get_metrics(args.from_date, args.to_date)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
