import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# [필수] 페이지 설정은 반드시 코드의 가장 첫 번째 Streamlit 명령어로 실행되어야 합니다.
st.set_page_config(page_title="심사 시스템", layout="wide")

# ===== 설정 =====
SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"
FOLDERS = {
    "사진": "1XNE_HmkcHQhxSusMfwzkXh80dPVFiQJd",
    "숏폼": "1baVZLTFNhL0AWuK4DpIbcJU7lU70wHtf"
}

# ===== 구글 서비스 연결 =====
@st.cache_resource
def get_services():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        # st.secrets 확인 필요
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes
        )
        sheet_client = gspread.authorize(creds)
        drive_client = build("drive", "v3", credentials=creds)
        spreadsheet = sheet_client.open_by_key(SPREADSHEET_ID)
        return drive_client, spreadsheet
    except Exception as e:
        st.error(f"구글 서비스 연결 실패: {e}")
        return None, None

def get_or_create_sheet(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except:
        return spreadsheet.add_worksheet(title=title, rows=1000, cols=50)

# ===== 파일 리스트 로드 (속도 최적화) =====
@st.cache_data(ttl=600)
def get_files_from_drive(folder_id, category):
    drive_client, _ = get_services()
    if not drive_client: return []
    
    mime_filter = "mimeType contains 'video/'" if category == "숏폼" else "mimeType contains 'image/'"
    
    results = drive_client.files().list(
        q=f"'{folder_id}' in parents and {mime_filter} and trashed=false",
        fields="files(id, name, mimeType, thumbnailLink)",
        orderBy="name"
    ).execute()
    return results.get("files", [])

# ===== 결과 저장 로직 =====
def save_result(judge_name, file_name, result, category, spreadsheet):
    raw_sheet = get_or_create_sheet(spreadsheet, category)
    data = raw_sheet.get_all_values()
    
    if not data:
        raw_sheet.append_row(["파일명"])
        data = [["파일명"]]

    headers = data[0]
    if judge_name not in headers:
        headers.append(judge_name)
        raw_sheet.update_cell(1, len(headers), judge_name)
        col_index = len(headers)
    else:
        col_index = headers.index(judge_name) + 1

    file_names = [row[0] for row in data[1:]]
    if file_name not in file_names:
        raw_sheet.update_cell(len(data) + 1, 1, file_name)
        row_index = len(data) + 1
    else:
        row_index = file_names.index(file_name) + 2

    raw_sheet.update_cell(row_index, col_index, result)

# ===== 앱 메인 로직 =====
drive_client, spreadsheet = get_services()

# 세션 상태 초기화
if 'name' not in st.session_state: st.session_state.name = ''
if 'category' not in st.session_state: st.session_state.category = ''
if 'index' not in st.session_state: st.session_state.index = 0

st.title("🚀 고속 심사 시스템")

# 1단계: 이름 입력
if not st.session_state.name:
    name_input = st.text_input("심사위원 성함을 입력하세요")
    if st.button("시작하기"):
        if name_input.strip():
            st.session_state.name = name_input
            st.rerun()
    st.stop()

# 2단계: 부문 선택
if not st.session_state.category:
    col1, col2 = st.columns(2)
    if col1.button("🖼️ 사진 부문"):
        st.session_state.category = "사진"
        st.rerun()
    if col2.button("🎬 숏폼 부문"):
        st.session_state.category = "숏폼"
        st.rerun()
    st.stop()

# 3단계: 심사 화면
files = get_files_from_drive(FOLDERS[st.session_state.category], st.session_state.category)

if not files:
    st.warning("폴더에 파일이 없습니다.")
    if st.button("부문 다시 선택"):
        st.session_state.category = ""
        st.rerun()
    st.stop()

# 사이드바 구성
with st.sidebar:
    st.write(f"👤 **{st.session_state.name}** 심사위원")
    if st.button("🔄 부문 변경"):
        st.session_state.category = ""
        st.session_state.index = 0
        st.rerun()
    st.write("---")

# 현재 파일 정보
if st.session_state.index < len(files):
    curr = files[st.session_state.index]
    st.subheader(f"{st.session_state.category} 심사: {st.session_state.index + 1} / {len(files)}")
    
    # 미디어 출력 (핵심 수정 부분)
    if st.session_state.category == "숏폼":
        # iframe 방식: 대용량 영상도 즉시 스트리밍 가능
        video_url = f"https://drive.google.com/file/d/{curr['id']}/preview"
        st.components.v1.iframe(video_url, height=500)
    else:
        # 이미지 직접 링크 방식: 가장 빠름
        img_url = f"https://drive.google.com/uc?id={curr['id']}"
        st.image(img_url, use_container_width=True)

    st.write(f"**파일명:** {curr['name']}")
    
    col1, col2, col3 = st.columns(3)
    if col1.button("✅ 합격", use_container_width=True):
        save_result(st.session_state.name, curr['name'], "합격", st.session_state.category, spreadsheet)
        st.session_state.index += 1
        st.rerun()
    if col2.button("❌ 불합격", use_container_width=True):
        save_result(st.session_state.name, curr['name'], "불합격", st.session_state.category, spreadsheet)
        st.session_state.index += 1
        st.rerun()
    if col3.button("⬅️ 이전", use_container_width=True):
        if st.session_state.index > 0:
            st.session_state.index -= 1
            st.rerun()
else:
    st.balloons()
    st.success("모든 심사가 끝났습니다!")
    if st.button("처음으로 돌아가기"):
        st.session_state.index = 0
        st.rerun()
