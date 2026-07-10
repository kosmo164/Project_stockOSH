from flask import Flask, render_template, jsonify
import pymysql
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'stock_user',
    'password': 'stock1234',
    'db': 'stock_predict',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# 💡 실시간 환율을 가져오는 함수 (원화 기준 통화별 환율)
def get_exchange_rate(currency_code):
    if currency_code == 'KRW':
        return 1.0
    try:
        # 기준 통화가 USD인 실시간 환율 API 호출
        res = requests.get("https://open.er-api.com/v6/latest/USD").json()
        rates = res.get('rates', {})
        
        # 입력된 통화의 USD 대비 가치와 KRW의 USD 대비 가치를 이용해 환율 계산
        usd_to_krw = rates.get('KRW', 1400.0)
        usd_to_currency = rates.get(currency_code, 1.0)
        
        return usd_to_krw / usd_to_currency
    except Exception as e:
        print(f"환율 로드 실패: {e}")
        # API 장애 시 사용할 기본 대피용 환율(Fallback)
        fallback_rates = {'USD': 1400.0, 'EUR': 1500.0, 'JPY': 9.0, 'CNY': 190.0}
        return fallback_rates.get(currency_code, 1.0)

def get_historical_data(ticker):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)
    
    # Ticker 객체를 생성해 통화 단위(Currency) 정보를 함께 추출
    ticker_obj = yf.Ticker(ticker)
    df = ticker_obj.history(start=start_date, end=end_date)
    
    if df.empty:
        raise ValueError(f"야후 파이낸스에서 '{ticker}' 종목 데이터를 찾을 수 없습니다.")
        
    currency = ticker_obj.info.get('currency', 'USD') # 기본값 USD
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df = df.reset_index()
    
    # 'Close' 컬럼이 없으면 'Close'가 포함된 컬럼 자동 매핑 (yfinance 버그 방지)
    close_col = 'Close' if 'Close' in df.columns else df.filter(like='Close').columns[0]
    
    # ------------------ [일별 데이터 상태에서 볼린저 밴드 사전 계산] ------------------
    # 월별로 평균을 내기 전에 일별 데이터 기준으로 20일 이동평균과 표준편차를 구해야 정확합니다.
    df['MA20'] = df[close_col].rolling(window=20).mean()
    df['STD20'] = df[close_col].rolling(window=20).std()
    df['Upper'] = df['MA20'] + (df['STD20'] * 2)
    df['Lower'] = df['MA20'] - (df['STD20'] * 2)
    # --------------------------------------------------------------------------

    df['Month'] = df['Date'].dt.to_period('M')
    
    # 월별로 그룹화할 때 종가뿐만 아니라 볼린저 밴드 지표값들의 평균도 함께 연산
    monthly_avg = df.groupby('Month')[[close_col, 'MA20', 'Upper', 'Lower']].mean().reset_index()
    monthly_avg['Month'] = monthly_avg['Month'].astype(str)
    
    return monthly_avg, currency

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/historical-vs-prediction/<ticker>')
def get_historical_vs_prediction(ticker):
    try:
        # 데이터와 함께 해당 종목의 통화 단위를 받아옵니다.
        df_all, currency = get_historical_data(ticker)

        all_labels = df_all['Month'].tolist()
        for i in range(1, 13):
            future_date = datetime.strptime(all_labels[-1], '%Y-%m') + pd.DateOffset(months=i)
            all_labels.append(future_date.strftime('%Y-%m'))
            
        two_years_ago_str = (datetime.now() - timedelta(days=2*365)).strftime('%Y-%m')

        actual_72m = []
        predicted_72m = []
        
        # 볼린저 밴드 데이터를 담을 빈 리스트 선언
        bb_ma_72m = []
        bb_upper_72m = []
        bb_lower_72m = []

        # 해당 국가 통화 -> 원화 변경을 위한 실시간 환율 매니저 호출
        rate = get_exchange_rate(currency)

        close_col = df_all.columns[1] # 'Close' 데이터 컬럼
        
        # 과거 데이터 채우기 + 원화 환산 일괄 적용
        for _, row in df_all.iterrows():
            current_month = row['Month']
            
            # 원화 환산 가격 계산 (원래 가격 * 환율)
            krw_price = int(row[close_col] * rate)
            actual_72m.append(krw_price)
            
            # 볼린저 밴드 값 원화 환산 및 결측치(NaN) 처리
            # 데이터 수집 초기 19일 동안은 값이 없으므로(NaN), 파이썬의 None(JSON의 null)으로 채워 차트 공백 처리
            bb_ma_72m.append(int(row['MA20'] * rate) if pd.notnull(row['MA20']) else None)
            bb_upper_72m.append(int(row['Upper'] * rate) if pd.notnull(row['Upper']) else None)
            bb_lower_72m.append(int(row['Lower'] * rate) if pd.notnull(row['Lower']) else None)
            
            if current_month >= two_years_ago_str:
                predicted_72m.append(int(krw_price * 1.05))
            else:
                predicted_72m.append(None)

        # 미래 예측 데이터 채우기
        # 미래 12개월 영역에는 볼린저 밴드를 그리지 않으므로 None(null)을 삽입합니다.
        base_price = actual_72m[-1] * 1.05
        for i in range(1, 13):
            actual_72m.append(None)
            predicted_72m.append(int(base_price * (1 + (i * 0.01))))
            
            # 미래 영역 볼린저 밴드 공백 처리
            bb_ma_72m.append(None)
            bb_upper_72m.append(None)
            bb_lower_72m.append(None)

        return jsonify({
            'labels': all_labels,
            'actual_historical_5y': actual_72m,
            'predicted_2y_plus_future': predicted_72m,
            # 신규 추가된 볼린저 밴드 배열들을 JSON 응답에 포함
            'bb_ma': bb_ma_72m,
            'bb_upper': bb_upper_72m,
            'bb_lower': bb_lower_72m,
            'currency': currency,          # 프론트엔드 표시용 오리지널 통화명
            'rate_applied': round(rate, 2) # 적용된 환율 정보
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)