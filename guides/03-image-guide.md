# 이미지 가이드

## 1. 이미지 소스 선택

| 상황 | 추천 소스 |
|---|---|
| 실제 수업·실험·행사 | **내 휴대폰 사진** (가장 신뢰도 높음) |
| 도구 사용법 | 화면 캡처 (개인정보 가리기) |
| 개념 설명, 정책 해설, 썸네일 | **AI 생성 이미지** (Canva AI 등) |
| 표·그래프 | 직접 제작 (Canva / 구글 시트) |

## 2. 휴대폰 사진 → 블로그로 가져오는 방법

1. `images/phone/<글-슬러그>/` 폴더에 업로드 (GitHub 앱/웹 업로드, 또는 구글 드라이브 폴더 공유)
2. 파일명: `01-실험준비.jpg`, `02-모둠활동.jpg` 처럼 순서 + 내용
3. 올리면 Claude가 사진을 보고 → 글 흐름에 맞게 배치·캡션 작성

### 촬영 팁
- 가로 사진 위주(블로그 본문 폭에 맞음), 썸네일용 정사각 1장
- 손·실험도구·결과물 **클로즈업**이 얼굴 없는 좋은 사진
- 칠판/화면은 정면에서, 반사 피하기

### ⚠️ 개인정보 체크 (필수)
- 학생 **얼굴, 이름표, 명찰, 학교명, 교실 게시물의 이름** 가리기
- 학생 작품·글씨: 이름 가리고, 필요 시 동의
- 위치정보(EXIF GPS) 제거 — 업로드 전 휴대폰 설정에서 위치 태그 끄기 권장
- 학교 초상권·SNS 게시 동의 방침 확인

## 3. AI 이미지 생성 프롬프트 공식

```
[스타일], [주제/장면], [구성], [색감], [텍스트 없음], [비율]
```

### 채널 톤 (일관성용 기본값 — 논의 후 확정)
- 스타일: `flat vector illustration, clean, friendly, educational`
- 색감: `soft blue and mint green palette, white background`
- 공통: `no text, no logos, no real people faces`

### 유형별 예시
- T1 썸네일: `flat vector illustration of a middle school science classroom, students' hands doing an experiment with beakers, soft blue and mint palette, no text, 16:9`
- T3 정책: `isometric illustration of Seoul city skyline with a school building and a lightbulb, clean infographic style, soft blue palette, no text, 16:9`
- T6 과학: `cute educational illustration explaining <개념>, labeled-diagram style without text, pastel colors, 1:1`

### 표기
- 본문 이미지 캡션에 `(AI 생성 이미지)` 표기
