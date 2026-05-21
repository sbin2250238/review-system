import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ===== 설정 =====
SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"
FOLDERS = {
    "사진": "1XNE_HmkcHQhxSusMfwzkXh80dPVFiQJd",
    "숏폼": "1baVZLTFNhL0AWuK4DpIbcJU7lU70wHtf"
}
THUMB_RANGE = 5

# ===== 구글 서비스 연결 =====
@st.cache_resource
def get_services():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    sheet_client = gspread.authorize(creds)
    drive_client = build("drive", "v3", credentials=creds)
    spreadsheet = sheet_client.open_by_key(SPREADSHEET_ID)
    return drive_client, spreadsheet

# ===== 파일 리스트 로드 (속도 최적화) =====
@st.cache_data(ttl=600)
def get_files_from_drive(folder_id, category):
    drive_client, _ = get_services()
    mime_filter = "mimeType contains 'video/'" if category == "숏폼" else "mimeType contains 'image/'"
    
    # thumbnailLink와 webViewLink를 함께 가져옵니다.
    results = drive_client.files().list(
        q=f"'{folder_id}' in parents and {mime_filter} and trashed=false",
        fields="files(id, name, mimeType, thumbnailLink, webViewLink)",
        orderBy="name"
    ).execute()
    return results.get("files", [])

# [중요] 기존의 무거운 download_file 함수를 사용하지 않고 URL 방식을 사용합니다.

# ===== 메인 UI 시작 =====
st.set_page_config(page_title="심사 시스템", layout="wide")
drive_client, spreadsheet = get_services()

# (세션 초기화 및 이름/부문 선택 로직은 기존과 동일하므로 생략...)

# ===== 메인 심사 화면 로직 수정 =====
if 'index' in st.session_state and st.session_state.category:
    files = get_files_from_drive(FOLDERS[st.session_state.category], st.session_state.category)
    
    if st.session_state.index < len(files):
        current_file = files[st.session_state.index]
        file_id = current_file['id']
        
        st.subheader(f"📊 {st.session_state.category} 심사 중 ({st.session_state.index + 1}/{len(files)})")

        if st.session_state.category == "숏폼":
            # [해결] st.video 대신 iframe 사용 (로그인 없이 보려면 파일 공유 설정을 '링크가 있는 모든 사용자'로 권장)
            preview_url = f"https://drive.google.com/file/d/{file_id}/preview"
            st.components.v1.iframe(preview_url, height=600, scrolling=True)
        else:
            # [해결] 이미지는 썸네일 혹은 직접 링크 활용
            img_url = f"https://drive.google.com/uc?id={file_id}"
            st.image(img_url, use_container_width=True)

        # (합격/불합격 버튼 로직...)
