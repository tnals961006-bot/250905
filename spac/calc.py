"""스팩 균등배정 청약 분석기.

data/candidates.json(청약 예정 스팩) + data/history.csv(최근 스팩 상장 성과) + settings.json
→ 종목별 예상 배정주, 손익분기 상승률, 시나리오별 손익, 추천 등급을 계산해
  메일 본문(out/email.txt)과 제목(out/subject.txt)을 만든다.

외부 라이브러리 없이 동작한다.  사용: python3 calc.py [--today YYYY-MM-DD]
"""
import argparse
import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

BASE = Path(__file__).parent
SCENARIOS = [0.0, 0.1, 0.3, 0.5, 1.0]            # 첫날 매도가 상승률 시나리오
APPLICANT_SCENARIOS = [100_000, 200_000, 400_000]  # 청약건수 모를 때 가정


def load():
    settings = json.loads((BASE / "settings.json").read_text(encoding="utf-8"))
    candidates = json.loads((BASE / "data/candidates.json").read_text(encoding="utf-8"))
    with open(BASE / "data/history.csv", encoding="utf-8") as f:
        history = list(csv.DictReader(f))
    return settings, candidates, history


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def fee_for(cand, settings):
    """주관·인수 증권사 중 수수료가 가장 싼 곳 기준."""
    fees = settings["fees"]
    brokers = cand.get("brokers") or []
    known = [fees[b] for b in brokers if b in fees]
    return (min(known), True) if known else (fees["default"], False)


def profit(shares, sell_price, offer, fee, costs):
    """배정주 × 매도가 기준 순이익(원). 배정 0주면 수수료도 없음."""
    if shares <= 0:
        return 0.0
    gross = shares * (sell_price - offer)
    sell_cost = shares * sell_price * (costs["transaction_tax"] + costs["brokerage"])
    return gross - fee - sell_cost


def expected_profit(pool, applicants, r, offer, fee, costs):
    """1인 기대 배정주(추첨 포함)로 기대 순이익을 계산."""
    per = pool / applicants
    sell = offer * (1 + r)
    if per >= 1:
        return math.floor(per), profit(math.floor(per), sell, offer, fee, costs)
    # 1주도 안 돌아가면 추첨: 확률 per로 1주
    return per, per * profit(1, sell, offer, fee, costs)


def breakeven(shares, offer, fee, costs):
    """순이익 0이 되는 매도가 상승률."""
    if shares < 1:
        shares = 1
    c = costs["transaction_tax"] + costs["brokerage"]
    sell = (shares * offer + fee) / (shares * (1 - c))
    return sell / offer - 1


def market_mood(history, window):
    rows = sorted(history, key=lambda r: r["listing_date"], reverse=True)[:window]

    def avg(col):
        vals = [num(r[col]) / num(r["offer_price"]) - 1 for r in rows if num(r[col])]
        return (mean(vals), len(vals)) if vals else (None, 0)

    apps = [num(r["applicants"]) for r in rows if num(r["applicants"])]
    return {
        "n": len(rows),
        "open": avg("open_price"),
        "high": avg("high_price"),
        "close": avg("close_price"),
        "applicants_median": median(apps) if apps else None,
    }


def pct(x):
    return "미확인" if x is None else f"{x*100:+.1f}%"


def won(x):
    return f"{x:+,.0f}원"


def analyze(cand, settings, mood):
    offer = cand.get("offer_price") or settings["offer_price_default"]
    costs = settings["sell_costs"]
    g = settings["grading"]
    fee, fee_known = fee_for(cand, settings)
    retail = num(cand.get("retail_shares"))
    pool = retail * 0.5 if retail else None  # 일반청약 물량의 50% 이상이 균등

    applicants = num(cand.get("applicants")) or num(cand.get("expected_applicants")) \
        or mood["applicants_median"]
    app_note = "실제 청약건수" if num(cand.get("applicants")) else (
        "예상치" if applicants else None)

    out = {"name": cand["name"], "fee": fee, "fee_known": fee_known, "offer": offer,
           "pool": pool, "demand": num(cand.get("demand_ratio"))}

    scen_apps = [applicants] if applicants else APPLICANT_SCENARIOS
    out["alloc"] = []
    for n in scen_apps:
        if not pool:
            break
        shares, _ = expected_profit(pool, n, 0, offer, fee, costs)
        rows = [(r, expected_profit(pool, n, r, offer, fee, costs)[1]) for r in SCENARIOS]
        out["alloc"].append({"applicants": n, "shares": shares,
                             "breakeven": breakeven(shares, offer, fee, costs),
                             "rows": rows})
    out["app_note"] = app_note or "청약건수 미확인 → 가정 시나리오"

    # 등급: 최근 스팩 시초가 평균 상승률(기준 시나리오)에서 기대이익
    base_r = mood["open"][0]
    grade, reasons = "C", []
    if pool and base_r is not None:
        mid = out["alloc"][len(out["alloc"]) // 2]
        _, base_profit = expected_profit(pool, mid["applicants"], base_r, offer, fee, costs)
        out["base_profit"] = base_profit
        reasons.append(f"최근 스팩 시초가 평균 {pct(base_r)} 가정 시 기대이익 {won(base_profit)}")
        if base_profit >= g["min_profit_A"] and (out["demand"] or 0) >= g["demand_ratio_strong"]:
            grade = "A"
        elif base_profit > 0:
            grade = "B"
    else:
        reasons.append("일반청약 물량 또는 최근 시초가 데이터가 없어 등급 계산 불가")
        grade = "?"
    d = out["demand"]
    if d is None:
        reasons.append("수요예측 경쟁률 미확인")
    elif d >= g["demand_ratio_strong"]:
        reasons.append(f"수요예측 {d:,.0f}:1 강함")
    elif d < g["demand_ratio_weak"]:
        reasons.append(f"수요예측 {d:,.0f}:1 약함")
        if grade == "A":
            grade = "B"
    if not fee_known:
        reasons.append(f"청약수수료 기본값 {fee:,}원 적용🟡")
    out["grade"], out["reasons"] = grade, reasons
    return out


def render(settings, candidates, mood, today):
    lines, soon_sub, soon_list = [], [], []
    horizon = today + timedelta(days=7)
    for c in candidates:
        s = c.get("subscription_start")
        l = c.get("listing_date")
        if s and today <= date.fromisoformat(c.get("subscription_end") or s) <= horizon:
            soon_sub.append(c)
        if l and today <= date.fromisoformat(l) <= today + timedelta(days=2):
            soon_list.append(c)

    lines.append(f"[스팩 균등청약 알림] {today.isoformat()}")
    lines.append("")
    lines.append("■ 시장 분위기 (최근 스팩 상장 첫날, 공모가 대비)")
    for key, label in (("open", "시초가"), ("high", "장중고가"), ("close", "종가")):
        v, k = mood[key]
        lines.append(f"  - {label} 평균: {pct(v)} (표본 {k}건)")
    if mood["close"][0] is not None and mood["high"][0] is not None \
            and mood["high"][0] - mood["close"][0] > 0.5:
        lines.append("  ⚠ 고가 대비 종가가 크게 밀림 → '장 초반 매도'가 유리했던 흐름")
    lines.append("")

    results = []
    if soon_sub:
        lines.append("■ 7일 내 청약 스팩")
        for c in soon_sub:
            r = analyze(c, settings, mood)
            results.append(r)
            lines.append("")
            lines.append(f"▶ {r['name']}  [등급 {r['grade']}]")
            lines.append(f"  청약 {c.get('subscription_start')} ~ {c.get('subscription_end')}"
                         f" / 상장 {c.get('listing_date') or '미정'}"
                         f" / 증권사 {', '.join(c.get('brokers') or []) or '미확인'}")
            min_dep = settings["min_subscription_shares"] * r["offer"] // 2
            lines.append(f"  최소 증거금 {min_dep:,}원 (최소 {settings['min_subscription_shares']}주 × 증거금률 50%)")
            for why in r["reasons"]:
                lines.append(f"  · {why}")
            for a in r["alloc"]:
                sh = a["shares"]
                sh_txt = f"{sh}주" if sh >= 1 else f"추첨(확률 {sh*100:.0f}%로 1주)"
                lines.append(f"  - 청약 {a['applicants']:,.0f}건 가정({r['app_note']}): 균등 {sh_txt},"
                             f" 손익분기 {pct(a['breakeven'])}")
                lines.append("    " + " | ".join(f"{pct(x)}→{won(p)}" for x, p in a["rows"]))
            for src in c.get("sources", []):
                lines.append(f"  출처: {src}")
    else:
        lines.append("■ 7일 내 청약 예정 스팩 없음")

    if soon_list:
        lines.append("")
        lines.append("■ 곧 상장하는 스팩 (매도 준비)")
        for c in soon_list:
            lines.append(f"  - {c['name']}: 상장일 {c['listing_date']}")
        lines.append("  매도 팁: 최근 사례는 장중 고가 후 종가가 공모가 근처로 밀렸다.")
        lines.append("  미리 정한 규칙대로(예: 시초가 절반 + 9시 10분 전 나머지) 파는 것을 검토.")

    lines.append("")
    lines.append("※ 투자 권유 아님. 🟡=확인 필요 값. 숫자는 settings.json에서 조정.")
    return "\n".join(lines), soon_sub, soon_list, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=date.today().isoformat())
    args = ap.parse_args()
    today = date.fromisoformat(args.today)
    settings, candidates, history = load()
    mood = market_mood(history, settings["grading"]["recent_window"])
    body, subs, lists, results = render(settings, candidates, mood, today)

    grades = [r["grade"] for r in results]
    if subs or lists:
        tags = []
        if subs:
            tags.append(f"추천 {grades.count('A')}건" if "A" in grades else f"청약 {len(subs)}건")
        if lists:
            tags.append(f"상장임박 {len(lists)}건")
        subject = f"[스팩알림] {today:%m/%d} " + " · ".join(tags)
    else:
        subject = ""  # 보낼 소식 없음
    (BASE / "out").mkdir(exist_ok=True)
    (BASE / "out/email.txt").write_text(body, encoding="utf-8")
    (BASE / "out/subject.txt").write_text(subject, encoding="utf-8")
    print(subject or "(보낼 알림 없음)")
    print(body)


if __name__ == "__main__":
    main()
