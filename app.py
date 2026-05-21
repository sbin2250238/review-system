import streamlit as st
import gspread
import pandas as pd

from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# =========================================================
# 설정
# =========================================================

SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"

FOLDERS = {
    "사진": "1XNE_HmkcHQhxSusMfwzkXh80dPVFiQJd",
    "영상": "1baVZLTFNhL0AWuK4DpIbcJU7lU70wHtf"
}

THUMB_RANGE = 5

# =========================================================
# 구글 연결
# =========================================================

@st.cache_resource
def get_services():

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )

    sheet_client = gspread.authorize(creds)

    drive_client = build(
        "drive",
        "v3",
        credentials=creds
    )

    spreadsheet = sheet_client.open_by_key(
        SPREADSHEET_ID
    )

    return drive_client, spreadsheet


def get_or_create_sheet(spreadsheet, title):

    try:
        return spreadsheet.worksheet(title)

    except:
        return spreadsheet.add_worksheet(
            title=title,
            rows=5000,
            cols=20
        )

# =========================================================
# 드라이브 파일 로드
# =========================================================

@st.cache_data(ttl=30)
def get_files_from_drive(folder_id, category):

    drive_client, _ = get_services()

    if category == "사진":
        mime_query = "mimeType contains 'image/'"

    else:
        mime_query = "mimeType contains 'video/'"

    results = drive_client.files().list(
        q=f"'{folder_id}' in parents and {mime_query} and trashed=false",
        fields="files(id,name,mimeType)",
        orderBy="name"
    ).execute()

    return results.get("files", [])

# =========================================================
# 저장
# =========================================================

def save_result(
    judge_name,
    file_id,
    file_name,
    result,
    category
):

    _, spreadsheet = get_services()

    log_sheet = get_or_create_sheet(
        spreadsheet,
        "심사로그"
    )

    if not log_sheet.get_all_values():

        log_sheet.append_row([
            "시간",
            "심사위원",
            "파일ID",
            "파일명",
            "결과",
            "부문"
        ])

    log_sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        judge_name,
        file_id,
        file_name,
        result,
        category
    ])

    update_summary(spreadsheet)

# =========================================================
# 집계
# =========================================================

def update_summary(spreadsheet):

    log_sheet = get_or_create_sheet(
        spreadsheet,
        "심사로그"
    )

    summary_sheet = get_or_create_sheet(
        spreadsheet,
        "최종집계"
    )

    records = log_sheet.get_all_records()

    if not records:
        return

    df = pd.DataFrame(records)

    if df.empty:
        return

    df = df.sort_values("시간")

    latest = df.drop_duplicates(
        subset=["심사위원", "파일ID"],
        keep="last"
    )

    grouped = (
        latest.groupby(
            ["부문", "파일명", "결과"]
        )
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    if "합격" not in grouped.columns:
        grouped["합격"] = 0

    if "불합격" not in grouped.columns:
        grouped["불합격"] = 0

    grouped["총심사수"] = (
        grouped["합격"] +
        grouped["불합격"]
    )

    grouped = grouped[
        [
            "부문",
            "파일명",
            "합격",
            "불합격",
            "총심사수"
        ]
    ]

    summary_sheet.clear()

    summary_sheet.update(
        "A1",
        [
            grouped.columns.tolist()
        ] + grouped.values.tolist()
    )

# =========================================================
# 페이지
# =========================================================

st.set_page_config(
    page_title="사진/영상 심사 시스템",
    layout="wide"
)

st.title("🚀 사진/영상 심사 시스템")

# =========================================================
# 세션
# =========================================================

if "name" not in st.session_state:
    st.session_state.name = ""

if "category" not in st.session_state:
    st.session_state.category = ""

if "index" not in st.session_state:
    st.session_state.index = 0

# =========================================================
# 이름 입력
# =========================================================

if not st.session_state.name:

    st.subheader("👤 심사위원 이름 입력")

    name_input = st.text_input(
        "이름",
        placeholder="예: 홍길동"
    )

    if st.button(
        "다음",
        use_container_width=True
    ):

        if name_input.strip():

            st.session_state.name = (
                name_input.strip()
            )

            st.rerun()

        else:
            st.warning("이름을 입력해주세요.")

    st.stop()

# =========================================================
# 부문 선택
# =========================================================

if not st.session_state.category:

    st.subheader("📂 부문 선택")

    for cat in FOLDERS:

        if st.button(
            f"{cat} 심사하기",
            use_container_width=True
        ):

            st.session_state.category = cat
            st.session_state.index = 0

            st.rerun()

    st.stop()

# =========================================================
# 파일 로드
# =========================================================

category = st.session_state.category

folder_id = FOLDERS[category]

files = get_files_from_drive(
    folder_id,
    category
)

if not files:

    st.error("파일이 없습니다.")
    st.stop()

total_files = len(files)

# =========================================================
# 사이드바
# =========================================================

with st.sidebar:

    st.caption(
        f"심사위원: {st.session_state.name}"
    )

    st.caption(
        f"부문: {category}"
    )

    if st.button(
        "🔀 부문 변경",
        use_container_width=True
    ):

        st.session_state.category = ""
        st.session_state.index = 0

        st.rerun()

    st.write("---")

    st.caption("파일 목록")

    start = max(
        0,
        st.session_state.index - THUMB_RANGE
    )

    end = min(
        total_files,
        st.session_state.index + THUMB_RANGE + 1
    )

    visible = files[start:end]

    for i, file in enumerate(visible):

        actual_index = start + i

        file_id = file["id"]

        is_current = (
            actual_index ==
            st.session_state.index
        )

        image_url = (
            f"https://drive.google.com/thumbnail?id={file_id}&sz=w300"
        )

        st.image(
            image_url,
            use_container_width=True
        )

        button_text = (
            f"👉 {actual_index + 1}번"
            if is_current
            else f"{actual_index + 1}번"
        )

        if st.button(
            button_text,
            key=f"move_{actual_index}",
            use_container_width=True
        ):

            st.session_state.index = actual_index
            st.rerun()

        st.write("")

# =========================================================
# 현재 파일
# =========================================================

current = files[
    st.session_state.index
]

file_id = current["id"]
file_name = current["name"]
mime_type = current["mimeType"]

st.subheader(
    f"[{category}] "
    f"{st.session_state.index + 1}"
    f" / {total_files}"
)

# =========================================================
# 이미지 / 영상 표시
# =========================================================

if "video" in mime_type:

    video_url = (
        f"https://drive.google.com/uc?id={file_id}"
    )

    st.video(video_url)

else:

    image_url = (
        f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600"
    )

    st.image(
        image_url,
        use_container_width=True
    )

st.write(file_name)

st.write("---")

# =========================================================
# 버튼
# =========================================================

col1, col2, col3 = st.columns(3)

with col1:

    if st.button(
        "✅ 합격",
        use_container_width=True
    ):

        save_result(
            st.session_state.name,
            file_id,
            file_name,
            "합격",
            category
        )

        if st.session_state.index < total_files - 1:
            st.session_state.index += 1

        st.rerun()

with col2:

    if st.button(
        "❌ 불합격",
        use_container_width=True
    ):

        save_result(
            st.session_state.name,
            file_id,
            file_name,
            "불합격",
            category
        )

        if st.session_state.index < total_files - 1:
            st.session_state.index += 1

        st.rerun()

with col3:

    if st.button(
        "⬅️ 이전",
        use_container_width=True
    ):

        if st.session_state.index > 0:

            st.session_state.index -= 1
            st.rerun()

# =========================================================
# 완료
# =========================================================

if (
    st.session_state.index ==
    total_files - 1
):

    st.success(
        "마지막 파일입니다."
    )
