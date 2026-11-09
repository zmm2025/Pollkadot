"""Build data/results/patches/2024_IN_SEN_monroe.csv (fill: Monroe County, 18105) from the
Indiana Election Division's certified 2024 General Election results (ENR archive JSON
OffCatC_1006_A.json, saved in data/raw/state/2024_IN_SEN_monroe/).

Run from the repo root: python -P pipeline/patches/2024_IN_SEN_monroe.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _in_enr import build  # noqa: E402

if __name__ == "__main__":
    build("2024_IN_SEN_monroe", "SEN", "OffCatC_1006_A.json")
