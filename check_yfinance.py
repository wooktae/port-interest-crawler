import yfinance as yf
from datetime import datetime, timedelta

# 🔥 여기만 바꾸면 됨
TICKER = "082270.KQ"
TARGET_DATE = "2022-05-02"

target_date = datetime.strptime(TARGET_DATE, "%Y-%m-%d").date()

# --------------------------
# 1️⃣ 단일 날짜 조회 (문제 있는 방식)
# --------------------------
print("=== 단일 날짜 조회 ===")

df1 = yf.download(
    TICKER,
    start=target_date.strftime("%Y-%m-%d"),
    end=(target_date + timedelta(days=1)).strftime("%Y-%m-%d"),
    interval="1d",
    progress=False
)

print(df1)


# --------------------------
# 2️⃣ 범위 조회 (정상 방식)
# --------------------------
print("\n=== 범위 조회 ===")

df2 = yf.download(
    TICKER,
    start=(target_date - timedelta(days=5)).strftime("%Y-%m-%d"),
    end=(target_date + timedelta(days=1)).strftime("%Y-%m-%d"),
    interval="1d",
    progress=False
)

print(df2)

# target_date만 필터
if not df2.empty:
    df2 = df2.reset_index()
    df2 = df2[df2["Date"].dt.date == target_date]

print("\n=== 필터 결과 ===")
print(df2)