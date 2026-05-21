import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ===== 설정 =====
SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"
img_ids = [
    "1vEqexaibtRobiHw5LfEoz2nKCYVwS3h6",
    "1vnI_HYQWvfnBoAEnTN-lchTxXW_I2WgS"
]

# ===== 구글 시트 연결 =====
@st.cache_resource
def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1

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

# ===== 심사 화면 =====
total_images = len(img_ids)

if 'index' not in st.session_state:
    st.session_state.index = 0

st.caption(f"심사위원: {st.session_state.name}")

if st.session_state.index < total_images:
    current_num = st.session_state.index + 1
    current_id = img_ids[st.session_state.index]

    st.subheader(f"📊 심사 중: {current_num}번째 / 총 {total_images}장")

    st.markdown(
        f'<img src="https://drive.google.com/thumbnail?id={current_id}&sz=w1200" style="width:100%; border-radius:8px;">',
        unsafe_allow_html=True
    )
    st.caption(f"이미지 ID: {current_id}")
    st.write("---")

    col1, col2, col3 = st.columns(3)

    def save_result(result):
        sheet = get_sheet()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([st.session_state.name, current_id, result, now])
        st.session_state.index += 1
        st.rerun()

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