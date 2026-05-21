import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import requests
from google.auth.transport.requests import Request
import io

# 1. 페이지 설정 (가장 먼저 실행)
st.set_page_config(page_title="심사 시스템", layout="wide")

# ===== 설정 =====
SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"
FOLDERS = {
    "사진": "1XNE_HmkcHQhxSusMfwzkXh80dPVFiQJd",
    "숏폼": "1baVZLTFNhL0AWuK4DpIbcJU7lU70wHtf"
}

# ===== 구글 연결 (기존 로직 복구) =====
@st.cache_resource
def get_services():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    sheet_client = gspread.authorize(creds)
    drive_client = build("drive", "v3", credentials=creds)
    spreadsheet = sheet_client.open_by_key(SPREADSHEET_ID)
    return creds, sheet_client, drive_client, spreadsheet

# ===== 파일 다운로드 (보안 유지형) =====
def download_file(file_id):
    creds, _, _, _ = get_services()
    if not creds.valid:
        creds.refresh(Request())
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    headers = {"Authorization": f"Bearer {creds.token}"}
    response = requests.get(url, headers=headers)
    return response.content

@st.cache_data(ttl=60)
def get_files_from_drive(folder_id, category):
    _, _, drive_client, _ = get_services()
    mime_filter = "mimeType contains 'video/'" if category == "숏폼" else "mimeType contains 'image/'"
    results = drive_client.files().list(
        q=f"'{folder_id}' in parents and {mime_filter} and trashed=false",
        fields="files(id, name, mimeType)",
        orderBy="name"
    ).execute()
    return results.get("files", [])

# ===== 세션 초기화 =====
if 'name' not in st.session_state: st.session_state.name = ''
if 'category' not in st.session_state: st.session_state.category = ''
if 'index' not in st.session_state: st.session_state.index = 0

# (이름 입력/부문 선택 로직은 이전과 동일하므로 생략 - 그대로 유지하세요)
# ... 이름/부문 선택 후 ...

# ===== 메인 심사 화면 (수정된 핵심 파트) =====
if st.session_state.name and st.session_state.category:
    files = get_files_from_drive(FOLDERS[st.session_state.category], st.session_state.category)
    
    if st.session_state.index < len(files):
        curr = files[st.session_state.index]
        st.subheader(f"📊 {st.session_state.category} 심사 중: {st.session_state.index + 1} / {len(files)}")
        
        with st.spinner("미디어를 불러오는 중입니다..."):
            try:
                # 파일을 바이트로 다운로드
                file_bytes = download_file(curr['id'])
                
                if st.session_state.category == "사진":
                    # 사진은 그대로 표시
                    st.image(file_bytes, use_container_width=True)
                else:
                    # [중요] 영상 재생 문제 해결: 바이트 데이터를 BytesIO로 감싸서 전달
                    video_data = io.BytesIO(file_bytes)
                    st.video(video_data)
                    
            except Exception as e:
                st.error(f"파일 로드 중 오류 발생: {e}")

        # 파일명 표시 및 심사 버튼
        st.write(f"**파일명:** {curr['name']}")
        col1, col2, col3 = st.columns(3)
        # (기존 버튼 로직 logic...)
