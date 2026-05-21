import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime

# ===== 설정 =====
SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"
FOLDER_ID = "1XNE_HmkcHQhxSusMfwzkXh80dPVFiQJd"
THUMB_RANGE = 5  # 현재 기준 앞뒤 몇 장씩 보여줄지

# ===== 구글 연결 =====
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
    drive_client = build("drive", "v3", credentials=creds)
    spreadsheet = sheet_client.open_by_key(SPREADSHEET_ID)

    try:
        raw_sheet = spreadsheet.worksheet("raw")
    except:
        raw_sheet = spreadsheet.add_worksheet(title="raw", rows=1000, cols=50)

    try:
        summary_sheet = spreadsheet.worksheet("집계")
    except:
        summary_sheet = spreadsheet.add_worksheet(title="집계", rows=1000, cols=10)

    return raw_sheet, summary_sheet, drive_client

# ===== 드라이브 폴더에서 이미지 자동 로드 =====
@st.cache_data(ttl=60)
def get_images_from_drive():
    _, __, drive = get_services()
    results = drive.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType contains 'image/' and trashed=false",
        fields="files(id, name)",
        orderBy="name"
    ).execute()
    return results.get("files", [])

# ===== 결과 저장 함수 (덮어쓰기) =====
def save_result(judge_name, file_name, result):
    raw_sheet, summary_sheet, _ = get_services()
    data = raw_sheet.get_all_values()

    if not data:
        raw_sheet.append_row(["파일명"])
        data = [["파일명"]]

    headers = data[0]

    if judge_name not in headers:
        headers.append(judge_name)
        col_index = len(headers)
        raw_sheet.update_cell(1, col_index, judge_name)
    else:
        col_index = headers.index(judge_name) + 1

    file_names = [row[0] for row in data[1:]] if len(data) > 1 else []
    if file_name not in file_names:
        row_index = len(data) + 1
        raw_sheet.update_cell(row_index, 1, file_name)
    else:
        row_index = file_names.index(file_name) + 2

    raw_sheet.update_cell(row_index, col_index, result)
    update_summary(raw_sheet, summary_sheet)

# ===== 집계 시트 업데이트 =====
def update_summary(raw_sheet, summary_sheet):
    data = raw_sheet.get_all_values()
    if not data or len(data) < 2:
        return

    summary_sheet.clear()
    summary_sheet.append_row(["파일명", "합격수", "불합격수", "총심사수", "최종결과"])

    for row in data[1:]:
        if not row[0]:
            continue
        file_name = row[0]
        votes = row[1:]
        pass_count = votes.count("합격")
        fail_count = votes.count("불합격")
        total = pass_count + fail_count
        if pass_count > fail_count:
            final = "합격"
        elif fail_count > pass_count:
            final = "불합격"
        else:
            final = "동점"
        summary_sheet.append_row([file_name, pass_count, fail_count, total, final])

# ===== 페이지 설정 =====
st.set_page_config(page_title="이미지 심사 시스템", layout="wide")
st.title("🚀 이미지 심사 시스템")

# ===== 이름 입력 화면 =====
if 'name' not in st.session_state:
    st.session_state.name = ""

if not st.session_state.name:
    st.subheader("👤 심사위원 이름을 입력해주세요")
    name_input = st.text_input("이름", placeholder="예: 홍길동")
    if st.button("심사 시작", use_container_width=True):
        if name_input.strip():
            st.session_state.name = name_input.strip()
            st.session_state.index = 0
            st.rerun()
        else:
            st.warning("이름을 입력해주세요!")
    st.stop()

# ===== 이미지 불러오기 =====
images = get_images_from_drive()

if not images:
    st.error("📁 드라이브 폴더에 이미지가 없거나 폴더 ID가 잘못되었습니다.")
    st.stop()

total_images = len(images)

if 'index' not in st.session_state:
    st.session_state.index = 0

# ===== 사이드바 썸네일 네비게이션 =====
with st.sidebar:
    st.caption(f"심사위원: {st.session_state.name}")
    st.write("---")
    st.caption("📸 사진 목록 (클릭해서 이동)")

    start = max(0, st.session_state.index - THUMB_RANGE)
    end = min(total_images, st.session_state.index + THUMB_RANGE + 1)
    visible = images[start:end]

    for i, img in enumerate(visible):
        actual_index = start + i
        img_id = img["id"]
        is_current = actual_index == st.session_state.index

        border_color = "#FF4B4B" if is_current else "#ccc"
        st.markdown(
            f'''<img src="https://drive.google.com/thumbnail?id={img_id}&sz=w200"
            style="width:100%; border-radius:6px; border: 3px solid {border_color}; margin-bottom:4px;">
            <p style="text-align:center; font-size:11px; margin:0 0 4px 0;">{actual_index + 1}번</p>''',
            unsafe_allow_html=True
        )
        if st.button(f"{'👉 ' if is_current else ''}{actual_index + 1}번으로 이동",
                     key=f"thumb_{actual_index}",
                     use_container_width=True):
            st.session_state.index = actual_index
            st.rerun()
        st.write("")

# ===== 메인 심사 화면 =====
if st.session_state.index < total_images:
    current_num = st.session_state.index + 1
    current_file = images[st.session_state.index]
    current_id = current_file["id"]
    current_name = current_file["name"]

    st.subheader(f"📊 심사 중: {current_num}번째 / 총 {total_images}장")

    st.markdown(
        f'<img src="https://drive.google.com/thumbnail?id={current_id}&sz=w1200" style="width:100%; border-radius:8px;">',
        unsafe_allow_html=True
    )
    st.caption(f"파일명: {current_name}")
    st.write("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ 합격", use_container_width=True):
            save_result(st.session_state.name, current_name, "합격")
            st.session_state.index += 1
            st.rerun()

    with col2:
        if st.button("❌ 불합격", use_container_width=True):
            save_result(st.session_state.name, current_name, "불합격")
            st.session_state.index += 1
            st.rerun()

    with col3:
        if st.button("⬅️ 이전으로", use_container_width=True):
            if st.session_state.index > 0:
                st.session_state.index -= 1
                st.rerun()
            else:
                st.warning("첫 번째 이미지입니다!")

else:
    st.balloons()
    st.success("🎉 모든 이미지를 심사했습니다! 수고하셨습니다.")
    if st.button("🔄 처음부터 다시하기", use_container_width=True):
        st.session_state.index = 0
        st.rerun()
