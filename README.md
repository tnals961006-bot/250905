# 교육 블로그 작업실

중학교 과학 교육 · AI 교육 · 서울 교육을 주제로 한 블로그 글을 **유형(템플릿) 기반**으로 기획·작성하는 저장소.

## 폴더 구조
```
guides/
  01-benchmark-analysis.md   # 참고 블로그 유형 분석
  02-post-types.md           # 글 유형 7가지 + 주제×유형 매트릭스 + 운영 리듬
  03-image-guide.md          # 폰 사진/AI 이미지 사용 규칙, 프롬프트 공식
templates/                   # T1~T7 채워 쓰는 템플릿
posts/
  drafts/                    # 작성 중
  published/                 # 발행 완료 (발행 URL 기록)
images/
  phone/<글-슬러그>/         # 휴대폰 사진 업로드 위치
  generated/                 # AI 생성 이미지
ideas.md                     # 글감 백로그
```

## 글 하나 쓰는 흐름
1. `ideas.md`에서 글감 선택 → `02-post-types.md`로 유형 결정
2. Claude에게: "T1으로 ○○ 수업 글 초안 써줘" + 메모/사진 전달
3. 사진은 `images/phone/<슬러그>/`에 업로드 (학생 얼굴·이름 가림 확인)
4. 초안 검토 → 🟡 표시 부분을 실제 경험으로 채우기 → 발행
5. 발행 후 `posts/published/`로 이동, 반응(조회수·댓글) 메모 → 유형 개선
