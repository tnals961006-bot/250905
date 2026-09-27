# 스팩 알림 루틴 실행 절차 (Claude가 매일 따르는 문서)

매 평일 아침 새 세션이 이 문서를 읽고 1~6단계를 수행한다.

## 0. 준비
```bash
git fetch origin claude/spac-investment-automation-hxefi4
git checkout claude/spac-investment-automation-hxefi4 && git pull
cd spac
```

## 1. 청약 예정 스팩 수집 → `data/candidates.json`
- 오늘부터 **14일 안에 일반청약하거나 상장하는** 스팩(기업인수목적회사)을 찾는다.
- 시도 순서: ① `curl`로 KIND 공모일정·DART 청약달력 → ② 막히면 WebSearch
  (예: "스팩 수요예측 결과 {이번달}", "스팩 청약 {이번주}", "스팩 상장 {다음주}").
- 종목마다 채울 값: `name, brokers(청약 가능한 주관·인수 증권사 목록, settings.json의 fees 표기와 같은 이름),
  subscription_start, subscription_end, listing_date, offer_size_eok, retail_shares(일반청약 배정 주식수),
  demand_ratio(수요예측 경쟁률), applicants(청약 마감 후 청약건수, 있으면), sources(URL 목록)`
- 계좌가 없는 증권사 스팩은 `calc.py`가 "계좌 개설 필요"로 표시한다. 청약 시작 **7일 이상 전**에 알아야 개설할 수 있으니 수요예측 공고 단계부터 수집한다.
- **규칙**
  - 기사·공시에서 확인한 값만 넣는다. 못 찾은 값은 넣지 않는다(키 생략).
  - 출처끼리 숫자가 다르면 넣지 않고 메일 본문 끝에 "출처 충돌: …"으로 적는다.
  - 이미 상장이 끝난 종목은 candidates에서 빼고 2단계로 넘긴다.

## 2. 상장 첫날 성과 기록 → `data/history.csv`
- 최근 3일 안에 상장한 스팩을 한 줄 추가(이미 있으면 빈칸만 보충). 컬럼은 파일 헤더를 따른다.
  - broker(대표주관사), offer_size_eok(공모규모 억원), open_price(시초가),
    early_price·early_time(기사에 나온 장 초반 가격과 시각), high_price, close_price,
    demand_ratio(수요예측), sub_ratio(일반청약 경쟁률)
- **equal_shares_per_person(1인당 균등배정 주식수)** 와 applicants(청약건수)는 가장 중요한 값이다. 청약 마감 뉴스나 증권사 공지에서 찾으면 꼭 기록한다.
- note에 불확실한 부분, source에 URL을 적는다. 출처가 충돌하면 비워둔다.

## 3. 계산
```bash
python3 calc.py
```
`out/subject.txt`가 비어 있으면 **메일을 보내지 않는다**(보낼 소식 없음).
단, 월요일은 비어 있어도 "이번 주 스팩 일정 없음 + 시장 분위기" 요약을 한 통 보낸다.

## 4. 메일 발송 (Gmail 커넥터)
- 받는 사람: `settings.json`의 `email_to`
- 제목: `out/subject.txt` (월요일 빈 경우 `[스팩알림] MM/DD 주간 요약`)
- 본문: `out/email.txt` 그대로 + 맨 아래에 이번 조사에서 확인 못 한 값·출처 충돌 목록
- 숫자를 임의로 고치거나 추측값을 넣지 않는다.

## 5. 저장
```bash
git add data && git commit -m "spac: $(date +%F) 데이터 갱신" && git push -u origin claude/spac-investment-automation-hxefi4
```
변경이 없으면 커밋하지 않는다.

## 6. 문제 발생 시
검색 결과가 없거나 계산이 실패하면, 메일 제목을 `[스팩알림] 점검 필요`로 하고 원인을 짧게 적어 보낸다.
