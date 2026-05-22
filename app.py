import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ===== 설정 =====
SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"
FOLDER_ID = "1XNE_HmkcHQhxSusMfwzkXh80dPVFiQJd"
SHEET_NAME = "사진"
THUMB_RANGE = 5

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
    return sheet_client, drive_client, spreadsheet

def get_or_create_sheet(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except:
        return spreadsheet.add_worksheet(title=title, rows=1000, cols=50)

# ===== 드라이브 폴더에서 파일 로드 =====
@st.cache_data(ttl=60)
def get_files_from_drive():
    _, drive_client, __ = get_services()
    results = drive_client.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType contains 'image/' and trashed=false",
        fields="files(id, name)",
        orderBy="name"
    ).execute()
    return results.get("files", [])

# ===== 결과 저장 =====
def save_result(judge_name, file_name, result):
    _, __, spreadsheet = get_services()
    raw_sheet = get_or_create_sheet(spreadsheet, SHEET_NAME)
    summary_sheet = get_or_create_sheet(spreadsheet, f"{SHEET_NAME}_집계")

    for attempt in range(3):
        try:
            data = raw_sheet.get_all_values()

            # 시트가 비어있거나 A1이 "파일명"이 아니면 초기화
            if not data or data[0][0] != "파일명":
                raw_sheet.clear()
                raw_sheet.update("A1", [["파일명", judge_name]])
                data = [["파일명", judge_name]]

            headers = data[0]  # ["파일명", "심사위원1", ...]

            # 심사위원 열 찾기
            if judge_name not in headers:
                col_index = len(headers) + 1
                raw_sheet.update_cell(1, col_index, judge_name)
                headers = headers + [judge_name]
            else:
                col_index = headers.index(judge_name) + 1

            # 파일명 행 찾기 (2행부터)
            file_col = [row[0] if row else "" for row in data[1:]]
            if file_name not in file_col:
                row_index = len(data) + 1
                raw_sheet.update_cell(row_index, 1, file_name)
            else:
                row_index = file_col.index(file_name) + 2

            # 결과 저장
            raw_sheet.update_cell(row_index, col_index, result)
            update_summary(raw_sheet, summary_sheet)
            break

        except gspread.exceptions.APIError:
            if attempt == 2:
                st.error("저장 중 오류가 발생했습니다. 다시 시도해주세요.")

# ===== 집계 업데이트 =====
def update_summary(raw_sheet, summary_sheet):
    data = raw_sheet.get_all_values()
    if not data or len(data) < 2:
        return

    summary_sheet.clear()
    summary_sheet.update("A1", [["파일명", "합격수", "불합격수", "총심사수"]])

    rows_to_add = []
    for row in data[1:]:
        if not row or not row[0]:
            continue
        file_name = row[0]
        votes = [v for v in row[1:] if v in ["합격", "불합격"]]
        pass_count = votes.count("합격")
        fail_count = votes.count("불합격")
        total = pass_count + fail_count
        rows_to_add.append([file_name, pass_count, fail_count, total])

    if rows_to_add:
        summary_sheet.append_rows(rows_to_add)

# ===== 페이지 설정 =====
st.set_page_config(page_title="사진 심사 시스템", layout="wide")
st.title("🖼️ 사진 심사 시스템")

# ===== 세션 초기화 =====
for key, val in [('name', ''), ('index', 0)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ===== 이름 입력 =====
if not st.session_state.name:
    st.subheader("👤 심사위원 이름을 입력해주세요")
    name_input = st.text_input("이름", placeholder="예: 홍길동")
    if st.button("심사 시작", use_container_width=True):
        if name_input.strip():
            st.session_state.name = name_input.strip()
            st.rerun()
        else:
            st.warning("이름을 입력해주세요!")
    st.stop()

# ===== 파일 불러오기 =====
files = get_files_from_drive()

if not files:
    st.error("📁 드라이브 폴더에 이미지가 없거나 폴더 ID가 잘못되었습니다.")
    st.stop()

total_files = len(files)

# ===== 사이드바 썸네일 =====
with st.sidebar:
    st.caption(f"심사위원: {st.session_state.name}")
    st.write("---")
    st.caption("📋 목록 (버튼 클릭해서 이동)")

    start = max(0, st.session_state.index - THUMB_RANGE)
    end = min(total_files, st.session_state.index + THUMB_RANGE + 1)
    visible = files[start:end]

    for i, f in enumerate(visible):
        actual_index = start + i
        file_id = f["id"]
        is_current = actual_index == st.session_state.index
        border_color = "#FF4B4B" if is_current else "#ccc"

        st.markdown(
            f'''<img src="https://drive.google.com/thumbnail?id={file_id}&sz=w200"
            style="width:100%; border-radius:6px; border: 3px solid {border_color}; margin-bottom:2px;">
            <p style="text-align:center; font-size:11px; margin:0 0 4px 0;">{actual_index + 1}번</p>''',
            unsafe_allow_html=True
        )
        if not is_current:
            if st.button(f"{actual_index + 1}번으로 이동", key=f"thumb_{actual_index}", use_container_width=True):
                st.session_state.index = actual_index
                st.rerun()
        else:
            st.button("👉 현재", key=f"thumb_{actual_index}", use_container_width=True, disabled=True)

# ===== 메인 심사 화면 =====
if st.session_state.index < total_files:
    current_num = st.session_state.index + 1
    current_file = files[st.session_state.index]
    current_id = current_file["id"]
    current_name = current_file["name"]

    st.subheader(f"📊 심사 중: {current_num}번째 / 총 {total_files}개")

    st.markdown(
        f'''<div style="display:flex; justify-content:center;">
        <img src="https://drive.google.com/thumbnail?id={current_id}&sz=w1200"
        style="max-height:60vh; max-width:100%; border-radius:8px; object-fit:contain;">
        </div>''',
        unsafe_allow_html=True
    )

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
                st.warning("첫 번째입니다!")

else:
    st.balloons()
    st.success("🎉 모든 사진을 심사했습니다! 수고하셨습니다.")
    if st.button("🔄 처음부터 다시하기", use_container_width=True):
        st.session_state.index = 0
        st.rerun()