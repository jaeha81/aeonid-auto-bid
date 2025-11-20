# app.py
import sqlite3
import requests
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# --- 1. 설정 및 상수 ---
DB_FILE = "bids.db"
NARA_API_URL = "http://apis.data.go.kr/1230000/BidPublicInfoService04/getBidPblancListInfoCnstwk"
NARA_API_KEY = "여기에_공공데이터포털_인증키를_넣으세요"  # ★ 실제 API 쓸 때 수정

# 필터 설정
INCLUDE_KEYWORDS = ["인테리어", "실내건축", "리모델링", "환경개선", "의장"]
EXCLUDE_KEYWORDS = ["폐기물", "용역", "전기", "통신", "소방", "구매"]

# --- 2. 데이터베이스 초기화 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bid_no TEXT UNIQUE,
            title TEXT,
            agency TEXT,
            price TEXT,
            date_close TEXT,
            link TEXT,
            is_favorite INTEGER DEFAULT 0,
            status TEXT DEFAULT '신규',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# --- 3. 필터링 로직 ---
def is_target_bid(title, price):
    # 1. 제외 키워드 체크
    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return False
    # 2. 포함 키워드 체크
    has_keyword = any(kw in title for kw in INCLUDE_KEYWORDS)
    if not has_keyword:
        return False
    # 3. 금액 체크 (예: 2천만원 이상)
    try:
        if int(price) < 20000000:
            return False
    except:
        pass
    return True

# --- 4. 공고 수집기 (Mock 데이터 모드) ---
def fetch_bids():
    print(f"[{datetime.now()}] 공고 수집 시작...")

    # ★ 테스트용 가짜 데이터 (API 키 없이 바로 확인 가능)
    mock_data = [
        {
            "bidNtceNo": "202405-001",
            "bidNtceNm": "서울지방조달청 본관 실내건축 환경개선공사",
            "dminsttNm": "서울지방조달청",
            "presmptPrce": "250000000",
            "bidClseDt": "2024-05-25 10:00",
            "dtilViewUrl": "#"
        },
        {
            "bidNtceNo": "202405-002",
            "bidNtceNm": "경기도 교육연수원 리모델링 공사",
            "dminsttNm": "경기도교육청",
            "presmptPrce": "1520000000",
            "bidClseDt": "2024-05-28 14:00",
            "dtilViewUrl": "#"
        },
        {
            "bidNtceNo": "202405-003",
            "bidNtceNm": "[긴급] 서초구청사 폐기물 처리 용역",
            "dminsttNm": "서초구청",
            "presmptPrce": "50000000",
            "bidClseDt": "2024-05-24 18:00",
            "dtilViewUrl": "#"
        }  # 이건 필터링에서 걸러져야 함
    ]

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    saved_count = 0

    for item in mock_data:
        title = item['bidNtceNm']
        price_raw = item['presmptPrce']

        # 필터 적용
        if is_target_bid(title, price_raw):
            try:
                cursor.execute('''
                    INSERT INTO bids (bid_no, title, agency, price, date_close, link)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    item['bidNtceNo'],
                    title,
                    item['dminsttNm'],
                    format(int(price_raw), ','),
                    item['bidClseDt'],
                    item['dtilViewUrl']
                ))
                saved_count += 1
            except sqlite3.IntegrityError:
                # 이미 존재하는 공고는 패스
                pass

    conn.commit()
    conn.close()
    print(f"[{datetime.now()}] 수집 완료. {saved_count}건 저장됨.")

# --- 5. 웹 서버 라우팅 (화면 연결) ---
@app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bids ORDER BY created_at DESC")
    bids = cursor.fetchall()
    conn.close()
    return render_template('dashboard.html', bids=bids)

@app.route('/mobile')
def mobile():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bids ORDER BY created_at DESC")
    bids = cursor.fetchall()
    conn.close()
    return render_template('mobile.html', bids=bids)

@app.route('/collect')
def manual_collect():
    fetch_bids()
    return redirect(url_for('dashboard'))

@app.route('/toggle_fav/<int:bid_id>')
def toggle_fav(bid_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE bids SET is_favorite = 1 - is_favorite WHERE id = ?", (bid_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

# --- 6. 실행 진입점 ---
if __name__ == '__main__':
    init_db()  # DB 생성

    # 스케줄러 시작 (현재는 테스트용: 1시간마다)
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=fetch_bids, trigger="interval", hours=1)
    scheduler.start()

    # 최초 1회 실행
    fetch_bids()

    # 서버 실행
    app.run(debug=True, port=5000)
