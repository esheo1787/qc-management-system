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
    compute_timeline,
    compute_work_seconds,
    count_workdays,
    format_duration,
    get_timeline_dates,
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
Filter UI: TextInput / MultiSelect / Button 크기 통일 (38px)
========================================================= */

/* 공통 라벨 스타일 */
[data-testid="stTextInput"] label,
[data-testid="stMultiSelect"] label{
font-size: 14px !important;
font-weight: 400 !important;
}

/* TextInput: 컨테이너 및 입력창 */
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stTextInput"] [data-baseweb="base-input"]{
min-height: 38px !important;
}
[data-testid="stTextInput"] input{
height: 38px !important;
min-height: 38px !important;
padding: 0 12px !important;
font-size: 14px !important;
line-height: 38px !important;
}

/* MultiSelect: 컨테이너 */
[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div{
min-height: 38px !important;
}

/* MultiSelect: placeholder 및 입력 텍스트 */
[data-testid="stMultiSelect"] [data-baseweb="select"] input,
[data-testid="stMultiSelect"] [data-baseweb="select"] span,
[data-testid="stMultiSelect"] [data-baseweb="select"] div[aria-selected]{
font-size: 14px !important;
}

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

# 테이블 컬럼 라벨 (공통)
UI_LABELS = {
    "id": "번호",
    "case_uid": "케이스ID",
    "display_name": "이름",
    "project": "프로젝트",
    "part": "부위",
    "hospital": "병원",
    "status": "상태",
    "pause_reason": "중단 사유",
    "revision": "수정",
    "assignee": "담당자",
    "work_time": "작업 시간",
    "man_days": "작업일수(MD)",
    "created_at": "등록일",
    "difficulty": "난이도",
    "slice_thickness": "슬라이스 두께(mm)",
    "nas_path": "NAS 경로",
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
    height: int = 400,
    hide_columns: list = None,
    enable_selection: bool = True,
    show_toolbar: bool = True,
    pinnable_columns: list = None,
    user_role: str = None,
) -> dict:
    """
    AG Grid 기반 테이블 렌더링.
    - 컬럼/값 길이에 맞춰 자동 조절
    - 화면 크기에 반응 (flex)
    - 왼쪽 정렬
    - 메뉴/정렬 아이콘 제거
    - 툴바: CSV 내보내기, 컬럼 숨기기/고정

    Args:
        df: 데이터프레임
        key: 위젯 키
        height: 테이블 높이
        hide_columns: 숨길 컬럼 리스트 (코드에서 강제 숨김)
        enable_selection: 행 선택 활성화 여부
        show_toolbar: 툴바 표시 여부
        pinnable_columns: 고정 가능한 컬럼 리스트 (None이면 모든 컬럼)
        user_role: 사용자 역할 (admin/worker) - 설정 저장용

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
                    is_all_visible = len(current_visible) == len(all_columns) and set(current_visible) == set(all_columns)
                    # 체크박스가 session_state에 없을 때만 초기값 설정
                    if select_all_visible_key not in st.session_state:
                        st.session_state[select_all_visible_key] = is_all_visible
                    select_all_visible = st.checkbox(
                        "전체",
                        key=select_all_visible_key,
                    )
                # 체크박스 변경 시 전체 선택/해제
                if select_all_visible and not is_all_visible:
                    st.session_state[visible_key] = all_columns.copy()
                    st.rerun()
                elif not select_all_visible and is_all_visible:
                    st.session_state[visible_key] = []
                    st.rerun()

                visible_cols = st.multiselect(
                    "표시할 컬럼 (비어있으면 전체)",
                    options=all_columns,
                    default=st.session_state.get(visible_key, []),
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
                    is_all_pinned = len(current_pinned) == len(available_for_pin) and set(current_pinned) == set(available_for_pin)
                    # 체크박스가 session_state에 없을 때만 초기값 설정
                    if select_all_pinned_key not in st.session_state:
                        st.session_state[select_all_pinned_key] = is_all_pinned
                    select_all_pinned = st.checkbox(
                        "전체",
                        key=select_all_pinned_key,
                    )
                # 체크박스 변경 시 전체 선택/해제
                if select_all_pinned and not is_all_pinned:
                    st.session_state[pinned_key] = list(available_for_pin)
                    st.rerun()
                elif not select_all_pinned and is_all_pinned:
                    st.session_state[pinned_key] = []
                    st.rerun()

                available_for_pin = pinnable_columns if pinnable_columns else all_columns
                pinned_cols = st.multiselect(
                    "왼쪽 고정 컬럼",
                    options=available_for_pin,
                    default=st.session_state.get(pinned_key, []),
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

    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)

    grid_options = gb.build()

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
        height=height,
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
                assignee_options = sorted(df[UI_LABELS["assignee"]].dropna().unique().tolist())
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
    height: int = 400,
    enable_filter: bool = True,
) -> dict:
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return None

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

    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)

    grid_options = gb.build()

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
        height=height,
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
            UI_LABELS["work_time"]: format_duration(work_seconds),
            UI_LABELS["man_days"]: float(f"{compute_man_days(work_seconds, workday_hours):.2f}"),
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
    st.subheader(f"케이스 상세: {case.display_name}")

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

    st.markdown(f"**{icon} 상태:** {case.status.value}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**{UI_LABELS['project']}:** {case.project.name}")
        st.write(f"**{UI_LABELS['part']}:** {case.part.name}")
    with col2:
        st.write(f"**{UI_LABELS['hospital']}:** {case.hospital or UI_LABELS['unassigned']}")
        st.write(f"**{UI_LABELS['difficulty']}:** {case.difficulty.value}")
    with col3:
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
            # Get last pause reason
            last_pause_reason = None
            for wl in reversed(worklogs):
                if wl.action_type == ActionType.PAUSE and wl.reason_code:
                    last_pause_reason = wl.reason_code
                    break
            if last_pause_reason:
                st.warning(f"일시중지 | 누적: {work_duration} | 사유: {last_pause_reason}")
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

    if preqc or autoqc:
        st.markdown("---")
        st.markdown("### QC 정보")

        qc_col1, qc_col2 = st.columns(2)

        with qc_col1:
            if preqc:
                st.markdown("**Pre-QC 요약:**")
                st.write(f"- 슬라이스 수: {preqc.slice_count or 'N/A'}")

                # Parse and display flags
                if preqc.flags_json:
                    try:
                        flags = json.loads(preqc.flags_json)
                        if flags:
                            flags_str = ", ".join(flags) if isinstance(flags, list) else str(flags)
                            st.write(f"- 플래그: {flags_str}")
                    except json.JSONDecodeError:
                        st.write(f"- 플래그: {preqc.flags_json}")

                # Parse and display expected segments
                if preqc.expected_segments_json:
                    try:
                        segments = json.loads(preqc.expected_segments_json)
                        if segments:
                            st.write(f"- 예상 세그먼트: {', '.join(segments)}")
                    except json.JSONDecodeError:
                        st.write(f"- 예상 세그먼트: {preqc.expected_segments_json}")
            else:
                st.info("Pre-QC 데이터 없음")

        with qc_col2:
            if autoqc:
                st.markdown("**Auto-QC 요약:**")
                if autoqc.qc_pass:
                    st.success("QC 통과")
                else:
                    st.error("QC 실패")

                if autoqc.geometry_mismatch:
                    st.warning("지오메트리 불일치 감지됨")

                # Parse and display missing segments
                if autoqc.missing_segments_json:
                    try:
                        missing = json.loads(autoqc.missing_segments_json)
                        if missing:
                            st.write(f"- 누락된 세그먼트: {', '.join(missing)}")
                    except json.JSONDecodeError:
                        pass

                # Parse and display warnings
                if autoqc.warnings_json:
                    try:
                        warnings_list = json.loads(autoqc.warnings_json)
                        if warnings_list:
                            st.write("- 경고:")
                            for w in warnings_list[:5]:
                                st.caption(f"  - {w}")
                    except json.JSONDecodeError:
                        pass
            else:
                st.info("Auto-QC 데이터 없음")

        # ========== Worker QC 피드백 입력 (Submit 전 작성 가능) ==========
        # IN_PROGRESS 상태에서 Auto-QC가 있는 경우에만 표시
        if autoqc and case.status == CaseStatus.IN_PROGRESS:
            st.markdown("---")
            st.markdown("#### QC 피드백 작성")
            st.caption("Auto-QC 결과에 대한 피드백을 미리 작성할 수 있습니다. 제출 시 함께 저장됩니다.")

            qc_error_key = f"qc_error_pre_{case.id}"
            qc_text_key = f"qc_feedback_pre_{case.id}"

            # Initialize session state if needed
            if qc_error_key not in st.session_state:
                st.session_state[qc_error_key] = False
            if qc_text_key not in st.session_state:
                st.session_state[qc_text_key] = ""

            st.checkbox(
                "QC 결과 오류",
                help="Auto-QC 결과가 잘못된 경우 체크하세요",
                key=qc_error_key
            )
            st.text_area(
                "추가 수정 사항",
                placeholder="QC 오류 내용이나 추가 수정한 부분을 기록하세요\n예: hepatic_vein 실제로 있음, renal_artery 추가 수정",
                key=qc_text_key,
                height=80
            )

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
                    if st.button("예, 시작", key=f"confirm_yes_{case.id}", type="primary"):
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

                    # 미리 작성한 QC 피드백 표시
                    qc_error_key = f"qc_error_pre_{case.id}"
                    qc_text_key = f"qc_feedback_pre_{case.id}"
                    qc_feedback_error = st.session_state.get(qc_error_key, False)
                    qc_feedback_text = st.session_state.get(qc_text_key, "")

                    if autoqc and (qc_feedback_error or qc_feedback_text.strip()):
                        st.info("QC 피드백이 함께 저장됩니다")
                        if qc_feedback_error:
                            st.caption("- QC 결과 오류 표시됨")
                        if qc_feedback_text.strip():
                            st.caption(f"- 추가 수정 사항: {qc_feedback_text.strip()[:50]}...")

                    if st.button("예, 제출", key=f"confirm_yes_submit_{case.id}", type="primary"):
                        now = datetime.now(TIMEZONE)

                        # Save QC feedback if provided (from pre-filled fields)
                        if autoqc and (qc_feedback_error or qc_feedback_text.strip()):
                            feedback = WorkerQcFeedback(
                                case_id=case.id,
                                user_id=user["id"],
                                qc_result_error=qc_feedback_error,
                                feedback_text=qc_feedback_text.strip() if qc_feedback_text.strip() else None,
                                created_at=now,
                            )
                            db.add(feedback)

                        # Create WorkLog SUBMIT
                        worklog = WorkLog(
                            case_id=case.id,
                            user_id=user["id"],
                            action_type=ActionType.SUBMIT,
                            timestamp=now,
                        )
                        db.add(worklog)

                        # Create Event SUBMITTED
                        event = Event(
                            case_id=case.id,
                            user_id=user["id"],
                            event_type=EventType.SUBMITTED,
                            idempotency_key=generate_idempotency_key(case.id, "SUBMITTED"),
                            created_at=now,
                        )
                        db.add(event)

                        # Update case
                        case.status = CaseStatus.SUBMITTED
                        case.worker_completed_at = now

                        db.commit()
                        st.session_state[submit_key] = False

                        # Clear QC feedback session state
                        if qc_error_key in st.session_state:
                            del st.session_state[qc_error_key]
                        if qc_text_key in st.session_state:
                            del st.session_state[qc_text_key]

                        # Show final time
                        final_worklogs = db.query(WorkLog).filter(
                            WorkLog.case_id == case.id
                        ).order_by(WorkLog.timestamp).all()
                        final_seconds = compute_work_seconds(final_worklogs, auto_timeout)
                        final_duration = format_duration(final_seconds)
                        final_md = compute_man_days(final_seconds, workday_hours)

                        st.success(f"제출 완료! 총 작업시간: {final_duration} ({final_md:.2f} MD)")
                        st.rerun()
                    if st.button("제출 취소", key=f"cancel_submit_{case.id}"):
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
        "휴무 관리", "공휴일", "가용량", "QC 불일치"
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
            show_capacity_metrics(db)

        with tab9:
            show_qc_disagreements(db)
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
            display_name = st.text_input(
                "표시 이름 *",
                placeholder="예: Patient F - Liver CT",
                help="케이스 표시용 이름"
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
                index=1  # Default: MID
            )
            slice_thickness = st.number_input(
                "슬라이스 두께 (mm)",
                min_value=0.0,
                max_value=10.0,
                value=1.0,
                step=0.1,
                help="선택사항"
            )
            nas_path = st.text_input(
                "NAS 경로",
                placeholder="예: /data/cases/CASE-006",
                help="원본 데이터 경로 (선택사항)"
            )

        submitted = st.form_submit_button("케이스 등록", type="primary")

        if submitted:
            # Validation
            if not case_uid or not case_uid.strip():
                st.error("케이스 ID를 입력하세요.")
                return
            if not display_name or not display_name.strip():
                st.error("표시 이름을 입력하세요.")
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
            new_case = Case(
                case_uid=case_uid.strip(),
                display_name=display_name.strip(),
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
                UI_LABELS["display_name"]: c.display_name,
                UI_LABELS["project"]: c.project.name,
                UI_LABELS["part"]: c.part.name,
                UI_LABELS["hospital"]: c.hospital or UI_LABELS["unassigned"],
                UI_LABELS["slice_thickness"]: c.slice_thickness_mm if c.slice_thickness_mm else "-",
                UI_LABELS["nas_path"]: c.nas_path if c.nas_path else "-",
                UI_LABELS["difficulty"]: c.difficulty.value,
                UI_LABELS["status"]: c.status.value,
                UI_LABELS["created_at"]: c.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        render_styled_dataframe(pd.DataFrame(data), key="recent_cases_grid", enable_selection=False, height=300, user_role="admin")
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
            qc_icon = "✅" if autoqc.qc_pass else "❌"
        else:
            qc_icon = "⚪"

        with st.expander(
            f"{qc_icon} {case.display_name} ({case.case_uid}) - {UI_LABELS['revision']} {case.revision}",
            expanded=False
        ):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**{UI_LABELS['project']}:** {case.project.name}")
                st.write(f"**{UI_LABELS['part']}:** {case.part.name}")
                st.write(f"**{UI_LABELS['assignee']}:** {case.assigned_user.username if case.assigned_user else UI_LABELS['unassigned']}")
            with col2:
                st.write(f"**{UI_LABELS['hospital']}:** {case.hospital or UI_LABELS['unassigned']}")
                st.write(f"**{UI_LABELS['difficulty']}:** {case.difficulty.value}")
            with col3:
                if case.started_at:
                    st.write(f"**시작일:** {case.started_at.strftime('%Y-%m-%d %H:%M')}")
                if case.worker_completed_at:
                    st.write(f"**제출일:** {case.worker_completed_at.strftime('%Y-%m-%d %H:%M')}")

            # AutoQC Summary display
            if autoqc:
                st.markdown("---")
                st.markdown("**Auto-QC 요약:**")

                qc_col1, qc_col2 = st.columns(2)
                with qc_col1:
                    if autoqc.qc_pass:
                        st.success("QC 통과")
                    else:
                        st.error("QC 실패")

                    if autoqc.geometry_mismatch:
                        st.warning("지오메트리 불일치 감지됨")

                with qc_col2:
                    # Parse and display missing segments
                    if autoqc.missing_segments_json:
                        try:
                            missing = json.loads(autoqc.missing_segments_json)
                            if missing:
                                st.write(f"**누락된 세그먼트:** {', '.join(missing)}")
                        except json.JSONDecodeError:
                            pass

                    # Parse and display warnings
                    if autoqc.warnings_json:
                        try:
                            warnings = json.loads(autoqc.warnings_json)
                            if warnings:
                                st.write("**경고:**")
                                for w in warnings[:5]:  # Limit to 5
                                    st.caption(f"- {w}")
                        except json.JSONDecodeError:
                            pass

                st.caption(f"Auto-QC 실행 시간: {autoqc.created_at.strftime('%Y-%m-%d %H:%M')}")

                # Worker QC Feedback 표시
                worker_feedbacks = db.query(WorkerQcFeedback).filter(
                    WorkerQcFeedback.case_id == case.id
                ).order_by(WorkerQcFeedback.created_at.desc()).all()

                if worker_feedbacks:
                    st.markdown("---")
                    st.markdown("**작업자 QC 피드백:**")
                    for fb in worker_feedbacks:
                        fb_icon = "⚠️" if fb.qc_result_error else "📝"
                        error_str = " [QC 결과 오류 신고]" if fb.qc_result_error else ""
                        st.write(f"{fb_icon} {fb.user.username}{error_str}")
                        if fb.feedback_text:
                            st.caption(f"   → {fb.feedback_text}")
                        st.caption(f"   {fb.created_at.strftime('%Y-%m-%d %H:%M')}")
            else:
                st.markdown("---")
                st.info("이 케이스에는 Auto-QC 요약이 없습니다.")

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

                            event = Event(
                                case_id=case.id,
                                user_id=user["id"],
                                event_type=EventType.ACCEPTED,
                                idempotency_key=generate_idempotency_key(case.id, "ACCEPTED"),
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

                    # QC summary confirmed checkbox (only if AutoQC exists)
                    rework_qc_confirmed = False
                    if autoqc:
                        rework_qc_confirmed = st.checkbox(
                            "Auto-QC 결과 정확성 확인",
                            key=f"rework_qc_confirm_{case.id}"
                        )

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
                                    qc_summary_confirmed=rework_qc_confirmed,
                                    extra_tags_json=tags_json,
                                    created_at=now,
                                )
                                db.add(note)

                                # Create REWORK event
                                event = Event(
                                    case_id=case.id,
                                    user_id=user["id"],
                                    event_type=EventType.REWORK_REQUESTED,
                                    idempotency_key=generate_idempotency_key(case.id, "REWORK_REQUESTED"),
                                    payload_json=json.dumps({"reason": reason.strip()}),
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

        row = {
            UI_LABELS["id"]: c.id,
            UI_LABELS["case_uid"]: c.case_uid,
            UI_LABELS["display_name"]: c.display_name,
            UI_LABELS["project"]: c.project.name,
            UI_LABELS["part"]: c.part.name,
            UI_LABELS["hospital"]: c.hospital or UI_LABELS["unassigned"],
            UI_LABELS["slice_thickness"]: c.slice_thickness_mm if c.slice_thickness_mm else "-",
            UI_LABELS["nas_path"]: c.nas_path if c.nas_path else "-",
            UI_LABELS["status"]: status_display,
            UI_LABELS["difficulty"]: c.difficulty.value,
            UI_LABELS["pause_reason"]: pause_reason if pause_reason else "-",
            UI_LABELS["revision"]: c.revision,
            UI_LABELS["assignee"]: c.assigned_user.username if c.assigned_user else "-",
            UI_LABELS["work_time"]: format_duration(work_seconds),
            UI_LABELS["man_days"]: float(f"{compute_man_days(work_seconds, workday_hours):.2f}"),
            UI_LABELS["created_at"]: c.created_at.strftime("%Y-%m-%d"),
        }
        data.append(row)
        case_map[c.id] = c

    df = pd.DataFrame(data)

    # 필터 UI + DataFrame 필터링
    filtered_df = render_case_filters(df, "all_cases", show_assignee=True)

    # 공통 AG Grid 렌더링
    grid_response = render_styled_dataframe(
        filtered_df,
        key="all_cases_grid",
        height=450,
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

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**{UI_LABELS['case_uid']}:** {case.case_uid}")
        st.write(f"**{UI_LABELS['display_name']}:** {case.display_name}")
        st.write(f"**{UI_LABELS['status']}:** {case.status.value}")
        st.write(f"**{UI_LABELS['revision']}:** {case.revision}")
        st.write(f"**{UI_LABELS['project']}:** {case.project.name}")
        st.write(f"**{UI_LABELS['part']}:** {case.part.name}")

    with col2:
        st.write(f"**{UI_LABELS['hospital']}:** {case.hospital or UI_LABELS['unassigned']}")
        st.write(f"**{UI_LABELS['difficulty']}:** {case.difficulty.value}")
        st.write(f"**{UI_LABELS['assignee']}:** {case.assigned_user.username if case.assigned_user else UI_LABELS['unassigned']}")

    # Metrics
    st.markdown("---")
    st.markdown("**작업 지표:**")
    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric(UI_LABELS["work_time"], format_duration(work_seconds))
    with metric_cols[1]:
        st.metric(UI_LABELS["man_days"], f"{compute_man_days(work_seconds, workday_hours):.2f}")
    with metric_cols[2]:
        st.metric("소요 일수", compute_timeline(first_start, last_end))

    # WorkLog timeline
    if worklogs:
        st.markdown("**작업 기록:**")
        for wl in worklogs:
            reason_str = f" ({wl.reason_code})" if wl.reason_code else ""
            st.write(f"- {wl.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | {wl.action_type.value}{reason_str} | {wl.user.username}")

    # Events
    if case.events:
        st.markdown("**이벤트 이력:**")
        for e in case.events:
            st.write(f"- {e.created_at.strftime('%Y-%m-%d %H:%M:%S')} | {e.event_type.value} | {e.user.username}")

    # Review Notes
    if case.review_notes:
        st.markdown("**검수 메모:**")
        for n in case.review_notes:
            st.write(f"- {n.created_at.strftime('%Y-%m-%d %H:%M')} | {n.reviewer.username}: {n.note_text}")


def show_assign_cases(db: Session):
    """Show case assignment interface."""
    st.subheader("케이스 배정")

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
                case.assigned_user_id = worker_options[selected_worker]
                db.commit()
                st.success(f"{selected_worker}에게 배정되었습니다")
                st.rerun()

        st.markdown("---")


def show_event_log(db: Session):
    """Show recent event log."""
    st.subheader("최근 이벤트")

    events = db.query(Event).order_by(Event.created_at.desc()).limit(50).all()

    if not events:
        st.info("이벤트가 없습니다.")
        return

    data = []
    for e in events:
        case = db.query(Case).filter(Case.id == e.case_id).first()
        data.append({
            "시간": e.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "이벤트": e.event_type.value,
            "케이스": case.case_uid if case else "?",
            "사용자": e.user.username,
            "코드": e.event_code or "-",
        })

    render_styled_dataframe(pd.DataFrame(data), key="recent_events_grid", enable_selection=False, height=300, user_role="admin")


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

    # Add holiday
    st.markdown("### 공휴일 추가")

    col1, col2 = st.columns([3, 1])

    with col1:
        new_holiday = st.date_input(
            "날짜",
            value=date.today(),
            key="new_holiday_date"
        )

    with col2:
        st.write("")
        st.write("")
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

            render_styled_dataframe(pd.DataFrame(data), key=f"holidays_{year}_grid", enable_selection=False, height=250, user_role="admin")

    # Delete holiday
    st.markdown("---")
    st.markdown("### 공휴일 삭제")

    delete_holiday = st.date_input(
        "삭제할 날짜 선택",
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


def show_capacity_metrics(db: Session):
    """Show team capacity metrics."""
    st.subheader("팀 가용량 지표")

    # Get configs
    workday_hours = get_config_value(db, "workday_hours", 8)
    auto_timeout = get_config_value(db, "auto_timeout_minutes", 120)

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

    # Get all workers
    workers = db.query(User).filter(
        User.role == UserRole.WORKER,
        User.is_active == True
    ).all()

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


# ============== QC Disagreements Section ==============
def show_qc_disagreements(db: Session):
    """Show QC disagreement analysis (ADMIN only)."""
    st.subheader("QC 불일치 분석")

    st.markdown("""
    **QC 불일치** = Auto-QC 결과와 검수자 판단이 다른 경우:
    - **위양성(FP)**: Auto-QC 통과 → 검수자가 재작업 요청
    - **위음성(FN)**: Auto-QC 실패 → 검수자가 승인
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

    # Get all cases with AutoQC summary in date range
    from sqlalchemy import and_, or_

    # Get cases with AutoQC that have been reviewed (accepted or rework)
    cases_with_autoqc = (
        db.query(Case, AutoQcSummary)
        .join(AutoQcSummary, Case.id == AutoQcSummary.case_id)
        .filter(
            Case.status.in_([CaseStatus.ACCEPTED, CaseStatus.REWORK]),
            or_(
                and_(Case.accepted_at.isnot(None),
                     Case.accepted_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE)),
                and_(Case.status == CaseStatus.REWORK)
            )
        )
        .all()
    )

    if not cases_with_autoqc:
        st.info("선택한 기간에 Auto-QC 데이터가 있는 검수 완료 케이스가 없습니다.")
        return

    # Calculate disagreements
    disagreements = []
    false_positives = 0
    false_negatives = 0
    total_with_autoqc = len(cases_with_autoqc)

    # Stats by category
    stats_by_part = {}
    stats_by_hospital = {}
    stats_by_difficulty = {}

    for case, autoqc in cases_with_autoqc:
        part_name = case.part.name
        hospital = case.hospital or "Unknown"
        difficulty = case.difficulty.value

        # Initialize stats
        for stat_dict, key in [(stats_by_part, part_name), (stats_by_hospital, hospital), (stats_by_difficulty, difficulty)]:
            if key not in stat_dict:
                stat_dict[key] = {"total": 0, "disagreements": 0}
            stat_dict[key]["total"] += 1

        # Check for rework event (to determine if rework was requested after autoqc pass)
        rework_event = (
            db.query(Event)
            .filter(Event.case_id == case.id, Event.event_type == EventType.REWORK_REQUESTED)
            .order_by(Event.created_at.desc())
            .first()
        )

        is_disagreement = False
        disagreement_type = None

        if autoqc.qc_pass and rework_event:
            # False Positive: AutoQC passed but rework was requested
            is_disagreement = True
            disagreement_type = "FALSE_POSITIVE"
            false_positives += 1
        elif not autoqc.qc_pass and case.status == CaseStatus.ACCEPTED:
            # False Negative: AutoQC failed but case was accepted
            is_disagreement = True
            disagreement_type = "FALSE_NEGATIVE"
            false_negatives += 1

        if is_disagreement:
            disagreements.append({
                "case_id": case.id,
                "case_uid": case.case_uid,
                "display_name": case.display_name,
                "hospital": hospital,
                "part_name": part_name,
                "difficulty": difficulty,
                "autoqc_pass": autoqc.qc_pass,
                "case_status": case.status.value,
                "disagreement_type": disagreement_type,
                "accepted_at": case.accepted_at,
                "rework_at": rework_event.created_at if rework_event else None,
            })

            # Update disagreement stats
            for stat_dict, key in [(stats_by_part, part_name), (stats_by_hospital, hospital), (stats_by_difficulty, difficulty)]:
                stat_dict[key]["disagreements"] += 1

    # Summary metrics
    st.markdown("### 요약")

    total_disagreements = len(disagreements)
    disagreement_rate = (total_disagreements / total_with_autoqc * 100) if total_with_autoqc > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("AutoQC 케이스 수", total_with_autoqc)
    with col2:
        st.metric("불일치 건수", total_disagreements)
    with col3:
        st.metric("불일치율", f"{disagreement_rate:.1f}%")
    with col4:
        fp_fn_ratio = f"{false_positives}:{false_negatives}"
        st.metric("FP : FN", fp_fn_ratio)

    st.markdown("---")

    # Distribution charts (using Streamlit basic charts)
    st.markdown("### 불일치 분포")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        # By disagreement type
        if total_disagreements > 0:
            st.markdown("**유형별**")
            type_data = {
                "Type": ["False Positive", "False Negative"],
                "Count": [false_positives, false_negatives],
            }
            st.bar_chart(data={"위양성(FP)": false_positives, "위음성(FN)": false_negatives})

    with chart_col2:
        # By difficulty
        if stats_by_difficulty:
            st.markdown("**난이도별**")
            diff_chart_data = {}
            for diff, stats in stats_by_difficulty.items():
                if stats["disagreements"] > 0:
                    diff_chart_data[diff] = stats["disagreements"]
            if diff_chart_data:
                st.bar_chart(diff_chart_data)

    # By Part chart
    st.markdown("**부위별 (불일치율)**")
    part_rate_data = []
    for part, stats in sorted(stats_by_part.items()):
        rate = (stats["disagreements"] / stats["total"] * 100) if stats["total"] > 0 else 0
        part_rate_data.append({
            "부위": part,
            "불일치율 (%)": rate,
            "불일치": stats["disagreements"],
            "전체": stats["total"],
        })

    if part_rate_data:
        render_styled_dataframe(pd.DataFrame(part_rate_data), key="qc_part_rate_grid", enable_selection=False, height=200, user_role="admin")

    # By Hospital chart
    st.markdown("**병원별 (불일치율)**")
    hospital_rate_data = []
    for hosp, stats in sorted(stats_by_hospital.items()):
        rate = (stats["disagreements"] / stats["total"] * 100) if stats["total"] > 0 else 0
        hospital_rate_data.append({
            "병원": hosp,
            "불일치율 (%)": rate,
            "불일치": stats["disagreements"],
            "전체": stats["total"],
        })

    if hospital_rate_data:
        render_styled_dataframe(pd.DataFrame(hospital_rate_data), key="qc_hospital_rate_grid", enable_selection=False, height=200, user_role="admin")

    st.markdown("---")

    # Disagreement list
    st.markdown("### 불일치 목록")

    if not disagreements:
        st.success("선택한 기간에 QC 불일치가 없습니다.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            type_filter = st.selectbox(
                "유형",
                options=["전체", "FALSE_POSITIVE", "FALSE_NEGATIVE"],
                key="disagree_type_filter"
            )
        with col2:
            part_options = ["전체"] + sorted(set(d["part_name"] for d in disagreements))
            part_filter = st.selectbox("부위", options=part_options, key="disagree_part_filter")
        with col3:
            hosp_options = ["전체"] + sorted(set(d["hospital"] for d in disagreements))
            hospital_filter = st.selectbox("병원", options=hosp_options, key="disagree_hosp_filter")

        # Apply filters
        filtered = disagreements
        if type_filter != "전체":
            filtered = [d for d in filtered if d["disagreement_type"] == type_filter]
        if part_filter != "전체":
            filtered = [d for d in filtered if d["part_name"] == part_filter]
        if hospital_filter != "전체":
            filtered = [d for d in filtered if d["hospital"] == hospital_filter]

        # Display table
        display_data = []
        for d in filtered:
            display_data.append({
                "케이스 UID": d["case_uid"],
                "이름": d["display_name"][:30],
                "부위": d["part_name"],
                "병원": d["hospital"][:20] if d["hospital"] else "-",
                "난이도": d["difficulty"],
                "AutoQC": "통과" if d["autoqc_pass"] else "실패",
                "상태": d["case_status"],
                "유형": d["disagreement_type"],
            })

        render_styled_dataframe(pd.DataFrame(display_data), key="qc_disagreement_grid", enable_selection=False, height=350, user_role="admin")

        st.caption(f"{len(disagreements)}건 중 {len(filtered)}건 표시")


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
