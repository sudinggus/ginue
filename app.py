import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from collections import defaultdict

# ==========================================
# 1. 초기 설정 및 페이지 레이아웃
# ==========================================
st.set_page_config(page_title="근무표 자동화 시스템", layout="wide")

# CSS: 표 디자인 및 가독성 향상
st.markdown("""
    <style>
        .stTable { border: 1px solid #333; }
        th { background-color: #f2f2f2 !important; color: black !important; text-align: center !important; }
        td { text-align: center !important; min-width: 100px; }
    </style>
""", unsafe_allow_html=True)

# 상수 설정
LOCATIONS_CONFIG = {
    "인천": {"생활관1": 2, "생활관2": 2, "생활관3": 2, "상황실1": 3, "도서관1": 2},
    "경기": {"생활관1": 2, "생활관2": 2, "상황실2": 3, "도서관2": 2}
}
HOLIDAYS = ['2025-10-03', '2025-10-06', '2025-10-09']

# 요일 변환 함수
def get_korean_weekday(date_obj):
    return ['월', '화', '수', '목', '금', '토', '일'][date_obj.weekday()]

# ==========================================
# 2. 핵심 로직 엔진 (코랩 로직)
# ==========================================

def generate_schedule_logic(df_staff, start_dt, end_dt):
    df_staff['이름'] = df_staff['이름'].astype(str).str.strip()
    work_counts = {name: 0 for name in df_staff['이름'].unique()}
    schedule_results = []
    
    fixed_assignments = defaultdict(list)
    for _, row in df_staff.iterrows():
        if pd.notna(row.get('고정근무일자')):
            raw_dates = str(row['고정근무일자']).split(',')
            raw_locs = str(row['고정근무지']).split(',') if pd.notna(row.get('고정근무지')) else []
            for i, d_str in enumerate(raw_dates):
                try:
                    clean_date = datetime.strptime(d_str.strip(), '%Y-%m-%d').strftime('%Y-%m-%d')
                    loc_target = raw_locs[i].strip() if i < len(raw_locs) else (raw_locs[0].strip() if raw_locs else "미지정")
                    fixed_assignments[clean_date].append((row['이름'], loc_target, row['캠퍼스']))
                    work_counts[row['이름']] += 1
                except: continue

    date_range = []
    curr = start_dt
    while curr <= end_dt:
        if curr.weekday() < 5 and curr.strftime("%Y-%m-%d") not in HOLIDAYS:
            date_range.append(curr)
        curr += timedelta(days=1)

    for date in date_range:
        date_str = date.strftime("%Y-%m-%d")
        today_assigned = []
        
        # 고정 근무 배정
        if date_str in fixed_assignments:
            for name, loc, campus in fixed_assignments[date_str]:
                schedule_results.append({"날짜": date_str, "캠퍼스": campus, "근무지": loc, "직원": name, "유형": "고정"})
                today_assigned.append(name)

        # 일반 근무 랜덤 배정
        for campus, locs in LOCATIONS_CONFIG.items():
            for loc_name, total_required in locs.items():
                already_filled = len([s for s in schedule_results if s['날짜'] == date_str and s['캠퍼스'] == campus and s['근무지'] == loc_name])
                needed = total_required - already_filled
                if needed <= 0: continue
                
                possible_staff = df_staff[((df_staff['캠퍼스'] == campus) | (df_staff['캠퍼스'] == "모두")) & (~df_staff['이름'].isin(today_assigned))]
                final_candidates = []
                for _, s_row in possible_staff.iterrows():
                    dept = str(s_row['소속'])
                    is_excluded = any(key in dept and key in loc_name for key in ['생활관', '상황실', '도서관'])
                    if not is_excluded: final_candidates.append(s_row['이름'])

                random.shuffle(final_candidates)
                final_candidates.sort(key=lambda x: work_counts[x])
                assigned_now = final_candidates[:needed]
                for person in assigned_now:
                    schedule_results.append({"날짜": date_str, "캠퍼스": campus, "근무지": loc_name, "직원": person, "유형": "일반"})
                    work_counts[person] += 1
                    today_assigned.append(person)

    return pd.DataFrame(schedule_results), work_counts

def make_final_excel_blob(df, stats):
    """3개 시트가 포함된 엑셀 파일 생성"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # 시트 1: 원본 데이터
        df.to_excel(writer, sheet_name='1_전체데이터', index=False)
        
        # 시트 2: 주간근무표 (피벗 형태)
        pivot_all = df.pivot_table(
            index=['캠퍼스', '근무지'],
            columns='날짜',
            values='직원',
            aggfunc=lambda x: ", ".join(x)
        ).fillna("-")
        pivot_all.to_excel(writer, sheet_name='2_주간근무표')
        
        # 시트 3: 근무통계
        stats_df = pd.DataFrame(list(stats.items()), columns=['직원 이름', '횟수'])
        stats_df.to_excel(writer, sheet_name='3_근무통계', index=False)
        
    return output.getvalue()

# ==========================================
# 3. 세션 관리 및 UI 구성
# ==========================================

if 'df' not in st.session_state: st.session_state.df = None
if 'stats' not in st.session_state: st.session_state.stats = {}

with st.sidebar:
    st.title("🔐 관리자 제어")
    pw = st.text_input("관리자 암호", type="password")
    if pw == "1234":
        st.success("인증 성공")
        file = st.file_uploader("명단 파일(xlsx) 업로드", type=['xlsx'])
        s_date = st.date_input("시작일", datetime.today())
        e_date = st.date_input("종료일", datetime.today() + timedelta(days=14))
        
        if st.button("🚀 근무표 생성 및 게시"):
            if file:
                input_df = pd.read_excel(file)
                res_df, res_stats = generate_schedule_logic(input_df, s_date, e_date)
                st.session_state.df = res_df
                st.session_state.stats = res_stats
                st.rerun()

st.title("📢 실시간 근무 게시판")

if st.session_state.df is not None:
    df = st.session_state.df.copy()
    df['날짜'] = pd.to_datetime(df['날짜'])
    
    # 다운로드 버튼
    excel_data = make_final_excel_blob(df, st.session_state.stats)
    st.download_button(
        label="📥 전체 근무표(3개 시트) 엑셀 다운로드",
        data=excel_data,
        file_name=f"근무표_{datetime.now().strftime('%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()

    # --- 주간 단위 세로 나열 시각화 ---
    st.subheader("🗓️ 주간 근무 현황")
    
    # 주차(ISO Week) 계산
    df['주차'] = df['날짜'].dt.isocalendar().week
    weeks = sorted(df['주차'].unique())
    
    for i, week in enumerate(weeks):
        st.markdown(f"#### 📅 {i+1}주차 근무 일정")
        week_df = df[df['주차'] == week]
        
        # 가로축을 날짜로 정렬하여 피벗
        pivot_week = week_df.pivot_table(
            index=['캠퍼스', '근무지'],
            columns='날짜',
            values='직원',
            aggfunc=lambda x: ", ".join(x)
        ).fillna("-")
        
        # 컬럼명을 "MM-DD(요일)" 형태로 변형
        pivot_week.columns = [f"{d.strftime('%m-%d')}({get_korean_weekday(d)})" for d in pivot_week.columns]
        
        st.table(pivot_week)
        st.write("") # 간격 조절

else:
    st.warning("현재 게시된 근무표가 없습니다. 관리자 메뉴에서 파일을 업로드해 주세요.")