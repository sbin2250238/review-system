# 1. 파일 목록 가져올 때 webContentLink(다운로드용)와 webViewLink(보기용)를 추가로 요청합니다.
@st.cache_data(ttl=3600) # 캐시 시간을 늘려 속도 향상
def get_files_from_drive(folder_id, category):
    _, __, drive_client, ___ = get_services()
    mime_filter = "mimeType contains 'video/'" if category == "숏폼" else "mimeType contains 'image/'"
    
    results = drive_client.files().list(
        q=f"'{folder_id}' in parents and {mime_filter} and trashed=false",
        # id, name 외에 webContentLink를 가져옵니다.
        fields="files(id, name, mimeType, webContentLink, thumbnailLink)",
        orderBy="name"
    ).execute()
    return results.get("files", [])

# 2. 메인 화면에서 영상/이미지 출력 방식 변경
def display_media(file):
    # API 키를 통한 직접 접근용 URL 생성 (가장 빠름)
    # 구글 드라이브 파일 권한이 '링크가 있는 모든 사용자'로 되어 있어야 가장 원활합니다.
    file_id = file['id']
    
    if "video" in file['mimeType']:
        # 바이트 다운로드 대신 URL 직접 연결
        # 주의: 구글 드라이브 정책상 큰 영상은 st.video(url)이 막힐 수 있음. 
        # 이 경우 iframe을 사용하는 것이 가장 확실합니다.
        embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
        st.components.v1.iframe(embed_url, height=500)
    else:
        # 이미지의 경우 기존 download_file 대신 링크 활용 고려
        img_url = f"https://drive.google.com/uc?id={file_id}"
        st.image(img_url, use_container_width=True)
