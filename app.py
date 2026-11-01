"""Giao dien Streamlit: Thanh khoan va ap luc so lenh (NEO API VPBankS).
 
Chay:  python3 -m streamlit run app.py
Doc du lieu tho do collector.py ghi (thu muc data/), hoac du lieu mau (data_sample/).
Cong cu hoc thuat, khong phai khuyen nghi dau tu.
"""
import time
from datetime import datetime
from pathlib import Path
 
import altair as alt
import pandas as pd
import streamlit as st
 
import analysis
import make_sample
import parse_raw
 
st.set_page_config(page_title="Thanh khoản & áp lực sổ lệnh", page_icon="📊", layout="wide")
 
BRAND, ERR, GOOD, WARN = "#6b566c", "#ba1a1a", "#1E9E5A", "#B7791F"   # tim thuong hieu; do/xanh/vang la mau ngu nghia them vao
 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;500;600&display=swap');
html, body, .stApp, [data-testid="stSidebar"] { font-family: 'Inter', sans-serif; font-feature-settings: 'tnum' 1, 'zero' 1; }
h1, h2, h3 { font-family: 'Anton', 'Inter', sans-serif !important; font-weight: 400 !important; color: #141B2B; letter-spacing: -0.01em; }
h1 { font-size: 30px !important; line-height: 38px; }
h3 { font-size: 18px !important; line-height: 24px; }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #C3C6D2; }
[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #C3C6D2; border-radius: 12px; padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04), 0 1px 2px rgba(0,0,0,.02); }
[data-testid="stMetricLabel"] p { font-size: 11px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: #434750; }
[data-testid="stMetricValue"] { font-family: 'Anton', 'Inter', sans-serif; font-size: 26px; line-height: 32px; color: #141B2B; }
button[data-baseweb="tab"] { font-weight: 600; }
.chip { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 12px; font-weight: 600;
  color: #6b566c; background: #f1d7f3; margin: 0 4px 4px 0; }
.live { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; letter-spacing: .05em;
  text-transform: uppercase; padding: 3px 10px; border-radius: 9999px; background: #EFEAEE; color: #434750; margin-right: 10px; }
.live .dot { width: 8px; height: 8px; border-radius: 50%; background: #1E9E5A; animation: pulse 1.8s infinite; }
.live.off .dot { background: #737781; animation: none; }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(30,158,90,.5); } 70% { box-shadow: 0 0 0 8px rgba(30,158,90,0); }
  100% { box-shadow: 0 0 0 0 rgba(30,158,90,0); } }
.disclaimer { display: inline-block; margin-top: 24px; padding: 6px 12px; background: #F9F9FF; border: 1px solid #C3C6D2;
  border-radius: 9999px; color: #737781; font-size: 11px; font-weight: 400; }
</style>
""", unsafe_allow_html=True)
 
REAL_DIR, SAMPLE_DIR = Path("data"), Path("data_sample")
ALERT_COLS = {"alert_wide_spread": "Spread giãn rộng",
              "alert_buy_pressure": "Áp lực mua",
              "alert_sell_pressure": "Áp lực bán"}
 
 
# ---------------------------------------------------------------- tải & xử lý dữ liệu
def _signature(folder: Path):
    return tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(folder.glob("raw_*.jsonl")))
 
 
@st.cache_data(ttl=30, show_spinner="Đang đọc dữ liệu...")
def load_data(folder: str, signature: tuple):
    df = parse_raw.load_raw(folder)
    return df, dict(df.attrs)
 
 
@st.cache_data(show_spinner="Đang tính chỉ báo...")
def compute_bars(df: pd.DataFrame, only_continuous: bool, freq: str, window: int, z_thr: float):
    d = parse_raw.filter_continuous(df) if only_continuous else df
    if d.empty:
        return pd.DataFrame()
    return analysis.add_signals(analysis.to_bars(d, freq), window=window,
                                min_periods=max(3, window // 3), z_threshold=z_thr)
 
 
def naive(bars: pd.DataFrame) -> pd.DataFrame:
    out = bars.copy()
    out["time"] = out["ts"].dt.tz_localize(None)
    return out
 
 
# ---------------------------------------------------------------- thanh bên
st.sidebar.header("Bộ lọc")
has_real = REAL_DIR.exists() and any(REAL_DIR.glob("raw_*.jsonl"))
source = st.sidebar.radio("Nguồn dữ liệu", ["Dữ liệu thật (data/)", "Dữ liệu mẫu (data_sample/)"],
                          index=0 if has_real else 1)
is_sample = source.startswith("Dữ liệu mẫu")
folder = SAMPLE_DIR if is_sample else REAL_DIR
 
if is_sample and not any(SAMPLE_DIR.glob("raw_*.jsonl")):
    make_sample.generate(folder=str(SAMPLE_DIR))
 
only_cont = st.sidebar.checkbox("Chỉ phiên khớp lệnh liên tục (09:15–11:30, 13:00–14:30)", value=True)
freq = st.sidebar.selectbox("Khung thời gian", ["1min", "5min"], index=0)
window = st.sidebar.slider("Cửa sổ z-score (số khung)", 10, 120, 30, step=5)
z_thr = st.sidebar.slider("Ngưỡng cảnh báo |z|", 1.0, 4.0, 2.0, step=0.5)
 
with st.sidebar.expander("Trọng số điểm thanh khoản"):
    w_spread = st.slider("Spread (thấp là tốt)", 0.0, 1.0, 0.4, 0.05)
    w_depth = st.slider("Độ sâu sổ lệnh", 0.0, 1.0, 0.4, 0.05)
    w_turn = st.slider("Giá trị khớp", 0.0, 1.0, 0.2, 0.05)
 
auto = st.sidebar.checkbox("Tự làm mới", value=False)
every = st.sidebar.number_input("Chu kỳ (giây)", 10, 600, 60, step=10, disabled=not auto)
if st.sidebar.button("Tải lại dữ liệu"):
    st.cache_data.clear()
st.sidebar.caption("Công cụ học thuật, không phải khuyến nghị đầu tư.")
 
# ---------------------------------------------------------------- tiêu đề & nạp dữ liệu
st.title("📊 Thanh khoản & áp lực sổ lệnh")
st.caption("Nguồn: NEO API (VPBankS), kênh stockInfo, sổ lệnh 3 mức giá. Giờ Việt Nam (UTC+7).")
 
try:
    if not folder.exists() or not any(folder.glob("raw_*.jsonl")):
        st.warning("Chưa có dữ liệu trong thư mục `data/`. Hãy chạy `python3 collector.py` trong giờ giao dịch, "
                   "hoặc chọn **Dữ liệu mẫu** ở thanh bên.")
        st.stop()
    raw, attrs = load_data(str(folder), _signature(folder))
    if raw.empty:
        st.warning("Đã đọc tệp dữ liệu nhưng chưa có bản ghi stockInfo hợp lệ. "
                   "Kiểm tra `collector.py` có nhận được dữ liệu không (dòng `[msg ...]`).")
        st.stop()
    bars_all = compute_bars(raw, only_cont, freq, window, z_thr)
    if bars_all.empty:
        st.warning("Không có bản ghi nào trong phiên khớp lệnh liên tục. "
                   "Bỏ chọn bộ lọc phiên ở thanh bên để xem toàn bộ.")
        st.stop()
except st.errors.StreamlitAPIException:
    raise
except Exception as e:  # noqa: BLE001
    st.error(f"Không xử lý được dữ liệu: {type(e).__name__}: {e}")
    st.stop()
 
# bộ lọc theo mã / ngày
all_symbols = sorted(bars_all["symbol"].unique())
dates = sorted(bars_all["ts"].dt.date.unique())
symbols = st.sidebar.multiselect("Mã cổ phiếu", all_symbols, default=all_symbols)
date_sel = st.sidebar.selectbox("Ngày", ["Tất cả"] + [str(d) for d in dates], index=0)
 
bars = bars_all[bars_all["symbol"].isin(symbols)]
if date_sel != "Tất cả":
    bars = bars[bars["ts"].dt.date.astype(str) == date_sel]
if bars.empty:
    st.info("Không có dữ liệu cho lựa chọn hiện tại. Chọn thêm mã hoặc đổi ngày.")
    st.stop()
 
# ---------------------------------------------------------------- trạng thái cập nhật
last_ts = raw["ts"].max()
age_min = (pd.Timestamp.now(tz=raw["ts"].dt.tz) - last_ts).total_seconds() / 60
if is_sample:
    pill = '<span class="live off"><span class="dot"></span>Dữ liệu mẫu</span>'
elif age_min <= 15:
    pill = '<span class="live"><span class="dot"></span>Trực tiếp</span>'
else:
    pill = '<span class="live off"><span class="dot"></span>Ngắt kết nối</span>'
chips = "".join(f'<span class="chip">{x}</span>' for x in symbols)
st.markdown(pill + chips, unsafe_allow_html=True)
 
c1, c2, c3, c4 = st.columns(4)
c1.metric("Nguồn", "Dữ liệu mẫu" if is_sample else "Dữ liệu thật")
c2.metric("Bản ghi hợp lệ", f"{len(raw):,}")
c3.metric("Bản ghi mới nhất", last_ts.strftime("%d/%m %H:%M:%S"))
c4.metric("Cách đây", "—" if is_sample else (f"{age_min:.0f} phút" if age_min < 120 else f"{age_min/60:.1f} giờ"))
if not is_sample and age_min > 15:
    st.info("Dữ liệu cũ hơn 15 phút. Nếu thị trường đang mở, kiểm tra `collector.py` còn chạy không.")
if attrs.get("bad_lines"):
    st.caption(f"Đã bỏ qua {attrs['bad_lines']} dòng JSON lỗi và {attrs.get('skipped_invalid_book', 0)} "
               "bản ghi sổ lệnh không hợp lệ (ATO/ATC, thiếu giá, sổ lệnh bị cắt nhau).")
 
# ---------------------------------------------------------------- tính xếp hạng
wsum = w_spread + w_depth + w_turn
weights = ({"spread": w_spread / wsum, "depth": w_depth / wsum, "turnover": w_turn / wsum}
           if wsum > 0 else None)
ranking = analysis.liquidity_ranking(bars, weights)
n_alerts = int(bars[list(ALERT_COLS)].sum().sum())
 
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Số mã theo dõi", bars["symbol"].nunique())
k2.metric("Spread trung vị", f"{bars['spread_pct'].median():.3f}%")
k3.metric("|Mất cân bằng| TB", f"{bars['imbalance'].abs().mean():.2f}")
k4.metric("Số cảnh báo", n_alerts)
k5.metric("Thanh khoản tốt nhất", ranking.iloc[0]["symbol"] if len(ranking) else "—")
 
tab1, tab2, tab3, tab4 = st.tabs(["Tổng quan", "Chi tiết theo mã", "Kiểm chứng", "Giải thích"])
 
# ---------------------------------------------------------------- tab 1: tổng quan
with tab1:
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Xếp hạng thanh khoản (0–100)")
        chart = (alt.Chart(ranking).mark_bar(color=BRAND, cornerRadiusEnd=4)
                 .encode(x=alt.X("liquidity_score:Q", title="Điểm thanh khoản", scale=alt.Scale(domain=[0, 100])),
                         y=alt.Y("symbol:N", sort="-x", title=None),
                         tooltip=["symbol", alt.Tooltip("liquidity_score:Q", format=".1f"),
                                  alt.Tooltip("median_spread_pct:Q", format=".3f"),
                                  alt.Tooltip("median_depth_value:Q", format=",.0f")])
                 .properties(width="container", height=max(120, 28 * len(ranking))))
        st.altair_chart(chart)
    with right:
        st.subheader("Bảng chi tiết")
        show = ranking.rename(columns={"symbol": "Mã", "median_spread_pct": "Spread TV (%)",
                                       "median_depth_value": "Độ sâu top-3 (VND)",
                                       "avg_daily_turnover": "GT khớp TB/ngày",
                                       "liquidity_score": "Điểm"})
        st.dataframe(show.round(3), hide_index=True)
 
    st.subheader("Cảnh báo gần đây")
    rows = []
    for col, label in ALERT_COLS.items():
        hit = bars[bars[col]]
        zcol = "z_spread" if col == "alert_wide_spread" else "z_imbalance"
        for _, r in hit.iterrows():
            rows.append({"Thời điểm": r["ts"].strftime("%d/%m %H:%M"), "Mã": r["symbol"], "Loại": label,
                         "z": round(float(r[zcol]), 2), "Spread (%)": round(float(r["spread_pct"]), 3),
                         "Mất cân bằng": round(float(r["imbalance"]), 2), "_t": r["ts"]})
    if rows:
        al = pd.DataFrame(rows).sort_values("_t", ascending=False).drop(columns="_t").head(200)
        tone = {"Áp lực mua": "background-color:#E3F4EA;color:#166A41;font-weight:600",
                "Áp lực bán": "background-color:#FCE4E4;color:#93000a;font-weight:600",
                "Spread giãn rộng": "background-color:#FFF1D6;color:#7A5200;font-weight:600"}
        st.dataframe(al.style.map(lambda v: tone.get(v, ""), subset=["Loại"]), hide_index=True)
    else:
        st.success("Chưa có cảnh báo nào với ngưỡng hiện tại (hoặc chưa đủ dữ liệu để tính z-score).")
 
# ---------------------------------------------------------------- tab 2: chi tiết theo mã
with tab2:
    sym = st.selectbox("Chọn mã", sorted(bars["symbol"].unique()))
    d = naive(bars[bars["symbol"] == sym])
 
    st.subheader(f"{sym}: chỉ số mất cân bằng sổ lệnh")
    base = alt.Chart(d).encode(x=alt.X("time:T", title=None))
    line = base.mark_line(color=BRAND).encode(y=alt.Y("imbalance:Q", title="Mất cân bằng (−1 bán … +1 mua)",
                                           scale=alt.Scale(domain=[-1, 1])))
    pts = (base.transform_filter("datum.alert_buy_pressure || datum.alert_sell_pressure")
           .mark_point(size=90, filled=True, color=ERR)
           .encode(y="imbalance:Q", tooltip=["time:T", alt.Tooltip("imbalance:Q", format=".2f"),
                                             alt.Tooltip("z_imbalance:Q", format=".2f")]))
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")
    st.altair_chart((line + pts + zero).properties(width="container", height=260))
    st.caption("Chấm đỏ: khung có |z| vượt ngưỡng cảnh báo.")
 
    cA, cB = st.columns(2)
    with cA:
        st.subheader("Spread (%)")
        sp = (alt.Chart(d).mark_line(color=BRAND).encode(x=alt.X("time:T", title=None),
                                              y=alt.Y("spread_pct:Q", title="Spread / giá giữa (%)"),
                                              tooltip=["time:T", alt.Tooltip("spread_pct:Q", format=".3f")])
              .properties(width="container", height=220))
        st.altair_chart(sp)
    with cB:
        st.subheader("Độ sâu top-3 (VND)")
        dp = (alt.Chart(d).mark_area(opacity=0.5, color=BRAND).encode(x=alt.X("time:T", title=None),
                                                         y=alt.Y("depth_value:Q", title="Giá trị 3 mức mua + bán"),
                                                         tooltip=["time:T", alt.Tooltip("depth_value:Q", format=",.0f")])
              .properties(width="container", height=220))
        st.altair_chart(dp)
 
# ---------------------------------------------------------------- tab 3: kiểm chứng
with tab3:
    st.subheader("Chỉ số mất cân bằng có dự báo hướng giá ngắn hạn không?")
    h = st.slider("Số khung nhìn trước", 1, 30, 5)
    thr = st.slider("Ngưỡng |mất cân bằng| để tính là 'tín hiệu'", 0.05, 0.9, 0.2, 0.05)
    res = analysis.imbalance_vs_forward_return(bars, horizon=h, signal_threshold=thr)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Số quan sát", res["n"])
    m2.metric("Tương quan hạng (Spearman)", "—" if res["spearman"] is None else f"{res['spearman']:+.3f}")
    m3.metric("Số tín hiệu", res["n_signals"])
    m4.metric("Tỷ lệ đúng hướng", "—" if res["hit_rate"] is None else f"{res['hit_rate']:.1%}")
    st.caption("Tương quan giữa mất cân bằng tại khung t và lợi suất giá giữa sau h khung (trong cùng ngày). "
               "Tỷ lệ đúng hướng 50% là ngẫu nhiên. Với ít phiên dữ liệu, kết quả chưa đủ kết luận; "
               "báo cáo nên nêu rõ điều này.")
    if is_sample:
        st.warning("Đang dùng dữ liệu mẫu sinh ngẫu nhiên: các con số trên không có ý nghĩa tài chính.")
 
# ---------------------------------------------------------------- tab 4: giải thích
with tab4:
    st.subheader("Cách tính")
    st.markdown(
        """
- **Spread (%)** = (giá bán 1 − giá mua 1) / giá giữa × 100. Càng nhỏ, thanh khoản càng tốt.
- **Độ sâu top-3** = tổng khối lượng (hoặc giá trị) 3 mức giá mua và 3 mức giá bán tốt nhất.
- **Mất cân bằng** = (KL mua − KL bán) / (KL mua + KL bán), từ −1 (áp lực bán) đến +1 (áp lực mua).
- **z-score** = (x − trung bình cửa sổ trước) / độ lệch chuẩn cửa sổ trước. Không dùng điểm hiện tại để tính
  trung bình, nên một cú sốc không tự làm loãng cảnh báo.
- **Điểm thanh khoản** = 100 × tổng có trọng số của thứ hạng (0–1) giữa các mã theo spread (thấp tốt hơn),
  độ sâu và giá trị khớp (cao tốt hơn). Thứ hạng là tương đối giữa các mã đang chọn.
"""
    )
    st.subheader("Hạn chế")
    st.markdown(
        """
- Sổ lệnh chỉ có **3 mức giá** mỗi phía, nên đây là áp lực ở đỉnh sổ lệnh, không phải toàn bộ sổ lệnh.
- Giá ATO/ATC không có giá mua/bán dạng số, các bản ghi này bị loại khỏi tính toán.
- Mất cân bằng lệnh chờ không bảo đảm giá sẽ đi theo hướng đó (lệnh có thể bị hủy hoặc bị "ảo").
- Số phiên dữ liệu ít nên thống kê kiểm chứng có độ tin cậy hạn chế.
- Điểm xếp hạng là so sánh tương đối trong nhóm mã đã chọn, không phải thước đo tuyệt đối.
"""
    )
    st.info("Sản phẩm phục vụ học tập. Không phải khuyến nghị đầu tư và không gửi lệnh giao dịch thật.")
 
st.markdown('<span class="disclaimer">Sản phẩm phục vụ học tập, không phải khuyến nghị đầu tư.</span>',
            unsafe_allow_html=True)
 
# ---------------------------------------------------------------- tự làm mới
if auto:
    time.sleep(int(every))
    st.cache_data.clear()
    st.rerun()
