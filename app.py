import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import requests
from google.auth.transport.requests import Request

# ===== 설정 =====
SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"

FOLDERS = {
    "사진": "1XNE_HmkcHQhxSusMfwzkXh80dPVFiQJd",
    "숏폼": "1baVZLTFNhL0AWuK4DpIbcJU7lU70wHtf"
}

THUMB_RANGE = 5

# ===== 구글 연결 =====
@st.cache_resource
def get_services():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    sheet_client = gspread.authorize(creds)
    drive_client = build("drive", "v3", credentials=creds)
    spreadsheet = sheet_client.open_by_key(SPREADSHEET_ID)
    return creds, sheet_client, drive_client, spreadsheet

def get_or_create_sheet(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except:
        return spreadsheet.add_worksheet(title=title, rows=1000, cols=50)

# ===== 파일 바이트 직접 다운로드 =====
def download_file(file_id):
    creds, _, __, ___ = get_services()
    if not creds.valid:
        creds.refresh(Request())
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    headers = {"Authorization": f"Bearer {creds.token}"}
    response = requests.get(url, headers=headers)
    return response.content

# ===== 드라이브 폴더에서 파일 로드 =====
@st.cache_data(ttl=60)
def get_files_from_drive(folder_id, category):
    _, __, drive_client, ___ = get_services()
    if category == "숏폼":
        mime_filter = "mimeType contains 'video/'"
    else:
        mime_filter = "mimeType contains 'image/'"
    results = drive_client.files().list(
        q=f"'{folder_id}' in parents and {mime_filter} and trashed=false",
        fields="files(id, name, mimeType)",
        orderBy="name"
    ).execute()
    return results.get("files", [])

# ===== 결과 저장 =====
def save_result(judge_name, file_name, result, category):
    _, __, ___, spreadsheet = get_services()
    raw_sheet = get_or_create_sheet(spreadsheet, category)
    summary_sheet = get_or_create_sheet(spreadsheet, f"{category}_집계")

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

# ===== 집계 업데이트 =====
def update_summary(raw_sheet, summary_sheet):
    data = raw_sheet.get_all_values()
    if not data or len(data) < 2:
        return

    summary_sheet.clear()
    summary_sheet.append_row(["파일명", "합격수", "불합격수", "총심사수"])

    for row in data[1:]:
        if not row[0]:
            continue
        file_name = row[0]
        votes = [v for v in row[1:] if v in ["합격", "불합격"]]
        pass_count = votes.count("합격")
        fail_count = votes.count("불합격")
        total = pass_count + fail_count
        summary_sheet.append_row([file_name, pass_count, fail_count, total])

# ===== 페이지 설정 =====
st.set_page_config(page_title="심사 시스템", layout="wide")
st.title("🚀 심사 시스템")

# ===== 세션 초기화 =====
for key, val in [('name', ''), ('category', ''), ('index', 0)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ===== 이름 입력 =====
if not st.session_state.name:
    st.subheader("👤 심사위원 이름을 입력해주세요")
    name_input = st.text_input("이름", placeholder="예: 홍길동")
    if st.button("다음", use_container_width=True):
        if name_input.strip():
            st.session_state.name = name_input.strip()
            st.rerun()
        else:
            st.warning("이름을 입력해주세요!")
    st.stop()

# ===== 부문 선택 =====
if not st.session_state.category:
    st.subheader("📂 심사할 부문을 선택해주세요")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🖼️ 사진 부문", use_container_width=True):
            st.session_state.category = "사진"
            st.session_state.index = 0
            st.rerun()
    with col2:
        if st.button("🎬 숏폼 부문", use_container_width=True):
            st.session_state.category = "숏폼"
            st.session_state.index = 0
            st.rerun()
    st.stop()

# ===== 파일 불러오기 =====
category = st.session_state.category
folder_id = FOLDERS[category]
files = get_files_from_drive(folder_id, category)

if not files:
    st.error("📁 드라이브 폴더에 파일이 없거나 폴더 ID가 잘못되었습니다.")
    st.stop()

total_files = len(files)

# ===== 사이드바 =====
with st.sidebar:
    st.caption(f"심사위원: {st.session_state.name}")
    st.caption(f"부문: {category}")
    if st.button("🔀 부문 변경", use_container_width=True):
        st.session_state.category = ""
        st.session_state.index = 0
        st.rerun()
    st.write("---")
    st.caption("📋 목록 (버튼 클릭해서 이동)")

    start = max(0, st.session_state.index - THUMB_RANGE)
    end = min(total_files, st.session_state.index + THUMB_RANGE + 1)
    visible = files[start:end]

    for i, f in enumerate(visible):
        actual_index = start + i
        file_id = f["id"]
        file_name = f["name"]
        is_current = actual_index == st.session_state.index
        border_color = "#FF4B4B" if is_current else "#ccc"

        if category == "사진":
            try:
                img_bytes = download_file(file_id)
                st.markdown(f'<div style="border: 3px solid {border_color}; border-radius:6px; margin-bottom:4px; overflow:hidden;">', unsafe_allow_html=True)
                st.image(img_bytes, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
                st.caption(f"{actual_index + 1}번")
            except:
                st.caption(f"{actual_index + 1}번 (로드 실패)")
        else:
            icon = "👉" if is_current else "▶️"
            st.markdown(
                f'''<div style="width:100%; padding:8px; border-radius:6px;
                border: 3px solid {border_color}; margin-bottom:4px; text-align:center; font-size:12px;">
                {icon} {actual_index + 1}번<br>
                <span style="font-size:10px;">{file_name[:20]}</span></div>''',
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
    current_mime = current_file["mimeType"]

    st.subheader(f"📊 [{category}] 심사 중: {current_num}번째 / 총 {total_files}개")

    if category == "사진":
        try:
            img_bytes = download_file(current_id)
            st.image(img_bytes, use_container_width=False, width=800)
        except Exception as e:
            st.error(f"이미지 로드 실패: {e}")
    else:
        try:
            video_bytes = download_file(current_id)
            st.video(video_bytes)
        except Exception as e:
            st.error(f"영상 로드 실패: {e}")

    st.write("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ 합격", use_container_width=True):
            save_result(st.session_state.name, current_name, "합격", category)
            st.session_state.index += 1
            st.rerun()

    with col2:
        if st.button("❌ 불합격", use_container_width=True):
            save_result(st.session_state.name, current_name, "불합격", category)
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
    st.success("🎉 모든 파일을 심사했습니다! 수고하셨습니다.")
    if st.button("🔄 처음부터 다시하기", use_container_width=True):
        st.session_state.index = 0
        st.rerun()
