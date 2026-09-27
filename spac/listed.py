"""기존 상장 스팩 저가매수 분석기.

data/listed.csv(상장 스팩 목록·현재가) + data/holdings.csv(내 보유) + settings.json
→ 종목별 '바닥 가치'(해산 시 예상 반환금), 괴리, 바닥까지 연환산 수익률, 매수/매도 신호를 계산해
  out/listed.txt 로 저장한다. (calc.py 메일 본문 뒤에 붙여 보낸다)

사용: python3 listed.py [--today YYYY-MM-DD] [--fetch]
  --fetch : 네이버 증권에서 현재가를 받아 listed.csv 의 price 를 갱신 (네트워크 허용 필요)
"""
import argparse
import csv
import json
import urllib.request
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
OFFER = 2000


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def fetch_price(code):
    """네이버 증권 모바일 API에서 현재가. 실패하면 None."""
    url = f"https://m.stock.naver.com/api/stock/{code}/basic"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        return num(data.get("closePrice"))
    except Exception:
        return None


def floor_value(listing, today, rate, cfg):
    """해산(상장 후 36개월) 시 주당 예상 반환금(이자소득세 차감)과 남은 기간(년)."""
    years_total = cfg["life_months"] / 12
    elapsed = (today - listing).days / 365
    left = max(years_total - elapsed, 0.05)
    interest = OFFER * rate * years_total          # 단리 근사 🟡
    payout = OFFER + interest * (1 - cfg["interest_tax"])
    return payout, left


def analyze(row, today, cfg, costs, held):
    price = num(row["price"])
    if not price or not row["listing_date"]:
        return None
    rate = num(row["trust_rate"]) or cfg["default_trust_rate"]
    payout, left = floor_value(date.fromisoformat(row["listing_date"]), today, rate, cfg)
    sell_cost = costs["transaction_tax"] + costs["brokerage"]
    floor_gain = payout / (price * (1 + costs["brokerage"])) - 1   # 해산 반환은 매도 아님 → 거래세 없음
    floor_annual = floor_gain / left
    target = price * (1 + cfg["target_gain"])
    status = row.get("status") or ""
    hurdle = max(cfg["bank_rate"], cfg.get("target_annual", 0))
    cap = cfg.get("buy_max_price") or float("inf")   # None이면 가격 상한 없음(목표 연수익만으로 판단)
    max_buy = payout / (1 + hurdle * left) / (1 + costs["brokerage"])

    signal, why = "관망", []
    if "합병" in status:
        signal = "제외"
        why.append(f"합병 진행({status}) → 바닥 보장 약해짐. 합병 반대 시 주식매수청구권 검토")
    elif price <= cap and floor_annual >= hurdle:
        signal = "매수 후보"
        why.append(f"바닥 연수익 {floor_annual*100:.1f}% ≥ 목표 {hurdle*100:.1f}% (연 {hurdle*100:.0f}% 되는 최대 매수가 {max_buy:,.0f}원)")
    elif price <= cap and price <= OFFER:
        why.append(f"가격은 싸지만 바닥 연수익 {floor_annual*100:.1f}% < 목표 {hurdle*100:.1f}%"
                   + (" (예금보다는 높음)" if floor_annual >= cfg["bank_rate"] else ""))
    if "관리" in status:
        why.append("관리종목: 해산 임박 가능성 → 반환금·일정 확인")

    h = held.get(row["name"])
    if h:
        bp = num(h["buy_price"])
        gain = (price * (1 - sell_cost)) / bp - 1
        if gain >= cfg["target_gain"]:
            signal = "매도 신호"
            why.insert(0, f"보유 {h['shares']}주 매수가 {bp:,.0f}원 → 현재 {gain*100:+.1f}% (목표 +{cfg['target_gain']*100:.0f}% 도달)")
        else:
            why.insert(0, f"보유 중 {gain*100:+.1f}% (목표가 {bp*(1+cfg['target_gain'])/(1-sell_cost):,.0f}원)")
    return {"name": row["name"], "price": price, "rate": rate, "rate_known": bool(num(row["trust_rate"])),
            "payout": payout, "left": left, "max_buy": max_buy, "floor_annual": floor_annual, "target": target,
            "signal": signal, "why": why, "price_date": row.get("price_date", "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--fetch", action="store_true")
    args = ap.parse_args()
    today = date.fromisoformat(args.today)
    settings = json.loads((BASE / "settings.json").read_text(encoding="utf-8"))
    cfg, costs = settings["listed_strategy"], settings["sell_costs"]

    path = BASE / "data/listed.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if args.fetch:
        for r in rows:
            if r["code"]:
                p = fetch_price(r["code"])
                if p:
                    r["price"], r["price_date"] = f"{p:.0f}", today.isoformat()
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

    held = {h["name"]: h for h in csv.DictReader(open(BASE / "data/holdings.csv", encoding="utf-8"))}
    res = [a for a in (analyze(r, today, cfg, costs, held) for r in rows) if a]
    order = {"매도 신호": 0, "매수 후보": 1, "관망": 2, "제외": 3}
    res.sort(key=lambda a: (order[a["signal"]], a["price"]))

    lines = ["", "■ 기존 상장 스팩 (저가매수 → +10% 매도 전략)"]
    no_price = [r["name"] for r in rows if not num(r["price"])]
    if not res:
        lines.append("  현재가 데이터 없음 → 네트워크 허용 후 --fetch 필요")
    for a in res:
        rate_txt = f"{a['rate']*100:.1f}%" + ("" if a["rate_known"] else "(가정🟡)")
        lines.append(f"  [{a['signal']}] {a['name']} {a['price']:,.0f}원 ({a['price_date'] or '날짜?'})"
                     f" · 해산 시 약 {a['payout']:,.0f}원(예치 {rate_txt}) · 남은 {a['left']:.1f}년"
                     f" · 바닥 연수익 {a['floor_annual']*100:+.1f}% · 목표수익 매수가 ≤{a['max_buy']:,.0f}원 · +10% 목표 {a['target']:,.0f}원")
        for w_ in a["why"]:
            lines.append(f"      · {w_}")
    if no_price:
        lines.append(f"  (현재가 없음 {len(no_price)}종목: {', '.join(no_price[:6])}{' 외' if len(no_price) > 6 else ''})")
    hurdle = max(cfg["bank_rate"], cfg.get("target_annual", 0))
    cap_txt = f"{cfg['buy_max_price']:,}원 이하 + " if cfg.get("buy_max_price") else ""
    lines.append(f"  규칙: {cap_txt}해산까지 보유해도 연 {hurdle*100:.1f}% 이상인 가격 → 매수 후보,"
                 f" 매수가 +{cfg['target_gain']*100:.0f}% → 매도, 합병 발표 종목은 제외. 한 종목 최대 {cfg['max_per_spac_won']:,}원")
    text = "\n".join(lines)
    (BASE / "out").mkdir(exist_ok=True)
    (BASE / "out/listed.txt").write_text(text, encoding="utf-8")
    buy = sum(a["signal"] == "매수 후보" for a in res)
    sell = sum(a["signal"] == "매도 신호" for a in res)
    tag = " · ".join(t for t in (f"매도신호 {sell}" if sell else "", f"매수후보 {buy}" if buy else "") if t)
    (BASE / "out/listed_subject.txt").write_text(f"기존스팩 {tag}" if tag else "", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
