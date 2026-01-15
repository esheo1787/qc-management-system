"""
Streamlit Dashboard for QC Management System.
Provides ADMIN and WORKER interfaces with WorkLog support.

NOTE: Real-time second-by-second timers are NOT implemented per Step 0 rules.
Time display shows "started at HH:MM" or "accumulated time at refresh".
"""
import json
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from config import TIMEZONE

# ============================================================
# 컬럼 설정 저장/로드 (로컬 JSON 파일)
# ============================================================
COLUMN_SETTINGS_DIR = Path("./data")
COLUMN_SETTINGS_FILE = COLUMN_SETTINGS_DIR / "column_settings.json"


def _load_column_settings() -> dict:
    """로컬 파일에서 컬럼 설정 로드."""
    if COLUMN_SETTINGS_FILE.exists():
        try:
            with open(COLUMN_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_column_settings(settings: dict) -> None:
    """컬럼 설정을 로컬 파일에 저장."""
    COLUMN_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(COLUMN_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def _get_user_column_settings(role: str, table_key: str) -> dict:
    """특정 역할/테이블의 컬럼 설정 가져오기."""
    settings = _load_column_settings()
    return settings.get(role, {}).get(table_key, {"visible": [], "pinned": []})


def _set_user_column_settings(role: str, table_key: str, visible: list, pinned: list) -> None:
    """특정 역할/테이블의 컬럼 설정 저장."""
    settings = _load_column_settings()
    if role not in settings:
        settings[role] = {}
    settings[role][table_key] = {"visible": visible, "pinned": pinned}
    _save_column_settings(settings)


from database import SessionLocal
from metrics import (
    compute_capacity_metrics,
    compute_man_days,
    compute_monthly_performance,
    compute_performance_stats,
    compute_timeline,
    compute_work_seconds,
    count_workdays,
    format_duration,
    get_timeline_dates,
)
from services import (
    get_case_feedbacks,
    create_feedback,
    update_feedback,
    delete_feedback,
)
from models import (
    ActionType,
    AppConfig,
    AutoQcSummary,
    Case,
    CaseStatus,
    Difficulty,
    Event,
    EventType,
    Part,
    PreQcSummary,
    Project,
    ReviewerQcFeedback,
    ReviewNote,
    TimeOffType,
    User,
    UserRole,
    UserTimeOff,
    WorkCalendar,
    WorkLog,
    WorkerQcFeedback,
)

# Page config
st.set_page_config(
    page_title="QC 관리 시스템",
    page_icon="",
    layout="wide",
)

# ============================================================
# 전역 CSS (모든 페이지에 동일 적용)
# ============================================================
st.markdown("""
<style>
/* =========================================================
AG Grid: 헤더 / 셀 왼쪽 정렬 + 줄바꿈
========================================================= */
.ag-theme-streamlit .ag-header-cell-label{
justify-content: flex-start !important;
}
.ag-theme-streamlit .ag-header-cell-text{
text-align: left !important;
}

/* 셀 왼쪽 정렬 (모든 컬럼) */
.ag-theme-streamlit .ag-cell{
display: flex !important;
align-items: center !important;
justify-content: flex-start !important;
}

/* 값 줄바꿈 (잘림 방지) */
.ag-theme-streamlit .ag-cell-value{
white-space: normal !important;
line-height: 1.3 !important;
}

/* 점 3개 메뉴 버튼 숨기기 */
.ag-theme-streamlit .ag-header-cell-menu-button{
display: none !important;
}

/* 정렬 아이콘 숨기기 */
.ag-theme-streamlit .ag-sort-indicator-icon,
.ag-theme-streamlit .ag-header-icon,
.ag-theme-streamlit .ag-sort-indicator-container{
display: none !important;
}

/* =========================================================
Filter UI: MultiSelect 태그(칩) 스타일
========================================================= */

/* MultiSelect: placeholder 텍스트 (Choose options) */
[data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="icon"]{
width: 20px !important;
height: 20px !important;
}

/* MultiSelect 태그(칩) 스타일 */
[data-testid="stMultiSelect"] [data-baseweb="tag"]{
background-color: #EEF2F7 !important;
color: #1F2937 !important;
border: 1px solid #D7DEE8 !important;
border-radius: 12px !important;
padding: 2px 8px !important;
margin: 3px 4px 3px 0 !important;
font-size: 13px !important;
height: 24px !important;
line-height: 20px !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span{
font-size: 13px !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] svg{
width: 14px !important;
height: 14px !important;
opacity: 0.7 !important;
}

/* MultiSelect "모두 지우기" 버튼 숨기기 (오른쪽 X 버튼) */
[data-testid="stMultiSelect"] [role="button"][aria-label="Clear all"],
[data-testid="stMultiSelect"] [data-baseweb="clear-icon"],
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div > div:last-child svg:first-of-type{
display: none !important;
}

/* MultiSelect "No results" 메시지 숨기기 */
[data-testid="stMultiSelect"] [data-baseweb="menu"] li:only-child,
[data-testid="stMultiSelect"] ul[role="listbox"] li:only-child,
[data-testid="stMultiSelect"] li[aria-disabled="true"]{
display: none !important;
}
/* 빈 드롭다운 메뉴 자체도 숨기기 */
[data-testid="stMultiSelect"] ul[role="listbox"]:empty,
[data-testid="stMultiSelect"] ul[role="listbox"]:has(> li:only-child){
display: none !important;
}

/* 버튼(필터 초기화 포함) 크기 통일 */
[data-testid="stButton"] button{
height: 38px !important;
min-height: 38px !important;
padding: 0 16px !important;
font-size: 14px !important;
line-height: 38px !important;
}

/* Metric 값 크기 */
[data-testid="stMetricValue"]{
font-size: 24px !important;
}

/* =========================================================
Tabs: 화면 너비에 맞게 균등 배치
========================================================= */
/* 탭 컨테이너를 전체 너비로 */
[data-testid="stTabs"] > div:first-child{
width: 100% !important;
}

/* 탭 버튼 목록 flex로 균등 배치 */
[data-testid="stTabs"] [role="tablist"]{
display: flex !important;
width: 100% !important;
gap: 0 !important;
}

/* 각 탭 버튼을 균등하게 확장 */
[data-testid="stTabs"] [role="tablist"] button{
flex: 1 !important;
justify-content: center !important;
padding: 12px 16px !important;
font-size: 15px !important;
white-space: nowrap !important;
}

/* 탭 하단 밑줄(indicator) 숨기거나 조정 */
[data-testid="stTabs"] [data-baseweb="tab-highlight"]{
display: none !important;
}

/* 선택된 탭 강조 */
[data-testid="stTabs"] [role="tablist"] button[aria-selected="true"]{
border-bottom: 3px solid #FF4B4B !important;
font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# Pause reason options
PAUSE_REASONS = [
    "다른 업무",
    "기술적 문제",
    "기타",
]

# ============================================================
# 공통 UI 상수 및 라벨 (Admin/Worker 동일 적용)
# ============================================================

# 상태 옵션 (영어 키 그대로 사용)
STATUS_OPTIONS = [
    CaseStatus.TODO.value,
    CaseStatus.IN_PROGRESS.value,
    CaseStatus.SUBMITTED.value,
    CaseStatus.REWORK.value,
    CaseStatus.ACCEPTED.value,
]

# ============================================================
# 테이블 동적 높이 계산 (공통 헬퍼)
# ============================================================

# 상수 정의
TABLE_ROW_HEIGHT = 35  # 행 높이 (px)
TABLE_HEADER_HEIGHT = 40  # 헤더 높이 (px)
TABLE_FOOTER_HEIGHT = 50  # 페이지네이션 영역 높이 (px)
TABLE_MIN_ROWS = 5  # 최소 표시 행 수
TABLE_DEFAULT_PAGE_SIZE = 25  # 기본 페이지 사이즈

# st.dataframe용 상수 (페이지네이션 없음)
DATAFRAME_ROW_HEIGHT = 35  # 행 높이 (px)
DATAFRAME_HEADER_HEIGHT = 38  # 헤더 높이 (px)
DATAFRAME_PADDING = 10  # 상하 여백 (px)


def calculate_table_height(
    row_count: int,
    page_size: int = TABLE_DEFAULT_PAGE_SIZE,
    min_rows: int = TABLE_MIN_ROWS,
) -> int:
    """
    테이블 행 수에 따른 동적 높이 계산 (AgGrid용).

    - row_count < page_size: 행 수에 맞춰 높이 축소
    - row_count >= page_size: 고정 높이 (page_size 기준)
    - 최소 높이는 min_rows 기준으로 유지

    Args:
        row_count: 현재 표시할 데이터 행 수
        page_size: 페이지당 최대 행 수 (기본 25)
        min_rows: 최소 표시 행 수 (기본 5)

    Returns:
        계산된 테이블 높이 (px)
    """
    # 표시할 행 수 결정
    display_rows = min(row_count, page_size)

    # 최소 행 수 보장
    display_rows = max(display_rows, min_rows)

    # 높이 계산: 헤더 + (행 수 * 행 높이) + 푸터
    height = TABLE_HEADER_HEIGHT + (display_rows * TABLE_ROW_HEIGHT) + TABLE_FOOTER_HEIGHT

    return height


def calculate_dataframe_height(
    row_count: int,
    max_rows: int = 10,
    min_rows: int = 3,
) -> int:
    """
    st.dataframe용 동적 높이 계산.

    - row_count < max_rows: 행 수에 맞춰 높이 축소
    - row_count >= max_rows: 고정 높이 (max_rows 기준)
    - 최소 높이는 min_rows 기준으로 유지

    Args:
        row_count: 현재 표시할 데이터 행 수
        max_rows: 최대 표시 행 수 (기본 10)
        min_rows: 최소 표시 행 수 (기본 3)

    Returns:
        계산된 테이블 높이 (px)
    """
    # 표시할 행 수 결정
    display_rows = min(row_count, max_rows)

    # 최소 행 수 보장
    display_rows = max(display_rows, min_rows)

    # 높이 계산: 헤더 + (행 수 * 행 높이) + 여백
    height = DATAFRAME_HEADER_HEIGHT + (display_rows * DATAFRAME_ROW_HEIGHT) + DATAFRAME_PADDING

    return height


# ============================================================
# 테이블 렌더 SSOT (Single Source of Truth)
# 모든 테이블은 이 두 함수를 통해서만 렌더링됨
# ============================================================

def render_table_df(
    df: pd.DataFrame,
    *,
    height: int = None,
    max_rows: int = 10,
    min_rows: int = 3,
    hide_index: bool = True,
    use_container_width: bool = True,
    key: str = None,
) -> None:
    """
    st.dataframe 기반 테이블 렌더링 (SSOT).
    보조/요약 테이블용. 페이지네이션 없음.

    Args:
        df: 표시할 데이터프레임
        height: 테이블 높이 (None이면 자동 계산)
        max_rows: 최대 표시 행 수 (기본 10)
        min_rows: 최소 표시 행 수 (기본 3)
        hide_index: 인덱스 숨김 여부
        use_container_width: 컨테이너 너비 사용
        key: 위젯 키
    """
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return

    row_count = len(df)

    # 높이 자동 계산 (height가 None일 때만)
    calculated_height = height if height is not None else calculate_dataframe_height(row_count, max_rows, min_rows)

    st.dataframe(
        df,
        height=calculated_height,
        hide_index=hide_index,
        use_container_width=use_container_width,
        key=key,
    )


# 테이블 컬럼 라벨 (공통)
UI_LABELS = {
    "id": "번호",
    "case_uid": "케이스 ID",
    "original_name": "원본 이름",
    "display_name": "이름",
    "project": "프로젝트",
    "part": "부위",
    "hospital": "병원",
    "status": "상태",
    "pause_reason": "중단 사유",
    "revision": "재작업",
    "assignee": "담당자",
    "work_days_time": "작업일수/시간",
    "created_at": "등록일",
    "difficulty": "난이도",
    "slice_thickness": "두께(mm)",
    "nas_path": "폴더 경로",
    "filter_reset": "필터 초기화",
    "all": "전체",
    "unassigned": "미지정",
}

# ============================================================
# 공통 데이터프레임 렌더링 함수
# ============================================================

def render_styled_dataframe(
    df: pd.DataFrame,
    key: str = None,
    height: int = None,
    hide_columns: list = None,
    enable_selection: bool = True,
    show_toolbar: bool = True,
    pinnable_columns: list = None,
    user_role: str = None,
    page_size: int = TABLE_DEFAULT_PAGE_SIZE,
) -> dict:
    """
    AG Grid 기반 테이블 렌더링.
    - 컬럼/값 길이에 맞춰 자동 조절
    - 화면 크기에 반응 (flex)
    - 왼쪽 정렬
    - 메뉴/정렬 아이콘 제거
    - 툴바: CSV 내보내기, 컬럼 숨기기/고정
    - 행 수에 따른 동적 높이 조절

    Args:
        df: 데이터프레임
        key: 위젯 키
        height: 테이블 높이 (None이면 행 수에 따라 자동 계산)
        hide_columns: 숨길 컬럼 리스트 (코드에서 강제 숨김)
        enable_selection: 행 선택 활성화 여부
        show_toolbar: 툴바 표시 여부
        pinnable_columns: 고정 가능한 컬럼 리스트 (None이면 모든 컬럼)
        user_role: 사용자 역할 (admin/worker) - 설정 저장용
        page_size: 페이지당 행 수 (기본 25)

    Returns:
        grid_response (enable_selection=True) 또는 None
    """
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return None

    display_df = df.copy()

    # 코드에서 강제 숨김 컬럼 제거
    if hide_columns:
        display_df = display_df.drop(columns=hide_columns, errors="ignore")

    all_columns = list(display_df.columns)

    # 세션 상태 키
    visible_key = f"{key}_visible_cols" if key else "_visible_cols"
    pinned_key = f"{key}_pinned_cols" if key else "_pinned_cols"

    # 파일에서 저장된 설정 로드 (세션에 없을 때만)
    if user_role and key:
        if visible_key not in st.session_state:
            saved = _get_user_column_settings(user_role, key)
            st.session_state[visible_key] = saved.get("visible", [])
            st.session_state[pinned_key] = saved.get("pinned", [])

    # 전체 선택 체크박스 키
    select_all_visible_key = f"{key}_select_all_visible" if key else "_select_all_visible"
    select_all_pinned_key = f"{key}_select_all_pinned" if key else "_select_all_pinned"

    # 컬럼 초기화 콜백 함수 (on_click에서 사용)
    def _reset_column_settings():
        st.session_state[visible_key] = []
        st.session_state[pinned_key] = []
        # 전체 선택 체크박스도 초기화
        if select_all_visible_key in st.session_state:
            del st.session_state[select_all_visible_key]
        if select_all_pinned_key in st.session_state:
            del st.session_state[select_all_pinned_key]
        # 파일에도 초기화 저장
        if user_role and key:
            _set_user_column_settings(user_role, key, [], [])

    # 툴바 렌더링
    if show_toolbar:
        with st.expander("컬럼 설정", expanded=False):
            setting_cols = st.columns(2)

            with setting_cols[0]:
                # 라벨과 전체 체크박스를 한 줄에
                label_col, check_col = st.columns([3, 1])
                with label_col:
                    st.markdown("**표시할 컬럼**")
                with check_col:
                    current_visible = st.session_state.get(visible_key, [])
                    is_all_visible = len(current_visible) == len(all_columns) and set(current_visible) == set(all_columns) if all_columns else False
                    
                    # 체크박스 상태를 multiselect 상태에 맞춰 동기화
                    st.session_state[select_all_visible_key] = is_all_visible
                    
                    def on_visible_checkbox_change():
                        if st.session_state[select_all_visible_key]:
                            st.session_state[visible_key] = list(all_columns)
                        else:
                            st.session_state[visible_key] = []
                    
                    st.checkbox(
                        "전체",
                        key=select_all_visible_key,
                        on_change=on_visible_checkbox_change,
                    )

                st.multiselect(
                    "표시할 컬럼 (비어있으면 전체)",
                    options=all_columns,
                    key=visible_key,
                    label_visibility="collapsed",
                )

            with setting_cols[1]:
                # 라벨과 전체 체크박스를 한 줄에
                label_col2, check_col2 = st.columns([3, 1])
                with label_col2:
                    st.markdown("**왼쪽 고정 컬럼**")
                with check_col2:
                    available_for_pin = pinnable_columns if pinnable_columns else all_columns
                    current_pinned = st.session_state.get(pinned_key, [])
                    is_all_pinned = len(current_pinned) == len(available_for_pin) and set(current_pinned) == set(available_for_pin) if available_for_pin else False
                    
                    # 체크박스 상태를 multiselect 상태에 맞춰 동기화
                    st.session_state[select_all_pinned_key] = is_all_pinned
                    
                    def on_pinned_checkbox_change():
                        if st.session_state[select_all_pinned_key]:
                            st.session_state[pinned_key] = list(available_for_pin)
                        else:
                            st.session_state[pinned_key] = []
                    
                    st.checkbox(
                        "전체",
                        key=select_all_pinned_key,
                        on_change=on_pinned_checkbox_change,
                    )

                available_for_pin = pinnable_columns if pinnable_columns else all_columns
                st.multiselect(
                    "왼쪽 고정 컬럼",
                    options=available_for_pin,
                    key=pinned_key,
                    label_visibility="collapsed",
                )

            # 초기화 버튼 (on_click 콜백 사용)
            st.button(
                "컬럼 설정 초기화",
                key=f"{key}_reset_cols" if key else "_reset_cols",
                on_click=_reset_column_settings,
            )

            # 설정이 변경되면 파일에 저장
            if user_role and key:
                current_visible = st.session_state.get(visible_key, [])
                current_pinned = st.session_state.get(pinned_key, [])
                _set_user_column_settings(user_role, key, current_visible, current_pinned)

    # 표시할 컬럼 결정 (선택된 게 없으면 전체 표시)
    visible_cols_state = st.session_state.get(visible_key, [])
    visible_columns = visible_cols_state if visible_cols_state else all_columns
    display_df = display_df[visible_columns]

    # CSV 내보내기 (표 바로 위)
    if show_toolbar:
        csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="CSV 내보내기",
            data=csv_data,
            file_name=f"{key or 'data'}.csv",
            mime="text/csv",
            key=f"{key}_csv_download" if key else None,
        )

    # 고정 컬럼
    pinned_columns = st.session_state.get(pinned_key, [])

    gb = GridOptionsBuilder.from_dataframe(display_df)

    # 기본 컬럼 설정: 왼쪽 정렬, 메뉴/정렬 제거, flex
    gb.configure_default_column(
        filter=False,
        sortable=False,  # 정렬 아이콘 제거
        resizable=True,
        suppressMenu=True,  # 메뉴 제거
        floatingFilter=False,
        cellStyle={"textAlign": "left"},  # 왼쪽 정렬
        wrapText=True,
        autoHeight=True,
        flex=1,  # 화면 크기에 맞춰 자동 조절
        minWidth=80,
    )

    # 컬럼별 minWidth 추정 (값/헤더 길이 기반)
    def _estimate_min_width(col: str) -> int:
        header_len = len(str(col))
        s = display_df[col].astype(str)
        if len(s) > 100:
            s = s.sample(100, random_state=0)
        val_len = int(s.map(len).max()) if len(s) else 0
        max_len = max(header_len, val_len)
        # NAS 경로 등 긴 컬럼은 넓게
        if "경로" in col or "path" in col.lower():
            return max(200, min(400, max_len * 8 + 20))
        return int(min(300, max(60, max_len * 8 + 16)))

    for col in display_df.columns:
        is_pinned = col in pinned_columns
        gb.configure_column(
            col,
            minWidth=_estimate_min_width(col),
            pinned="left" if is_pinned else None,
        )

    if enable_selection:
        gb.configure_selection(selection_mode="single", use_checkbox=False)

    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=page_size)

    grid_options = gb.build()

    # Page Size 옵션 설정
    grid_options["paginationPageSizeSelector"] = [25, 50, 100]

    # 동적 높이 계산 (height가 None이면 자동 계산)
    row_count = len(display_df)
    calculated_height = height if height is not None else calculate_table_height(row_count, page_size)

    # 행 수가 page_size보다 적을 때 자동 높이 적용 (빈 공간 제거)
    if row_count < page_size:
        grid_options["domLayout"] = "autoHeight"

    # columnDefs 강제 덮어쓰기 (메뉴/정렬 완전 제거 + 왼쪽 정렬)
    for col in grid_options.get("columnDefs", []):
        col["suppressMenu"] = True
        col["suppressHeaderContextMenu"] = True  # 헤더 우클릭 메뉴 제거
        col["sortable"] = False  # 정렬 아이콘 제거
        col["cellStyle"] = {"textAlign": "left"}
        col["headerClass"] = "ag-header-cell-left"
        col["wrapText"] = True
        col["autoHeight"] = True

    # 렌더 후 컬럼 자동 크기 조절 + 화면 맞춤
    grid_options["onFirstDataRendered"] = JsCode("""
    function(params) {
        const allCols = params.columnApi.getAllColumns().map(c => c.getColId());
        params.columnApi.autoSizeColumns(allCols, false);
        params.api.sizeColumnsToFit();
    }
    """)

    # 화면 크기 변경 시 다시 맞춤
    grid_options["onGridSizeChanged"] = JsCode("""
    function(params) {
        params.api.sizeColumnsToFit();
    }
    """)

    # 셀/헤더 우클릭 메뉴 비활성화
    grid_options["suppressContextMenu"] = True

    # CSS: 왼쪽 정렬 + 정렬 아이콘 숨김
    custom_css = {
        ".ag-header-cell-label": {"justify-content": "flex-start"},
        ".ag-header-cell-text": {"text-align": "left"},
        ".ag-cell": {
            "display": "flex",
            "align-items": "center",
            "justify-content": "flex-start",
        },
        ".ag-cell-value": {"white-space": "normal", "line-height": "1.3"},
        ".ag-sort-indicator-icon": {"display": "none"},
        ".ag-header-icon": {"display": "none"},
    }

    grid_response = AgGrid(
        display_df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        height=calculated_height,
        key=key,
        theme="streamlit",
        custom_css=custom_css,
    )

    return grid_response if enable_selection else None


# ============================================================
# 필터 UI 렌더링 (공통)
# ============================================================

def _reset_case_filters(prefix: str, show_assignee: bool):
    """필터 초기화 콜백 함수 (on_click용)."""
    st.session_state[f"{prefix}_case_id_search"] = ""
    st.session_state[f"{prefix}_filter_project"] = []
    st.session_state[f"{prefix}_filter_part"] = []
    st.session_state[f"{prefix}_filter_hospital"] = []
    st.session_state[f"{prefix}_filter_status"] = []
    if show_assignee:
        st.session_state[f"{prefix}_filter_assignee"] = []


def render_case_filters(
    df: pd.DataFrame,
    prefix: str,
    show_assignee: bool = True,
) -> pd.DataFrame:
    """
    Streamlit 네이티브 필터 UI 렌더링.
    AG Grid Enterprise 없이 필터 기능 제공.

    Args:
        df: 원본 DataFrame
        prefix: 세션 키 prefix (admin/worker)
        show_assignee: 담당자 필터 표시 여부

    Returns:
        필터링된 DataFrame
    """
    if df.empty:
        return df

    # 위젯 생성 전에 session_state 초기값 설정 (setdefault)
    st.session_state.setdefault(f"{prefix}_case_id_search", "")
    st.session_state.setdefault(f"{prefix}_filter_project", [])
    st.session_state.setdefault(f"{prefix}_filter_part", [])
    st.session_state.setdefault(f"{prefix}_filter_hospital", [])
    st.session_state.setdefault(f"{prefix}_filter_status", [])
    if show_assignee:
        st.session_state.setdefault(f"{prefix}_filter_assignee", [])

    filtered_df = df.copy()

    # 전체 선택 체크박스 처리 헬퍼
    def _render_filter_with_select_all(label: str, checkbox_key: str, filter_key: str, options: list):
        """라벨과 전체선택 체크박스를 렌더링하고 multiselect 반환."""
        current = st.session_state.get(filter_key, [])
        is_all = len(current) == len(options) and set(current) == set(options) if options else False

        # 체크박스 상태를 위젯 렌더링 전에 동기화 (핵심!)
        # 이미 존재하는 경우에도 multiselect 상태에 맞춰 업데이트
        st.session_state[checkbox_key] = is_all

        label_col, check_col = st.columns([3, 1])
        with label_col:
            st.markdown(f"**{label}**")
        with check_col:
            # on_change 콜백으로 체크박스 클릭 처리
            def on_checkbox_change():
                if st.session_state[checkbox_key]:
                    st.session_state[filter_key] = list(options)
                else:
                    st.session_state[filter_key] = []

            st.checkbox(
                "전체",
                key=checkbox_key,
                on_change=on_checkbox_change if options else None,
                disabled=not options,
            )

        # multiselect 렌더링
        st.multiselect(
            label,
            options=options,
            key=filter_key,
            label_visibility="collapsed",
        )

    # 필터 UI를 expander로 감싸기
    with st.expander("필터", expanded=False):
        # 1행: 케이스ID + 프로젝트 + 부위
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**케이스ID**")
            st.text_input(
                "케이스ID",
                key=f"{prefix}_case_id_search",
                placeholder="검색...",
                label_visibility="collapsed",
            )

        with col2:
            project_options = []
            if UI_LABELS["project"] in df.columns:
                project_options = sorted(df[UI_LABELS["project"]].dropna().unique().tolist())
            _render_filter_with_select_all(
                "프로젝트",
                f"{prefix}_select_all_project",
                f"{prefix}_filter_project",
                project_options,
            )

        with col3:
            part_options = []
            if UI_LABELS["part"] in df.columns:
                part_options = sorted(df[UI_LABELS["part"]].dropna().unique().tolist())
            _render_filter_with_select_all(
                "부위",
                f"{prefix}_select_all_part",
                f"{prefix}_filter_part",
                part_options,
            )

        # 2행: 병원 + 상태 + 담당자
        col4, col5, col6 = st.columns(3)

        with col4:
            hospital_options = []
            if UI_LABELS["hospital"] in df.columns:
                hospital_options = sorted(df[UI_LABELS["hospital"]].dropna().unique().tolist())
            _render_filter_with_select_all(
                "병원",
                f"{prefix}_select_all_hospital",
                f"{prefix}_filter_hospital",
                hospital_options,
            )

        with col5:
            status_options = []
            if UI_LABELS["status"] in df.columns:
                status_options = sorted(df[UI_LABELS["status"]].dropna().unique().tolist())
            _render_filter_with_select_all(
                "상태",
                f"{prefix}_select_all_status",
                f"{prefix}_filter_status",
                status_options,
            )

        with col6:
            if show_assignee and UI_LABELS["assignee"] in df.columns:
                # "-"나 빈 문자열 제외
                assignee_options = sorted([
                    x for x in df[UI_LABELS["assignee"]].dropna().unique().tolist()
                    if x and x.strip() and x != "-"
                ])
                _render_filter_with_select_all(
                    "담당자",
                    f"{prefix}_select_all_assignee",
                    f"{prefix}_filter_assignee",
                    assignee_options,
                )
            else:
                st.write("")  # 빈 공간

        # 필터 초기화 버튼 (on_click 콜백 사용)
        st.button(
            "필터 초기화",
            key=f"{prefix}_reset_filters",
            type="secondary",
            on_click=_reset_case_filters,
            kwargs={"prefix": prefix, "show_assignee": show_assignee},
        )

    # 필터 적용
    # 케이스ID 텍스트 검색
    case_id_val = st.session_state.get(f"{prefix}_case_id_search", "")
    if case_id_val:
        filtered_df = filtered_df[
            filtered_df[UI_LABELS["case_uid"]].astype(str).str.contains(case_id_val, case=False, na=False)
        ]

    # 프로젝트 필터
    selected_projects = st.session_state.get(f"{prefix}_filter_project", [])
    if selected_projects and UI_LABELS["project"] in df.columns:
        filtered_df = filtered_df[filtered_df[UI_LABELS["project"]].isin(selected_projects)]

    # 부위 필터
    selected_parts = st.session_state.get(f"{prefix}_filter_part", [])
    if selected_parts and UI_LABELS["part"] in df.columns:
        filtered_df = filtered_df[filtered_df[UI_LABELS["part"]].isin(selected_parts)]

    # 병원 필터
    selected_hospitals = st.session_state.get(f"{prefix}_filter_hospital", [])
    if selected_hospitals and UI_LABELS["hospital"] in df.columns:
        filtered_df = filtered_df[filtered_df[UI_LABELS["hospital"]].isin(selected_hospitals)]

    # 상태 필터
    selected_statuses = st.session_state.get(f"{prefix}_filter_status", [])
    if selected_statuses and UI_LABELS["status"] in df.columns:
        filtered_df = filtered_df[filtered_df[UI_LABELS["status"]].isin(selected_statuses)]

    # 담당자 필터
    selected_assignees = st.session_state.get(f"{prefix}_filter_assignee", [])
    if selected_assignees and show_assignee and UI_LABELS["assignee"] in df.columns:
        filtered_df = filtered_df[filtered_df[UI_LABELS["assignee"]].isin(selected_assignees)]

    return filtered_df


def render_cases_aggrid(
    df: pd.DataFrame,
    grid_key: str,
    show_assignee: bool = True,
    height: int = None,
    enable_filter: bool = True,
    page_size: int = TABLE_DEFAULT_PAGE_SIZE,
) -> dict:
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return None

    # 동적 높이 계산 (height가 None이면 행 수에 따라 자동 계산)
    row_count = len(df)
    calculated_height = height if height is not None else calculate_table_height(row_count, page_size)

    gb = GridOptionsBuilder.from_dataframe(df)

    # ✅ 기본값: 가운데 정렬 + 줄바꿈(안 잘리게) + 높이 자동
    # ✅ AG Grid 내장 필터 활성화 (컬럼 헤더 메뉴)
    gb.configure_default_column(
        filter=enable_filter,
        sortable=True,
        resizable=True,
        suppressMenu=False,  # 메뉴 활성화
        floatingFilter=False,
        cellStyle={"textAlign": "center", "whiteSpace": "normal"},
        headerClass="ag-header-cell-center",
        wrapText=True,
        autoHeight=True,
        minWidth=60,
        flex=1,   # ✅ 기본은 모두 반응형
    )

    # ✅ 헤더/값 길이 중 큰 쪽으로 minWidth 추정 (너무 과하지 않게 상한/하한)
    # - 길이가 긴 컬럼만 더 넓게 잡히고
    # - 화면 폭에 따라 sizeColumnsToFit으로 다시 맞춰짐
    def _estimate_min_width(col: str) -> int:
        header_len = len(str(col))
        # 값 길이(샘플링) - 너무 비싸면 200개만
        s = df[col].astype(str)
        if len(s) > 200:
            s = s.sample(200, random_state=0)
        val_len = int(s.map(len).max()) if len(s) else 0

        max_len = max(header_len, val_len)
        # 대충 1글자 ~ 9px 정도로 잡고, 최소/최대 캡
        return int(min(360, max(70, max_len * 9 + 24)))

    for col in df.columns:
        gb.configure_column(col, minWidth=_estimate_min_width(col), flex=1)

    # 담당자 컬럼 숨김 (Worker 화면)
    if not show_assignee and UI_LABELS["assignee"] in df.columns:
        gb.configure_column(UI_LABELS["assignee"], hide=True)

    gb.configure_selection(selection_mode="single", use_checkbox=False)

    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=page_size)

    grid_options = gb.build()

    # Page Size 옵션 설정
    grid_options["paginationPageSizeSelector"] = [25, 50, 100]

    # 행 수가 page_size보다 적을 때 자동 높이 적용 (빈 공간 제거)
    if row_count < page_size:
        grid_options["domLayout"] = "autoHeight"

    # columnDefs 강제 덮어쓰기 (가운데 헤더 + 필터 설정 반영)
    for col in grid_options.get("columnDefs", []):
        col["filter"] = enable_filter  # enable_filter 파라미터 반영
        col["floatingFilter"] = False
        col["suppressMenu"] = not enable_filter  # 필터 활성화 시 메뉴도 활성화
        col["sortable"] = True
        col["headerClass"] = "ag-header-cell-center"
        col["wrapText"] = True
        col["autoHeight"] = True

    # ✅ 렌더 직후: 값 기준 autoSize → 화면폭에 맞게 sizeColumnsToFit
    grid_options["onFirstDataRendered"] = JsCode("""
    function(params) {
        const allCols = params.columnApi.getAllColumns().map(c => c.getColId());

        // 1) 내용(값) 기준으로 먼저 늘림
        params.columnApi.autoSizeColumns(allCols, false);

        // 2) 화면 폭에 맞게 반응형으로 맞춤
        params.api.sizeColumnsToFit();
    }
    """)

    # ✅ 화면 크기 변경 시 다시 맞춤 (진짜 “반응형”)
    grid_options["onGridSizeChanged"] = JsCode("""
    function(params) {
        params.api.sizeColumnsToFit();
    }
    """)

    # custom_css: iframe 내부에 직접 주입 (확실한 가운데 정렬)
    custom_css = {
        ".ag-header-cell-label": {"justify-content": "center"},
        ".ag-header-cell-text": {"text-align": "center", "width": "100%"},
        ".ag-cell": {
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
        },
        ".ag-cell-value": {"white-space": "normal", "line-height": "1.2"},
    }

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=False,  # 우리가 JS로 컨트롤
        allow_unsafe_jscode=True,
        height=calculated_height,
        key=grid_key,
        theme="streamlit",
        custom_css=custom_css,
    )

    return grid_response


def group_consecutive_timeoffs(timeoffs: list) -> list[dict]:
    """
    Group consecutive time-offs by user and type.
    Returns list of grouped periods.
    """
    if not timeoffs:
        return []

    # Sort by user, type, date
    sorted_timeoffs = sorted(timeoffs, key=lambda t: (t.user.username, t.type.value, t.date))

    groups = []
    current_group = None

    for t in sorted_timeoffs:
        if current_group is None:
            # Start new group
            current_group = {
                "user_id": t.user_id,
                "username": t.user.username,
                "type": t.type,
                "start_date": t.date,
                "end_date": t.date,
                "days": 1,
                "ids": [t.id],
            }
        elif (
            current_group["user_id"] == t.user_id
            and current_group["type"] == t.type
            and (t.date - current_group["end_date"]).days == 1
        ):
            # Extend current group (consecutive date)
            current_group["end_date"] = t.date
            current_group["days"] += 1
            current_group["ids"].append(t.id)
        else:
            # Save current group and start new one
            groups.append(current_group)
            current_group = {
                "user_id": t.user_id,
                "username": t.user.username,
                "type": t.type,
                "start_date": t.date,
                "end_date": t.date,
                "days": 1,
                "ids": [t.id],
            }

    # Don't forget the last group
    if current_group:
        groups.append(current_group)

    # Calculate hours and format period
    for g in groups:
        if g["type"] == TimeOffType.VACATION:
            g["hours"] = g["days"] * 8
            g["days_display"] = f"{g['days']}일"
        else:  # HALF_DAY
            g["hours"] = g["days"] * 4
            g["days_display"] = f"{g['days'] * 0.5}일"

        # Format period string
        if g["start_date"] == g["end_date"]:
            g["period"] = g["start_date"].strftime("%Y-%m-%d")
        else:
            g["period"] = f"{g['start_date'].strftime('%Y-%m-%d')} ~ {g['end_date'].strftime('%m-%d')}"

    # Sort by start_date descending
    groups.sort(key=lambda x: x["start_date"], reverse=True)

    return groups


def get_db() -> Session:
    """Get database session."""
    return SessionLocal()


def get_config_value(db: Session, key: str, default=None):
    """Get config value from AppConfig."""
    config = db.query(AppConfig).filter(AppConfig.key == key).first()
    if config:
        return json.loads(config.value_json)
    return default


def authenticate(api_key: str) -> Optional[User]:
    """Authenticate user by API key."""
    db = get_db()
    try:
        user = db.query(User).filter(
            User.api_key == api_key,
            User.is_active == True
        ).first()
        return user
    finally:
        db.close()


def generate_idempotency_key(case_id: int, event_type: str) -> str:
    """Generate a unique idempotency key."""
    return f"{case_id}-{event_type}-{uuid.uuid4().hex[:8]}"


def get_last_worklog_action(db: Session, case_id: int) -> Optional[ActionType]:
    """Get the last worklog action for a case."""
    last_log = (
        db.query(WorkLog)
        .filter(WorkLog.case_id == case_id)
        .order_by(WorkLog.timestamp.desc())
        .first()
    )
    return last_log.action_type if last_log else None


def get_user_wip_count(db: Session, user_id: int, exclude_paused: bool = True) -> int:
    """Count user's IN_PROGRESS cases.

    Args:
        db: Database session
        user_id: User ID
        exclude_paused: If True, exclude cases where last action is PAUSE
    """
    cases = db.query(Case).filter(
        Case.assigned_user_id == user_id,
        Case.status == CaseStatus.IN_PROGRESS,
    ).all()

    if not exclude_paused:
        return len(cases)

    # Count only actively working cases (last action is START, RESUME, or REWORK_START)
    active_count = 0
    for case in cases:
        last_log = (
            db.query(WorkLog)
            .filter(WorkLog.case_id == case.id)
            .order_by(WorkLog.timestamp.desc())
            .first()
        )
        if last_log and last_log.action_type in (ActionType.START, ActionType.RESUME, ActionType.REWORK_START):
            active_count += 1

    return active_count


# ============== Session State ==============
if "user" not in st.session_state:
    st.session_state.user = None
if "api_key" not in st.session_state:
    st.session_state.api_key = None


# ============== Login ==============
def show_login():
    """Show login form."""
    st.title("QC 관리 시스템")
    st.markdown("---")

    api_key = st.text_input("API 키", type="password", key="login_api_key")

    if st.button("로그인", type="primary"):
        if api_key:
            user = authenticate(api_key)
            if user:
                st.session_state.user = {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role.value,
                }
                st.session_state.api_key = api_key
                st.rerun()
            else:
                st.error("유효하지 않은 API 키이거나 비활성 사용자입니다")
        else:
            st.warning("API 키를 입력하세요")


def logout():
    """Logout user."""
    st.session_state.user = None
    st.session_state.api_key = None
    st.rerun()


# ============== Worker View ==============
def show_worker_dashboard():
    """Show worker dashboard with WorkLog support."""
    user = st.session_state.user

    st.title(f"내 작업 - {user['username']}")

    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("로그아웃"):
            logout()

    st.markdown("---")

    # Tabs for worker
    tab1, tab2 = st.tabs(["내 작업", "휴무 관리"])

    db = get_db()
    try:
        with tab1:
            show_worker_tasks(db, user)

        with tab2:
            show_worker_timeoff(db, user)
    finally:
        db.close()


def show_worker_tasks(db: Session, user: dict):
    """Show worker tasks with AG Grid table (Google Sheets style filtering)."""
    # Get config
    wip_limit = get_config_value(db, "wip_limit", 1)
    auto_timeout = get_config_value(db, "auto_timeout_minutes", 120)
    workday_hours = get_config_value(db, "workday_hours", 8)

    # Get current WIP count (active only, excluding paused)
    current_wip = get_user_wip_count(db, user["id"], exclude_paused=True)
    total_in_progress = get_user_wip_count(db, user["id"], exclude_paused=False)
    paused_count = total_in_progress - current_wip

    # Show WIP status
    if paused_count > 0:
        st.info(f"진행 중: {current_wip}/{wip_limit} (활성) | {paused_count}건 일시중지")
    else:
        st.info(f"진행 중: {current_wip}/{wip_limit} (진행 중인 케이스)")

    # 본인 케이스 전체 조회 (DB 필터 없음 - AG Grid에서 필터링)
    cases = db.query(Case).filter(
        Case.assigned_user_id == user["id"]
    ).order_by(Case.created_at.desc()).all()
    total_count = len(cases)

    # 건수 표시
    st.caption(f"총 {total_count}건 표시 중")

    if not cases:
        st.info("배정된 작업이 없습니다.")
        return

    # DataFrame 구성 (AG Grid용)
    table_data = []
    for c in cases:
        worklogs = db.query(WorkLog).filter(WorkLog.case_id == c.id).order_by(WorkLog.timestamp).all()
        work_seconds = compute_work_seconds(worklogs, auto_timeout)

        # Determine status with pause info
        status_display = c.status.value
        last_action = get_last_worklog_action(db, c.id)
        is_paused = last_action == ActionType.PAUSE
        if c.status == CaseStatus.IN_PROGRESS and is_paused:
            status_display = "IN_PROGRESS (PAUSED)"

        # 작업일수/시간 통합 포맷
        man_days = compute_man_days(work_seconds, workday_hours)
        work_time_str = format_duration(work_seconds)
        work_days_time = f"{man_days:.2f}일 ({work_time_str})" if work_seconds > 0 else "-"

        row = {
            UI_LABELS["id"]: c.id,
            UI_LABELS["case_uid"]: c.case_uid,
            UI_LABELS["display_name"]: c.display_name,
            UI_LABELS["project"]: c.project.name,
            UI_LABELS["part"]: c.part.name,
            UI_LABELS["hospital"]: c.hospital or UI_LABELS["unassigned"],
            UI_LABELS["status"]: status_display,
            UI_LABELS["difficulty"]: c.difficulty.value,
            UI_LABELS["revision"]: c.revision,
            UI_LABELS["work_days_time"]: work_days_time,
            UI_LABELS["created_at"]: c.created_at.strftime("%Y-%m-%d"),
        }
        table_data.append(row)

    df = pd.DataFrame(table_data)

    # 필터 UI + DataFrame 필터링
    filtered_df = render_case_filters(df, "worker", show_assignee=False)

    # 공통 AG Grid 렌더링 (담당자 컬럼 제외)
    grid_response = render_styled_dataframe(
        filtered_df,
        key="worker_cases_grid",
        height=350,
        hide_columns=[UI_LABELS["assignee"]],
        user_role="worker",
    )

    # 선택된 케이스 ID 추출 (AG Grid)
    selected_case_id = None
    if grid_response:
        selected_rows = grid_response.get("selected_rows", None)
        if selected_rows is not None and len(selected_rows) > 0:
            selected_case_id = int(selected_rows.iloc[0][UI_LABELS["id"]])

    # 선택되지 않은 경우 selectbox로 선택
    if selected_case_id is None:
        st.markdown("---")
        case_options = [(c.id, f"{c.display_name} ({c.case_uid}) - {c.status.value}") for c in cases]
        selected_case_id = st.selectbox(
            "케이스 선택",
            options=[opt[0] for opt in case_options],
            format_func=lambda x: next((opt[1] for opt in case_options if opt[0] == x), str(x))
        )

    # 선택된 케이스 상세 및 작업 버튼
    if selected_case_id:
        case = db.query(Case).filter(Case.id == selected_case_id).first()
        if case:
            show_worker_case_detail(db, case, user, wip_limit, current_wip, auto_timeout, workday_hours)


def show_worker_case_detail(db: Session, case: Case, user: dict, wip_limit: int, current_wip: int, auto_timeout: int, workday_hours: int):
    """Show detailed case view with action buttons for worker."""
    st.markdown("---")
    original_name_display = case.original_name if case.original_name else case.display_name
    st.subheader(f"케이스 상세: {original_name_display}")

    # Get worklogs for this case
    worklogs = db.query(WorkLog).filter(
        WorkLog.case_id == case.id
    ).order_by(WorkLog.timestamp).all()

    last_action = get_last_worklog_action(db, case.id)
    is_working = last_action in (ActionType.START, ActionType.RESUME, ActionType.REWORK_START)
    is_paused = last_action == ActionType.PAUSE

    # Calculate accumulated time
    work_seconds = compute_work_seconds(worklogs, auto_timeout)
    work_duration = format_duration(work_seconds)

    # Status icon
    if case.status == CaseStatus.REWORK:
        icon = "🔴"
    elif case.status == CaseStatus.IN_PROGRESS:
        icon = "🟡" if is_paused else "🟢"
    else:
        icon = "⚪"

    # 중단 사유 확인 (PAUSED 상태일 때)
    pause_reason = ""
    if is_paused and worklogs:
        last_log = worklogs[-1]
        if last_log.action_type == ActionType.PAUSE and last_log.reason_code:
            pause_reason = last_log.reason_code

    status_display = case.status.value
    if is_paused:
        status_display = "IN_PROGRESS (PAUSED)"
    st.markdown(f"**{icon} 상태:** {status_display}")
    if pause_reason:
        st.caption(f"중단 사유: {pause_reason}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**{UI_LABELS['case_uid']}:** {case.case_uid}")
        st.write(f"**{UI_LABELS['original_name']}:** {original_name_display}")
        st.write(f"**{UI_LABELS['nas_path']}:** {case.nas_path if case.nas_path else '-'}")
        st.write(f"**{UI_LABELS['project']}:** {case.project.name}")
    with col2:
        st.write(f"**{UI_LABELS['part']}:** {case.part.name}")
        st.write(f"**{UI_LABELS['hospital']}:** {case.hospital or UI_LABELS['unassigned']}")
        st.write(f"**{UI_LABELS['slice_thickness']}:** {case.slice_thickness_mm if case.slice_thickness_mm else '-'}")
    with col3:
        st.write(f"**{UI_LABELS['difficulty']}:** {case.difficulty.value}")
        st.write(f"**{UI_LABELS['revision']}:** {case.revision}")

    # Time info (no real-time timer per Step 0)
    if case.status == CaseStatus.IN_PROGRESS:
        if is_working:
            # Find last start time
            last_start = None
            for wl in reversed(worklogs):
                if wl.action_type in (ActionType.START, ActionType.RESUME, ActionType.REWORK_START):
                    last_start = wl.timestamp
                    break
            if last_start:
                st.success(f"작업중 (시작: {last_start.strftime('%H:%M')})")
        elif is_paused:
            # Get last pause worklog
            last_pause = None
            for wl in reversed(worklogs):
                if wl.action_type == ActionType.PAUSE:
                    last_pause = wl
                    break

            if last_pause:
                current_reason = last_pause.reason_code or ""
                st.warning(f"일시중지 | 누적: {work_duration} | 사유: {current_reason if current_reason else '없음'}")

                # 사유 수정 UI
                edit_key = f"edit_pause_{case.id}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False

                if not st.session_state[edit_key]:
                    if st.button("사유 수정", key=f"edit_pause_btn_{case.id}"):
                        st.session_state[edit_key] = True
                        st.rerun()
                else:
                    st.markdown("**사유 수정**")
                    edit_col1, edit_col2 = st.columns(2)
                    with edit_col1:
                        new_reason = st.selectbox(
                            "중단 사유",
                            PAUSE_REASONS,
                            key=f"edit_reason_{case.id}"
                        )
                    with edit_col2:
                        new_reason_text = st.text_input(
                            "상세 사유",
                            placeholder="상세 내용 입력",
                            key=f"edit_reason_text_{case.id}"
                        )

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("저장", key=f"save_pause_{case.id}", type="primary"):
                            if new_reason_text.strip():
                                last_pause.reason_code = f"{new_reason}: {new_reason_text.strip()}"
                            else:
                                last_pause.reason_code = new_reason
                            db.commit()
                            st.session_state[edit_key] = False
                            st.success("사유가 수정되었습니다")
                            st.rerun()
                    with col_cancel:
                        if st.button("취소", key=f"cancel_edit_{case.id}"):
                            st.session_state[edit_key] = False
                            st.rerun()
            else:
                st.warning(f"일시중지 | 누적: {work_duration}")
        else:
            st.write(f"누적 시간: {work_duration}")
    elif work_seconds > 0:
        st.write(f"총 작업 시간: {work_duration}")

    # Show review notes if REWORK
    if case.status == CaseStatus.REWORK:
        notes = db.query(ReviewNote).filter(
            ReviewNote.case_id == case.id
        ).order_by(ReviewNote.created_at.desc()).limit(3).all()
        if notes:
            st.error("**재작업 사유:**")
            for note in notes:
                st.write(f"- {note.note_text} ({note.reviewer.username})")

    # ========== Pre-QC / Auto-QC 정보 표시 (Worker용) ==========
    preqc = db.query(PreQcSummary).filter(PreQcSummary.case_id == case.id).first()
    autoqc = db.query(AutoQcSummary).filter(AutoQcSummary.case_id == case.id).first()

    st.markdown("---")
    st.markdown("### QC 정보")

    qc_col1, qc_col2 = st.columns(2)

    with qc_col1:
        st.markdown("**Pre-QC**")
        with st.container(border=True):
            if preqc:
                # 슬라이스 수
                slice_count_display = preqc.slice_count if preqc.slice_count else "-"
                st.write(f"슬라이스: {slice_count_display}")

                # 두께
                thickness_icon = {"OK": "✅", "WARN": "⚠️", "THICK": "❌"}.get(preqc.slice_thickness_flag, "")
                thickness_display = f"{preqc.slice_thickness_mm:.2f}mm {thickness_icon}" if preqc.slice_thickness_mm is not None else "-"
                st.write(f"두께: {thickness_display}")

                # 노이즈
                noise_icon = {"LOW": "🟢", "MODERATE": "🟡", "HIGH": "🔴"}.get(preqc.noise_level, "")
                if preqc.noise_level:
                    noise_mean = f" (평균: {preqc.noise_sigma_mean:.2f})" if preqc.noise_sigma_mean is not None else ""
                    st.write(f"노이즈: {noise_icon} {preqc.noise_level}{noise_mean}")
                else:
                    st.write("노이즈: -")

                # 조영제
                contrast_icon = {"GOOD": "🟢", "BORDERLINE": "🟡", "POOR": "🔴"}.get(preqc.contrast_flag, "")
                if preqc.contrast_flag:
                    delta_hu = f" (Delta HU: {preqc.delta_hu:.1f})" if preqc.delta_hu is not None else ""
                    st.write(f"조영제: {contrast_icon} {preqc.contrast_flag}{delta_hu}")
                else:
                    st.write("조영제: -")

                # 혈관 가시성
                vis_icon = {"EXCELLENT": "🟢", "USABLE": "🟢", "BORDERLINE": "🟡", "POOR": "🔴"}.get(preqc.vascular_visibility_level, "")
                if preqc.vascular_visibility_level:
                    vis_score = f" (점수: {preqc.vascular_visibility_score:.1f})" if preqc.vascular_visibility_score is not None else ""
                    st.write(f"혈관 가시성: {vis_icon} {preqc.vascular_visibility_level}{vis_score}")
                else:
                    st.write("혈관 가시성: -")

                # 난이도
                diff_icon = {"EASY": "🟢", "NORMAL": "🟡", "HARD": "🔴", "VERY_HARD": "🔴"}.get(preqc.difficulty, "")
                if preqc.difficulty:
                    st.write(f"난이도: {diff_icon} {preqc.difficulty}")
                else:
                    st.write("난이도: -")

                # 스페이싱
                if preqc.spacing_json:
                    try:
                        spacing = json.loads(preqc.spacing_json)
                        spacing_str = str(spacing) if spacing else "-"
                        st.write(f"스페이싱: {spacing_str}")
                    except json.JSONDecodeError:
                        st.write(f"스페이싱: {preqc.spacing_json}")
                else:
                    st.write("스페이싱: -")

                # 메모
                if preqc.notes:
                    st.info(f"메모: {preqc.notes}")
                else:
                    st.write("메모: -")
            else:
                st.caption("Pre-QC 데이터 없음")

    with qc_col2:
        st.markdown("**Auto-QC**")
        with st.container(border=True):
            if autoqc:
                # 상태
                status_icon = {"PASS": "✅", "WARN": "⚠️", "INCOMPLETE": "❌"}.get(autoqc.status, "")
                st.write(f"상태: {status_icon} {autoqc.status or '-'}")

                # 재작업 및 이전 대비
                revision = autoqc.revision if hasattr(autoqc, 'revision') and autoqc.revision else 1
                comparison_display = "-"
                if revision > 1:
                    # 현재 이슈 수 계산
                    current_issue_count = 0
                    if autoqc.issue_count_json:
                        try:
                            counts = json.loads(autoqc.issue_count_json)
                            current_issue_count = counts.get("warn_level", 0) + counts.get("incomplete_level", 0)
                        except json.JSONDecodeError:
                            pass
                    # 이전 이슈 수
                    prev_count = autoqc.previous_issue_count if hasattr(autoqc, 'previous_issue_count') and autoqc.previous_issue_count is not None else 0
                    if current_issue_count < prev_count:
                        comparison_display = "✅ 개선"
                    elif current_issue_count == prev_count:
                        comparison_display = "⚠️ 동일"
                    else:
                        comparison_display = "❌ 악화"
                st.write(f"재작업: {revision} (이전 대비: {comparison_display})")

                st.markdown("---")

                # 누락 세그먼트
                st.write("📋 누락 세그먼트:")
                if autoqc.missing_segments_json:
                    try:
                        missing = json.loads(autoqc.missing_segments_json)
                        if missing:
                            for seg in missing:
                                st.caption(f"  • {seg}")
                        else:
                            st.caption("  없음")
                    except json.JSONDecodeError:
                        st.caption("  없음")
                else:
                    st.caption("  없음")

                # 이름 불일치
                mismatch_count = 0
                mismatches = []
                if autoqc.name_mismatches_json:
                    try:
                        mismatches = json.loads(autoqc.name_mismatches_json)
                        mismatch_count = len(mismatches) if mismatches else 0
                    except json.JSONDecodeError:
                        pass
                st.write(f"📋 이름 불일치 ({mismatch_count}건):")
                if mismatches:
                    for m in mismatches[:10]:
                        expected = m.get('expected', '?')
                        found = m.get('found', '?')
                        mtype = m.get('type', '')
                        st.caption(f"  • {expected} → {found} ({mtype})")
                    if len(mismatches) > 10:
                        st.caption(f"  ... 외 {len(mismatches) - 10}건")
                else:
                    st.caption("  없음")

                # 이슈 목록
                st.write("📋 이슈 목록:")
                if autoqc.issues_json:
                    try:
                        issues = json.loads(autoqc.issues_json)
                        if issues:
                            severity_icons = {"WARN": "⚠️", "INCOMPLETE": "❌", "INFO": "ℹ️"}
                            for issue in issues[:10]:
                                level = issue.get("level", "")
                                segment = issue.get("segment", "")
                                msg = issue.get("message", str(issue))
                                icon = severity_icons.get(level, "•")
                                st.caption(f"  • {icon}: {segment} - {msg}")
                            if len(issues) > 10:
                                st.caption(f"  ... 외 {len(issues) - 10}건")
                        else:
                            st.caption("  없음")
                    except json.JSONDecodeError:
                        st.caption("  없음")
                else:
                    st.caption("  없음")

                # 추가 세그먼트
                extra_segments_display = "없음"
                if autoqc.extra_segments_json:
                    try:
                        extra = json.loads(autoqc.extra_segments_json)
                        if extra:
                            extra_segments_display = ", ".join(extra)
                    except json.JSONDecodeError:
                        pass
                st.write(f"📋 추가 세그먼트: {extra_segments_display}")

                st.markdown("---")

                # WARN / INCOMPLETE 건수
                warn_cnt = 0
                inc_cnt = 0
                if autoqc.issue_count_json:
                    try:
                        counts = json.loads(autoqc.issue_count_json)
                        warn_cnt = counts.get("warn_level", 0)
                        inc_cnt = counts.get("incomplete_level", 0)
                    except json.JSONDecodeError:
                        pass
                st.write(f"WARN: {warn_cnt}건 / INCOMPLETE: {inc_cnt}건")
            else:
                st.caption("Auto-QC 데이터 없음")

    # ========== 검수자 판정 결과 표시 (ACCEPTED/REWORK인 경우) ==========
    if case.status in [CaseStatus.ACCEPTED, CaseStatus.REWORK]:
        reviewer_fb = db.query(ReviewerQcFeedback).filter(
            ReviewerQcFeedback.case_id == case.id
        ).order_by(ReviewerQcFeedback.created_at.desc()).first()

        st.markdown("---")
        status_label = "✅ 승인됨" if case.status == CaseStatus.ACCEPTED else "🔄 재작업 요청"
        st.markdown(f"#### 검수 결과: {status_label}")

        if reviewer_fb:
            fb_time = reviewer_fb.created_at.strftime('%Y-%m-%d %H:%M')
            st.caption(f"검수 일시: {fb_time}")

            if reviewer_fb.has_disagreement:
                disagreement_type = reviewer_fb.disagreement_type or "N/A"
                disagreement_label = "놓친 문제 (Missed)" if disagreement_type == "MISSED" else "잘못된 경고 (False Alarm)" if disagreement_type == "FALSE_ALARM" else disagreement_type
                st.warning(f"불일치 유형: {disagreement_label}")
                if reviewer_fb.disagreement_segments_json:
                    try:
                        segments = json.loads(reviewer_fb.disagreement_segments_json)
                        if segments:
                            st.caption(f"세그먼트: {', '.join(segments)}")
                    except json.JSONDecodeError:
                        pass
                if reviewer_fb.disagreement_detail:
                    st.caption(f"상세: {reviewer_fb.disagreement_detail}")

            if reviewer_fb.review_memo:
                st.info(f"📝 검수자 코멘트: {reviewer_fb.review_memo}")
        else:
            st.caption("검수자 피드백 없음")

    # ========== 기존 QC 피드백 목록 표시 (수정/삭제 가능) ==========
    if autoqc:
        existing_feedbacks = get_case_feedbacks(db, case.id)
        if existing_feedbacks:
            st.markdown("---")
            st.markdown("#### 수정 내역")

            for fb in existing_feedbacks:
                # 각 피드백에 대해 수정 모드 상태 관리
                edit_mode_key = f"edit_feedback_{fb.id}"
                delete_confirm_key = f"delete_feedback_{fb.id}"

                if edit_mode_key not in st.session_state:
                    st.session_state[edit_mode_key] = False
                if delete_confirm_key not in st.session_state:
                    st.session_state[delete_confirm_key] = False

                with st.container():
                    # 수정 모드
                    if st.session_state[edit_mode_key]:
                        st.markdown(f"**수정 중** - {fb.created_at.strftime('%Y-%m-%d %H:%M')}")

                        edit_error_key = f"edit_error_{fb.id}"
                        edit_text_key = f"edit_text_{fb.id}"

                        # 초기값 설정
                        if edit_error_key not in st.session_state:
                            st.session_state[edit_error_key] = fb.qc_result_error
                        if edit_text_key not in st.session_state:
                            st.session_state[edit_text_key] = fb.feedback_text or ""

                        st.checkbox("QC 결과 오류", key=edit_error_key)
                        st.text_area("피드백 내용", key=edit_text_key, height=80)

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("저장", key=f"save_fb_{fb.id}", type="primary"):
                                new_error = st.session_state[edit_error_key]
                                new_text = st.session_state[edit_text_key]

                                update_feedback(
                                    db=db,
                                    feedback_id=fb.id,
                                    user_id=user["id"],
                                    qc_result_error=new_error,
                                    feedback_text=new_text.strip() if new_text.strip() else None,
                                )

                                # 상태 초기화
                                st.session_state[edit_mode_key] = False
                                del st.session_state[edit_error_key]
                                del st.session_state[edit_text_key]
                                st.success("피드백이 수정되었습니다.")
                                st.rerun()
                        with col_cancel:
                            if st.button("취소", key=f"cancel_edit_{fb.id}"):
                                st.session_state[edit_mode_key] = False
                                if edit_error_key in st.session_state:
                                    del st.session_state[edit_error_key]
                                if edit_text_key in st.session_state:
                                    del st.session_state[edit_text_key]
                                st.rerun()

                    # 삭제 확인 모드
                    elif st.session_state[delete_confirm_key]:
                        st.warning(f"이 피드백을 삭제하시겠습니까? ({fb.created_at.strftime('%Y-%m-%d %H:%M')})")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("예, 삭제", key=f"confirm_del_{fb.id}", type="primary"):
                                delete_feedback(db, fb.id, user["id"])
                                st.session_state[delete_confirm_key] = False
                                st.success("피드백이 삭제되었습니다.")
                                st.rerun()
                        with col_no:
                            if st.button("취소", key=f"cancel_del_{fb.id}"):
                                st.session_state[delete_confirm_key] = False
                                st.rerun()

                    # 일반 표시 모드
                    else:
                        # 피드백 내용 표시
                        fb_time = fb.created_at.strftime('%Y-%m-%d %H:%M')
                        error_badge = "🔴 QC 오류" if fb.qc_result_error else "✅ QC 정상"
                        st.markdown(f"**{fb_time}** | {error_badge}")
                        if fb.feedback_text:
                            st.caption(f"📝 {fb.feedback_text}")

                        # 수정/삭제 버튼 (본인이 작성한 피드백만)
                        if fb.user_id == user["id"]:
                            col_edit, col_delete, col_spacer = st.columns([1, 1, 4])
                            with col_edit:
                                if st.button("수정", key=f"edit_btn_{fb.id}"):
                                    st.session_state[edit_mode_key] = True
                                    st.rerun()
                            with col_delete:
                                if st.button("삭제", key=f"del_btn_{fb.id}"):
                                    st.session_state[delete_confirm_key] = True
                                    st.rerun()

                    st.markdown("---")

    # ========== Worker QC 피드백 입력 (Phase 4: 확장된 피드백 UI) ==========
    # IN_PROGRESS 상태에서 Auto-QC가 있는 경우에만 표시
    if autoqc and case.status == CaseStatus.IN_PROGRESS:
        st.markdown("#### QC 피드백 작성")
        st.caption("Auto-QC 결과에 대한 피드백을 작성하세요. 임시저장 또는 제출 시 함께 저장됩니다.")

        # 기존 피드백 불러오기
        from services import get_worker_feedback, save_or_update_worker_feedback
        existing_fb = get_worker_feedback(db, case.id, user["id"])

        # Session state keys
        qc_fixes_key = f"qc_fixes_{case.id}"
        additional_fixes_key = f"additional_fixes_{case.id}"
        memo_key = f"memo_{case.id}"
        add_fix_segment_key = f"add_fix_segment_{case.id}"
        add_fix_desc_key = f"add_fix_desc_{case.id}"

        # Initialize session state
        if qc_fixes_key not in st.session_state:
            if existing_fb and existing_fb.qc_fixes_json:
                try:
                    st.session_state[qc_fixes_key] = json.loads(existing_fb.qc_fixes_json)
                except:
                    st.session_state[qc_fixes_key] = []
            else:
                st.session_state[qc_fixes_key] = []

        if additional_fixes_key not in st.session_state:
            if existing_fb and existing_fb.additional_fixes_json:
                try:
                    st.session_state[additional_fixes_key] = json.loads(existing_fb.additional_fixes_json)
                except:
                    st.session_state[additional_fixes_key] = []
            else:
                st.session_state[additional_fixes_key] = []

        # 입력 필드 초기화 (위젯 생성 전에 해야 함)
        if add_fix_segment_key not in st.session_state:
            st.session_state[add_fix_segment_key] = ""
        if add_fix_desc_key not in st.session_state:
            st.session_state[add_fix_desc_key] = ""

        # 추가 완료 플래그 처리 (위젯 생성 전에 초기화)
        clear_add_fix_key = f"clear_add_fix_{case.id}"
        if st.session_state.get(clear_add_fix_key, False):
            st.session_state[add_fix_segment_key] = ""
            st.session_state[add_fix_desc_key] = ""
            st.session_state[clear_add_fix_key] = False

        if memo_key not in st.session_state:
            st.session_state[memo_key] = existing_fb.memo if existing_fb else ""

        # ========== 1. Auto-QC 이슈별 수정 체크박스 ==========
        issues_list = []
        if autoqc.issues_json:
            try:
                issues_list = json.loads(autoqc.issues_json)
            except:
                pass

        if issues_list:
            st.markdown("**QC 이슈 수정 체크**")
            with st.container(border=True):
                # QC fixes 초기화 (issues_list와 동기화)
                current_fixes = st.session_state[qc_fixes_key]
                existing_fix_ids = {f.get("issue_id") for f in current_fixes}

                # issues_list에서 누락된 항목 추가
                for idx, issue in enumerate(issues_list):
                    if idx not in existing_fix_ids:
                        current_fixes.append({
                            "issue_id": idx,
                            "segment": issue.get("segment", ""),
                            "code": issue.get("code", ""),
                            "fixed": False,
                        })
                st.session_state[qc_fixes_key] = current_fixes

                # 이슈별 체크박스 표시
                for idx, issue in enumerate(issues_list):
                    segment = issue.get("segment", "Unknown")
                    code = issue.get("code", "")
                    level = issue.get("level", "")
                    message = issue.get("message", "")

                    # 현재 fixed 상태 찾기
                    fix_item = next((f for f in st.session_state[qc_fixes_key] if f.get("issue_id") == idx), None)
                    is_fixed = fix_item.get("fixed", False) if fix_item else False

                    # 표시 텍스트
                    level_icon = {"WARN": "⚠️", "INCOMPLETE": "❌"}.get(level, "")
                    display_text = f"{level_icon} {segment} - {message or code}"

                    # 체크박스
                    checkbox_key = f"fix_check_{case.id}_{idx}"
                    new_fixed = st.checkbox(display_text, value=is_fixed, key=checkbox_key)

                    # 상태 업데이트
                    if fix_item:
                        fix_item["fixed"] = new_fixed

                # 수정율 표시
                total_issues = len(issues_list)
                fixed_count = sum(1 for f in st.session_state[qc_fixes_key] if f.get("fixed", False))
                st.caption(f"수정율: {fixed_count}/{total_issues}")
        else:
            st.info("Auto-QC에서 발견된 이슈가 없습니다.")

        # ========== 2. 추가 수정 사항 입력 ==========
        st.markdown("**추가 수정 사항** (QC에 없지만 수정한 것)")

        with st.container(border=True):
            # 기존 추가 수정 사항 표시
            if st.session_state[additional_fixes_key]:
                for i, fix in enumerate(st.session_state[additional_fixes_key]):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        fix_type = fix.get('fix_type', '')
                        type_label = "🔴 놓침" if fix_type == "missed" else "🟡 잘못된 경고" if fix_type == "false_alarm" else ""
                        st.write(f"• {type_label} **{fix.get('segment', '')}**: {fix.get('description', '')}")
                    with col2:
                        if st.button("삭제", key=f"del_addfix_{case.id}_{i}"):
                            st.session_state[additional_fixes_key].pop(i)
                            st.rerun()

            # 새 항목 입력
            add_fix_type_key = f"add_fix_type_{case.id}"
            if add_fix_type_key not in st.session_state:
                st.session_state[add_fix_type_key] = "missed"

            add_col1, add_col2, add_col3, add_col4 = st.columns([1.5, 2, 2.5, 1])
            with add_col1:
                fix_type_options = {"놓침 (Missed)": "missed", "잘못된 경고 (False Alarm)": "false_alarm"}
                selected_type_label = st.selectbox(
                    "수정 유형",
                    options=list(fix_type_options.keys()),
                    key=add_fix_type_key + "_select",
                )
                selected_fix_type = fix_type_options[selected_type_label]
            with add_col2:
                segment_input = st.text_input("세그먼트", key=add_fix_segment_key, placeholder="예: Renal_Artery")
            with add_col3:
                desc_input = st.text_input("설명", key=add_fix_desc_key, placeholder="예: 구멍 메움")
            with add_col4:
                st.write("")  # 간격 맞춤
                if st.button("추가", key=f"add_fix_btn_{case.id}"):
                    seg = st.session_state.get(add_fix_segment_key, "").strip()
                    desc = st.session_state.get(add_fix_desc_key, "").strip()
                    if seg and desc:
                        st.session_state[additional_fixes_key].append({
                            "segment": seg,
                            "description": desc,
                            "fix_type": selected_fix_type,
                        })
                        # 플래그 설정 후 rerun (다음 사이클에서 입력 필드 초기화)
                        st.session_state[clear_add_fix_key] = True
                        st.rerun()
                    else:
                        st.warning("세그먼트와 설명을 모두 입력하세요.")

        # ========== 3. 메모 입력 ==========
        st.markdown("**메모**")
        st.text_area(
            "작업 관련 메모",
            placeholder="작업 관련 메모를 입력하세요 (예: 전반적으로 혈관 경계 불분명)",
            key=memo_key,
            height=80,
            label_visibility="collapsed"
        )

        # ========== 4. 임시저장 버튼 ==========
        if st.button("📁 임시저장", key=f"save_feedback_{case.id}"):
            save_or_update_worker_feedback(
                db=db,
                case_id=case.id,
                user_id=user["id"],
                qc_fixes=st.session_state[qc_fixes_key],
                additional_fixes=st.session_state[additional_fixes_key],
                memo=st.session_state[memo_key].strip() if st.session_state[memo_key] else None,
            )
            st.success("피드백이 임시저장되었습니다.")
            st.rerun()

    st.markdown("---")

    # Action buttons based on state
    if case.status in [CaseStatus.TODO, CaseStatus.REWORK]:
        # START button
        can_start = current_wip < wip_limit

        if not can_start:
            st.warning(f"시작 불가: WIP 한도 도달 ({current_wip}/{wip_limit})")
        else:
            confirm_key = f"confirm_start_{case.id}"
            if confirm_key not in st.session_state:
                st.session_state[confirm_key] = False

            if not st.session_state[confirm_key]:
                if st.button("작업 시작", key=f"start_{case.id}", type="primary"):
                    st.session_state[confirm_key] = True
                    st.rerun()
            else:
                st.warning("이 작업을 시작하시겠습니까?")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("시작", key=f"confirm_yes_{case.id}", type="primary"):
                        now = datetime.now(TIMEZONE)
                        action_type = ActionType.REWORK_START if case.status == CaseStatus.REWORK else ActionType.START

                        # Create WorkLog
                        worklog = WorkLog(
                            case_id=case.id,
                            user_id=user["id"],
                            action_type=action_type,
                            timestamp=now,
                        )
                        db.add(worklog)

                        # Create Event
                        event = Event(
                            case_id=case.id,
                            user_id=user["id"],
                            event_type=EventType.STARTED,
                            idempotency_key=generate_idempotency_key(case.id, "STARTED"),
                            created_at=now,
                        )
                        db.add(event)

                        # Update case
                        case.status = CaseStatus.IN_PROGRESS
                        if case.started_at is None:
                            case.started_at = now

                        db.commit()
                        st.session_state[confirm_key] = False
                        st.success("작업이 시작되었습니다!")
                        st.rerun()
                with col_b:
                    if st.button("취소", key=f"confirm_no_{case.id}"):
                        st.session_state[confirm_key] = False
                        st.rerun()

    elif case.status == CaseStatus.IN_PROGRESS:
        if is_working:
            # PAUSE and SUBMIT buttons
            col_a, col_b = st.columns(2)

            with col_a:
                # PAUSE with reason
                pause_key = f"pause_mode_{case.id}"
                if pause_key not in st.session_state:
                    st.session_state[pause_key] = False

                if not st.session_state[pause_key]:
                    if st.button("일시중지", key=f"pause_{case.id}"):
                        st.session_state[pause_key] = True
                        st.rerun()
                else:
                    reason = st.selectbox(
                        "중단 사유",
                        options=PAUSE_REASONS,
                        key=f"pause_reason_{case.id}"
                    )
                    reason_text = st.text_input(
                        "상세 사유",
                        placeholder="중단 사유를 입력하세요",
                        key=f"pause_reason_text_{case.id}"
                    )
                    if st.button("중단 확인", key=f"confirm_pause_{case.id}"):
                        if not reason_text.strip():
                            st.error("중단 사유를 입력해야 합니다.")
                        else:
                            now = datetime.now(TIMEZONE)
                            # Combine reason code and text
                            full_reason = f"{reason}: {reason_text.strip()}"
                            worklog = WorkLog(
                                case_id=case.id,
                                user_id=user["id"],
                                action_type=ActionType.PAUSE,
                                reason_code=full_reason,
                                timestamp=now,
                            )
                            db.add(worklog)
                            db.commit()
                            st.session_state[pause_key] = False
                            st.success("작업이 일시중지되었습니다!")
                            st.rerun()
                    if st.button("중단 취소", key=f"cancel_pause_{case.id}"):
                        st.session_state[pause_key] = False
                        st.rerun()

            with col_b:
                # SUBMIT
                submit_key = f"confirm_submit_{case.id}"
                if submit_key not in st.session_state:
                    st.session_state[submit_key] = False

                if not st.session_state[submit_key]:
                    if st.button("제출", key=f"submit_{case.id}", type="primary"):
                        st.session_state[submit_key] = True
                        st.rerun()
                else:
                    st.markdown("**검수를 위해 제출**")

                    # Phase 4: 확장된 QC 피드백 표시
                    qc_fixes_key = f"qc_fixes_{case.id}"
                    additional_fixes_key = f"additional_fixes_{case.id}"
                    memo_key = f"memo_{case.id}"

                    qc_fixes = st.session_state.get(qc_fixes_key, [])
                    additional_fixes = st.session_state.get(additional_fixes_key, [])
                    memo = st.session_state.get(memo_key, "")

                    has_feedback = bool(qc_fixes or additional_fixes or (memo and memo.strip()))

                    if autoqc and has_feedback:
                        st.info("QC 피드백이 함께 저장됩니다")
                        if qc_fixes:
                            fixed_count = sum(1 for f in qc_fixes if f.get("fixed", False))
                            st.caption(f"- QC 이슈 수정율: {fixed_count}/{len(qc_fixes)}")
                        if additional_fixes:
                            st.caption(f"- 추가 수정 사항: {len(additional_fixes)}건")
                        if memo and memo.strip():
                            st.caption(f"- 메모: {memo.strip()[:50]}...")

                    col_submit, col_cancel = st.columns(2)
                    with col_submit:
                        submit_clicked = st.button("제출", key=f"confirm_yes_submit_{case.id}", type="primary")
                    with col_cancel:
                        cancel_clicked = st.button("취소", key=f"cancel_submit_{case.id}")

                    if submit_clicked:
                        now = datetime.now(TIMEZONE)

                        # Phase 4: 확장된 QC 피드백 저장
                        if autoqc and has_feedback:
                            save_or_update_worker_feedback(
                                db=db,
                                case_id=case.id,
                                user_id=user["id"],
                                qc_fixes=qc_fixes if qc_fixes else None,
                                additional_fixes=additional_fixes if additional_fixes else None,
                                memo=memo.strip() if memo and memo.strip() else None,
                            )

                        # Create WorkLog SUBMIT
                        worklog = WorkLog(
                            case_id=case.id,
                            user_id=user["id"],
                            action_type=ActionType.SUBMIT,
                            timestamp=now,
                        )
                        db.add(worklog)

                        # Create Event SUBMITTED
                        fixed_count = sum(1 for f in qc_fixes if f.get("fixed", False)) if qc_fixes else 0
                        additional_count = len(additional_fixes) if additional_fixes else 0
                        submit_payload = {
                            "fixes": fixed_count,
                            "total_issues": len(qc_fixes) if qc_fixes else 0,
                            "additional": additional_count,
                            "has_memo": bool(memo and memo.strip()),
                        }
                        submit_event_code = f"제출 (수정 {fixed_count}건, 추가 {additional_count}건)"

                        event = Event(
                            case_id=case.id,
                            user_id=user["id"],
                            event_type=EventType.SUBMITTED,
                            idempotency_key=generate_idempotency_key(case.id, "SUBMITTED"),
                            event_code=submit_event_code,
                            payload_json=json.dumps(submit_payload, ensure_ascii=False),
                            created_at=now,
                        )
                        db.add(event)

                        # Update case
                        case.status = CaseStatus.SUBMITTED
                        case.worker_completed_at = now

                        db.commit()
                        st.session_state[submit_key] = False

                        # Clear QC feedback session state (Phase 4 keys)
                        for key_suffix in ["qc_fixes_", "additional_fixes_", "memo_", "add_fix_segment_", "add_fix_desc_", "clear_add_fix_"]:
                            key_to_clear = f"{key_suffix}{case.id}"
                            if key_to_clear in st.session_state:
                                del st.session_state[key_to_clear]

                        # Show final time
                        final_worklogs = db.query(WorkLog).filter(
                            WorkLog.case_id == case.id
                        ).order_by(WorkLog.timestamp).all()
                        final_seconds = compute_work_seconds(final_worklogs, auto_timeout)
                        final_duration = format_duration(final_seconds)
                        final_md = compute_man_days(final_seconds, workday_hours)

                        st.success(f"제출 완료! 총 작업시간: {final_duration} ({final_md:.2f} MD)")
                        st.rerun()
                    if cancel_clicked:
                        st.session_state[submit_key] = False
                        st.rerun()

        elif is_paused:
            # RESUME button - check WIP limit first
            # current_wip already excludes this paused case, so resuming would add 1
            can_resume = current_wip < wip_limit

            if not can_resume:
                st.warning(f"재개 불가: WIP 한도 도달 ({current_wip}/{wip_limit}). 다른 작업을 먼저 중지하세요.")
            else:
                if st.button("작업 재개", key=f"resume_{case.id}", type="primary"):
                    now = datetime.now(TIMEZONE)
                    worklog = WorkLog(
                        case_id=case.id,
                        user_id=user["id"],
                        action_type=ActionType.RESUME,
                        timestamp=now,
                    )
                    db.add(worklog)
                    db.commit()
                    st.success("작업이 재개되었습니다!")
                    st.rerun()


# ============== Admin View ==============
def show_admin_dashboard():
    """Show admin dashboard with WorkLog metrics."""
    user = st.session_state.user

    st.title(f"관리자 대시보드 - {user['username']}")

    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("로그아웃"):
            logout()

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "검수 대기", "전체 케이스", "케이스 등록", "케이스 배정", "이벤트 로그",
        "휴무 관리", "공휴일", "작업 통계", "QC 현황"
    ])

    db = get_db()
    try:
        with tab1:
            show_review_queue(db, user)

        with tab2:
            show_all_cases(db)

        with tab3:
            show_register_case(db, user)

        with tab4:
            show_assign_cases(db)

        with tab5:
            show_event_log(db)

        with tab6:
            show_timeoff_management(db, user)

        with tab7:
            show_holiday_management(db, user)

        with tab8:
            show_work_statistics(db)

        with tab9:
            show_qc_status(db)
    finally:
        db.close()


def show_register_case(db: Session, user: dict):
    """Show case registration form."""
    st.subheader("케이스 등록")

    # Get existing projects and parts for suggestions
    projects = db.query(Project).filter(Project.is_active == True).all()
    parts = db.query(Part).filter(Part.is_active == True).all()
    project_names = [p.name for p in projects]
    part_names = [p.name for p in parts]

    # Registration form
    with st.form("register_case_form"):
        st.markdown("### 새 케이스 정보")

        col1, col2 = st.columns(2)

        with col1:
            case_uid = st.text_input(
                "케이스 ID *",
                placeholder="예: CASE-006",
                help="고유한 케이스 식별자"
            )
            original_name = st.text_input(
                "원본 이름",
                placeholder="예: 김철수_20250113_liver",
                help="원본 폴더명"
            )
            project_name = st.text_input(
                "프로젝트 *",
                placeholder="예: Sample Project",
                help=f"기존: {', '.join(project_names)}" if project_names else "새 프로젝트명 입력"
            )
            part_name = st.text_input(
                "부위 *",
                placeholder="예: Liver",
                help=f"기존: {', '.join(part_names)}" if part_names else "새 부위명 입력"
            )

        with col2:
            hospital = st.text_input(
                "병원",
                placeholder="예: Seoul National Hospital",
                help="병원명 (선택사항)"
            )
            difficulty = st.selectbox(
                "난이도",
                options=[d.value for d in Difficulty],
                index=1  # Default: NORMAL
            )
            slice_thickness = st.number_input(
                "두께(mm)",
                min_value=0.0,
                max_value=10.0,
                value=1.0,
                step=0.1,
                help="선택사항"
            )
            nas_path = st.text_input(
                "폴더 경로",
                placeholder="예: /data/cases/CASE-006",
                help="원본 데이터 경로 (선택사항)"
            )

        submitted = st.form_submit_button("케이스 등록", type="primary")

        if submitted:
            # Validation
            if not case_uid or not case_uid.strip():
                st.error("케이스 ID를 입력하세요.")
                return
            if not project_name or not project_name.strip():
                st.error("프로젝트를 입력하세요.")
                return
            if not part_name or not part_name.strip():
                st.error("부위를 입력하세요.")
                return

            # Check for duplicate case_uid
            existing = db.query(Case).filter(Case.case_uid == case_uid.strip()).first()
            if existing:
                st.error(f"케이스 ID '{case_uid}'가 이미 존재합니다.")
                return

            # Get or create project
            project = db.query(Project).filter(Project.name == project_name.strip()).first()
            if not project:
                project = Project(name=project_name.strip(), is_active=True)
                db.add(project)
                db.flush()

            # Get or create part
            part = db.query(Part).filter(Part.name == part_name.strip()).first()
            if not part:
                part = Part(name=part_name.strip(), is_active=True)
                db.add(part)
                db.flush()

            # Create case
            original_name_value = original_name.strip() if original_name else None
            display_name_value = original_name_value or case_uid.strip()

            new_case = Case(
                case_uid=case_uid.strip(),
                original_name=original_name_value,
                display_name=display_name_value,
                hospital=hospital.strip() if hospital else None,
                slice_thickness_mm=slice_thickness if slice_thickness > 0 else None,
                nas_path=nas_path.strip() if nas_path else None,
                project_id=project.id,
                part_id=part.id,
                difficulty=Difficulty(difficulty),
                status=CaseStatus.TODO,
                revision=1,
            )
            db.add(new_case)
            db.commit()

            st.success(f"케이스 '{case_uid}'가 등록되었습니다.")
            st.rerun()

    # CSV 일괄 등록
    st.markdown("---")
    st.markdown("### CSV 일괄 등록")

    # 템플릿 다운로드
    template_csv = "case_uid,original_name,project,part,hospital,difficulty,slice_thickness_mm,nas_path,wwl,memo,tags\n"
    template_csv += "CASE_001,김철수_20250113_liver,abdomen_vessel,abdomen_vessel,Seoul Hospital,NORMAL,0.6,/nas/data/001,350/40,메모 내용,태그1;태그2\n"
    st.download_button(
        "CSV 템플릿 다운로드",
        template_csv.encode("utf-8-sig"),
        "case_template.csv",
        "text/csv",
        key="csv_template_download"
    )

    # 파일 업로드
    uploaded = st.file_uploader("CSV 파일 선택", type=["csv"], key="csv_upload")

    if uploaded:
        try:
            df = pd.read_csv(uploaded, encoding="utf-8-sig")
        except Exception:
            try:
                uploaded.seek(0)
                df = pd.read_csv(uploaded, encoding="utf-8")
            except Exception as e:
                st.error(f"CSV 파일 읽기 오류: {e}")
                df = None

        if df is not None:
            # 필수 컬럼 체크
            required = ["case_uid", "display_name", "project", "part"]
            missing = [c for c in required if c not in df.columns]

            if missing:
                st.error(f"필수 컬럼 누락: {missing}")
            else:
                # 중복 체크
                existing_uids = [c.case_uid for c in db.query(Case.case_uid).all()]
                df["중복"] = df["case_uid"].isin(existing_uids)

                # 미리보기
                render_table_df(df, max_rows=15)
                dup_count = df["중복"].sum()
                new_count = len(df) - dup_count
                st.caption(f"총 {len(df)}건 | 신규: {new_count}건 | 중복(건너뜀): {dup_count}건")

                # 등록 버튼
                if new_count > 0:
                    if st.button("일괄 등록", type="primary", key="bulk_register_btn"):
                        success = 0
                        skip = 0
                        errors = []

                        for _, row in df.iterrows():
                            if row.get("중복", False):
                                skip += 1
                                continue

                            try:
                                # Project 생성/조회
                                project_name = str(row["project"]).strip()
                                project = db.query(Project).filter(Project.name == project_name).first()
                                if not project:
                                    project = Project(name=project_name, is_active=True)
                                    db.add(project)
                                    db.flush()

                                # Part 생성/조회
                                part_name = str(row["part"]).strip()
                                part = db.query(Part).filter(Part.name == part_name).first()
                                if not part:
                                    part = Part(name=part_name, is_active=True)
                                    db.add(part)
                                    db.flush()

                                # 난이도 파싱
                                difficulty_val = str(row.get("difficulty", "NORMAL")).strip().upper()
                                if difficulty_val not in ["EASY", "NORMAL", "HARD", "VERY_HARD"]:
                                    difficulty_val = "NORMAL"

                                # slice_thickness 파싱
                                slice_val = row.get("slice_thickness_mm")
                                if pd.isna(slice_val) or slice_val == "":
                                    slice_val = None
                                else:
                                    try:
                                        slice_val = float(slice_val)
                                    except (ValueError, TypeError):
                                        slice_val = None

                                # tags 파싱 (세미콜론 구분)
                                tags_val = row.get("tags")
                                tags_json = None
                                if pd.notna(tags_val) and str(tags_val).strip():
                                    tags_list = [t.strip() for t in str(tags_val).split(";") if t.strip()]
                                    if tags_list:
                                        tags_json = json.dumps(tags_list, ensure_ascii=False)

                                # original_name 파싱 (없으면 display_name, 그것도 없으면 case_uid)
                                original_name_val = None
                                if "original_name" in row and pd.notna(row.get("original_name")):
                                    original_name_val = str(row["original_name"]).strip()
                                elif "display_name" in row and pd.notna(row.get("display_name")):
                                    original_name_val = str(row["display_name"]).strip()

                                display_name_val = original_name_val or str(row["case_uid"]).strip()

                                # Case 생성
                                new_case = Case(
                                    case_uid=str(row["case_uid"]).strip(),
                                    original_name=original_name_val,
                                    display_name=display_name_val,
                                    project_id=project.id,
                                    part_id=part.id,
                                    hospital=str(row.get("hospital", "")).strip() if pd.notna(row.get("hospital")) else None,
                                    difficulty=Difficulty(difficulty_val),
                                    slice_thickness_mm=slice_val,
                                    nas_path=str(row.get("nas_path", "")).strip() if pd.notna(row.get("nas_path")) else None,
                                    wwl=str(row.get("wwl", "")).strip() if pd.notna(row.get("wwl")) else None,
                                    memo=str(row.get("memo", "")).strip() if pd.notna(row.get("memo")) else None,
                                    tags_json=tags_json,
                                    status=CaseStatus.TODO,
                                    revision=1,
                                )
                                db.add(new_case)
                                success += 1
                            except Exception as e:
                                errors.append(f"{row.get('case_uid', 'unknown')}: {str(e)}")

                        db.commit()

                        if success > 0:
                            st.success(f"등록 완료! 성공: {success}건, 건너뜀: {skip}건")
                        if errors:
                            st.warning(f"오류 발생: {len(errors)}건")
                            for err in errors[:5]:
                                st.caption(f"- {err}")
                        st.rerun()
                else:
                    st.warning("등록할 새 케이스가 없습니다 (모두 중복)")

    # Recent registered cases
    st.markdown("---")
    st.markdown("### 최근 등록된 케이스")

    recent_cases = db.query(Case).order_by(Case.created_at.desc()).limit(10).all()
    if recent_cases:
        data = []
        for c in recent_cases:
            data.append({
                UI_LABELS["id"]: c.id,
                UI_LABELS["case_uid"]: c.case_uid,
                UI_LABELS["original_name"]: c.original_name if c.original_name else c.display_name,
                UI_LABELS["project"]: c.project.name,
                UI_LABELS["part"]: c.part.name,
                UI_LABELS["hospital"]: c.hospital or UI_LABELS["unassigned"],
                UI_LABELS["slice_thickness"]: c.slice_thickness_mm if c.slice_thickness_mm else "-",
                UI_LABELS["difficulty"]: c.difficulty.value,
                UI_LABELS["nas_path"]: c.nas_path if c.nas_path else "-",
                UI_LABELS["created_at"]: c.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        # 데이터 개수에 따라 높이 자동 계산 (최대 25행)
        row_count = len(data)
        auto_height = min(max(row_count * 35 + 100, 200), 975)
        render_styled_dataframe(pd.DataFrame(data), key="recent_cases_grid", enable_selection=False, height=auto_height, user_role="admin")
    else:
        st.info("등록된 케이스가 없습니다.")


def show_review_queue(db: Session, user: dict):
    """Show cases pending review with metrics and AutoQC summary."""
    st.subheader("검수 대기 목록")

    auto_timeout = get_config_value(db, "auto_timeout_minutes", 120)
    workday_hours = get_config_value(db, "workday_hours", 8)

    cases = db.query(Case).filter(
        Case.status == CaseStatus.SUBMITTED
    ).order_by(Case.worker_completed_at.asc()).all()

    if not cases:
        st.info("검수 대기 중인 케이스가 없습니다.")
        return

    for case in cases:
        # Get worklogs and compute metrics
        worklogs = db.query(WorkLog).filter(
            WorkLog.case_id == case.id
        ).order_by(WorkLog.timestamp).all()

        work_seconds = compute_work_seconds(worklogs, auto_timeout)
        work_duration = format_duration(work_seconds)
        man_days = compute_man_days(work_seconds, workday_hours)
        first_start, last_end = get_timeline_dates(worklogs)
        timeline = compute_timeline(first_start, last_end)

        # Get AutoQC summary
        autoqc = db.query(AutoQcSummary).filter(AutoQcSummary.case_id == case.id).first()

        # Determine icon based on AutoQC result
        if autoqc:
            if autoqc.status == "PASS":
                qc_icon = "✅"
            elif autoqc.status == "WARN":
                qc_icon = "⚠️"
            elif autoqc.status == "INCOMPLETE":
                qc_icon = "❌"
            else:
                qc_icon = "⚪"
        else:
            qc_icon = "⚪"

        original_name_display = case.original_name if case.original_name else case.display_name
        with st.expander(
            f"{qc_icon} {original_name_display} ({case.case_uid}) - {UI_LABELS['revision']} {case.revision}",
            expanded=False
        ):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**{UI_LABELS['case_uid']}:** {case.case_uid}")
                st.write(f"**{UI_LABELS['original_name']}:** {original_name_display}")
                st.write(f"**{UI_LABELS['nas_path']}:** {case.nas_path if case.nas_path else '-'}")
                st.write(f"**{UI_LABELS['project']}:** {case.project.name}")
            with col2:
                st.write(f"**{UI_LABELS['part']}:** {case.part.name}")
                st.write(f"**{UI_LABELS['hospital']}:** {case.hospital or UI_LABELS['unassigned']}")
                st.write(f"**{UI_LABELS['slice_thickness']}:** {case.slice_thickness_mm if case.slice_thickness_mm else '-'}")
            with col3:
                st.write(f"**{UI_LABELS['difficulty']}:** {case.difficulty.value}")
                st.write(f"**{UI_LABELS['assignee']}:** {case.assigned_user.username if case.assigned_user else UI_LABELS['unassigned']}")
                if case.started_at:
                    st.write(f"**시작일:** {case.started_at.strftime('%Y-%m-%d %H:%M')}")
                if case.worker_completed_at:
                    st.write(f"**제출일:** {case.worker_completed_at.strftime('%Y-%m-%d %H:%M')}")

            # ====== QC 이슈 + 작업자 수정 현황 상세 표시 ======
            st.markdown("---")

            # 작업자 피드백 로드
            worker_feedback = db.query(WorkerQcFeedback).filter(
                WorkerQcFeedback.case_id == case.id
            ).order_by(WorkerQcFeedback.created_at.desc()).first()

            # QC 수정 현황 파싱
            qc_fixes_map = {}  # {issue_id or segment: {"fixed": bool, ...}}
            additional_fixes = []
            worker_memo = ""
            if worker_feedback:
                if worker_feedback.qc_fixes_json:
                    try:
                        qc_fixes_list = json.loads(worker_feedback.qc_fixes_json)
                        for fix in qc_fixes_list:
                            key = fix.get("issue_id") or fix.get("segment", "")
                            qc_fixes_map[key] = fix
                    except json.JSONDecodeError:
                        pass
                if worker_feedback.additional_fixes_json:
                    try:
                        additional_fixes = json.loads(worker_feedback.additional_fixes_json)
                    except json.JSONDecodeError:
                        pass
                worker_memo = worker_feedback.memo or ""

            if autoqc:
                # 상태 아이콘
                status_icon = {"PASS": "✅", "WARN": "⚠️", "INCOMPLETE": "❌"}.get(autoqc.status, "")

                # 이슈 목록 파싱
                issues = []
                if autoqc.issues_json:
                    try:
                        issues = json.loads(autoqc.issues_json)
                    except json.JSONDecodeError:
                        pass

                # 수정율 계산
                total_issues = len(issues)
                fixed_count = sum(1 for i, issue in enumerate(issues) if qc_fixes_map.get(i, {}).get("fixed", False) or qc_fixes_map.get(issue.get("segment", ""), {}).get("fixed", False))

                st.markdown("**📋 Auto-QC 이슈 목록 (작업자 수정 → 검수자 확인):**")
                with st.container(border=True):
                    if issues:
                        severity_icons = {"WARN": "⚠️", "INCOMPLETE": "❌", "INFO": "ℹ️"}
                        for i, issue in enumerate(issues):
                            level = issue.get("level", "")
                            segment = issue.get("segment", "")
                            msg = issue.get("message", str(issue))
                            code = issue.get("code", "")
                            sev_icon = severity_icons.get(level, "•")

                            # 작업자 수정 여부 확인 (index 또는 segment로 매칭)
                            is_fixed = qc_fixes_map.get(i, {}).get("fixed", False) or qc_fixes_map.get(segment, {}).get("fixed", False)
                            fix_status = "수정완료" if is_fixed else "미수정"

                            # 검수자 확인 체크박스 (session_state 전용)
                            reviewer_check_key = f"reviewer_check_{case.id}_{i}"
                            col_check, col_info = st.columns([1, 5])
                            with col_check:
                                st.checkbox(
                                    "확인",
                                    key=reviewer_check_key,
                                    label_visibility="collapsed"
                                )
                            with col_info:
                                fix_icon = "✅" if is_fixed else "❌"
                                st.markdown(f"{fix_icon} {sev_icon} {level}: {segment} - {msg} [{fix_status}]")
                    else:
                        st.caption("이슈 없음")

                    # 범례
                    st.caption("체크박스 = 검수자 확인용 / ✅ = 작업자 수정완료 / ❌ = 작업자 미수정")

                # 추가 수정 사항 (QC에 없던 것)
                if additional_fixes:
                    st.markdown("**📋 추가 수정 사항 (QC에 없던 것):**")
                    with st.container(border=True):
                        for idx, fix in enumerate(additional_fixes):
                            seg = fix.get("segment", "")
                            desc = fix.get("description", "")
                            fix_type = fix.get("fix_type", "")
                            type_label = "🔴 놓침" if fix_type == "missed" else "🟡 잘못된 경고" if fix_type == "false_alarm" else ""

                            # 검수자 확인 체크박스
                            reviewer_addfix_check_key = f"reviewer_addfix_check_{case.id}_{idx}"
                            col_check, col_info = st.columns([1, 5])
                            with col_check:
                                st.checkbox(
                                    "확인",
                                    key=reviewer_addfix_check_key,
                                    label_visibility="collapsed"
                                )
                            with col_info:
                                st.markdown(f"{type_label} {seg}: {desc}")

                # 작업자 메모
                if worker_memo:
                    st.markdown("**📋 작업자 메모:**")
                    with st.container(border=True):
                        st.markdown(f'"{worker_memo}"')

                # 요약
                st.markdown("**[요약]**")
                summary_cols = st.columns(3)
                with summary_cols[0]:
                    fix_rate = (fixed_count / total_issues * 100) if total_issues > 0 else 0
                    st.metric("Auto-QC 이슈", f"{total_issues}건 중 {fixed_count}건 수정 ({fix_rate:.0f}%)")
                with summary_cols[1]:
                    st.metric("추가 수정", f"{len(additional_fixes)}건")
                with summary_cols[2]:
                    st.metric("상태", f"{status_icon} {autoqc.status or '-'}")

                st.caption(f"Auto-QC 실행: {autoqc.created_at.strftime('%Y-%m-%d %H:%M')}")
            else:
                st.markdown("**Auto-QC**")
                with st.container(border=True):
                    st.caption("Auto-QC 데이터 없음")

            # Metrics display
            st.markdown("---")
            st.markdown("**작업 지표:**")
            metric_cols = st.columns(3)
            with metric_cols[0]:
                st.metric("총 시간", work_duration)
            with metric_cols[1]:
                st.metric("공수(MD)", f"{man_days:.2f} MD")
            with metric_cols[2]:
                st.metric("소요 일수", timeline)

            # WorkLog timeline
            if worklogs:
                st.markdown("**작업 기록:**")
                for wl in worklogs:
                    reason_str = f" ({wl.reason_code})" if wl.reason_code else ""
                    st.write(f"- {wl.timestamp.strftime('%Y-%m-%d %H:%M')} | {wl.action_type.value}{reason_str} | {wl.user.username}")

            st.markdown("---")

            # ====== 검수자 Auto-QC 불일치 기록 섹션 ======
            if autoqc:
                st.markdown("**Auto-QC 불일치 기록**")

                # 기존 불일치 기록 로드
                existing_reviewer_fb = db.query(ReviewerQcFeedback).filter(
                    ReviewerQcFeedback.case_id == case.id,
                    ReviewerQcFeedback.reviewer_id == user["id"]
                ).first()

                # 세션 키 정의
                edit_mode_key = f"disagree_edit_mode_{case.id}"
                add_mode_key = f"disagree_add_mode_{case.id}"

                if edit_mode_key not in st.session_state:
                    st.session_state[edit_mode_key] = False
                if add_mode_key not in st.session_state:
                    st.session_state[add_mode_key] = False

                has_record = existing_reviewer_fb and existing_reviewer_fb.has_disagreement
                is_editing = st.session_state[edit_mode_key]
                is_adding = st.session_state[add_mode_key]

                # 상단 [불일치 추가] 버튼 (편집/추가 모드가 아닐 때만)
                if not is_editing and not is_adding:
                    # 기존 기록이 있으면 추가 버튼 비활성화 (case당 1개 제한)
                    if not has_record:
                        if st.button("불일치 추가", key=f"add_disagree_btn_{case.id}"):
                            st.session_state[add_mode_key] = True
                            st.rerun()

                # 저장된 불일치 기록 목록 표시 (편집/추가 모드가 아닐 때)
                if has_record and not is_editing and not is_adding:
                    with st.container(border=True):
                        # 세그먼트 파싱
                        segments_str = "-"
                        if existing_reviewer_fb.disagreement_segments_json:
                            try:
                                segments = json.loads(existing_reviewer_fb.disagreement_segments_json)
                                segments_str = ", ".join(segments) if segments else "-"
                            except json.JSONDecodeError:
                                pass

                        # 유형 표시
                        type_display = "놓친 문제" if existing_reviewer_fb.disagreement_type == "MISSED" else "잘못된 경고"

                        # 테이블 형식으로 표시
                        col_type, col_detail, col_seg = st.columns([1, 2, 1.5])
                        with col_type:
                            st.markdown(f"**유형:** {type_display}")
                        with col_detail:
                            st.markdown(f"**상세:** {existing_reviewer_fb.disagreement_detail or '-'}")
                        with col_seg:
                            st.markdown(f"**세그먼트:** {segments_str}")

                        # 수정/삭제 버튼
                        col_edit, col_del, col_space = st.columns([1, 1, 3])
                        with col_edit:
                            if st.button("수정", key=f"edit_disagree_{case.id}"):
                                st.session_state[edit_mode_key] = True
                                st.rerun()
                        with col_del:
                            if st.button("삭제", key=f"delete_disagree_{case.id}"):
                                existing_reviewer_fb.has_disagreement = False
                                existing_reviewer_fb.disagreement_type = None
                                existing_reviewer_fb.disagreement_detail = None
                                existing_reviewer_fb.disagreement_segments_json = None
                                db.commit()
                                st.success("불일치 기록이 삭제되었습니다.")
                                st.rerun()

                # 기록이 없고 추가 모드도 아닐 때 안내 문구
                elif not has_record and not is_adding:
                    st.caption("아직 저장된 불일치 기록이 없습니다.")

                # 불일치 기록 입력 폼 (추가 또는 수정 모드)
                if is_editing or is_adding:
                    mode_label = "수정" if is_editing else "추가"
                    st.info(f"불일치 기록 {mode_label} 중...")

                    with st.container(border=True):
                        st.markdown("**불일치 유형:**")
                        disagree_type_options = ["놓친 문제 (PASS였는데 문제 발견)", "잘못된 경고 (WARN/INCOMPLETE였는데 문제 없음)"]

                        # 수정 모드일 때 기존 값으로 초기화
                        default_type_idx = 0
                        if is_editing and existing_reviewer_fb and existing_reviewer_fb.disagreement_type == "FALSE_ALARM":
                            default_type_idx = 1

                        disagree_type = st.radio(
                            "유형 선택",
                            options=disagree_type_options,
                            index=default_type_idx,
                            key=f"disagree_type_{case.id}",
                            label_visibility="collapsed"
                        )

                        st.markdown("**상세 내용 (선택):**")
                        default_detail = ""
                        if is_editing and existing_reviewer_fb and existing_reviewer_fb.disagreement_detail:
                            default_detail = existing_reviewer_fb.disagreement_detail

                        disagree_detail = st.text_area(
                            "상세 내용",
                            value=default_detail,
                            key=f"disagree_detail_{case.id}",
                            placeholder="어떤 문제를 놓쳤는지 / 왜 문제없는지 입력...",
                            label_visibility="collapsed"
                        )

                        st.markdown("**해당 세그먼트 (선택):**")
                        # 기존 세그먼트 목록 로드
                        existing_segments = []
                        if is_editing and existing_reviewer_fb and existing_reviewer_fb.disagreement_segments_json:
                            try:
                                existing_segments = json.loads(existing_reviewer_fb.disagreement_segments_json)
                            except json.JSONDecodeError:
                                pass

                        # 세그먼트 입력 (쉼표 구분)
                        segment_input = st.text_input(
                            "세그먼트 (쉼표 구분)",
                            value=", ".join(existing_segments) if existing_segments else "",
                            key=f"disagree_segments_{case.id}",
                            placeholder="예: IVC, Aorta, Portal_vein",
                            label_visibility="collapsed"
                        )

                        # 버튼 행
                        col_save, col_cancel, col_sp = st.columns([1, 1, 3])

                        with col_save:
                            if st.button("저장", key=f"save_disagree_{case.id}", type="primary"):
                                # 유형 변환
                                disagree_type_code = "MISSED" if "놓친 문제" in disagree_type else "FALSE_ALARM"

                                # 세그먼트 파싱
                                segments_list = [s.strip() for s in segment_input.split(",") if s.strip()] if segment_input.strip() else []
                                segments_json = json.dumps(segments_list, ensure_ascii=False) if segments_list else None

                                if existing_reviewer_fb:
                                    # 기존 레코드 업데이트
                                    existing_reviewer_fb.has_disagreement = True
                                    existing_reviewer_fb.disagreement_type = disagree_type_code
                                    existing_reviewer_fb.disagreement_detail = disagree_detail.strip() or None
                                    existing_reviewer_fb.disagreement_segments_json = segments_json
                                else:
                                    # 새로 생성
                                    new_fb = ReviewerQcFeedback(
                                        case_id=case.id,
                                        reviewer_id=user["id"],
                                        has_disagreement=True,
                                        disagreement_type=disagree_type_code,
                                        disagreement_detail=disagree_detail.strip() or None,
                                        disagreement_segments_json=segments_json,
                                    )
                                    db.add(new_fb)

                                db.commit()
                                st.session_state[edit_mode_key] = False
                                st.session_state[add_mode_key] = False
                                st.success("불일치 기록이 저장되었습니다!")
                                st.rerun()

                        with col_cancel:
                            if st.button("취소", key=f"cancel_disagree_{case.id}"):
                                st.session_state[edit_mode_key] = False
                                st.session_state[add_mode_key] = False
                                st.rerun()

            st.markdown("---")

            # Review actions with enhanced ReviewNote input
            col_a, col_b = st.columns(2)

            with col_a:
                # Accept with optional note
                accept_key = f"accept_mode_{case.id}"
                if accept_key not in st.session_state:
                    st.session_state[accept_key] = False

                if not st.session_state[accept_key]:
                    if st.button("승인", key=f"accept_{case.id}", type="primary"):
                        st.session_state[accept_key] = True
                        st.rerun()
                else:
                    st.markdown("**승인 (메모 선택사항):**")

                    # QC summary confirmed checkbox (only if AutoQC exists)
                    qc_confirmed = False
                    if autoqc:
                        qc_confirmed = st.checkbox(
                            "Auto-QC 결과 정확성 확인",
                            key=f"qc_confirm_{case.id}"
                        )

                    accept_note = st.text_area(
                        "메모 (선택)",
                        key=f"accept_note_{case.id}",
                        placeholder="케이스에 대한 코멘트..."
                    )

                    accept_tags = st.text_input(
                        "태그 (쉼표 구분, 선택)",
                        key=f"accept_tags_{case.id}",
                        placeholder="예: edge_case, needs_review"
                    )

                    col_x, col_y = st.columns(2)
                    with col_x:
                        if st.button("승인 확인", key=f"confirm_accept_{case.id}", type="primary"):
                            now = datetime.now(TIMEZONE)

                            # Create review note if there's any input
                            if accept_note.strip() or qc_confirmed or accept_tags.strip():
                                tags_json = None
                                if accept_tags.strip():
                                    tags_list = [t.strip() for t in accept_tags.split(",") if t.strip()]
                                    tags_json = json.dumps(tags_list)

                                note = ReviewNote(
                                    case_id=case.id,
                                    reviewer_user_id=user["id"],
                                    note_text=accept_note.strip() or "승인됨",
                                    qc_summary_confirmed=qc_confirmed,
                                    extra_tags_json=tags_json,
                                    created_at=now,
                                )
                                db.add(note)

                            # ReviewerQcFeedback에 코멘트 추가 (불일치 기록은 이미 별도 저장됨)
                            if accept_note.strip():
                                existing_fb = db.query(ReviewerQcFeedback).filter(
                                    ReviewerQcFeedback.case_id == case.id,
                                    ReviewerQcFeedback.reviewer_id == user["id"]
                                ).first()

                                if existing_fb:
                                    existing_fb.review_memo = accept_note.strip()
                                else:
                                    new_fb = ReviewerQcFeedback(
                                        case_id=case.id,
                                        reviewer_id=user["id"],
                                        has_disagreement=False,
                                        review_memo=accept_note.strip(),
                                    )
                                    db.add(new_fb)

                            event = Event(
                                case_id=case.id,
                                user_id=user["id"],
                                event_type=EventType.ACCEPTED,
                                idempotency_key=generate_idempotency_key(case.id, "ACCEPTED"),
                                event_code=f"승인: {accept_note.strip()[:30] if accept_note.strip() else '메모 없음'}",
                                payload_json=json.dumps({"feedback": accept_note.strip() or ""}, ensure_ascii=False),
                                created_at=now,
                            )
                            db.add(event)
                            case.status = CaseStatus.ACCEPTED
                            case.accepted_at = now
                            db.commit()
                            st.session_state[accept_key] = False
                            st.success("케이스가 승인되었습니다!")
                            st.rerun()
                    with col_y:
                        if st.button("취소", key=f"cancel_accept_{case.id}"):
                            st.session_state[accept_key] = False
                            st.rerun()

            with col_b:
                rework_key = f"rework_mode_{case.id}"
                if rework_key not in st.session_state:
                    st.session_state[rework_key] = False

                if not st.session_state[rework_key]:
                    if st.button("재작업 요청", key=f"rework_{case.id}"):
                        st.session_state[rework_key] = True
                        st.rerun()
                else:
                    st.markdown("**재작업 요청:**")

                    reason = st.text_area(
                        "사유 (필수)",
                        key=f"rework_reason_{case.id}",
                        placeholder="수정이 필요한 내용을 설명하세요..."
                    )

                    rework_tags = st.text_input(
                        "태그 (쉼표 구분, 선택)",
                        key=f"rework_tags_{case.id}",
                        placeholder="예: missing_segment, boundary_error"
                    )

                    col_x, col_y = st.columns(2)
                    with col_x:
                        if st.button("재작업 확인", key=f"confirm_rework_{case.id}"):
                            if not reason.strip():
                                st.error("사유는 필수 입력 항목입니다!")
                            else:
                                now = datetime.now(TIMEZONE)

                                tags_json = None
                                if rework_tags.strip():
                                    tags_list = [t.strip() for t in rework_tags.split(",") if t.strip()]
                                    tags_json = json.dumps(tags_list)

                                # Create review note
                                note = ReviewNote(
                                    case_id=case.id,
                                    reviewer_user_id=user["id"],
                                    note_text=reason.strip(),
                                    qc_summary_confirmed=False,
                                    extra_tags_json=tags_json,
                                    created_at=now,
                                )
                                db.add(note)

                                # ReviewerQcFeedback에 코멘트 추가 (불일치 기록은 이미 별도 저장됨)
                                existing_fb = db.query(ReviewerQcFeedback).filter(
                                    ReviewerQcFeedback.case_id == case.id,
                                    ReviewerQcFeedback.reviewer_id == user["id"]
                                ).first()

                                if existing_fb:
                                    existing_fb.review_memo = reason.strip()
                                else:
                                    new_fb = ReviewerQcFeedback(
                                        case_id=case.id,
                                        reviewer_id=user["id"],
                                        has_disagreement=False,
                                        review_memo=reason.strip(),
                                    )
                                    db.add(new_fb)

                                # Create REWORK event (REJECT)
                                event = Event(
                                    case_id=case.id,
                                    user_id=user["id"],
                                    event_type=EventType.REJECT,
                                    idempotency_key=generate_idempotency_key(case.id, "REJECT"),
                                    event_code=f"반려: {reason.strip()[:30]}...",
                                    payload_json=json.dumps({"reason": reason.strip()}, ensure_ascii=False),
                                    created_at=now,
                                )
                                db.add(event)
                                case.status = CaseStatus.REWORK
                                case.revision += 1
                                db.commit()
                                st.session_state[rework_key] = False
                                st.success("재작업이 요청되었습니다!")
                                st.rerun()
                    with col_y:
                        if st.button("취소", key=f"cancel_rework_{case.id}"):
                            st.session_state[rework_key] = False
                            st.rerun()


def show_all_cases(db: Session):
    """Show all cases with AG Grid table (Google Sheets style filtering)."""
    st.subheader("전체 케이스")

    auto_timeout = get_config_value(db, "auto_timeout_minutes", 120)
    workday_hours = get_config_value(db, "workday_hours", 8)

    # 전체 케이스 조회 (DB 필터 없음 - AG Grid에서 필터링)
    cases = db.query(Case).order_by(Case.created_at.desc()).limit(500).all()
    total_count = len(cases)

    # 건수 표시
    st.caption(f"총 {total_count}건 표시 중")

    if not cases:
        st.info("케이스가 없습니다.")
        return

    # DataFrame 구성 (AG Grid용)
    data = []
    case_map = {}  # id -> case 매핑 (상세 조회용)
    for c in cases:
        worklogs = db.query(WorkLog).filter(WorkLog.case_id == c.id).order_by(WorkLog.timestamp).all()
        work_seconds = compute_work_seconds(worklogs, auto_timeout)

        # Determine status with pause info
        status_display = c.status.value
        pause_reason = ""
        if c.status == CaseStatus.IN_PROGRESS and worklogs:
            last_log = worklogs[-1]
            if last_log.action_type == ActionType.PAUSE:
                status_display = "IN_PROGRESS (PAUSED)"
                if last_log.reason_code:
                    pause_reason = last_log.reason_code

        # 작업일수/시간 통합 포맷
        man_days = compute_man_days(work_seconds, workday_hours)
        work_time_str = format_duration(work_seconds)
        work_days_time = f"{man_days:.2f}일 ({work_time_str})" if work_seconds > 0 else "-"

        row = {
            UI_LABELS["id"]: c.id,
            UI_LABELS["case_uid"]: c.case_uid,
            UI_LABELS["original_name"]: c.original_name if c.original_name else c.display_name,
            UI_LABELS["project"]: c.project.name,
            UI_LABELS["part"]: c.part.name,
            UI_LABELS["hospital"]: c.hospital or UI_LABELS["unassigned"],
            UI_LABELS["slice_thickness"]: c.slice_thickness_mm if c.slice_thickness_mm else "-",
            UI_LABELS["difficulty"]: c.difficulty.value,
            UI_LABELS["status"]: status_display,
            UI_LABELS["pause_reason"]: pause_reason if pause_reason else "-",
            UI_LABELS["revision"]: c.revision,
            UI_LABELS["assignee"]: c.assigned_user.username if c.assigned_user else "-",
        }
        data.append(row)
        case_map[c.id] = c

    df = pd.DataFrame(data)

    # 필터 UI + DataFrame 필터링
    filtered_df = render_case_filters(df, "all_cases", show_assignee=True)

    # 데이터 개수에 따라 높이 자동 계산 (최대 25행)
    row_count = len(filtered_df)
    auto_height = min(max(row_count * 35 + 100, 200), 975)

    # 공통 AG Grid 렌더링
    grid_response = render_styled_dataframe(
        filtered_df,
        key="all_cases_grid",
        height=auto_height,
        user_role="admin",
    )

    # 선택된 케이스 ID 추출 (AG Grid)
    selected_case_id = None
    if grid_response:
        selected_rows = grid_response.get("selected_rows", None)
        if selected_rows is not None and len(selected_rows) > 0:
            selected_case_id = int(selected_rows.iloc[0][UI_LABELS["id"]])

    # Case detail view
    st.markdown("---")
    st.subheader("케이스 상세")

    # 선택되지 않은 경우 selectbox로 선택
    if selected_case_id is None:
        case_ids = [c.id for c in cases]
        selected_case_id = st.selectbox("케이스 선택", options=case_ids, format_func=lambda x: f"케이스 {x}")

    if selected_case_id:
        show_case_detail(db, selected_case_id, auto_timeout, workday_hours)


def show_case_detail(db: Session, case_id: int, auto_timeout: int, workday_hours: int):
    """Show detailed case view with metrics."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        st.error("케이스를 찾을 수 없습니다")
        return

    worklogs = db.query(WorkLog).filter(WorkLog.case_id == case.id).order_by(WorkLog.timestamp).all()
    work_seconds = compute_work_seconds(worklogs, auto_timeout)
    first_start, last_end = get_timeline_dates(worklogs)

    # 중단 사유 확인 (PAUSED 상태일 때)
    pause_reason = ""
    last_action = get_last_worklog_action(db, case.id)
    is_paused = last_action == ActionType.PAUSE
    if is_paused and worklogs:
        last_log = worklogs[-1]
        if last_log.action_type == ActionType.PAUSE and last_log.reason_code:
            pause_reason = last_log.reason_code

    status_display = case.status.value
    if case.status == CaseStatus.IN_PROGRESS and is_paused:
        status_display = "IN_PROGRESS (PAUSED)"

    original_name_display = case.original_name if case.original_name else case.display_name

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**{UI_LABELS['case_uid']}:** {case.case_uid}")
        st.write(f"**{UI_LABELS['original_name']}:** {original_name_display}")
        st.write(f"**{UI_LABELS['nas_path']}:** {case.nas_path if case.nas_path else '-'}")
        st.write(f"**{UI_LABELS['project']}:** {case.project.name}")
        st.write(f"**{UI_LABELS['part']}:** {case.part.name}")
        st.write(f"**{UI_LABELS['hospital']}:** {case.hospital or UI_LABELS['unassigned']}")
        st.write(f"**{UI_LABELS['slice_thickness']}:** {case.slice_thickness_mm if case.slice_thickness_mm else '-'}")

    with col2:
        st.write(f"**{UI_LABELS['difficulty']}:** {case.difficulty.value}")
        st.write(f"**{UI_LABELS['status']}:** {status_display}")
        if pause_reason:
            st.write(f"**{UI_LABELS['pause_reason']}:** {pause_reason}")
        st.write(f"**{UI_LABELS['revision']}:** {case.revision}")
        st.write(f"**{UI_LABELS['assignee']}:** {case.assigned_user.username if case.assigned_user else UI_LABELS['unassigned']}")

    # Metrics
    st.markdown("---")
    st.markdown("**작업 지표:**")
    man_days = compute_man_days(work_seconds, workday_hours)
    work_time_str = format_duration(work_seconds)
    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric(UI_LABELS["work_days_time"], f"{man_days:.2f}일 ({work_time_str})")
    with metric_cols[1]:
        st.metric("소요 일수", compute_timeline(first_start, last_end))
    with metric_cols[2]:
        pass  # 빈 컬럼

    # WorkLog timeline
    if worklogs:
        st.markdown("**작업 기록:**")
        for wl in worklogs:
            reason_str = f" ({wl.reason_code})" if wl.reason_code else ""
            st.write(f"- {wl.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | {wl.action_type.value}{reason_str} | {wl.user.username}")

    # Events
    if case.events:
        st.markdown("**이벤트 이력:**")
        event_icons = {
            "STARTED": "▶️", "SUBMITTED": "📤", "REWORK_REQUESTED": "🔄", "ACCEPTED": "✅",
            "ASSIGN": "📋", "REASSIGN": "🔀", "REJECT": "❌",
            "FEEDBACK_CREATED": "💬", "FEEDBACK_UPDATED": "✏️", "FEEDBACK_DELETED": "🗑️",
            "FEEDBACK_SUBMIT": "📝", "CANCEL": "⛔", "EDIT": "📝",
        }
        for e in case.events:
            icon = event_icons.get(e.event_type.value, "📌")
            detail = f" | {e.event_code}" if e.event_code else ""
            st.write(f"- {e.created_at.strftime('%m-%d %H:%M')} | {icon} {e.event_type.value} | {e.user.username}{detail}")

    # Review Notes
    if case.review_notes:
        st.markdown("**검수 메모:**")
        for n in case.review_notes:
            st.write(f"- {n.created_at.strftime('%Y-%m-%d %H:%M')} | {n.reviewer.username}: {n.note_text}")

    # QC 정보
    st.markdown("---")
    st.markdown("### QC 정보")

    preqc = db.query(PreQcSummary).filter(PreQcSummary.case_id == case.id).first()
    autoqc = db.query(AutoQcSummary).filter(AutoQcSummary.case_id == case.id).first()

    qc_col1, qc_col2 = st.columns(2)

    with qc_col1:
        st.markdown("**Pre-QC**")
        with st.container(border=True):
            if preqc:
                # 슬라이스 수
                slice_count_display = preqc.slice_count if preqc.slice_count else "-"
                st.write(f"슬라이스: {slice_count_display}")

                # 두께
                thickness_icon = {"OK": "✅", "WARN": "⚠️", "THICK": "❌"}.get(preqc.slice_thickness_flag, "")
                thickness_display = f"{preqc.slice_thickness_mm:.2f}mm {thickness_icon}" if preqc.slice_thickness_mm is not None else "-"
                st.write(f"두께: {thickness_display}")

                # 노이즈
                noise_icon = {"LOW": "🟢", "MODERATE": "🟡", "HIGH": "🔴"}.get(preqc.noise_level, "")
                if preqc.noise_level:
                    noise_mean = f" (평균: {preqc.noise_sigma_mean:.2f})" if preqc.noise_sigma_mean is not None else ""
                    st.write(f"노이즈: {noise_icon} {preqc.noise_level}{noise_mean}")
                else:
                    st.write("노이즈: -")

                # 조영제
                contrast_icon = {"GOOD": "🟢", "BORDERLINE": "🟡", "POOR": "🔴"}.get(preqc.contrast_flag, "")
                if preqc.contrast_flag:
                    delta_hu = f" (Delta HU: {preqc.delta_hu:.1f})" if preqc.delta_hu is not None else ""
                    st.write(f"조영제: {contrast_icon} {preqc.contrast_flag}{delta_hu}")
                else:
                    st.write("조영제: -")

                # 혈관 가시성
                vis_icon = {"EXCELLENT": "🟢", "USABLE": "🟢", "BORDERLINE": "🟡", "POOR": "🔴"}.get(preqc.vascular_visibility_level, "")
                if preqc.vascular_visibility_level:
                    vis_score = f" (점수: {preqc.vascular_visibility_score:.1f})" if preqc.vascular_visibility_score is not None else ""
                    st.write(f"혈관 가시성: {vis_icon} {preqc.vascular_visibility_level}{vis_score}")
                else:
                    st.write("혈관 가시성: -")

                # 난이도
                diff_icon = {"EASY": "🟢", "NORMAL": "🟡", "HARD": "🔴", "VERY_HARD": "🔴"}.get(preqc.difficulty, "")
                if preqc.difficulty:
                    st.write(f"난이도: {diff_icon} {preqc.difficulty}")
                else:
                    st.write("난이도: -")

                # 스페이싱
                if preqc.spacing_json:
                    try:
                        spacing = json.loads(preqc.spacing_json)
                        spacing_str = str(spacing) if spacing else "-"
                        st.write(f"스페이싱: {spacing_str}")
                    except json.JSONDecodeError:
                        st.write(f"스페이싱: {preqc.spacing_json}")
                else:
                    st.write("스페이싱: -")

                # 메모
                if preqc.notes:
                    st.info(f"메모: {preqc.notes}")
                else:
                    st.write("메모: -")
            else:
                st.caption("Pre-QC 데이터 없음")

    with qc_col2:
        st.markdown("**Auto-QC**")
        with st.container(border=True):
            if autoqc:
                # 상태
                status_icon = {"PASS": "✅", "WARN": "⚠️", "INCOMPLETE": "❌"}.get(autoqc.status, "")
                st.write(f"상태: {status_icon} {autoqc.status or '-'}")

                # 재작업 및 이전 대비
                revision = autoqc.revision if hasattr(autoqc, 'revision') and autoqc.revision else 1
                comparison_display = "-"
                if revision > 1:
                    current_issue_count = 0
                    if autoqc.issue_count_json:
                        try:
                            counts = json.loads(autoqc.issue_count_json)
                            current_issue_count = counts.get("warn_level", 0) + counts.get("incomplete_level", 0)
                        except json.JSONDecodeError:
                            pass
                    prev_count = autoqc.previous_issue_count if hasattr(autoqc, 'previous_issue_count') and autoqc.previous_issue_count is not None else 0
                    if current_issue_count < prev_count:
                        comparison_display = "✅ 개선"
                    elif current_issue_count == prev_count:
                        comparison_display = "⚠️ 동일"
                    else:
                        comparison_display = "❌ 악화"
                st.write(f"재작업: {revision} (이전 대비: {comparison_display})")

                st.markdown("---")

                # 누락 세그먼트
                st.write("📋 누락 세그먼트:")
                if autoqc.missing_segments_json:
                    try:
                        missing = json.loads(autoqc.missing_segments_json)
                        if missing:
                            for seg in missing:
                                st.caption(f"  • {seg}")
                        else:
                            st.caption("  없음")
                    except json.JSONDecodeError:
                        st.caption("  없음")
                else:
                    st.caption("  없음")

                # 이름 불일치
                mismatch_count = 0
                mismatches = []
                if autoqc.name_mismatches_json:
                    try:
                        mismatches = json.loads(autoqc.name_mismatches_json)
                        mismatch_count = len(mismatches) if mismatches else 0
                    except json.JSONDecodeError:
                        pass
                st.write(f"📋 이름 불일치 ({mismatch_count}건):")
                if mismatches:
                    for m in mismatches[:10]:
                        expected = m.get('expected', '?')
                        found = m.get('found', '?')
                        mtype = m.get('type', '')
                        st.caption(f"  • {expected} → {found} ({mtype})")
                    if len(mismatches) > 10:
                        st.caption(f"  ... 외 {len(mismatches) - 10}건")
                else:
                    st.caption("  없음")

                # 이슈 목록
                st.write("📋 이슈 목록:")
                if autoqc.issues_json:
                    try:
                        issues = json.loads(autoqc.issues_json)
                        if issues:
                            severity_icons = {"WARN": "⚠️", "INCOMPLETE": "❌", "INFO": "ℹ️"}
                            for issue in issues[:10]:
                                level = issue.get("level", "")
                                segment = issue.get("segment", "")
                                msg = issue.get("message", str(issue))
                                icon = severity_icons.get(level, "•")
                                st.caption(f"  • {icon}: {segment} - {msg}")
                            if len(issues) > 10:
                                st.caption(f"  ... 외 {len(issues) - 10}건")
                        else:
                            st.caption("  없음")
                    except json.JSONDecodeError:
                        st.caption("  없음")
                else:
                    st.caption("  없음")

                # 추가 세그먼트
                extra_segments_display = "없음"
                if autoqc.extra_segments_json:
                    try:
                        extra = json.loads(autoqc.extra_segments_json)
                        if extra:
                            extra_segments_display = ", ".join(extra)
                    except json.JSONDecodeError:
                        pass
                st.write(f"📋 추가 세그먼트: {extra_segments_display}")

                st.markdown("---")

                # WARN / INCOMPLETE 건수
                warn_cnt = 0
                inc_cnt = 0
                if autoqc.issue_count_json:
                    try:
                        counts = json.loads(autoqc.issue_count_json)
                        warn_cnt = counts.get("warn_level", 0)
                        inc_cnt = counts.get("incomplete_level", 0)
                    except json.JSONDecodeError:
                        pass
                st.write(f"WARN: {warn_cnt}건 / INCOMPLETE: {inc_cnt}건")
            else:
                st.caption("Auto-QC 데이터 없음")


def show_assign_cases(db: Session):
    """Show case assignment interface."""
    st.subheader("케이스 배정")

    # Get current user for event logging
    user = st.session_state.get("user")
    if not user:
        st.error("로그인이 필요합니다")
        return

    # Get unassigned TODO cases
    unassigned = db.query(Case).filter(
        Case.status == CaseStatus.TODO,
        Case.assigned_user_id == None
    ).order_by(Case.created_at.asc()).all()

    if not unassigned:
        st.info("미배정 케이스가 없습니다.")
        return

    # Get workers
    workers = db.query(User).filter(
        User.role == UserRole.WORKER,
        User.is_active == True
    ).all()

    if not workers:
        st.warning("활성 작업자가 없습니다.")
        return

    worker_options = {w.username: w.id for w in workers}

    st.write(f"**미배정 케이스 {len(unassigned)}건**")

    for case in unassigned:
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            st.write(f"**{case.display_name}** ({case.case_uid})")
            hospital_info = case.hospital or UI_LABELS["unassigned"]
            st.caption(f"{case.project.name} / {case.part.name} / {hospital_info} / {case.difficulty.value}")

        with col2:
            selected_worker = st.selectbox(
                "담당자 지정",
                options=list(worker_options.keys()),
                key=f"assign_select_{case.id}"
            )

        with col3:
            st.write("")
            if st.button("배정", key=f"assign_btn_{case.id}"):
                import uuid
                prev_worker = case.assigned_user.username if case.assigned_user else None
                new_worker_id = worker_options[selected_worker]

                # 이전 담당자가 있으면 REASSIGN, 없으면 ASSIGN
                if prev_worker:
                    event_type = EventType.REASSIGN
                    event_code = f"{prev_worker} → {selected_worker}"
                    payload = {"from": prev_worker, "to": selected_worker}
                else:
                    event_type = EventType.ASSIGN
                    event_code = f"{selected_worker}에게 배정"
                    payload = {"worker": selected_worker}

                case.assigned_user_id = new_worker_id

                # Event 생성
                event = Event(
                    case_id=case.id,
                    user_id=user["id"],
                    event_type=event_type,
                    idempotency_key=f"{event_type.value}_{case.id}_{uuid.uuid4().hex[:8]}",
                    event_code=event_code,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
                db.add(event)
                db.commit()
                st.success(f"{selected_worker}에게 배정되었습니다")
                st.rerun()

        st.markdown("---")


def show_event_log(db: Session):
    """Show recent event log (Event + WorkLog 통합)."""
    st.subheader("이벤트 로그")

    # 이벤트 타입별 아이콘 매핑
    EVENT_ICONS = {
        # 작업자 상태
        "STARTED": "▶️",
        "SUBMITTED": "📤",
        "REWORK_REQUESTED": "🔄",
        "ACCEPTED": "✅",
        # 어드민 액션
        "ASSIGN": "📋",
        "REASSIGN": "🔀",
        "REJECT": "❌",
        # 피드백
        "FEEDBACK_CREATED": "💬",
        "FEEDBACK_UPDATED": "✏️",
        "FEEDBACK_DELETED": "🗑️",
        "FEEDBACK_SUBMIT": "📝",
        # 기타
        "CANCEL": "⛔",
        "EDIT": "📝",
        # WorkLog
        "START": "▶️",
        "PAUSE": "⏸️",
        "RESUME": "▶️",
        "SUBMIT": "📤",
        "REWORK_START": "🔄",
    }

    # Event 조회
    events = db.query(Event).order_by(Event.created_at.desc()).limit(100).all()

    # WorkLog 조회
    worklogs = db.query(WorkLog).order_by(WorkLog.timestamp.desc()).limit(100).all()

    # 통합 리스트 생성
    all_logs = []

    for e in events:
        case = db.query(Case).filter(Case.id == e.case_id).first()
        icon = EVENT_ICONS.get(e.event_type.value, "📌")
        all_logs.append({
            "시간": e.created_at,
            "유형": "이벤트",
            "이벤트": f"{icon} {e.event_type.value}",
            "케이스": case.case_uid if case else "?",
            "사용자": e.user.username,
            "상세": e.event_code or "-",
        })

    for wl in worklogs:
        case = db.query(Case).filter(Case.id == wl.case_id).first()
        icon = EVENT_ICONS.get(wl.action_type.value, "⏱️")
        all_logs.append({
            "시간": wl.timestamp,
            "유형": "작업",
            "이벤트": f"{icon} {wl.action_type.value}",
            "케이스": case.case_uid if case else "?",
            "사용자": wl.user.username,
            "상세": wl.reason_code or "-",
        })

    if not all_logs:
        st.info("이벤트가 없습니다.")
        return

    # 시간순 정렬
    all_logs.sort(key=lambda x: x["시간"], reverse=True)

    # 상위 50개만 표시
    display_logs = all_logs[:50]

    # DataFrame 변환
    df = pd.DataFrame(display_logs)
    df["시간"] = df["시간"].apply(lambda x: x.strftime("%m-%d %H:%M"))

    render_styled_dataframe(df, key="event_log_grid", enable_selection=False, height=400, user_role="admin")


def show_timeoff_management(db: Session, user: dict):
    """Show time-off management interface (ADMIN)."""
    st.subheader("휴무 관리")

    # Get all workers
    workers = db.query(User).filter(
        User.role == UserRole.WORKER,
        User.is_active == True
    ).all()

    if not workers:
        st.info("활성 작업자가 없습니다.")
        return

    # Register new time-off
    st.markdown("### 휴무 등록")

    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])

    with col1:
        worker_options = {w.username: w.id for w in workers}
        selected_worker = st.selectbox(
            "작업자",
            options=list(worker_options.keys()),
            key="timeoff_worker"
        )

    with col2:
        timeoff_start = st.date_input(
            "시작일",
            value=date.today(),
            key="timeoff_start"
        )

    with col3:
        timeoff_end = st.date_input(
            "종료일",
            value=date.today(),
            key="timeoff_end"
        )

    with col4:
        timeoff_type = st.selectbox(
            "유형",
            options=[t.value for t in TimeOffType],
            key="timeoff_type"
        )

    with col5:
        st.write("")
        st.write("")
        if st.button("추가", key="add_timeoff", type="primary"):
            if timeoff_start > timeoff_end:
                st.error("시작일이 종료일보다 앞서야 합니다")
            else:
                # Register time-off for each day in range
                current_date = timeoff_start
                added_count = 0
                skipped_dates = []

                while current_date <= timeoff_end:
                    # Check for duplicate
                    existing = db.query(UserTimeOff).filter(
                        UserTimeOff.user_id == worker_options[selected_worker],
                        UserTimeOff.date == current_date
                    ).first()

                    if existing:
                        skipped_dates.append(str(current_date))
                    else:
                        timeoff = UserTimeOff(
                            user_id=worker_options[selected_worker],
                            date=current_date,
                            type=TimeOffType(timeoff_type),
                        )
                        db.add(timeoff)
                        added_count += 1

                    current_date += timedelta(days=1)

                if added_count > 0:
                    db.commit()
                    st.success(f"{selected_worker}에 {added_count}건 휴무 추가됨")
                    if skipped_dates:
                        st.warning(f"건너뜀 (이미 존재): {', '.join(skipped_dates)}")
                    st.rerun()
                elif skipped_dates:
                    st.error(f"모든 날짜에 이미 휴무가 등록되어 있습니다")

    st.markdown("---")

    # Date range filter and worker filter
    st.markdown("### 휴무 조회")

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        start_filter = st.date_input(
            "시작",
            value=date.today() - timedelta(days=30),
            key="timeoff_filter_start"
        )
    with col2:
        end_filter = st.date_input(
            "종료",
            value=date.today() + timedelta(days=60),
            key="timeoff_filter_end"
        )
    with col3:
        # Worker filter
        worker_filter_options = {"전체": None}
        worker_filter_options.update({w.username: w.id for w in workers})
        selected_worker_filter = st.selectbox(
            "작업자",
            options=list(worker_filter_options.keys()),
            key="timeoff_worker_filter"
        )

    # Get time-offs
    query = db.query(UserTimeOff).filter(
        UserTimeOff.date >= start_filter,
        UserTimeOff.date <= end_filter
    )

    # Apply worker filter
    if worker_filter_options[selected_worker_filter] is not None:
        query = query.filter(UserTimeOff.user_id == worker_filter_options[selected_worker_filter])

    query = query.order_by(UserTimeOff.date.desc())
    timeoffs = query.all()

    if not timeoffs:
        st.info("선택한 기간에 휴무가 없습니다.")
        return

    # Group consecutive time-offs
    grouped = group_consecutive_timeoffs(timeoffs)

    # Display grouped table
    data = []
    for g in grouped:
        data.append({
            "작업자": g["username"],
            "기간": g["period"],
            "유형": g["type"].value,
            "일수/시간": f"{g['days_display']} ({g['hours']}h)",
        })

    render_styled_dataframe(pd.DataFrame(data), key="admin_timeoff_grid", enable_selection=False, height=300, user_role="admin")

    # Delete time-off (with grouped periods)
    st.markdown("### 휴무 삭제")

    # Create delete options from groups
    delete_options = []
    for i, g in enumerate(grouped):
        label = f"{g['username']} - {g['period']} ({g['type'].value}, {g['days_display']})"
        delete_options.append((i, label, g["ids"]))

    if delete_options:
        selected_delete_idx = st.selectbox(
            "삭제할 휴무 선택",
            options=range(len(delete_options)),
            format_func=lambda x: delete_options[x][1],
            key="delete_timeoff_group"
        )

        selected_ids = delete_options[selected_delete_idx][2]
        days_count = len(selected_ids)

        if days_count > 1:
            st.warning(f"{days_count}개의 연속 휴무가 삭제됩니다.")

        if st.button("삭제", key="delete_timeoff_btn"):
            for tid in selected_ids:
                timeoff = db.query(UserTimeOff).filter(UserTimeOff.id == tid).first()
                if timeoff:
                    db.delete(timeoff)
            db.commit()
            st.success(f"{days_count}건 휴무 삭제됨")
            st.rerun()


def show_holiday_management(db: Session, user: dict):
    """Show holiday management interface (ADMIN)."""
    st.subheader("공휴일 관리")

    # Get or create work calendar
    calendar = db.query(WorkCalendar).first()
    if not calendar:
        calendar = WorkCalendar(holidays_json="[]", timezone="Asia/Seoul")
        db.add(calendar)
        db.commit()
        db.refresh(calendar)

    holidays_list = json.loads(calendar.holidays_json)
    holidays = [date.fromisoformat(d) for d in holidays_list]

    st.write(f"**타임존:** {calendar.timezone}")
    st.write(f"**총 공휴일:** {len(holidays)}일")

    st.markdown("---")

    # 공휴일 추가/삭제 나란히 배치
    add_col, delete_col = st.columns(2)

    with add_col:
        st.markdown("### 공휴일 추가")
        new_holiday = st.date_input(
            "추가할 날짜",
            value=date.today(),
            key="new_holiday_date"
        )
        if st.button("추가", key="add_holiday_btn", type="primary"):
            date_str = new_holiday.isoformat()
            if date_str in holidays_list:
                st.warning("이미 등록된 공휴일입니다")
            else:
                holidays_list.append(date_str)
                holidays_list.sort()
                calendar.holidays_json = json.dumps(holidays_list)
                db.commit()
                st.success(f"공휴일 추가됨: {new_holiday}")
                st.rerun()

    with delete_col:
        st.markdown("### 공휴일 삭제")
        delete_holiday = st.date_input(
            "삭제할 날짜",
            value=date.today(),
            key="delete_holiday_date"
        )
        if st.button("삭제", key="remove_holiday_btn"):
            date_str = delete_holiday.isoformat()
            if date_str in holidays_list:
                holidays_list.remove(date_str)
                calendar.holidays_json = json.dumps(holidays_list)
                db.commit()
                st.success(f"공휴일 삭제됨: {delete_holiday}")
                st.rerun()
            else:
                st.warning("해당 날짜는 공휴일이 아닙니다")

    st.markdown("---")

    # Display holidays by year
    st.markdown("### 공휴일 목록")

    if not holidays:
        st.info("등록된 공휴일이 없습니다.")
        return

    # Group by year
    holidays_by_year = {}
    for h in sorted(holidays):
        year = h.year
        if year not in holidays_by_year:
            holidays_by_year[year] = []
        holidays_by_year[year].append(h)

    weekday_korean = {
        "Monday": "월요일",
        "Tuesday": "화요일",
        "Wednesday": "수요일",
        "Thursday": "목요일",
        "Friday": "금요일",
        "Saturday": "토요일",
        "Sunday": "일요일",
    }

    for year in sorted(holidays_by_year.keys(), reverse=True):
        with st.expander(f"{year}년 ({len(holidays_by_year[year])}일)", expanded=(year == date.today().year)):
            year_holidays = holidays_by_year[year]

            data = []
            for h in year_holidays:
                data.append({
                    "날짜": h.strftime("%Y-%m-%d"),
                    "요일": weekday_korean.get(h.strftime("%A"), h.strftime("%A")),
                })

            # 데이터 개수에 따라 높이 자동 계산
            row_count = len(data)
            # 행 높이 28px + 헤더 40px + 페이지네이션 50px
            auto_height = min(max(row_count * 28 + 90, 150), 800)
            render_styled_dataframe(pd.DataFrame(data), key=f"holidays_{year}_grid", enable_selection=False, show_toolbar=False, height=auto_height, user_role="admin")


def show_work_statistics(db: Session):
    """Show work statistics with sub-tabs."""
    st.subheader("작업 통계")

    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["성과", "분포", "가동률"])

    with sub_tab1:
        show_performance_tab(db)

    with sub_tab2:
        show_distribution_stats(db)

    with sub_tab3:
        show_utilization_stats(db)


def show_performance_tab(db: Session):
    """성과 탭 - 요약 카드 + 작업자별 테이블 + 월별 추이."""
    from calendar import monthrange

    current_year = date.today().year
    current_month = date.today().month

    # 작업자 목록 조회
    workers = db.query(User).filter(User.role == UserRole.WORKER).all()
    worker_names = sorted([w.username for w in workers])

    # 공휴일 목록 조회
    calendar = db.query(WorkCalendar).first()
    if calendar:
        holidays_list = json.loads(calendar.holidays_json)
        holidays = [date.fromisoformat(d) for d in holidays_list]
    else:
        holidays = []

    # ========== 필터 영역 ==========
    with st.expander("필터", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            year_options = list(range(2025, current_year + 2))
            year = st.selectbox("연도", options=year_options, index=year_options.index(current_year) if current_year in year_options else 0, key="perf_year")
        with col2:
            month_options = ["전체"] + [f"{m}월" for m in range(1, 13)]
            month_select = st.selectbox("월", options=month_options, index=current_month, key="perf_month_select")

        # 월 선택에 따른 기간 결정
        if month_select == "전체":
            # 전체 선택: 기간 입력 활성화
            col3, col4 = st.columns(2)
            with col3:
                default_start = date(year, 1, 1)
                start_date = st.date_input("시작일", value=default_start, key="perf_start")
            with col4:
                default_end = date.today() if year == current_year else date(year, 12, 31)
                end_date = st.date_input("종료일", value=default_end, key="perf_end")
        else:
            # 특정월 선택: 기간 자동 세팅, 비활성화 표시
            month_num = int(month_select.replace("월", ""))
            month_start = date(year, month_num, 1)
            month_end = date(year, month_num, monthrange(year, month_num)[1])

            col3, col4 = st.columns(2)
            with col3:
                st.text_input("시작일", value=month_start.strftime("%Y-%m-%d"), disabled=True, key="perf_start_disabled")
            with col4:
                st.text_input("종료일", value=month_end.strftime("%Y-%m-%d"), disabled=True, key="perf_end_disabled")

            start_date = month_start
            end_date = month_end

        selected_workers = st.multiselect(
            "작업자",
            options=worker_names,
            default=[],
            key="perf_worker_filter"
        )

    if start_date > end_date:
        st.error("시작일이 종료일보다 앞서야 합니다.")
        return

    # ========== 데이터 조회 ==========
    cases = db.query(Case).filter(
        Case.status == CaseStatus.ACCEPTED,
        Case.accepted_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE),
        Case.accepted_at <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE),
    ).all()

    # 근무일 수 계산
    workdays = count_workdays(start_date, end_date, holidays)

    # 성과 통계 계산
    stats = compute_performance_stats(
        cases=cases,
        start_date=start_date,
        end_date=end_date,
        workdays=workdays,
        selected_workers=selected_workers if selected_workers else None,
    )

    # ========== 1) 전체 요약 (상단 카드 4개) ==========
    st.markdown("### 전체 요약")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 완료", f"{stats['summary']['total_completed']}건")
    with col2:
        st.metric("평균 소요일", f"{stats['summary']['avg_days']}일", help="시작→완료")
    with col3:
        st.metric("재작업률", f"{stats['summary']['rework_rate']}%")
    with col4:
        st.metric("일일 평균", f"{stats['summary']['daily_avg']}건/일", help="근무일 기준")

    st.caption(f"기간: {start_date} ~ {end_date} | 근무일: {workdays}일")

    st.markdown("---")

    # ========== 2) 작업자별 성과 테이블 + CSV 버튼 ==========
    st.markdown("### 작업자별 성과")

    if stats["by_worker"]:
        # DataFrame 생성
        worker_data = []
        for w in stats["by_worker"]:
            worker_data.append({
                "작업자": w["worker"],
                "완료": w["completed"],
                "재작업": w["rework"],
                "재작업률(%)": w["rework_rate"],
                "1차 통과": w["first_pass"],
                "1차 통과율(%)": w["first_pass_rate"],
            })

        # 합계 행 추가
        worker_data.append({
            "작업자": "합계",
            "완료": stats["totals"]["completed"],
            "재작업": stats["totals"]["rework"],
            "재작업률(%)": stats["totals"]["rework_rate"],
            "1차 통과": stats["totals"]["first_pass"],
            "1차 통과율(%)": stats["totals"]["first_pass_rate"],
        })

        worker_df = pd.DataFrame(worker_data)
        render_styled_dataframe(worker_df, key="perf_worker_table", enable_selection=False, user_role="admin")

        # CSV 다운로드 버튼
        csv_worker = worker_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="작업자별 성과 CSV",
            data=csv_worker,
            file_name=f"worker_performance_{start_date}_{end_date}.csv",
            mime="text/csv",
            key="csv_worker_perf"
        )
    else:
        st.info("해당 조건에 맞는 데이터가 없습니다.")

    st.markdown("---")

    # ========== 3) 월별 추이 테이블 + CSV 버튼 + 차트 보기 체크박스 ==========
    st.markdown("### 월별 추이")

    if month_select == "전체":
        # 전체: 12개월 표시
        monthly_stats = compute_monthly_performance(
            cases=cases,
            year=year,
            start_date=start_date,
            end_date=end_date,
            selected_workers=selected_workers if selected_workers else None,
        )

        monthly_data = []
        for m in monthly_stats:
            if m["in_range"]:
                monthly_data.append({
                    "월": m["month"],
                    "완료": m["completed"],
                    "재작업": m["rework"],
                    "재작업률(%)": m["rework_rate"],
                    "1차 통과율(%)": m["first_pass_rate"],
                })
            else:
                monthly_data.append({
                    "월": m["month"],
                    "완료": "-",
                    "재작업": "-",
                    "재작업률(%)": "-",
                    "1차 통과율(%)": "-",
                })

        monthly_df = pd.DataFrame(monthly_data)
        render_styled_dataframe(monthly_df, key="perf_monthly_table", enable_selection=False, user_role="admin")

        # CSV 다운로드 (- 대신 빈칸으로)
        csv_monthly_data = []
        for m in monthly_stats:
            if m["in_range"]:
                csv_monthly_data.append({
                    "월": m["month"],
                    "완료": m["completed"],
                    "재작업": m["rework"],
                    "재작업률(%)": m["rework_rate"],
                    "1차 통과율(%)": m["first_pass_rate"],
                })
            else:
                csv_monthly_data.append({
                    "월": m["month"],
                    "완료": "",
                    "재작업": "",
                    "재작업률(%)": "",
                    "1차 통과율(%)": "",
                })

        csv_monthly_df = pd.DataFrame(csv_monthly_data)
        csv_monthly = csv_monthly_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="월별 추이 CSV",
            data=csv_monthly,
            file_name=f"monthly_trend_{year}.csv",
            mime="text/csv",
            key="csv_monthly_trend"
        )

        # 차트 보기 체크박스
        show_chart = st.checkbox("차트 보기", key="perf_show_chart")
        if show_chart:
            # 범위 내 월만 차트에 표시
            chart_data = []
            for m in monthly_stats:
                if m["in_range"]:
                    chart_data.append({
                        "월": m["month"],
                        "완료": m["completed"],
                        "재작업": m["rework"],
                    })

            if chart_data:
                chart_df = pd.DataFrame(chart_data)
                chart_df = chart_df.set_index("월")
                st.line_chart(chart_df)
            else:
                st.info("차트에 표시할 데이터가 없습니다.")

    else:
        # 특정월: 1행만 표시
        month_num = int(month_select.replace("월", ""))

        # 해당 월 집계 (이미 조회된 cases에서 필터링)
        completed = 0
        rework = 0
        for case in cases:
            if not case.assigned_user:
                continue
            if selected_workers and case.assigned_user.username not in selected_workers:
                continue
            completed += 1
            if case.revision > 1:
                rework += 1

        first_pass = completed - rework
        rework_rate = (rework / completed * 100) if completed > 0 else 0
        first_pass_rate = (first_pass / completed * 100) if completed > 0 else 0

        monthly_data = [{
            "월": f"{year}-{month_num:02d}",
            "완료": completed,
            "재작업": rework,
            "재작업률(%)": round(rework_rate, 1),
            "1차 통과율(%)": round(first_pass_rate, 1),
        }]

        monthly_df = pd.DataFrame(monthly_data)
        render_styled_dataframe(monthly_df, key="perf_monthly_single", enable_selection=False, user_role="admin")

        # CSV 다운로드
        csv_monthly = monthly_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="월별 추이 CSV",
            data=csv_monthly,
            file_name=f"monthly_trend_{year}_{month_num:02d}.csv",
            mime="text/csv",
            key="csv_monthly_single"
        )

        # 특정월 선택 시 차트는 숨김
        st.caption("차트는 월=전체 선택 시에만 표시됩니다.")


def show_distribution_stats(db: Session):
    """분포 - 병원별/부위별."""
    # 작업자 목록 조회
    workers = db.query(User).filter(User.role == UserRole.WORKER).all()
    worker_names = sorted([w.username for w in workers])

    # 필터
    with st.expander("필터", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("시작", value=date.today() - timedelta(days=365), key="dist_start")
        with col2:
            end_date = st.date_input("종료", value=date.today(), key="dist_end")

        dist_type = st.radio("분포 기준", ["병원별", "부위별"], horizontal=True, key="dist_type")

        selected_workers = st.multiselect(
            "작업자",
            options=worker_names,
            default=[],
            key="dist_worker_filter"
        )

    # 케이스 조회
    cases = db.query(Case).filter(
        Case.created_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE),
        Case.created_at <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE),
    ).all()

    if not cases:
        st.info("해당 기간에 케이스가 없습니다.")
        return

    # 집계
    distribution = {}
    for case in cases:
        username = case.assigned_user.username if case.assigned_user else "미배정"

        # 작업자 필터 적용
        if selected_workers and username not in selected_workers:
            continue

        if dist_type == "병원별":
            key = case.hospital or "미지정"
        else:
            key = case.part.name

        if username not in distribution:
            distribution[username] = {}
        distribution[username][key] = distribution[username].get(key, 0) + 1

    if not distribution:
        st.info("해당 조건에 맞는 데이터가 없습니다.")
        return

    # 모든 키 (병원 또는 부위)
    all_keys = sorted(set(k for u in distribution for k in distribution[u]))

    # DataFrame 생성
    data = []
    for username in sorted(distribution.keys()):
        row = {"작업자": username}
        total = 0
        for key in all_keys:
            count = distribution[username].get(key, 0)
            row[key] = count if count > 0 else ""
            total += count
        row["합계"] = total
        data.append(row)

    # 총계 행
    if data:
        total_row = {"작업자": "합계"}
        grand_total = 0
        for key in all_keys:
            key_total = sum(distribution[u].get(key, 0) for u in distribution)
            total_row[key] = key_total if key_total > 0 else ""
            grand_total += key_total
        total_row["합계"] = grand_total
        data.append(total_row)

    render_styled_dataframe(pd.DataFrame(data), key="dist_stats", enable_selection=False, user_role="admin")


def show_utilization_stats(db: Session):
    """가동률 - 기존 show_capacity_metrics 내용."""
    show_capacity_metrics(db)


def show_capacity_metrics(db: Session):
    """Show team capacity metrics."""
    st.markdown("### 팀 가용량 지표")

    # Get configs
    workday_hours = get_config_value(db, "workday_hours", 8)
    auto_timeout = get_config_value(db, "auto_timeout_minutes", 120)

    # 작업자 목록 조회
    all_workers = db.query(User).filter(User.role == UserRole.WORKER, User.is_active == True).all()
    worker_names = sorted([w.username for w in all_workers])

    # 필터
    with st.expander("필터", expanded=False):
        # Date range selector
        col1, col2 = st.columns(2)

        with col1:
            start_date = st.date_input(
                "기간 시작",
                value=date.today().replace(day=1),
                key="capacity_start"
            )

        with col2:
            # Default to end of month
            next_month = date.today().replace(day=28) + timedelta(days=4)
            end_of_month = next_month - timedelta(days=next_month.day)
            end_date = st.date_input(
                "기간 종료",
                value=end_of_month,
                key="capacity_end"
            )

        selected_workers = st.multiselect(
            "작업자",
            options=worker_names,
            default=[],
            key="capacity_worker_filter"
        )

    if start_date > end_date:
        st.error("시작일이 종료일보다 앞서야 합니다")
        return

    # Get holidays
    calendar = db.query(WorkCalendar).first()
    if calendar:
        holidays_list = json.loads(calendar.holidays_json)
        holidays = [date.fromisoformat(d) for d in holidays_list]
    else:
        holidays = []

    # Count workdays in period
    total_workdays = count_workdays(start_date, end_date, holidays)

    st.markdown("---")

    # Period summary
    st.markdown("### 기간 요약")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("총 일수", (end_date - start_date).days + 1)
    with col2:
        st.metric("근무일", total_workdays)
    with col3:
        st.metric("총 시간", f"{total_workdays * workday_hours}h")

    st.markdown("---")

    # Get workers (filtered)
    if selected_workers:
        workers = [w for w in all_workers if w.username in selected_workers]
    else:
        workers = all_workers

    if not workers:
        st.info("활성 작업자가 없습니다.")
        return

    st.markdown("### 작업자별 가용량")

    # Calculate metrics for each worker
    worker_data = []
    total_available = 0.0
    total_actual = 0.0

    for worker in workers:
        # Get time-offs
        timeoffs = db.query(UserTimeOff).filter(
            UserTimeOff.user_id == worker.id,
            UserTimeOff.date >= start_date,
            UserTimeOff.date <= end_date
        ).all()

        # Get worklogs
        worklogs = db.query(WorkLog).filter(
            WorkLog.user_id == worker.id,
            WorkLog.timestamp >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE),
            WorkLog.timestamp <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE),
        ).order_by(WorkLog.timestamp).all()

        # Compute metrics
        metrics = compute_capacity_metrics(
            user_id=worker.id,
            username=worker.username,
            start_date=start_date,
            end_date=end_date,
            holidays=holidays,
            timeoffs=timeoffs,
            worklogs=worklogs,
            workday_hours=workday_hours,
            auto_timeout_minutes=auto_timeout,
        )

        total_available += metrics["available_hours"]
        total_actual += metrics["actual_work_hours"]

        worker_data.append({
            "작업자": metrics["username"],
            "근무일": metrics["total_workdays"],
            "휴무(h)": metrics["timeoff_hours"],
            "가용(h)": metrics["available_hours"],
            "실제(h)": metrics["actual_work_hours"],
            "가동률": f"{metrics['utilization_rate'] * 100:.1f}%",
        })

    render_styled_dataframe(pd.DataFrame(worker_data), key="team_capacity_grid", enable_selection=False, height=300, user_role="admin")

    # Team totals
    st.markdown("---")
    st.markdown("### 팀 합계")

    team_utilization = (total_actual / total_available * 100) if total_available > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("총 가용 시간", f"{total_available:.1f}h")
    with col2:
        st.metric("총 실제 시간", f"{total_actual:.1f}h")
    with col3:
        st.metric("팀 가동률", f"{team_utilization:.1f}%")


# ============== Worker TimeOff Section ==============
def show_worker_timeoff(db: Session, user: dict):
    """Show worker's own time-off management."""
    st.subheader("내 휴무")

    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_filter = st.date_input(
            "시작",
            value=date.today() - timedelta(days=30),
            key="my_timeoff_start"
        )
    with col2:
        end_filter = st.date_input(
            "종료",
            value=date.today() + timedelta(days=60),
            key="my_timeoff_end"
        )

    # Get my time-offs
    timeoffs = db.query(UserTimeOff).filter(
        UserTimeOff.user_id == user["id"],
        UserTimeOff.date >= start_filter,
        UserTimeOff.date <= end_filter
    ).order_by(UserTimeOff.date.desc()).all()

    st.markdown("---")

    # Register new time-off
    st.markdown("### 휴무 등록")

    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

    with col1:
        my_timeoff_start = st.date_input(
            "시작일",
            value=date.today(),
            key="my_timeoff_date_start"
        )

    with col2:
        my_timeoff_end = st.date_input(
            "종료일",
            value=date.today(),
            key="my_timeoff_date_end"
        )

    with col3:
        timeoff_type = st.selectbox(
            "유형",
            options=[t.value for t in TimeOffType],
            key="my_timeoff_type"
        )

    with col4:
        st.write("")
        st.write("")
        if st.button("추가", key="add_my_timeoff", type="primary"):
            if my_timeoff_start > my_timeoff_end:
                st.error("시작일이 종료일보다 앞서야 합니다")
            else:
                # Register time-off for each day in range
                current_date = my_timeoff_start
                added_count = 0
                skipped_dates = []

                while current_date <= my_timeoff_end:
                    # Check for duplicate
                    existing = db.query(UserTimeOff).filter(
                        UserTimeOff.user_id == user["id"],
                        UserTimeOff.date == current_date
                    ).first()

                    if existing:
                        skipped_dates.append(str(current_date))
                    else:
                        timeoff = UserTimeOff(
                            user_id=user["id"],
                            date=current_date,
                            type=TimeOffType(timeoff_type),
                        )
                        db.add(timeoff)
                        added_count += 1

                    current_date += timedelta(days=1)

                if added_count > 0:
                    db.commit()
                    st.success(f"{added_count}건 휴무 추가됨")
                    if skipped_dates:
                        st.warning(f"건너뜀 (이미 존재): {', '.join(skipped_dates)}")
                    st.rerun()
                elif skipped_dates:
                    st.error(f"모든 날짜에 이미 휴무가 등록되어 있습니다")

    st.markdown("---")

    # Display my time-offs
    if not timeoffs:
        st.info("선택한 기간에 등록된 휴무가 없습니다.")
        return

    # Group consecutive time-offs
    grouped = group_consecutive_timeoffs(timeoffs)

    # Display grouped table
    data = []
    for g in grouped:
        data.append({
            "기간": g["period"],
            "유형": g["type"].value,
            "일수/시간": f"{g['days_display']} ({g['hours']}h)",
        })

    render_styled_dataframe(pd.DataFrame(data), key="worker_timeoff_grid", enable_selection=False, height=250, user_role="worker")

    # Delete own time-off (only future)
    st.markdown("### 휴무 취소")

    # Filter groups to only future ones
    future_groups = [g for g in grouped if g["end_date"] >= date.today()]

    if future_groups:
        # Create delete options from groups
        delete_options = []
        for i, g in enumerate(future_groups):
            label = f"{g['period']} ({g['type'].value}, {g['days_display']})"
            delete_options.append((i, label, g["ids"]))

        selected_delete_idx = st.selectbox(
            "취소할 휴무 선택",
            options=range(len(delete_options)),
            format_func=lambda x: delete_options[x][1],
            key="delete_my_timeoff_group"
        )

        selected_ids = delete_options[selected_delete_idx][2]
        days_count = len(selected_ids)

        if days_count > 1:
            st.warning(f"{days_count}개의 연속 휴무가 취소됩니다.")

        if st.button("휴무 취소", key="delete_my_timeoff_btn"):
            for tid in selected_ids:
                timeoff = db.query(UserTimeOff).filter(UserTimeOff.id == tid).first()
                if timeoff:
                    db.delete(timeoff)
            db.commit()
            st.success(f"{days_count}건 휴무 취소됨")
            st.rerun()
    else:
        st.info("취소할 수 있는 미래 휴무가 없습니다.")


# ============== QC Status Section ==============
def show_qc_status(db: Session):
    """Show QC Status with sub-tabs (ADMIN only)."""
    st.subheader("QC 현황")

    qc_tab1, qc_tab2, qc_tab3 = st.tabs(["QC 요약", "불일치 분석", "QC 데이터 등록"])

    with qc_tab1:
        show_qc_summary(db)

    with qc_tab2:
        show_qc_disagreement_analysis(db)

    with qc_tab3:
        show_qc_data_upload(db)


def show_qc_summary(db: Session):
    """Show QC summary overview."""
    from models import PreQcSummary, AutoQcSummary

    # Get total cases
    total_cases = db.query(Case).count()

    # Get cases with Pre-QC
    cases_with_preqc = db.query(Case).join(PreQcSummary).count()

    # Get cases with Auto-QC
    cases_with_autoqc = db.query(Case).join(AutoQcSummary).count()

    # Auto-QC status breakdown (3단계)
    autoqc_pass = db.query(AutoQcSummary).filter(AutoQcSummary.status == "PASS").count()
    autoqc_warn = db.query(AutoQcSummary).filter(AutoQcSummary.status == "WARN").count()
    autoqc_incomplete = db.query(AutoQcSummary).filter(AutoQcSummary.status == "INCOMPLETE").count()

    # Summary metrics
    st.markdown("### 전체 QC 데이터 현황")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("전체 케이스", total_cases)
    with col2:
        preqc_rate = (cases_with_preqc / total_cases * 100) if total_cases > 0 else 0
        st.metric("Pre-QC 등록", f"{cases_with_preqc} ({preqc_rate:.1f}%)")
    with col3:
        autoqc_rate = (cases_with_autoqc / total_cases * 100) if total_cases > 0 else 0
        st.metric("Auto-QC 등록", f"{cases_with_autoqc} ({autoqc_rate:.1f}%)")

    # Auto-QC 상태별 현황
    st.markdown("### Auto-QC 상태별 현황")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pass_rate = (autoqc_pass / cases_with_autoqc * 100) if cases_with_autoqc > 0 else 0
        st.metric("✅ PASS", f"{autoqc_pass} ({pass_rate:.1f}%)")
    with col2:
        warn_rate = (autoqc_warn / cases_with_autoqc * 100) if cases_with_autoqc > 0 else 0
        st.metric("⚠️ WARN", f"{autoqc_warn} ({warn_rate:.1f}%)")
    with col3:
        incomplete_rate = (autoqc_incomplete / cases_with_autoqc * 100) if cases_with_autoqc > 0 else 0
        st.metric("❌ INCOMPLETE", f"{autoqc_incomplete} ({incomplete_rate:.1f}%)")
    with col4:
        pass_rate_total = (autoqc_pass / cases_with_autoqc * 100) if cases_with_autoqc > 0 else 0
        st.metric("PASS 비율", f"{pass_rate_total:.1f}%")

    st.markdown("---")

    # Recent QC data
    st.markdown("### 최근 QC 데이터")

    recent_preqc = (
        db.query(Case, PreQcSummary)
        .join(PreQcSummary)
        .order_by(PreQcSummary.created_at.desc())
        .limit(10)
        .all()
    )

    recent_autoqc = (
        db.query(Case, AutoQcSummary)
        .join(AutoQcSummary)
        .order_by(AutoQcSummary.created_at.desc())
        .limit(10)
        .all()
    )

    # Pre-QC 테이블 (전체 너비)
    st.markdown("**Pre-QC 목록**")
    if recent_preqc:
        preqc_data = []
        for case, preqc in recent_preqc:
            # 아이콘 매핑
            thickness_icon = {"OK": "✅", "WARN": "⚠️", "THICK": "❌"}.get(preqc.slice_thickness_flag, "-")
            noise_icon = {"LOW": "🟢", "MODERATE": "🟡", "HIGH": "🔴"}.get(preqc.noise_level, "-")
            contrast_icon = {"GOOD": "🟢", "BORDERLINE": "🟡", "POOR": "🔴"}.get(preqc.contrast_flag, "-")
            visibility_icon = {"EXCELLENT": "🟢", "USABLE": "🟢", "BORDERLINE": "🟡", "POOR": "🔴"}.get(preqc.vascular_visibility_level, "-")
            difficulty_icon = {"EASY": "🟢", "NORMAL": "🟡", "HARD": "🔴", "VERY_HARD": "🔴"}.get(preqc.difficulty, "-")

            preqc_data.append({
                "케이스 ID": case.case_uid,
                "슬라이스 수": preqc.slice_count or "-",
                "두께(mm)": f"{preqc.slice_thickness_mm:.1f}" if preqc.slice_thickness_mm else "-",
                "두께 상태": thickness_icon,
                "노이즈": f"{noise_icon} {preqc.noise_level}" if preqc.noise_level else "-",
                "조영제": f"{contrast_icon} {preqc.contrast_flag}" if preqc.contrast_flag else "-",
                "혈관 가시성": f"{visibility_icon} {preqc.vascular_visibility_level}" if preqc.vascular_visibility_level else "-",
                "난이도": f"{difficulty_icon} {preqc.difficulty}" if preqc.difficulty else "-",
                "등록일": preqc.created_at.strftime("%Y-%m-%d %H:%M") if preqc.created_at else "-",
            })
        render_styled_dataframe(pd.DataFrame(preqc_data), key="recent_preqc_grid", enable_selection=False, height=300, user_role="admin")
    else:
        st.info("Pre-QC 데이터가 없습니다.")

    st.markdown("---")

    # Auto-QC 테이블 (전체 너비)
    st.markdown("**Auto-QC 목록**")
    if recent_autoqc:
        autoqc_data = []
        for case, aqc in recent_autoqc:
            # 상태 아이콘
            status_icon = {"PASS": "✅", "WARN": "⚠️", "INCOMPLETE": "❌"}.get(aqc.status, "-")
            status_display = f"{status_icon} {aqc.status}" if aqc.status else "-"

            # 누락 세그먼트
            missing_segments = "-"
            if aqc.missing_segments_json:
                try:
                    missing_list = json.loads(aqc.missing_segments_json)
                    if missing_list:
                        missing_segments = ", ".join(missing_list)
                except json.JSONDecodeError:
                    pass

            # 이름 불일치 건수
            name_mismatch_count = "-"
            if aqc.name_mismatches_json:
                try:
                    mismatches = json.loads(aqc.name_mismatches_json)
                    if mismatches:
                        name_mismatch_count = str(len(mismatches))
                except json.JSONDecodeError:
                    pass

            # 이슈 카운트
            warn_count = 0
            incomplete_count = 0
            if aqc.issue_count_json:
                try:
                    counts = json.loads(aqc.issue_count_json)
                    warn_count = counts.get("warn_level", 0)
                    incomplete_count = counts.get("incomplete_level", 0)
                except json.JSONDecodeError:
                    pass
            current_issue_count = warn_count + incomplete_count

            # 재작업
            revision_display = str(aqc.revision) if hasattr(aqc, 'revision') and aqc.revision else "1"

            # 이전 대비 계산
            comparison_display = "-"
            if hasattr(aqc, 'revision') and aqc.revision and aqc.revision > 1:
                prev_count = aqc.previous_issue_count if hasattr(aqc, 'previous_issue_count') and aqc.previous_issue_count is not None else 0
                if current_issue_count < prev_count:
                    comparison_display = "✅ 개선"
                elif current_issue_count == prev_count:
                    comparison_display = "⚠️ 동일"
                else:
                    comparison_display = "❌ 악화"

            autoqc_data.append({
                "케이스 ID": case.case_uid,
                "상태": status_display,
                "누락 세그먼트": missing_segments,
                "이름 불일치": name_mismatch_count,
                "WARN 수": str(warn_count),
                "INCOMPLETE 수": str(incomplete_count),
                "재작업": revision_display,
                "이전 대비": comparison_display,
                "등록일": aqc.created_at.strftime("%Y-%m-%d %H:%M") if aqc.created_at else "-",
            })
        render_styled_dataframe(pd.DataFrame(autoqc_data), key="recent_autoqc_grid", enable_selection=False, height=300, user_role="admin")
    else:
        st.info("Auto-QC 데이터가 없습니다.")


def show_qc_data_upload(db: Session):
    """Show QC data upload interface."""
    st.markdown("### QC 데이터 일괄 등록")

    st.markdown("""
    로컬 PC에서 실행한 Pre-QC 또는 Auto-QC 결과를 CSV 파일로 업로드합니다.

    **주의**: QC는 로컬 PC에서만 실행되며, 서버는 결과 요약만 저장합니다.
    """)

    upload_tab1, upload_tab2 = st.tabs(["Pre-QC 업로드", "Auto-QC 업로드"])

    with upload_tab1:
        st.markdown("#### Pre-QC 데이터 업로드")

        st.markdown("""
        **CSV 형식** (필수 컬럼):
        - `case_uid`: 케이스 UID (필수)

        **선택 컬럼:**
        - `folder_path`: 폴더 경로
        - `slice_count`: 슬라이스 수
        - `spacing_json`: 스페이싱 JSON (예: `[0.5, 0.5, 1.0]`)
        - `volume_file`: 볼륨 파일명
        - `slice_thickness_mm`: 슬라이스 두께 (mm)
        - `slice_thickness_flag`: 두께 플래그 (OK/THIN/THICK)
        - `noise_sigma_mean`: 노이즈 시그마 평균
        - `noise_level`: 노이즈 레벨 (LOW/MEDIUM/HIGH)
        - `delta_hu`: 델타 HU
        - `contrast_flag`: 조영제 플래그 (ENHANCED/NON_ENHANCED/UNKNOWN)
        - `vessel_voxel_ratio`: 혈관 복셀 비율
        - `edge_strength`: 엣지 강도
        - `vascular_visibility_score`: 혈관 가시성 점수
        - `vascular_visibility_level`: 혈관 가시성 레벨 (EXCELLENT/USABLE/BORDERLINE/POOR)
        - `difficulty`: 난이도 (EASY/NORMAL/HARD/VERY_HARD)
        - `flags_json`: 플래그 JSON
        - `expected_segments_json`: 예상 세그먼트 JSON
        - `notes`: 메모
        """)

        # Download template
        preqc_template = pd.DataFrame({
            "case_uid": ["CASE_001", "CASE_002"],
            "folder_path": ["/data/case001", "/data/case002"],
            "slice_count": [100, 150],
            "spacing_json": ['[0.5, 0.5, 1.0]', '[0.7, 0.7, 2.0]'],
            "volume_file": ["volume.nrrd", "volume.nrrd"],
            "slice_thickness_mm": [1.0, 2.0],
            "slice_thickness_flag": ["OK", "THICK"],
            "noise_sigma_mean": [15.2, 22.5],
            "noise_level": ["LOW", "MEDIUM"],
            "delta_hu": [120.5, 85.3],
            "contrast_flag": ["ENHANCED", "NON_ENHANCED"],
            "vessel_voxel_ratio": [0.035, 0.028],
            "edge_strength": [0.85, 0.72],
            "vascular_visibility_score": [0.78, 0.65],
            "vascular_visibility_level": ["EXCELLENT", "USABLE"],
            "difficulty": ["NORMAL", "HARD"],
            "flags_json": ['["GOOD_QUALITY"]', '["NOISE_HIGH"]'],
            "expected_segments_json": ['["liver", "spleen"]', '["kidney"]'],
            "notes": ["", "혈관 가시성 낮음"],
        })

        st.download_button(
            "Pre-QC 템플릿 다운로드",
            preqc_template.to_csv(index=False).encode("utf-8-sig"),
            "preqc_template.csv",
            "text/csv",
            key="download_preqc_template"
        )

        preqc_file = st.file_uploader("Pre-QC CSV 파일 업로드", type=["csv"], key="preqc_upload")

        if preqc_file is not None:
            try:
                preqc_df = pd.read_csv(preqc_file)

                if "case_uid" not in preqc_df.columns:
                    st.error("case_uid 컬럼이 필요합니다.")
                else:
                    st.markdown(f"**{len(preqc_df)}건 데이터 미리보기:**")
                    render_table_df(preqc_df.head(10), max_rows=10)

                    if st.button("Pre-QC 데이터 저장", key="save_preqc"):
                        from models import PreQcSummary

                        created_count = 0
                        updated_count = 0
                        not_found = []

                        def safe_str(val):
                            """Convert value to string or None if empty/NaN."""
                            if pd.isna(val) or val == "" or val is None:
                                return None
                            return str(val).strip()

                        def safe_float(val):
                            """Convert value to float or None if empty/NaN."""
                            if pd.isna(val) or val == "" or val is None:
                                return None
                            try:
                                return float(val)
                            except (ValueError, TypeError):
                                return None

                        def safe_int(val):
                            """Convert value to int or None if empty/NaN."""
                            if pd.isna(val) or val == "" or val is None:
                                return None
                            try:
                                return int(float(val))
                            except (ValueError, TypeError):
                                return None

                        for _, row in preqc_df.iterrows():
                            case_uid = str(row["case_uid"]).strip()
                            case = db.query(Case).filter(Case.case_uid == case_uid).first()

                            if not case:
                                not_found.append(case_uid)
                                continue

                            # Check if PreQC already exists
                            existing = db.query(PreQcSummary).filter(PreQcSummary.case_id == case.id).first()

                            # Extract all fields
                            data = {
                                "folder_path": safe_str(row.get("folder_path")),
                                "slice_count": safe_int(row.get("slice_count")),
                                "spacing_json": safe_str(row.get("spacing_json")),
                                "volume_file": safe_str(row.get("volume_file")),
                                "slice_thickness_mm": safe_float(row.get("slice_thickness_mm")),
                                "slice_thickness_flag": safe_str(row.get("slice_thickness_flag")),
                                "noise_sigma_mean": safe_float(row.get("noise_sigma_mean")),
                                "noise_level": safe_str(row.get("noise_level")),
                                "delta_hu": safe_float(row.get("delta_hu")),
                                "contrast_flag": safe_str(row.get("contrast_flag")),
                                "vessel_voxel_ratio": safe_float(row.get("vessel_voxel_ratio")),
                                "edge_strength": safe_float(row.get("edge_strength")),
                                "vascular_visibility_score": safe_float(row.get("vascular_visibility_score")),
                                "vascular_visibility_level": safe_str(row.get("vascular_visibility_level")),
                                "difficulty": safe_str(row.get("difficulty")),
                                "flags_json": safe_str(row.get("flags_json")),
                                "expected_segments_json": safe_str(row.get("expected_segments_json")),
                                "notes": safe_str(row.get("notes")),
                            }

                            if existing:
                                for key, val in data.items():
                                    setattr(existing, key, val)
                                updated_count += 1
                            else:
                                preqc = PreQcSummary(case_id=case.id, **data)
                                db.add(preqc)
                                created_count += 1

                        db.commit()

                        st.success(f"Pre-QC 저장 완료: 신규 {created_count}건, 업데이트 {updated_count}건")
                        if not_found:
                            st.warning(f"찾을 수 없는 케이스: {', '.join(not_found[:10])}" + (f" 외 {len(not_found)-10}건" if len(not_found) > 10 else ""))

                        st.rerun()
            except Exception as e:
                st.error(f"파일 처리 오류: {e}")

    with upload_tab2:
        st.markdown("#### Auto-QC 데이터 업로드")

        st.markdown("""
        **CSV 형식** (필수 컬럼):
        - `case_uid`: 케이스 UID (필수)
        - `status`: QC 상태 (필수, PASS/WARN/INCOMPLETE)

        **선택 컬럼:**
        - `missing_segments_json`: 누락 세그먼트 JSON (예: `["liver", "portal_vein"]`)
        - `name_mismatches_json`: 이름 불일치 JSON (예: `[{"expected": "IVC", "found": "ivc", "type": "case_mismatch"}]`)
        - `extra_segments_json`: 추가 세그먼트 JSON
        - `issues_json`: 이슈 목록 JSON (예: `[{"level": "WARN", "message": "경고 내용"}]`)
        - `issue_count_json`: 이슈 수 JSON (예: `{"warn_level": 1, "incomplete_level": 0}`)
        - `geometry_mismatch`: 지오메트리 불일치 (true/false)
        - `warnings_json`: 경고 JSON (하위 호환)
        """)

        # Download template
        autoqc_template = pd.DataFrame({
            "case_uid": ["CASE_001", "CASE_002", "CASE_003"],
            "status": ["PASS", "WARN", "INCOMPLETE"],
            "missing_segments_json": ['', '["liver"]', '["portal_vein"]'],
            "name_mismatches_json": ['', '', '[{"expected": "IVC", "found": "ivc", "type": "case_mismatch"}]'],
            "extra_segments_json": ['', '', ''],
            "issues_json": ['', '[{"level": "WARN", "message": "경고 내용"}]', '[{"level": "INCOMPLETE", "message": "누락된 세그먼트"}]'],
            "issue_count_json": ['', '{"warn_level": 1, "incomplete_level": 0}', '{"warn_level": 0, "incomplete_level": 1}'],
            "geometry_mismatch": [False, True, False],
            "warnings_json": ['', '', ''],
        })

        st.download_button(
            "Auto-QC 템플릿 다운로드",
            autoqc_template.to_csv(index=False).encode("utf-8-sig"),
            "autoqc_template.csv",
            "text/csv",
            key="download_autoqc_template"
        )

        autoqc_file = st.file_uploader("Auto-QC CSV 파일 업로드", type=["csv"], key="autoqc_upload")

        if autoqc_file is not None:
            try:
                autoqc_df = pd.read_csv(autoqc_file)

                required_cols = ["case_uid", "status"]
                missing_cols = [c for c in required_cols if c not in autoqc_df.columns]

                if missing_cols:
                    st.error(f"필수 컬럼이 없습니다: {', '.join(missing_cols)}")
                else:
                    st.markdown(f"**{len(autoqc_df)}건 데이터 미리보기:**")
                    render_table_df(autoqc_df.head(10), max_rows=10)

                    if st.button("Auto-QC 데이터 저장", key="save_autoqc"):
                        from models import AutoQcSummary

                        created_count = 0
                        updated_count = 0
                        not_found = []
                        invalid_status = []

                        for _, row in autoqc_df.iterrows():
                            case_uid = str(row["case_uid"]).strip()
                            case = db.query(Case).filter(Case.case_uid == case_uid).first()

                            if not case:
                                not_found.append(case_uid)
                                continue

                            # Parse status (PASS/WARN/INCOMPLETE)
                            status_val = str(row["status"]).strip().upper()
                            if status_val not in ("PASS", "WARN", "INCOMPLETE"):
                                invalid_status.append(f"{case_uid}: {row['status']}")
                                continue

                            # Parse geometry_mismatch
                            geo_val = row.get("geometry_mismatch", False)
                            if pd.isna(geo_val):
                                geometry_mismatch = False
                            elif isinstance(geo_val, bool):
                                geometry_mismatch = geo_val
                            elif isinstance(geo_val, (int, float)):
                                geometry_mismatch = bool(geo_val)
                            else:
                                geometry_mismatch = str(geo_val).lower() in ("true", "1", "yes")

                            # Parse JSON fields
                            def get_json_field(field_name):
                                val = row.get(field_name)
                                if pd.isna(val) or not val or str(val).strip() == "":
                                    return None
                                return str(val).strip()

                            missing_segments_json = get_json_field("missing_segments_json")
                            name_mismatches_json = get_json_field("name_mismatches_json")
                            extra_segments_json = get_json_field("extra_segments_json")
                            issues_json = get_json_field("issues_json")
                            issue_count_json = get_json_field("issue_count_json")
                            warnings_json = get_json_field("warnings_json")

                            # Check if AutoQC already exists
                            existing = db.query(AutoQcSummary).filter(AutoQcSummary.case_id == case.id).first()

                            if existing:
                                existing.status = status_val
                                existing.missing_segments_json = missing_segments_json
                                existing.name_mismatches_json = name_mismatches_json
                                existing.extra_segments_json = extra_segments_json
                                existing.issues_json = issues_json
                                existing.issue_count_json = issue_count_json
                                existing.geometry_mismatch = geometry_mismatch
                                existing.warnings_json = warnings_json
                                updated_count += 1
                            else:
                                autoqc = AutoQcSummary(
                                    case_id=case.id,
                                    status=status_val,
                                    missing_segments_json=missing_segments_json,
                                    name_mismatches_json=name_mismatches_json,
                                    extra_segments_json=extra_segments_json,
                                    issues_json=issues_json,
                                    issue_count_json=issue_count_json,
                                    geometry_mismatch=geometry_mismatch,
                                    warnings_json=warnings_json,
                                )
                                db.add(autoqc)
                                created_count += 1

                        db.commit()

                        st.success(f"Auto-QC 저장 완료: 신규 {created_count}건, 업데이트 {updated_count}건")
                        if not_found:
                            st.warning(f"찾을 수 없는 케이스: {', '.join(not_found[:10])}" + (f" 외 {len(not_found)-10}건" if len(not_found) > 10 else ""))
                        if invalid_status:
                            st.warning(f"잘못된 status 값: {', '.join(invalid_status[:5])}" + (f" 외 {len(invalid_status)-5}건" if len(invalid_status) > 5 else ""))

                        st.rerun()
            except Exception as e:
                st.error(f"파일 처리 오류: {e}")


def _get_reviewer_disagreement_stats(db: Session, start_date=None, end_date=None):
    """
    검수자 기록 기반 불일치 통계를 계산하는 공통 함수.
    요약 섹션과 상세 섹션에서 동일한 기준으로 사용.

    Returns:
        dict: {
            "missed_count": int,
            "false_alarm_count": int,
            "total_count": int,
            "missed_records": list,
            "false_alarm_records": list,
            "segment_stats": dict,
        }
    """
    from sqlalchemy import and_

    # 기본 쿼리
    query = (
        db.query(ReviewerQcFeedback, Case)
        .join(Case, ReviewerQcFeedback.case_id == Case.id)
        .filter(ReviewerQcFeedback.has_disagreement == True)
    )

    # 날짜 필터 적용
    if start_date and end_date:
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE)
        query = query.filter(
            and_(
                ReviewerQcFeedback.created_at >= start_dt,
                ReviewerQcFeedback.created_at <= end_dt,
            )
        )

    reviewer_feedbacks = query.order_by(ReviewerQcFeedback.created_at.desc()).all()

    # 유형별 분류
    missed_records = []
    false_alarm_records = []
    segment_stats = {}  # 세그먼트별 통계

    for fb, case in reviewer_feedbacks:
        record = {
            "case_uid": case.case_uid,
            "detail": fb.disagreement_detail or "-",
            "segments": [],
            "reviewer": fb.reviewer.username if fb.reviewer else "-",
            "created_at": fb.created_at.strftime("%Y-%m-%d") if fb.created_at else "-",
        }
        if fb.disagreement_segments_json:
            try:
                record["segments"] = json.loads(fb.disagreement_segments_json)
            except json.JSONDecodeError:
                pass

        # 세그먼트별 통계 집계
        for seg in record["segments"]:
            if seg not in segment_stats:
                segment_stats[seg] = {"missed": 0, "false_alarm": 0}
            if fb.disagreement_type == "MISSED":
                segment_stats[seg]["missed"] += 1
            else:
                segment_stats[seg]["false_alarm"] += 1

        if fb.disagreement_type == "MISSED":
            missed_records.append(record)
        else:
            false_alarm_records.append(record)

    return {
        "missed_count": len(missed_records),
        "false_alarm_count": len(false_alarm_records),
        "total_count": len(missed_records) + len(false_alarm_records),
        "missed_records": missed_records,
        "false_alarm_records": false_alarm_records,
        "segment_stats": segment_stats,
    }


def show_qc_disagreement_analysis(db: Session):
    """Show QC disagreement analysis (ADMIN only)."""
    st.subheader("QC 불일치 분석")

    st.markdown("""
    **QC 불일치** = Auto-QC 결과와 검수자 판단이 다른 경우:
    - **놓친 문제**: Auto-QC가 통과시켰는데 검수자가 문제를 발견해서 재작업 요청
    - **잘못된 경고**: Auto-QC가 경고했는데 검수자가 확인 후 문제없어서 승인
    """)

    st.markdown("---")

    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "시작",
            value=date.today() - timedelta(days=90),
            key="qc_disagree_start"
        )
    with col2:
        end_date = st.date_input(
            "종료",
            value=date.today(),
            key="qc_disagree_end"
        )

    # 공통 집계 함수로 불일치 통계 조회 (요약과 상세가 동일 기준 사용)
    stats = _get_reviewer_disagreement_stats(db, start_date, end_date)

    # Summary metrics (검수자 기록 기반)
    st.markdown("### 요약")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("불일치 건수", stats["total_count"])
    with col2:
        st.metric("놓친 문제", stats["missed_count"])
    with col3:
        st.metric("잘못된 경고", stats["false_alarm_count"])

    # ====== 검수자 기록 불일치 상세 내용 ======
    st.markdown("---")
    st.markdown("### 검수자 기록 불일치 상세")

    # 공통 집계 함수에서 이미 조회한 데이터 재사용
    missed_records = stats["missed_records"]
    false_alarm_records = stats["false_alarm_records"]
    segment_stats = stats["segment_stats"]

    if stats["total_count"] == 0:
        st.info("선택한 기간에 검수자가 기록한 불일치 내용이 없습니다.")
    else:
        # ===== 놓친 문제 상세 테이블 =====
        st.markdown("#### 놓친 문제 상세")
        if missed_records:
            # 요약 테이블 (20자 제한)
            missed_data = []
            for r in missed_records:
                detail_text = r["detail"] if r["detail"] else "-"
                truncated = (detail_text[:20] + "...") if len(detail_text) > 20 else detail_text
                missed_data.append({
                    "케이스 ID": r["case_uid"],
                    "세그먼트": ", ".join(r["segments"]) if r["segments"] else "-",
                    "상세 내용": truncated,
                    "검수자": r["reviewer"],
                    "날짜": r["created_at"],
                })
            missed_df = pd.DataFrame(missed_data)
            render_table_df(missed_df, max_rows=10)

            # 상세 내용 expander
            st.markdown("##### 상세 내용 보기")
            for i, r in enumerate(missed_records):
                with st.expander(f"📋 {r['case_uid']} - {r['reviewer']} ({r['created_at']})"):
                    st.markdown(f"**케이스 ID:** {r['case_uid']}")
                    st.markdown(f"**검수자:** {r['reviewer']}")
                    st.markdown(f"**날짜:** {r['created_at']}")
                    st.markdown(f"**세그먼트:** {', '.join(r['segments']) if r['segments'] else '-'}")
                    st.markdown("**상세 내용:**")
                    detail_text = r["detail"] if r["detail"] else "-"
                    with st.container(border=True):
                        st.markdown(detail_text)
        else:
            st.caption("없음")

        # ===== 잘못된 경고 상세 테이블 =====
        st.markdown("#### 잘못된 경고 상세")
        if false_alarm_records:
            # 요약 테이블 (20자 제한)
            false_alarm_data = []
            for r in false_alarm_records:
                detail_text = r["detail"] if r["detail"] else "-"
                truncated = (detail_text[:20] + "...") if len(detail_text) > 20 else detail_text
                false_alarm_data.append({
                    "케이스 ID": r["case_uid"],
                    "세그먼트": ", ".join(r["segments"]) if r["segments"] else "-",
                    "상세 내용": truncated,
                    "검수자": r["reviewer"],
                    "날짜": r["created_at"],
                })
            false_alarm_df = pd.DataFrame(false_alarm_data)
            render_table_df(false_alarm_df, max_rows=10)

            # 상세 내용 expander
            st.markdown("##### 상세 내용 보기")
            for i, r in enumerate(false_alarm_records):
                with st.expander(f"📋 {r['case_uid']} - {r['reviewer']} ({r['created_at']})"):
                    st.markdown(f"**케이스 ID:** {r['case_uid']}")
                    st.markdown(f"**검수자:** {r['reviewer']}")
                    st.markdown(f"**날짜:** {r['created_at']}")
                    st.markdown(f"**세그먼트:** {', '.join(r['segments']) if r['segments'] else '-'}")
                    st.markdown("**상세 내용:**")
                    detail_text = r["detail"] if r["detail"] else "-"
                    with st.container(border=True):
                        st.markdown(detail_text)
        else:
            st.caption("없음")

        # ===== 세그먼트별 불일치 통계 테이블 =====
        st.markdown("#### 세그먼트별 불일치 통계")
        if segment_stats:
            segment_data = []
            for seg, stats in sorted(segment_stats.items()):
                total = stats["missed"] + stats["false_alarm"]
                segment_data.append({
                    "세그먼트": seg,
                    "놓친 문제": stats["missed"],
                    "잘못된 경고": stats["false_alarm"],
                    "총": total,
                })
            # 총 건수 기준 내림차순 정렬
            segment_data.sort(key=lambda x: x["총"], reverse=True)
            segment_df = pd.DataFrame(segment_data)
            render_table_df(segment_df, max_rows=10)
        else:
            st.caption("세그먼트 정보가 없습니다.")


# ============== Main ==============
def main():
    """Main entry point."""
    if st.session_state.user is None:
        show_login()
    else:
        role = st.session_state.user["role"]
        if role == "ADMIN":
            show_admin_dashboard()
        elif role == "WORKER":
            show_worker_dashboard()
        else:
            st.error("알 수 없는 역할")
            logout()


if __name__ == "__main__":
    main()
