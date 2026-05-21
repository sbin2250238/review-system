import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime

# ===== 설정 =====
SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"
FOLDER_ID = "1XNE_HmkcHQhxSusMfwzkXh80dPVFiQJd"  # ← 새로 추가!

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
    sheet = sheet_client.open_by_key(SPREADSHEET_ID).sheet1
    return sheet, drive_client

# ===== 드라이브 폴더에서 이미지 자동 로드 =====
@st.cache_data(ttl=60)  # 60초마다 새로고침
def get_images_from_drive():
    _, drive = get_services()
    results = drive.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType contains 'image/' and trashed=false",
        fields="files(id, name)",
        orderBy="name"
    ).execute()
    return results.get("files", [])

# ===== 페이지 설정 =====
st.set_page_config(page_title="이미지 심사 시스템", layout="centered")
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

# ===== 심사 화면 =====
st.caption(f"심사위원: {st.session_state.name}")

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

    def save_result(result):
        sheet, _ = get_services()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([st.session_state.name, current_name, current_id, result, now])
        st.session_state.index += 1
        st.rerun()

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ 합격", use_container_width=True):
            save_result("합격")

    with col2:
        if st.button("❌ 불합격", use_container_width=True):
            save_result("불합격")

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
