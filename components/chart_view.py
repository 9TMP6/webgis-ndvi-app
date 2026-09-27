# components/chart_view.py
import streamlit as st
import pandas as pd
import altair as alt

def render_chart_and_summary():
    """
    Hiển thị biểu đồ chuỗi thời gian (Time-series) và thống kê tóm tắt 
    dựa hoàn toàn trên dữ liệu thực tế (từ CSDL Supabase hoặc AI ONNX).
    """
    st.subheader("📈 Phân tích Chuỗi thời gian & Xu hướng NDVI")

    # Lấy dữ liệu đang được lưu trong st.session_state từ trang chính (app.py)
    df = st.session_state.get("ndvi_df", pd.DataFrame())

    if df.empty:
        st.info("ℹ️ Chưa có dữ liệu để vẽ biểu đồ. Vui lòng chọn thời gian và bấm nút chạy dự báo/tải dữ liệu ở menu bên trái.")
        return

    # Chuẩn hóa dữ liệu ngày tháng
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    elif "year" in df.columns and "month" in df.columns:
        df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
    else:
        st.warning("⚠️ Dữ liệu thiếu trường thời gian (date/year/month) để vẽ biểu đồ.")
        return

    # Gom nhóm theo thời gian để tính giá trị NDVI trung bình, min, max toàn vùng qua từng mốc
    df_grouped = df.groupby("date").agg({
        "ndvi_mean": "mean",
        "ndvi_min": "mean",
        "ndvi_max": "mean"
    }).reset_index().sort_values("date")

    if df_grouped.empty:
        st.warning("⚠️ Không đủ dữ liệu theo thời gian để hiển thị biểu đồ.")
        return

    # Chia layout thành 2 cột: Biểu đồ (rộng) và Thống kê nhanh (hẹp)
    col_chart, col_summary = st.columns([2.5, 1])

    with col_chart:
        st.markdown("##### 🌐 Biểu đồ biến động NDVI trung bình toàn vùng")
        
        # Vẽ biểu đồ Line Chart kết hợp vùng min-max bằng Altair
        base = alt.Chart(df_grouped).encode(
            x=alt.X("date:T", title="Thời gian (Tháng/Năm)")
        )

        # Vùng mờ thể hiện khoảng dao động min-max của thảm thực vật
        band = base.mark_area(opacity=0.2, color="green").encode(
            y=alt.Y("ndvi_min:Q", title="Chỉ số NDVI"),
            y2="ndvi_max:Q"
        )

        # Đường chính thể hiện giá trị trung bình (NDVI Mean)
        line = base.mark_line(strokeWidth=3, color="#2ca02c").encode(
            y=alt.Y("ndvi_mean:Q", title="Chỉ số NDVI Mean")
        )

        chart = (band + line).interactive().properties(height=350)
        st.altair_chart(chart, use_container_width=True)

    with col_summary:
        st.markdown("##### 📋 Tóm tắt chỉ số")
        
        # Tính toán các chỉ số thống kê cơ bản từ tập dữ liệu hiện tại
        current_mean = df_grouped["ndvi_mean"].mean()
        max_ndvi = df_grouped["ndvi_mean"].max()
        min_ndvi = df_grouped["ndvi_mean"].min()

        st.metric(
            label="🌱 NDVI Trung bình toàn chuỗi", 
            value=f"{current_mean:.3f}"
        )
        st.metric(
            label="📈 NDVI Cao nhất đạt được", 
            value=f"{max_ndvi:.3f}"
        )
        st.metric(
            label="📉 NDVI Thấp nhất ghi nhận", 
            value=f"{min_ndvi:.3f}"
        )

        # Đánh giá nhanh tình trạng thảm thực vật
        if current_mean > 0.5:
            st.success("✨ Thảm thực vật phát triển rất tốt, độ phủ xanh cao.")
        elif current_mean > 0.3:
            st.info("🌿 Thảm thực vật ở mức trung bình, ổn định.")
        else:
            st.warning("⚠️ Khu vực có mật độ thực vật thưa hoặc đang là đất trống/đô thị hóa.")

    # Xóa hàm rác cũ không còn dùng đến nếu có ở file ai_engine.py để code sạch sẽ tuyệt đối!
