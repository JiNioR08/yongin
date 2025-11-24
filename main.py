import streamlit as st

st.title("나의 첫 웹서비스!!")
name = st.text_input("이름을 입력해주세요.")
menu = st.selectbox('가장 많이 쓰는 앱은?', ['인스타그램', '페이스북', '트위터', '유튜브'])
time = st.slider('하루 사용 시간은? ',0,24,3)

if st.button('결과 보기'):
    st.write(f'{name}님은 {menu}를 하루 평균 {time}시간 사용하시네요. 균형 잡힌 시간관리가 중요해요!')
    st.balloons()
