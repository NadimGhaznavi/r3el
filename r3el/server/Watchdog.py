import argparse
import json
import time

from ax3l.activity.CheckServices import CheckServices

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ax3l-unit", required=True)
    parser.add_argument("--llm-health-url", required=True)
    args = parser.parse_args()
    while True:
        CheckServices().run(args.ax3l_unit, args.llm_health_url)
        time.sleep(10)
