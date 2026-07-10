import yfinance as yf
import pandas as pd
from prophet import Prophet
from datetime import datetime, timedelta

# 💡 여기에 DB_CONFIG를 추가해 둡니다. (추후 기능 확장이나 일관성을 위해 설정)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'stock_user',        # 👈 설정한 전용 계정명
    'password': 'stock1234',     # 👈 접속 비밀번호
    'db': 'stock_predict',       # 👈 대상 데이터베이스
    'charset': 'utf8mb4'
}

def get_stock_prediction(ticker_symbol):
    print(f"[{ticker_symbol}] 데이터 수집 중...")
    
    # 1. yfinance로 최근 3년치 주가 데이터 가져오기
    stock_data = yf.download(ticker_symbol, start="2023-01-01", progress=False)
    
    if stock_data.empty:
        print("데이터를 가져오지 못했습니다. 종목 코드를 확인해 주세요.")
        return None

    # 데이터 구조 단순화 및 인덱스 리셋
    df = stock_data[['Close']].reset_index()
    
    # Prophet 컬럼명 매핑
    df.columns = ['ds', 'y']
    
    # 시각대 정보 제거
    df['ds'] = df['ds'].dt.tz_localize(None)

    print("🔮 예측 모델 학습 및 미래 예측 시작...")
    # 2. Prophet 모델 생성 및 학습
    model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
    model.fit(df)

    # 3. 미래 365일치 데이터 프레임 만들기
    future = model.make_future_dataframe(periods=365)
    
    # 4. 미래 주가 예측하기
    forecast = model.predict(future)

    # 5. 오늘 기준으로 3, 6, 12개월 뒤 날짜 계산
    today = datetime.now()
    date_3m = today + timedelta(days=90)
    date_6m = today + timedelta(days=180)
    date_12m = today + timedelta(days=365)

    # 예측 데이터 중에서 가장 가까운 날짜의 데이터 추출하는 함수
    def get_nearest_pred(target_date):
        idx = (forecast['ds'] - target_date).abs().idxmin()
        nearest_row = forecast.loc[idx]
        return nearest_row['ds'].strftime('%Y-%m-%d'), int(nearest_row['yhat'])

    # 결과 매칭
    d_3, p_3 = get_nearest_pred(date_3m)
    d_6, p_6 = get_nearest_pred(date_6m)
    d_12, p_12 = get_nearest_pred(date_12m)
    
    current_price = int(df['y'].iloc[-1]) # 가장 최근 실제 종가

    # 결과 출력
    print("\n" + "="*40)
    print(f"📊 [{ticker_symbol}] 주가 예측 결과 요약")
    print("="*40)
    print(f"현재실제주가: {current_price:,}원")
    print(f" 3개월 후 ({d_3}) 예측: {p_3:,}원")
    print(f" 6개월 후 ({d_6}) 예측: {p_6:,}원")
    print(f"12개월 후 ({d_12}) 예측: {p_12:,}원")
    print("="*40)

# 삼성전자 종목코드로 테스트 실행
if __name__ == "__main__":
    get_stock_prediction("005930.KS")