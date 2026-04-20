#!/usr/bin/env python3
"""
공모전 아이디어 자동 리서치 파이프라인
공공데이터 / 정책제안 / 창업 / ESG / 마케팅 / 서비스기획 등 모든 유형 지원

사용법:
    python run_pipeline.py                          # 대화형 입력
    python run_pipeline.py "청년 고립 문제"          # 주제만 입력 (유형은 대화형)
    python run_pipeline.py "청년 고립 문제" 정책제안  # 주제 + 유형 함께 입력

흐름:
    1. 공모전 유형 + 주제 입력
    2. Claude API → 아이디어 5개 생성 + 점수화
    3. outputs/ 에 MD / JSON 저장
    4. Google Sheets에 행 append  (최초 실행 시 브라우저 로그인 필요)
"""

import os
import sys
import json
import datetime
from pathlib import Path

from dotenv import load_dotenv
import anthropic

load_dotenv()

# ── 경로 ─────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
OUTPUTS_DIR     = BASE_DIR / "outputs"
CREDENTIALS_DIR = BASE_DIR / "credentials"
OAUTH_FILE      = CREDENTIALS_DIR / "oauth.json"
TOKEN_FILE      = CREDENTIALS_DIR / "token.json"

# ── 환경변수 ─────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_SHEET_ID   = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME        = os.getenv("SHEET_NAME", "ideas")

# Google Sheets API 스코프
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Sheets 헤더 — ideas_master.csv 와 동일한 컬럼 순서
SHEET_HEADERS = [
    "contest_name", "contest_type", "topic", "title", "problem", "target",
    "solution", "resource_or_data",
    "novelty", "feasibility", "impact", "differentiation",
    "total", "recommendation", "created_at",
]

# 지원하는 공모전 유형 목록
CONTEST_TYPES = [
    "공공데이터",
    "정책제안",
    "창업",
    "ESG",
    "마케팅·브랜딩",
    "서비스기획",
    "기타",
]


# ─────────────────────────────────────────────────────────────
# Google OAuth 인증
# ─────────────────────────────────────────────────────────────
def get_sheets_service():
    """
    credentials/token.json 이 있으면 재사용하고,
    없거나 만료됐으면 브라우저 로그인 후 token.json 저장.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ImportError(
            f"Google 관련 패키지가 없습니다: {e}\n"
            "  pip install -r requirements.txt  를 실행해 주세요."
        ) from e

    if not OAUTH_FILE.exists():
        raise FileNotFoundError(
            f"OAuth 클라이언트 파일을 찾을 수 없습니다: {OAUTH_FILE}\n"
            "  credentials/oauth.json 파일이 있는지 확인해 주세요."
        )

    creds = None

    # 저장된 토큰 불러오기
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            creds = None  # 파일 손상 시 재로그인

    # 토큰 없음 or 만료
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("  토큰 갱신 중...")
            creds.refresh(Request())
        else:
            print("  브라우저에서 Google 계정 로그인이 필요합니다.")
            print("  잠시 후 브라우저가 자동으로 열립니다...\n")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(OAUTH_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 토큰 저장 (다음 실행부터 재사용)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        print(f"  토큰 저장 완료: {TOKEN_FILE}")

    return build("sheets", "v4", credentials=creds)


# ─────────────────────────────────────────────────────────────
# 1단계: Claude API로 아이디어 생성
# ─────────────────────────────────────────────────────────────
def generate_ideas(topic: str, contest_type: str, contest_name: str = "") -> dict:
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            ".env 파일에 ANTHROPIC_API_KEY가 설정되지 않았습니다.\n"
            "  .env.example 을 복사해 .env 를 만들고 키를 입력해 주세요."
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # 유형별 심사 기준 힌트
    type_hints = {
        "공공데이터":    "데이터 활용 창의성과 분석 완성도를 강조하세요. 공개 데이터 출처를 구체적으로 명시하세요.",
        "정책제안":      "실현 가능성과 정책 파급력을 강조하세요. 담당 부처·법령 근거를 포함하세요.",
        "창업":          "시장성과 수익 구조를 강조하세요. 타깃 고객과 비즈니스 모델을 명확히 정의하세요.",
        "ESG":           "측정 가능한 환경·사회적 임팩트를 강조하세요. 그린워싱으로 오해받지 않도록 구체적 수치를 포함하세요.",
        "마케팅·브랜딩": "타깃 명확성과 캠페인 실행력을 강조하세요. 채널·예산·타임라인을 구체화하세요.",
        "서비스기획":    "사용자 경험(UX)과 사용자 검증 여부를 강조하세요. 핵심 기능과 차별화된 가치 제안을 명확히 하세요.",
        "기타":          "실현 가능성과 참신성의 균형을 맞추세요.",
    }
    hint = type_hints.get(contest_type, type_hints["기타"])

    system_prompt = (
        f"당신은 {contest_type} 공모전 전문 아이디어 기획자입니다. "
        "주어진 주제에 대해 수상 가능성이 높은 아이디어 5개를 생성하고 점수화합니다. "
        "반드시 아래 JSON 형식으로만 응답하고, 다른 텍스트는 절대 포함하지 마세요."
    )

    user_prompt = f"""공모전 유형: {contest_type}
주제: {topic}
{f"공모전명: {contest_name}" if contest_name else ""}

전략 힌트: {hint}

다음 JSON 형식으로 아이디어 5개를 생성해 주세요.

{{
  "contest_name": "{contest_name}",
  "contest_type": "{contest_type}",
  "topic": "{topic}",
  "ideas": [
    {{
      "id": 1,
      "title": "아이디어 제목",
      "problem": "핵심 문제를 한 문장으로",
      "target": "수혜자 또는 고객 (구체적으로)",
      "solution": "해결 방식을 2~3문장으로",
      "resources": ["필요한 자원·데이터1", "자원·데이터2", "자원·데이터3"],
      "insights": ["기대 효과 또는 인사이트1", "기대 효과2"],
      "strengths": ["공모전 심사 강점1", "강점2"],
      "scores": {{
        "novelty": 8,
        "feasibility": 9,
        "impact": 8,
        "differentiation": 9
      }}
    }}
  ]
}}

점수 기준 (각 1~10점 정수):
- novelty: 기존 접근 방식 대비 독창성·참신함
- feasibility: 주어진 자원·기간 내 실제 구현 가능한 정도
- impact: 사회적·비즈니스적·정책적 파급력
- differentiation: 경쟁 아이디어 대비 뚜렷이 구별되는 강점"""

    print("  Claude API 호출 중...", flush=True)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.AuthenticationError:
        raise ValueError(
            "Claude API 인증 실패: ANTHROPIC_API_KEY 가 올바르지 않습니다.\n"
            "  https://console.anthropic.com 에서 키를 확인해 주세요."
        )
    except anthropic.BadRequestError as e:
        msg = str(e)
        if "credit balance is too low" in msg:
            raise ValueError(
                "Claude API 크레딧이 부족합니다.\n"
                "  https://console.anthropic.com → Plans & Billing 에서 크레딧을 충전해 주세요."
            )
        raise ValueError(f"Claude API 요청 오류: {e}")
    except anthropic.APIConnectionError:
        raise ConnectionError(
            "Claude API 서버에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요."
        )

    raw = message.content[0].text.strip()

    # 마크다운 코드블록 제거 (```json ... ``` 형태)
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Claude 응답을 JSON으로 파싱할 수 없습니다: {e}\n"
            f"  응답 원문 (앞 200자): {raw[:200]}"
        )

    data["generated_at"] = datetime.date.today().isoformat()

    # total 계산 및 recommendation 초기화
    for idea in data["ideas"]:
        s = idea["scores"]
        s["total"] = round(
            (s["novelty"] + s["feasibility"] + s["impact"] + s["differentiation"]) / 4,
            2,
        )
        idea["recommendation"] = False

    # 최고 total 점수에 recommendation = True
    best = max(data["ideas"], key=lambda x: x["scores"]["total"])
    best["recommendation"] = True

    return data


# ─────────────────────────────────────────────────────────────
# 2단계: outputs/ 폴더에 MD + JSON 저장
# ─────────────────────────────────────────────────────────────
def save_outputs(data: dict, topic: str) -> tuple:
    contest_type = data.get("contest_type", "기타")
    type_slug = contest_type.replace("·", "").replace("/", "").replace(" ", "")[:10]
    topic_slug = topic.strip().replace(" ", "_")[:25]
    date_str = data["generated_at"]
    base_name = f"{date_str}_{type_slug}_{topic_slug}"

    json_path = OUTPUTS_DIR / f"{base_name}.json"
    md_path   = OUTPUTS_DIR / f"{base_name}.md"

    # ── JSON ──
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Markdown ──
    contest_name = data.get("contest_name", "")
    md_lines = [
        "# 공모전 아이디어 리서치 결과\n",
        f"- **공모전명**: {contest_name}" if contest_name else "",
        f"- **공모전 유형**: {contest_type}",
        f"- **주제**: {data['topic']}",
        f"- **생성일**: {data['generated_at']}",
        "- **생성 모델**: claude-sonnet-4-6\n",
        "---\n",
    ]
    md_lines = [l for l in md_lines if l != ""]  # 빈 줄 제거

    for idea in data["ideas"]:
        s        = idea["scores"]
        rec_tag  = " ★ BEST" if idea["recommendation"] else ""
        md_lines += [
            f"## 아이디어 {idea['id']}. {idea['title']}{rec_tag}\n",
            f"**문제 정의**: {idea['problem']}\n",
            f"**타겟**: {idea['target']}\n",
            f"**해결 방식**: {idea['solution']}\n",
            "**필요한 자원/데이터**",
            *[f"- {r}" for r in idea.get("resources", [])],
            "",
            "**기대 효과**",
            *[f"- {i}" for i in idea.get("insights", [])],
            "",
            "**공모전 강점**",
            *[f"- {st}" for st in idea.get("strengths", [])],
            "",
            "| 독창성(novelty) | 실현가능성(feasibility) | 파급력(impact) | 차별성(differentiation) | **총점** |",
            "|----------------|----------------------|--------------|----------------------|---------|",
            f"| {s['novelty']} | {s['feasibility']} | {s['impact']} | {s['differentiation']} | **{s['total']}** |\n",
            "---\n",
        ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return json_path, md_path


# ─────────────────────────────────────────────────────────────
# 3단계: Google Sheets에 append
# ─────────────────────────────────────────────────────────────
def upload_to_sheets(data: dict):
    if not GOOGLE_SHEET_ID:
        print("  [건너뜀] .env 에 GOOGLE_SHEET_ID 가 설정되지 않았습니다.")
        return

    print("  Google 인증 확인 중...")
    service = get_sheets_service()
    sheets  = service.spreadsheets()

    # ── 시트가 비어 있으면 헤더 행 추가 ──
    result = (
        sheets.values()
        .get(spreadsheetId=GOOGLE_SHEET_ID, range=f"{SHEET_NAME}!A1:A1")
        .execute()
    )
    if not result.get("values"):
        sheets.values().append(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [SHEET_HEADERS]},
        ).execute()
        print(f"  헤더 행 추가 완료: {SHEET_HEADERS}")

    # ── 데이터 행 구성 ──
    rows = []
    for idea in data["ideas"]:
        s = idea["scores"]
        rows.append([
            data.get("contest_name", ""),
            data.get("contest_type", ""),
            data["topic"],
            idea["title"],
            idea["problem"],
            idea["target"],
            idea.get("solution", ""),
            "; ".join(idea.get("resources", [])),  # resource_or_data: 세미콜론 구분
            s["novelty"],
            s["feasibility"],
            s["impact"],
            s["differentiation"],
            s["total"],
            "YES" if idea["recommendation"] else "NO",
            data["generated_at"],
        ])

    sheets.values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    print(f"  {len(rows)}행 추가 완료 → 시트: {SHEET_NAME}")


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
def main():
    # ── 입력: 주제 + 공모전 유형 ──
    if len(sys.argv) >= 3:
        topic        = sys.argv[1].strip()
        contest_type = sys.argv[2].strip()
    elif len(sys.argv) == 2:
        topic        = sys.argv[1].strip()
        contest_type = ""
    else:
        topic        = input("분석 주제를 입력하세요 (예: 청년 1인가구 고립 문제): ").strip()
        contest_type = ""

    if not topic:
        print("오류: 주제를 입력해주세요.")
        sys.exit(1)

    # 유형 선택 (대화형)
    if not contest_type:
        print("\n공모전 유형을 선택하세요:")
        for i, t in enumerate(CONTEST_TYPES, 1):
            print(f"  {i}. {t}")
        choice = input("번호 입력 (기본값: 7. 기타): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(CONTEST_TYPES):
            contest_type = CONTEST_TYPES[int(choice) - 1]
        else:
            contest_type = "기타"

    contest_name = input("공모전명을 입력하세요 (없으면 Enter 건너뜀): ").strip()

    print(f"\n{'='*52}")
    print(f"  공모전 유형: {contest_type}")
    if contest_name:
        print(f"  공모전명   : {contest_name}")
    print(f"  주제       : {topic}")
    print(f"{'='*52}\n")

    # ── 1단계: 아이디어 생성 ──
    print("[1/3] Claude API로 아이디어 생성 중...")
    try:
        data = generate_ideas(topic, contest_type, contest_name)
    except (ValueError, ConnectionError) as e:
        print(f"\n[오류] {e}")
        sys.exit(1)

    print(f"  완료: {len(data['ideas'])}개 아이디어 생성\n")

    print("  ┌─ 점수 요약 " + "─" * 40)
    for idea in data["ideas"]:
        s       = idea["scores"]
        rec_tag = "  ← BEST" if idea["recommendation"] else ""
        short   = idea["title"][:36] + ("..." if len(idea["title"]) > 36 else "")
        print(f"  │ {idea['id']}. {short:<40} 총점: {s['total']:4}{rec_tag}")
    print("  └" + "─" * 51)

    # ── 2단계: 파일 저장 ──
    print("\n[2/3] outputs/ 폴더에 저장 중...")
    try:
        json_path, md_path = save_outputs(data, topic)
        print(f"  저장: {json_path.name}")
        print(f"  저장: {md_path.name}")
    except OSError as e:
        print(f"  [오류] 파일 저장 실패: {e}")
        sys.exit(1)

    # ── 3단계: Google Sheets 업로드 ──
    print("\n[3/3] Google Sheets 업로드 중...")
    try:
        upload_to_sheets(data)
    except FileNotFoundError as e:
        print(f"  [오류] {e}")
        print("  (로컬 파일은 정상 저장되었습니다)")
    except ImportError as e:
        print(f"  [오류] {e}")
        print("  (로컬 파일은 정상 저장되었습니다)")
    except Exception as e:
        print(f"  [오류] Google Sheets 업로드 실패: {e}")
        print("  (로컬 파일은 정상 저장되었습니다)")

    print(f"\n{'='*52}")
    print("  완료!")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
