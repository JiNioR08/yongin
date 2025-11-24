import streamlit as st
import folium
from streamlit_folium import st_folium

st.title("🗺️ 나만의 위치 북마크 지도")

st.write("아래에 장소 정보를 입력하고 지도에 표시해보세요!")

# 장소 입력
place = st.text_input("장소 이름", value="서울 시청")
lat = st.number_input("위도 (Latitude)", value=37.5665, format="%.6f")
lon = st.number_input("경도 (Longitude)", value=126.9780, format="%.6f")

# 세션 상태 저장
if "places" not in st.session_state:
    st.session_state.places = []

if st.button("지도에 추가하기"):
    st.session_state.places.append((place, lat, lon))

# 지도 그리기
m = folium.Map(location=[37.5665, 126.9780], zoom_start=6)
for name, lat, lon in st.session_state.places:
    folium.Marker([lat, lon], tooltip=name).add_to(m)

st_folium(m, width=700, height=500)
