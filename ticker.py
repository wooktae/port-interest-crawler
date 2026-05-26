import psycopg

# 1) 시총 Top10 종목 리스트
top10 = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("373220", "LG에너지솔루션"),
    ("207940", "삼성바이오로직스"),
    ("005380", "현대차"),
    ("012450", "한화에어로스페이스"),
    ("034020", "두산에너빌리티"),
    ("000270", "기아"),
    ("105560", "KB금융"),
    ("051910", "LG화학")
]

# 2) PostgreSQL 접속 설정
conn = psycopg.connect(
    host="localhost",
    port=5433,
    dbname="interest_crawler",
    user="postgres",
    password="doflwhsk3768!"
)
cur = conn.cursor()

# 3) ticker 테이블에 없는 종목만 INSERT
for code, name in top10:
    # 존재 여부 체크
    cur.execute("""
        SELECT id FROM ticker
        WHERE ticker_code = %s
    """, (code,))
    
    result = cur.fetchone()
    if result:
        print(f"[SKIP] 이미 있음: {code} {name}")
    else:
        cur.execute("""
            INSERT INTO ticker (ticker_code, name, market)
            VALUES (%s, %s, 'KOSPI')
        """, (code, name))
        print(f"[ADD] 넣음: {code} {name}")

# 커밋 + 종료
conn.commit()
cur.close()
conn.close()