"""상장 첫날 시간대별 공모가 대비 상승률 요약.  data/intraday.csv → 표 출력.
사용: python3 timing.py
"""
import csv
from pathlib import Path
from statistics import median

BASE = Path(__file__).parent
BUCKETS = [("시초가(09:00)", "09:00", "09:01"), ("09:01~09:20", "09:01", "09:20"),
           ("09:20~09:40", "09:20", "09:40"), ("09:40~10:30", "09:40", "10:30"),
           ("10:30~13:00", "10:30", "13:00"), ("13:00~15:00", "13:00", "15:00"),
           ("종가(15:30)", "15:30", "15:31")]


def main(offer=2000):
    rows = list(csv.DictReader(open(BASE / "data/intraday.csv", encoding="utf-8")))
    print(f"{'구간':<14}{'건수':>4}{'중앙값':>9}{'최저':>9}{'최고':>9}  종목")
    for label, lo, hi in BUCKETS:
        pts = [(r["name"], int(r["price"]) / offer - 1) for r in rows
               if r["time"] and lo <= r["time"] < hi]
        if not pts:
            print(f"{label:<14}{0:>4}")
            continue
        v = [p for _, p in pts]
        names = ", ".join(sorted({n.replace("스팩", "") for n, _ in pts}))
        print(f"{label:<14}{len(v):>4}{median(v)*100:>+8.0f}%{min(v)*100:>+8.0f}%{max(v)*100:>+8.0f}%  {names}")
    highs = [int(r["price"]) / offer - 1 for r in rows if r["kind"].startswith("고가")]
    if highs:
        print(f"{'장중고가':<14}{len(highs):>4}{median(highs)*100:>+8.0f}%{min(highs)*100:>+8.0f}%{max(highs)*100:>+8.0f}%")


if __name__ == "__main__":
    main()
