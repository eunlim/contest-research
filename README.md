# 공모전 아이디어 리서치 시스템

공공데이터, 정책제안, 창업, ESG, 마케팅, 서비스기획 등
**모든 공모전 유형**에서 재사용할 수 있는 아이디어 자동 생성·점수화 시스템입니다.
주제와 공모전 유형을 입력하면 Claude AI가 아이디어 5개를 생성하고
결과를 파일과 Google Sheets에 자동 저장합니다.

---

## 폴더 구조

```
contest-research/
├── README.md                        # 이 파일 (사용 안내)
├── run_pipeline.py                  # 자동 리서치 실행 스크립트
├── requirements.txt                 # Python 패키지 목록
├── .env.example                     # 환경변수 설정 예시
├── credentials/
│   ├── oauth.json                   # Google OAuth 클라이언트 키
│   └── token.json                   # 로그인 후 자동 생성 — 건드리지 마세요
├── prompts/
│   ├── research_prompt.md           # 수동 리서치용 프롬프트 모음 (전 유형 공용)
│   └── contest_idea_prompt.md       # 공모전 기획 전문가 프롬프트
├── outputs/                         # 자동 생성된 MD/JSON 결과물 저장
└── data/
    └── ideas_master.csv             # 전체 아이디어 누적 관리 시트
```

---

## 지원하는 공모전 유형

| 유형 | 핵심 심사 기준 | 생성 아이디어 방향 |
|------|-------------|----------------|
| 공공데이터 | 데이터 활용 창의성, 시각화 완성도 | 공개 데이터 출처와 분석 방법 구체화 |
| 정책제안 | 실현 가능성, 정책 파급력 | 담당 부처·법령 근거 포함 |
| 창업 | 시장성, 비즈니스 모델 | 타깃 고객·수익 구조 명확화 |
| ESG | 측정 가능한 임팩트 | 환경·사회 지표 수치화 |
| 마케팅·브랜딩 | 타깃 명확성, 실행력 | 채널·예산·타임라인 구체화 |
| 서비스기획 | UX 완성도, 사용자 검증 | 핵심 기능과 차별화 가치 제안 |

---

## 자동 파이프라인 실행법 (run_pipeline.py)

### 0단계: Python 설치 확인

```
python --version
```

Python 3.9 이상이면 됩니다. 없다면 python.org 에서 설치하세요.

---

### 1단계: 패키지 설치

```
pip install -r requirements.txt
```

---

### 2단계: 환경변수 설정

`.env.example` 파일을 복사해 `.env` 파일을 만드세요.

```
copy .env.example .env
```

메모장으로 `.env` 를 열어 Claude API 키를 입력하세요.

```
ANTHROPIC_API_KEY=sk-ant-여기에_키_입력
```

> Claude API 키 발급: https://console.anthropic.com

---

### 3단계: 파이프라인 실행

**방법 A — 대화형 입력 (초보자 추천):**
```
python run_pipeline.py
```
주제 → 공모전 유형 → 공모전명 순서로 물어봅니다.

**방법 B — 주제만 인수로 전달 (유형은 대화형):**
```
python run_pipeline.py "청년 1인가구 고립 문제"
```

**방법 C — 주제 + 유형 함께 전달:**
```
python run_pipeline.py "MZ세대 친환경 소비" "마케팅·브랜딩"
```

---

### 4단계: 결과 확인

실행이 끝나면 `outputs/` 폴더에 두 파일이 생깁니다.

```
outputs/
└── 2026-04-21_정책제안_청년_1인가구_고립_문제.md
└── 2026-04-21_정책제안_청년_1인가구_고립_문제.json
```

파일명 형식: `날짜_공모전유형_주제슬러그`

---

### (선택) Google Sheets 자동 업로드 설정

`credentials/oauth.json` 이 이미 있다면 **③번부터** 시작하세요.

---

**① Google Cloud에서 OAuth 클라이언트 키 발급**

1. https://console.cloud.google.com 접속
2. 새 프로젝트 생성
3. `API 및 서비스` → `라이브러리` → `Google Sheets API` 활성화
4. `사용자 인증 정보` → `OAuth 클라이언트 ID` → **데스크톱 앱** 선택
5. JSON 다운로드 → `credentials/oauth.json` 으로 저장

> 처음이라면 `OAuth 동의 화면` → `외부` 선택 → 앱 이름·이메일 입력 후 저장

---

**② 스프레드시트 준비**

1. https://sheets.google.com 에서 새 스프레드시트 생성
2. 첫 번째 시트 이름을 `ideas` 로 변경
3. URL에서 ID 복사: `https://docs.google.com/spreadsheets/d/【여기】/edit`

---

**③ .env 에 ID 입력**

```
GOOGLE_SHEET_ID=복사한_ID
```

---

**④ 최초 실행 시 브라우저 로그인**

처음 실행하면 브라우저가 자동으로 열립니다.
Google 계정 로그인 후 권한 허용 → `credentials/token.json` 자동 생성.
이후 실행부터는 로그인 없이 자동 연결됩니다.

---

**저장되는 컬럼 구조 (Sheets & ideas_master.csv)**

| contest_name | contest_type | topic | title | problem | target | solution | resource_or_data | novelty | feasibility | impact | differentiation | total | recommendation | created_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

---

## 수동 리서치 방법

`prompts/research_prompt.md` 를 열어 원하는 프롬프트를 복사합니다.
Claude 채팅에 붙여넣고 `[대괄호]` 안을 본인 주제로 채워 넣으세요.

---

## 예시 입력 3가지

### 예시 A — 공공데이터형

```
python run_pipeline.py "고령 운전자 교통사고 예방" "공공데이터"
```

주제를 분석해 교통안전 공공데이터 활용 아이디어 5개를 생성합니다.

---

### 예시 B — 정책제안형

```
python run_pipeline.py "청년 1인가구 고립 문제" "정책제안"
```

실현 가능성 중심의 청년 복지 정책 아이디어를 생성합니다.

---

### 예시 C — 마케팅·브랜딩형

```
python run_pipeline.py "MZ세대 친환경 소비 습관 형성" "마케팅·브랜딩"
```

타깃·채널·실행 계획까지 포함한 캠페인 아이디어를 생성합니다.

---

## 공모전 준비 체크리스트

- [ ] 공모전 유형 및 심사 기준 파악
- [ ] 주제 선정 및 문제 정의
- [ ] run_pipeline.py 로 아이디어 5개 자동 생성
- [ ] 최고 점수 아이디어 선정 및 심화 기획
- [ ] 필요한 자원·데이터 수집 → data/ 폴더에 저장
- [ ] 보고서 또는 발표자료 작성
- [ ] prompts/research_prompt.md 의 최종 점검 프롬프트로 검토

---

## 점수 항목 설명

| 항목 | 설명 | 만점 |
|------|------|------|
| novelty | 기존 접근 방식 대비 독창성·참신함 | 10 |
| feasibility | 주어진 자원·기간 내 구현 가능한 정도 | 10 |
| impact | 사회적·비즈니스적·정책적 파급력 | 10 |
| differentiation | 경쟁 아이디어 대비 뚜렷한 강점 | 10 |
| **total** | 위 4개 평균 | **10** |

---

## 팁

- 같은 주제도 공모전 유형을 바꾸면 전혀 다른 아이디어가 나옵니다. 여러 유형으로 실험해 보세요.
- `data/ideas_master.csv` 에 모든 결과가 누적되어 공모전별로 비교·관리할 수 있습니다.
- 크레딧이 부족하면 https://console.anthropic.com → Plans & Billing 에서 충전하세요.
