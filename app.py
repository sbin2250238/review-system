import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ===== 설정 =====
SPREADSHEET_ID = "1tLdbLIvTfpCS2HERHfeUBHGSL1dEKpPNGYk-9EJZvjU"
FOLDER_ID = "1XNE_HmkcHQhxSusMfwzkXh80dPVFiQJd"
SHEET_NAME = "사진"
THUMB_RANGE = 10

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
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=2000, cols=50)

# ===== 드라이브 폴더에서 파일 로드 =====
@st.cache_data(ttl=60)
def get_files_from_drive():
    _, drive_client, __ = get_services()
    all_files = []
    page_token = None
    while True:
        params = {
            "q": f"'{FOLDER_ID}' in parents and mimeType contains 'image/' and trashed=false",
            "fields": "nextPageToken, files(id, name)",
            "orderBy": "name",
            "pageSize": 1000
        }
        if page_token:
            params["pageToken"] = page_token
        results = drive_client.files().list(**params).execute()
        all_files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return all_files

# ===== 시트 파일명 자동 초기화 =====
def init_sheet_if_needed(files):
    _, __, spreadsheet = get_services()
    raw_sheet = get_or_create_sheet(spreadsheet, SHEET_NAME)
    data = raw_sheet.get_all_values()

    # 파일명이 이미 시트에 있으면 패스
    if data and data[0] and data[0][0] == "파일명" and len(data) > 1:
        return

    # 없으면 파일명 전체 한번에 입력
    with st.spinner("⏳ 심사 목록 초기화 중... 잠시만 기다려주세요."):
        raw_sheet.clear()
        rows = [["파일명"]] + [[f["name"]] for f in files]
        raw_sheet.update("A1", rows)

# ===== 내 심사 결과 불러오기 =====
@st.cache_data(ttl=30)
def get_my_results(judge_name):
    _, __, spreadsheet = get_services()
    try:
        raw_sheet = spreadsheet.worksheet(SHEET_NAME)
    except:
        return {}

    data = raw_sheet.get_all_values()
    results = {}
    if not data or not data[0] or data[0][0] != "파일명":
        return results

    headers = data[0]
    if judge_name not in headers:
        return results

    col_index = headers.index(judge_name)
    for row in data[1:]:
        if not row or not row[0]:
            continue
        file_name = row[0]
        value = row[col_index] if col_index < len(row) else ""
        if value in ["합격", "불합격"]:
            results[file_name] = value

    return results

# ===== 결과 저장 (빠른 버전) =====
def save_result(judge_name, file_name, result, file_index):
    _, __, spreadsheet = get_services()
    raw_sheet = get_or_create_sheet(spreadsheet, SHEET_NAME)

    for attempt in range(3):
        try:
            data = raw_sheet.get_all_values()
            headers = data[0] if data else ["파일명"]

            # 심사위원 열 찾기
            if judge_name not in headers:
                col_index = len(headers) + 1
                raw_sheet.update_cell(1, col_index, judge_name)
            else:
                col_index = headers.index(judge_name) + 1

            # 파일명 인덱스로 행 번호 바로 계산 (시트 전체 안 읽어도 됨)
            row_index = file_index + 2  # +1 헤더, +1 0-index 보정

            # 결과만 저장 ⚡
            raw_sheet.update_cell(row_index, col_index, result)
            get_my_results.clear()
            break

        except gspread.exceptions.APIError:
            if attempt == 2:
                st.error("저장 중 오류가 발생했습니다. 다시 시도해주세요.")

# ===== 집계 업데이트 (완료시에만) =====
def update_summary():
    _, __, spreadsheet = get_services()
    raw_sheet = get_or_create_sheet(spreadsheet, SHEET_NAME)
    summary_sheet = get_or_create_sheet(spreadsheet, f"{SHEET_NAME}_집계")

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
for key, val in [('name', ''), ('index', 0), ('summary_updated', False)]:
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

# ===== 시트 자동 초기화 =====
init_sheet_if_needed(files)

# ===== 내 심사 결과 불러오기 =====
my_results = get_my_results(st.session_state.name)
done_count = len(my_results)
all_done = done_count >= total_files

# ===== 완료시 집계 업데이트 (한번만) =====
if all_done and not st.session_state.summary_updated:
    with st.spinner("집계 중..."):
        update_summary()
    st.session_state.summary_updated = True

# ===== 사이드바 =====
with st.sidebar:
    st.caption(f"심사위원: {st.session_state.name}")
    st.progress(done_count / total_files, text=f"진행률: {done_count} / {total_files}장")
    st.write("---")

    st.caption("🔢 번호로 바로 이동")
    col_a, col_b = st.columns([3, 1])
    with col_a:
        jump_num = st.number_input(
            "번호 입력",
            min_value=1,
            max_value=total_files,
            value=st.session_state.index + 1,
            step=1,
            label_visibility="collapsed"
        )
    with col_b:
        if st.button("이동", use_container_width=True):
            st.session_state.index = int(jump_num) - 1
            st.rerun()

    st.write("---")
    st.caption("📋 앞뒤 10개 목록")

    start = max(0, st.session_state.index - THUMB_RANGE)
    end = min(total_files, st.session_state.index + THUMB_RANGE + 1)
    visible = files[start:end]

    for i, f in enumerate(visible):
        actual_index = start + i
        file_id = f["id"]
        file_name = f["name"]
        is_current = actual_index == st.session_state.index
        my_vote = my_results.get(file_name, "")

        border_color = "#FF4B4B" if is_current else ("#4CAF50" if my_vote == "합격" else "#f44336" if my_vote == "불합격" else "#ccc")
        vote_label = "✅" if my_vote == "합격" else "❌" if my_vote == "불합격" else "⬜"

        st.markdown(
            f'''<img src="https://drive.google.com/thumbnail?id={file_id}&sz=w200"
            style="width:100%; border-radius:6px; border: 3px solid {border_color}; margin-bottom:2px;">
            <p style="text-align:center; font-size:11px; margin:0 0 4px 0;">{vote_label} {actual_index + 1}번</p>''',
            unsafe_allow_html=True
        )
        if not is_current:
            if st.button(f"{actual_index + 1}번으로 이동", key=f"thumb_{actual_index}", use_container_width=True):
                st.session_state.index = actual_index
                st.rerun()
        else:
            st.button("👉 현재", key=f"thumb_{actual_index}", use_container_width=True, disabled=True)

# ===== 완료 화면 =====
if all_done:
    st.balloons()
    st.success("🎉 모든 사진 심사를 완료했습니다! 수고하셨습니다.")
    st.info(f"✅ 합격: {list(my_results.values()).count('합격')}장 / ❌ 불합격: {list(my_results.values()).count('불합격')}장")
    if st.button("🔄 다시 검토하기", use_container_width=True):
        st.session_state.summary_updated = False
        st.session_state.index = 0
        st.rerun()
    st.stop()

# ===== 메인 심사 화면 =====
if st.session_state.index < total_files:
    current_num = st.session_state.index + 1
    current_file = files[st.session_state.index]
    current_id = current_file["id"]
    current_name = current_file["name"]
    my_vote = my_results.get(current_name, "")

    st.subheader(f"📊 심사 중: {current_num}번째 / 총 {total_files}개")

    if my_vote:
        st.info(f"현재 선택: {'✅ 합격' if my_vote == '합격' else '❌ 불합격'} (변경 가능)")

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
            save_result(st.session_state.name, current_name, "합격", st.session_state.index)
            my_results[current_name] = "합격"
            st.session_state.index += 1
            st.rerun()

    with col2:
        if st.button("❌ 불합격", use_container_width=True):
            save_result(st.session_state.name, current_name, "불합격", st.session_state.index)
            my_results[current_name] = "불합격"
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
    undone = [i for i, f in enumerate(files) if f["name"] not in my_results]
    if undone:
        st.session_state.index = undone[0]
        st.rerun()
