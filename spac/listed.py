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


BROKER_PREFIX = [("케이비", "KB증권"), ("KB", "KB증권"), ("한국", "한국투자증권"), ("엔에이치", "NH투자증권"),
                 ("NH", "NH투자증권"), ("대신", "대신증권"), ("신한", "신한투자증권"), ("삼성", "삼성증권"),
                 ("교보", "교보증권"), ("키움", "키움증권"), ("하나", "하나증권"), ("미래에셋", "미래에셋증권"),
                 ("IBKS", "IBK투자증권"), ("유안타", "유안타증권"), ("DB", "DB증권"), ("SK", "SK증권"),
                 ("메리츠", "메리츠증권"), ("유진", "유진투자증권"), ("하이", "iM증권"), ("상상인", "상상인증권"),
                 ("한화", "한화투자증권"), ("BNK", "BNK투자증권"), ("신영", "신영증권"), ("현대차", "현대차증권"),
                 ("LS", "LS증권"), ("다올", "다올투자증권"), ("부국", "부국증권"), ("한양", "한양증권")]

# 합병 단계별 대응 안내 (reports/2026-09-28-merger.md 근거)
MERGER_GUIDE = {
    "합병 결의": "합병 공시 → 곧 예비심사·거래정지. 바닥(예치금) 보장 약해짐",
    "예비심사 청구": "심사 중 거래정지. 통과 시 재개 직후 급등 사례 多, 탈락·철회 시 재개일 평균 −8%",
    "거래정지": "심사 중 거래정지. 재개일 공지 확인",
    "예심 통과": "거래 재개 → 기대감 급등 구간. 보유분은 급등 시 분할 매도",
    "주총": "반대의사 통지 마감(주총 전일) 확인. 주주확정 기준일 보유자만 매수청구 가능",
}


def broker_of(name):
    for pre, b in BROKER_PREFIX:
        if name.startswith(pre):
            return b
    return None


def merger_view(row, today, settings, held):
    """합병 가능성(주관사 성공률·존립기한) 과 합병 진행 시 대응 안내."""
    cfg = settings["listed_strategy"]
    rates = settings.get("merger_success_by_broker", {})
    b = broker_of(row["name"])
    rate = rates.get(b)
    notes = []
    listing = date.fromisoformat(row["listing_date"])
    months_left = cfg["life_months"] - (today - listing).days / 30.44
    # 존립기한 6개월 전까지 예비심사를 청구해야 함 → 그 직전 6~12개월이 '짝 찾기 압박' 구간
    phase = ("합병 마감 임박(예심 청구 기한 경과 → 해산 가능성↑)" if months_left < 6 else
             "짝 찾기 막판(6~12개월)" if months_left < 12 else
             "탐색기" if months_left < 30 else "초기")
    notes.append(f"주관 {b or '?'} 합병성공률 {f'{rate}%' if rate else '미확인'} · 존립기한까지 {months_left:.0f}개월({phase})")
    status = row.get("status") or ""
    for k, g in MERGER_GUIDE.items():
        if k in status:
            sd = row.get("status_date") or ""
            notes.append(f"⚑ {status}{f'({sd})' if sd else ''}: {g}")
            if row["name"] in held:
                notes.append("   보유 대응: ① 급등하면 분할 매도 ② 합병상장 후 3개월 내 87.5% 하락(평균 −31.8%) → 합병기일 전 정리"
                             " ③ 대상 기업이 별로면 주총 전일까지 반대의사 통지 → 주식매수청구권")
            else:
                notes.append("   미보유: 바닥 보장 약해져 저가매수 전략에서 제외")
            break
    return notes, rate, months_left


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
    if any(k in status for k in ("합병", "예비심사", "거래정지", "예심", "주총")):
        signal = "합병 진행"
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
    order = {"매도 신호": 0, "합병 진행": 1, "매수 후보": 2, "관망": 3}
    for a in res:
        row = next(r for r in rows if r["name"] == a["name"])
        notes, a["merger_rate"], a["months_left"] = merger_view(row, today, settings, held)
        a["why"] += notes
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
    lines.append("  합병 대응 원칙: 합병 진행 종목은 신규 매수 X · 보유분은 급등 시 매도, 합병상장 전 정리 또는 매수청구권")
    lines.append(f"  규칙: {cap_txt}해산까지 보유해도 연 {hurdle*100:.1f}% 이상인 가격 → 매수 후보,"
                 f" 매수가 +{cfg['target_gain']*100:.0f}% → 매도, 합병 발표 종목은 제외. 한 종목 최대 {cfg['max_per_spac_won']:,}원")
    text = "\n".join(lines)
    (BASE / "out").mkdir(exist_ok=True)
    (BASE / "out/listed.txt").write_text(text, encoding="utf-8")
    buy = sum(a["signal"] == "매수 후보" for a in res)
    sell = sum(a["signal"] == "매도 신호" for a in res)
    recent = [r for r in rows if r.get("status_date") and (today - date.fromisoformat(r["status_date"])).days <= 7]
    if recent:
        tag_m = f"합병공시 {len(recent)}"
    else:
        tag_m = ""
    tag = " · ".join(t for t in (tag_m, f"매도신호 {sell}" if sell else "", f"매수후보 {buy}" if buy else "") if t)
    (BASE / "out/listed_subject.txt").write_text(f"기존스팩 {tag}" if tag else "", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
