# 스팩 알림 루틴 실행 절차 (Claude가 매일 따르는 문서)

매 평일 아침 새 세션이 이 문서를 읽고 1~6단계를 수행한다.

## 0. 준비
```bash
git fetch origin claude/spac-investment-automation-hxefi4
git checkout claude/spac-investment-automation-hxefi4 && git pull
cd spac
```

## 1. 청약 예정 스팩 수집 → `data/candidates.json`
- **모든 스팩 일정**을 점검한다: 오늘부터 **30일 안에** 수요예측·일반청약·상장이 있는 스팩, 그리고 최근 증권신고서를 낸 스팩(일정 미정 포함).
  - 청약 7일 전 이상이면 "예고", 7일 이내면 "추천/비추천 판정", 상장 2일 이내면 "매도 준비"로 메일에 구분해 적는다.
  - 판정은 calc.py 등급(A/B/C/?)과 이유를 그대로 쓰고, 계좌 없는 증권사면 개설 필요 여부를 맨 위에 적는다.
- 시도 순서: ⓪ 환경변수 `OPENDART_API_KEY`가 있으면 OpenDART로 최근 45일 발행공시(증권신고서) 중 회사명에 "스팩" 또는 "기업인수목적"이 들어간 건을 조회한다
  (`curl -s "https://opendart.fss.or.kr/api/list.json?crtfc_key=$OPENDART_API_KEY&bgn_de=YYYYMMDD&end_de=YYYYMMDD&pblntf_ty=C&page_count=100"` → `corp_name`, `report_nm`, `rcept_no` 확인.
  키 값은 절대 출력·커밋·메일에 넣지 않는다) → ① `curl`로 KIND 공모일정·DART 청약달력 → ② 막히면 WebSearch
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
- 같은 스팩의 **시각이 적힌 가격**("오전 9시 15분 기준 ○○원", 시초가, 종가, 고가)은 `data/intraday.csv`에 한 줄씩 추가한다. `python3 timing.py`로 시간대별 표가 갱신된다.

## 2-1. 기존 상장 스팩 점검 → `data/listed.csv`
- `python3 listed.py --fetch` 로 현재가를 갱신한다(네이버 증권, `m.stock.naver.com` 접속 필요). 실패한 종목은 WebSearch로 "종목명 주가"를 찾아 price·price_date를 채운다(찾은 날짜를 정확히 기록).
- 목록에 없는 상장 스팩(국내 약 70개)을 KIND 스팩 현황·DART에서 찾아 **한 번에 10개씩** 추가한다. code(6자리), listing_date 필수.
- trust_rate(예치이율)는 각 스팩 증권신고서의 "예치 이율"에서 찾아 기록한다. 모르면 비워둔다(기본값 가정으로 계산됨).
- status: 합병 상대 공시(합병 결의·예비심사 청구·거래정지)가 있으면 "합병 결의" 등으로, 존립기한 관련 관리종목이면 "관리종목"으로 적는다.
- `data/holdings.csv`는 사용자가 알려준 보유 내역만 적는다(추측 금지).

## 3. 계산
```bash
python3 calc.py
```
그다음 `python3 listed.py` 를 실행하고, 메일 본문 뒤에 `out/listed.txt`를 붙인다.
제목은 `out/subject.txt`와 `out/listed_subject.txt`를 " · "로 이어 붙인다(둘 다 비면 `[스팩알림] MM/DD 기존스팩 …` 형식 없이 생략).
두 제목 파일이 모두 비어 있으면 **메일을 보내지 않는다**(보낼 소식 없음).
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
