import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta
import requests
from fredapi import Fred
import warnings
warnings.filterwarnings('ignore')

# 페이지 설정
st.set_page_config(
    page_title="🚨 경제 위기 시그널 체크",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일링
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 1rem 0;
    }
    .alert-danger {
        background-color: #ffebee;
        border-left: 5px solid #f44336;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .alert-warning {
        background-color: #fff3e0;
        border-left: 5px solid #ff9800;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .alert-success {
        background-color: #e8f5e8;
        border-left: 5px solid #4caf50;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# FRED API 키 설정 (사용자가 입력하도록)
st.sidebar.title("⚙️ 설정")
fred_api_key = st.sidebar.text_input("FRED API Key", type="cf41351b81f43ad46071e4aa487f40c8", 
                                    help="https://fred.stlouisfed.org/docs/api/api_key.html 에서 무료로 발급받으세요")

# 메인 헤더
st.markdown('<h1 class="main-header">🚨 경제 위기 시그널 체크 대시보드</h1>', unsafe_allow_html=True)

if not fred_api_key:
    st.warning("FRED API 키를 입력해주세요. https://fred.stlouisfed.org/docs/api/api_key.html 에서 무료로 발급받을 수 있습니다.")
    st.stop()

# FRED API 초기화
fred = Fred(api_key=fred_api_key)

@st.cache_data(ttl=3600)  # 1시간 캐시
def get_sofr_data():
    """SOFR 데이터 가져오기"""
    try:
        sofr = fred.get_series('SOFR', start='2020-01-01')
        return sofr.dropna()
    except Exception as e:
        st.error(f"SOFR 데이터 로드 실패: {e}")
        return None

@st.cache_data(ttl=3600)
def get_pmi_data():
    """PMI 데이터 가져오기"""
    try:
        # ISM Manufacturing PMI
        pmi = fred.get_series('MANEMP', start='2020-01-01')  # ISM Manufacturing: Employment Index
        # 실제 PMI 데이터를 위해 다른 소스를 사용할 수도 있습니다
        return pmi.dropna()
    except Exception as e:
        st.error(f"PMI 데이터 로드 실패: {e}")
        return None

@st.cache_data(ttl=3600)
def get_yield_curve_data():
    """수익률 곡선 데이터 가져오기"""
    try:
        # 10년물 - 2년물 스프레드
        ten_year = fred.get_series('GS10', start='2020-01-01')
        two_year = fred.get_series('GS2', start='2020-01-01')
        
        # 공통 인덱스로 정렬
        yield_spread = ten_year - two_year
        return yield_spread.dropna()
    except Exception as e:
        st.error(f"수익률 곡선 데이터 로드 실패: {e}")
        return None

def analyze_sofr_signal(sofr_data):
    """SOFR 위기 시그널 분석"""
    if sofr_data is None or len(sofr_data) < 2:
        return None, None
    
    current_rate = sofr_data.iloc[-1]
    previous_rate = sofr_data.iloc[-2]
    daily_change = current_rate - previous_rate
    
    # 최근 30일 평균과 비교
    recent_avg = sofr_data.tail(30).mean()
    deviation_from_avg = current_rate - recent_avg
    
    signal = "정상"
    if daily_change >= 1.0:
        signal = "심각한 위기"
    elif daily_change >= 0.2:
        signal = "초기 경고"
    elif deviation_from_avg >= 0.5:
        signal = "주의 필요"
    
    return {
        'current_rate': current_rate,
        'daily_change': daily_change,
        'deviation_from_avg': deviation_from_avg,
        'signal': signal
    }, sofr_data

def analyze_pmi_signal(pmi_data):
    """PMI 위기 시그널 분석"""
    if pmi_data is None or len(pmi_data) < 3:
        return None, None
    
    current_pmi = pmi_data.iloc[-1]
    recent_3_months = pmi_data.tail(3)
    
    signal = "정상"
    if current_pmi < 45:
        if all(recent_3_months < 45):
            signal = "경제위기 현실화"
        else:
            signal = "경고"
    elif current_pmi < 50:
        signal = "주의"
    
    return {
        'current_pmi': current_pmi,
        'recent_3_months_avg': recent_3_months.mean(),
        'signal': signal
    }, pmi_data

def analyze_yield_curve_signal(yield_data):
    """일드커브 위기 시그널 분석"""
    if yield_data is None or len(yield_data) < 30:
        return None, None
    
    current_spread = yield_data.iloc[-1]
    recent_30_days = yield_data.tail(30)
    change_30_days = current_spread - yield_data.iloc[-30]
    
    signal = "정상"
    is_inverted = current_spread < 0
    rapid_normalization = False
    
    if is_inverted:
        signal = "일드커브 역전 (경기침체 예고)"
    elif change_30_days > 0.5 and yield_data.iloc[-30] < 0:
        # 역전 상태에서 빠른 정상화
        signal = "경기침체 임박 (급격한 정상화)"
        rapid_normalization = True
    
    return {
        'current_spread': current_spread,
        'change_30_days': change_30_days,
        'is_inverted': is_inverted,
        'rapid_normalization': rapid_normalization,
        'signal': signal
    }, yield_data

# 데이터 로드
with st.spinner("데이터를 로드하는 중..."):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📊 SOFR 단기자금시장 금리")
        sofr_analysis, sofr_data = analyze_sofr_signal(get_sofr_data())
        
        if sofr_analysis:
            # 시그널에 따른 색상 설정
            if sofr_analysis['signal'] == "심각한 위기":
                alert_class = "alert-danger"
                color = "red"
            elif sofr_analysis['signal'] in ["초기 경고", "주의 필요"]:
                alert_class = "alert-warning"
                color = "orange"
            else:
                alert_class = "alert-success"
                color = "green"
            
            st.markdown(f'<div class="{alert_class}"><strong>현재 상태: {sofr_analysis["signal"]}</strong></div>', 
                       unsafe_allow_html=True)
            
            st.metric("현재 SOFR 금리", f"{sofr_analysis['current_rate']:.2f}%", 
                     f"{sofr_analysis['daily_change']:+.2f}%")
            st.metric("30일 평균 대비", f"{sofr_analysis['deviation_from_avg']:+.2f}%p")
            
            # SOFR 차트
            fig_sofr = go.Figure()
            fig_sofr.add_trace(go.Scatter(
                x=sofr_data.index, 
                y=sofr_data.values,
                mode='lines',
                name='SOFR',
                line=dict(color='blue', width=2)
            ))
            fig_sofr.update_layout(
                title="SOFR 금리 추이",
                xaxis_title="날짜",
                yaxis_title="금리 (%)",
                height=300
            )
            st.plotly_chart(fig_sofr, use_container_width=True)
    
    with col2:
        st.subheader("🏭 제조업 PMI")
        pmi_analysis, pmi_data = analyze_pmi_signal(get_pmi_data())
        
        if pmi_analysis:
            if pmi_analysis['signal'] == "경제위기 현실화":
                alert_class = "alert-danger"
            elif pmi_analysis['signal'] in ["경고", "주의"]:
                alert_class = "alert-warning"
            else:
                alert_class = "alert-success"
            
            st.markdown(f'<div class="{alert_class}"><strong>현재 상태: {pmi_analysis["signal"]}</strong></div>', 
                       unsafe_allow_html=True)
            
            st.metric("현재 PMI", f"{pmi_analysis['current_pmi']:.1f}")
            st.metric("최근 3개월 평균", f"{pmi_analysis['recent_3_months_avg']:.1f}")
            
            # PMI 차트
            fig_pmi = go.Figure()
            fig_pmi.add_trace(go.Scatter(
                x=pmi_data.index, 
                y=pmi_data.values,
                mode='lines',
                name='PMI',
                line=dict(color='green', width=2)
            ))
            fig_pmi.add_hline(y=50, line_dash="dash", line_color="black", 
                            annotation_text="기준선 (50)")
            fig_pmi.add_hline(y=45, line_dash="dash", line_color="red", 
                            annotation_text="위기선 (45)")
            fig_pmi.update_layout(
                title="제조업 PMI 추이",
                xaxis_title="날짜",
                yaxis_title="PMI",
                height=300
            )
            st.plotly_chart(fig_pmi, use_container_width=True)
    
    with col3:
        st.subheader("📈 일드커브 (10Y-2Y)")
        yield_analysis, yield_data = analyze_yield_curve_signal(get_yield_curve_data())
        
        if yield_analysis:
            if yield_analysis['signal'] == "경기침체 임박 (급격한 정상화)":
                alert_class = "alert-danger"
            elif "역전" in yield_analysis['signal']:
                alert_class = "alert-warning"
            else:
                alert_class = "alert-success"
            
            st.markdown(f'<div class="{alert_class}"><strong>현재 상태: {yield_analysis["signal"]}</strong></div>', 
                       unsafe_allow_html=True)
            
            st.metric("현재 스프레드", f"{yield_analysis['current_spread']:.2f}%p", 
                     f"{yield_analysis['change_30_days']:+.2f}%p (30일)")
            
            # 일드커브 차트
            fig_yield = go.Figure()
            fig_yield.add_trace(go.Scatter(
                x=yield_data.index, 
                y=yield_data.values,
                mode='lines',
                name='10Y-2Y 스프레드',
                line=dict(color='purple', width=2)
            ))
            fig_yield.add_hline(y=0, line_dash="dash", line_color="red", 
                              annotation_text="역전선 (0)")
            fig_yield.update_layout(
                title="일드커브 스프레드 추이",
                xaxis_title="날짜",
                yaxis_title="스프레드 (%p)",
                height=300
            )
            st.plotly_chart(fig_yield, use_container_width=True)

# 종합 위기 시그널
st.markdown("---")
st.subheader("🚨 종합 위기 시그널")

danger_signals = 0
warning_signals = 0

if sofr_analysis and sofr_analysis['signal'] == "심각한 위기":
    danger_signals += 1
elif sofr_analysis and sofr_analysis['signal'] in ["초기 경고", "주의 필요"]:
    warning_signals += 1

if pmi_analysis and pmi_analysis['signal'] == "경제위기 현실화":
    danger_signals += 1
elif pmi_analysis and pmi_analysis['signal'] in ["경고", "주의"]:
    warning_signals += 1

if yield_analysis and "임박" in yield_analysis['signal']:
    danger_signals += 1
elif yield_analysis and "역전" in yield_analysis['signal']:
    warning_signals += 1

# 종합 판단
if danger_signals >= 2:
    overall_signal = "🔴 심각한 위기 - 즉각 대응 필요"
    alert_class = "alert-danger"
elif danger_signals >= 1 or warning_signals >= 2:
    overall_signal = "🟡 경고 - 자산 축소 준비"
    alert_class = "alert-warning"
else:
    overall_signal = "🟢 정상 - 시장 모니터링 지속"
    alert_class = "alert-success"

st.markdown(f'<div class="{alert_class}"><h3>{overall_signal}</h3></div>', unsafe_allow_html=True)

# 대응 가이드
st.subheader("📋 상황별 대응 가이드")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    **🟢 정상 상황**
    - 정상적인 포트폴리오 유지
    - 정기적인 지표 모니터링
    - 장기 투자 전략 유지
    """)

with col2:
    st.markdown("""
    **🟡 경고 상황**
    - 포트폴리오 리스크 축소
    - 현금 비중 증대
    - 고위험 자산 일부 매도
    """)

with col3:
    st.markdown("""
    **🔴 위기 상황**
    - 즉각적인 자산 매도
    - 현금/안전자산 비중 최대화
    - 방어적 포지션 전환
    """)

# 데이터 업데이트 정보
st.markdown("---")
st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("데이터 출처: FRED (Federal Reserve Economic Data)")

# 새로고침 버튼
if st.button("🔄 데이터 새로고침"):
    st.cache_data.clear()
    st.experimental_rerun()
