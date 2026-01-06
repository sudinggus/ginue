import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
from io import BytesIO

# --- 1. 기본 설정 및 배정 로직 (기존 코랩 코드 이식) ---
st.set_page_config(page_title="근무표 자동화 시스템", layout="wide")

LOCATIONS_CONFIG = {
    "인천": {"생활관1": 2, "생활관2": 2, "생활관3": 2, "상황실1": 3, "도서관1": 2},
    "경기": {"생활관1": 2, "생활관2": 2, "상황실2": 3, "도서관2": 2}
}

def generate_schedule(df_staff, start_dt, end_dt):
    # (질문자님의 기존 배정 알고리즘 로직이 이 자리에 들어갑니다)
    # 여기서는 예시 데이터를 생성하는 구조만 유지합니다.
    df_staff['이름'] = df_staff['이름'].astype(str).str.strip()
    results = []
    curr = start_dt
    while curr <= end_dt:
        if curr.weekday() < 5: # 평일만 배정 예시
            for cp in ["인천", "경기"]:
                for loc, num in LOCATIONS_CONFIG[cp].items():
                    for _ in range(num):
                        results.append({
                            "날짜": curr.strftime("%Y-%m-%d"),
                            "캠퍼스": cp, "근무지": loc,
                            "직원": random.choice(df_staff['이름'].tolist()),
                            "유형": "일반"
                        })
        curr += timedelta(days=1)
    return pd.DataFrame(results)

# --- 2. 상태 유지 (세션 상태) ---
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None

# --- 3. 사이드바: 설정 및 파일 업로드 ---
with st.sidebar:
    st.title("⚙️ 관리자 설정")
    uploaded_file = st.file_uploader("직원 명단(Excel) 업로드", type=['xlsx'])
    start_date = st.date_input("시작일", datetime.today())
    end_date = st.date_input("종료일", datetime.today() + timedelta(days=7))
    
    if st.button("근무표 새로 생성하기"):
        if uploaded_file:
            df_input = pd.read_excel(uploaded_file)
            st.session_state.schedule_df = generate_schedule(df_input, start_date, end_date)
            st.success("새 근무표가 생성되었습니다!")
        else:
            st.error("파일을 먼저 업로드해주세요.")

# --- 4. 메인 화면: 근무표 미리보기 및 교체 ---
st.title("📅 실시간 근무표 시스템")

    if st.session_state.schedule_df is not None:
        df = st.session_state.schedule_df

        # [추가] 엑셀처럼 예쁜 표를 만들기 위한 데이터 재구성 (Pivot)
        # 행: 캠퍼스, 근무지 / 열: 날짜 / 값: 직원
        pivot_df = df.pivot_table(
            index=['캠퍼스', '근무지'],
            columns='날짜',
            values='직원',
            aggfunc=lambda x: ", ".join(x)
        ).fillna("") # 빈자리는 공백으로

        # [디자인] CSS를 이용해 엑셀 느낌 내기
        st.markdown("""
            <style>
                table { border-collapse: collapse !important; width: 100%; }
                th { background-color: #F2F2F2 !important; color: black !important; font-weight: bold !important; border: 1px solid #333 !important; }
                td { border: 1px solid #333 !important; }
            </style>
        """, unsafe_allow_html=True)

        st.subheader("📊 주간 근무표 시각화")
        st.table(pivot_df) # 수정된 피벗 테이블 출력
    
    # 교체 기능 UI
    with st.expander("🔄 1:1 근무자 교체 신청"):
        col1, col2 = st.columns(2)
        with col1:
            idx1 = st.selectbox("첫 번째 사람 선택", df.index, format_func=lambda x: f"{df.loc[x, '날짜']} - {df.loc[x, '직원']} ({df.loc[x, '근무지']})")
        with col2:
            idx2 = st.selectbox("두 번째 사람 선택", df.index, format_func=lambda x: f"{df.loc[x, '날짜']} - {df.loc[x, '직원']} ({df.loc[x, '근무지']})")
        
        if st.button("선택한 두 사람 교체 확정"):
            # 데이터프레임 값 교체
            p1 = df.loc[idx1, '직원']
            p2 = df.loc[idx2, '직원']
            st.session_state.schedule_df.at[idx1, '직원'] = p2
            st.session_state.schedule_df.at[idx2, '직원'] = p1
            st.rerun()

    # 근무표 출력 (날짜별로 보기 좋게 시각화)
    dates = sorted(df['날짜'].unique())
    for d in dates:
        st.subheader(f"📍 {d}")
        day_df = df[df['날짜'] == d].pivot_table(
            index=['캠퍼스', '근무지'], 
            values='직원', 
            aggfunc=lambda x: ", ".join(x)
        )
        st.table(day_df) # 코랩 스타일의 표 출력

else:

    st.info("왼쪽 사이드바에서 파일을 업로드하고 근무표를 생성해주세요.")
