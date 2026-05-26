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
    except:
        return spreadsheet.add_worksheet(title=title, rows=1000, cols=50)

# ===== 드라이브 폴더에서 파일 로드 (1000개 이상 지원) =====
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

# ===== 내 심사 결과 불러오기 =====
def get_my_results(judge_name):
    _, __, spreadsheet = get_services()
    raw_sheet = get_or_create_sheet(spreadsheet, SHEET_NAME)
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

# ===== 결과 저장 =====
def save_result(judge_name, file_name, result):
    _, __, spreadsheet = get_services()
    raw_sheet = get_or_create_sheet(spreadsheet, SHEET_NAME)
    summary_sheet = get_or_create_sheet(spreadsheet, f"{SHEET_NAME}_집계")

    for attempt in range(3):
        try:
            data = raw_sheet.get_all_values()

            if not data or not data[0] or data[0][0] != "파일명":
                raw_sheet.clear()
                raw_sheet.update("A1", [["파일명", judge_name]])
                data = [["파일명", judge_name]]

            headers = data[0]

            if judge_name not in headers:
                col_index = len(headers) + 1
                raw_sheet.update_cell(1, col_index, judge_name)
                headers = headers + [judge_name]
            else:
                col_index = headers.index(judge_name) + 1

            file_col = [row[0] if row else "" for row in data[1:]]
            if file_name not in file_col:
                row_index = len(data) + 1
                raw_sheet.update_cell(row_index, 1, file_name)
            else:
                row_index = file_col.index(file_name) + 2

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
    if st.button("심사 시작", use_container_width=Tr
