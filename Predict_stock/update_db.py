import yfinance as yf
import pandas as pd
from prophet import Prophet
from datetime import datetime, timedelta
import pymysql

DB_CONFIG = {
    'host': 'localhost',
    'user': 'stock_user',        # 👈 전용 아이디
    'password': 'stock1234',     # 👈 전용 비밀번호
    'db': 'stock_predict',       # 👈 아까 만든 데이터베이스 이름
    'charset': 'utf8mb4'
}

def get_prediction_data(ticker_symbol):
    """1단계 엔진: 주가 수집 및 3,6,12개월 예측값 계산"""
    try:
        stock_data = yf.download(ticker_symbol, start="2023-01-01", progress=False)
        if stock_data.empty: return None

        df = stock_data[['Close']].reset_index()
        df.columns = ['ds', 'y']
        df['ds'] = df['ds'].dt.tz_localize(None)

        model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
        model.fit(df)

        future = model.make_future_dataframe(periods=365)
        forecast = model.predict(future)

        today = datetime.now()
        
        def get_nearest_pred(target_date):
            idx = (forecast['ds'] - target_date).abs().idxmin()
            return int(forecast.loc[idx, 'yhat'])

        current_price = int(df['y'].iloc[-1])
        p_3 = get_nearest_pred(today + timedelta(days=90))
        p_6 = get_nearest_pred(today + timedelta(days=180))
        p_12 = get_nearest_pred(today + timedelta(days=365))

        return current_price, p_3, p_6, p_12
    except Exception as e:
        print(f"❌ 예측 중 에러 발생 ({ticker_symbol}): {e}")
        return None

def save_to_db(ticker, stock_name):
    """2단계 엔진: 예측된 데이터를 MariaDB에 저장 또는 업데이트"""
    result = get_prediction_data(ticker)
    if not result:
        print(f"[{stock_name}] 예측 실패로 저장을 건너뜁니다.")
        return
        
    current_price, p_3, p_6, p_12 = result
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # MariaDB 연결
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # 데이터가 없으면 INSERT, 있으면 최신값으로 UPDATE 하는 쿼리문
    sql = """
        INSERT INTO predict_stock_list (ticker, stock_name, current_price, pred_3m, pred_6m, pred_12m, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            current_price = VALUES(current_price),
            pred_3m = VALUES(pred_3m),
            pred_6m = VALUES(pred_6m),
            pred_12m = VALUES(pred_12m),
            updated_at = VALUES(updated_at);
    """
    
    try:
        cursor.execute(sql, (ticker, stock_name, current_price, p_3, p_6, p_12, now))
        conn.commit()
        print(f"✅ [{stock_name}] DB 업데이트 성공! (현재가: {current_price:,}원)")
    except Exception as e:
        conn.rollback()
        print(f"❌ [{stock_name}] DB 저장 실패: {e}")
    finally:
        cursor.close()
        conn.close()

# 메인 실행부 (테스트할 관심 종목 리스트)
if __name__ == "__main__":
    my_interest_stocks = [
        ("005930.KS", "삼성전자"),
        ("000660.KS", "SK하이닉스"),
        ("AAPL", "애플")
    ]
    
    print("🚀 관심 종목 주가 예측 및 DB 업데이트 시작...")
    for ticker, name in my_interest_stocks:
        print(f" 진행 중: {name} ({ticker})")
        save_to_db(ticker, name)
    print("✨ 모든 프로세스가 완료되었습니다.")