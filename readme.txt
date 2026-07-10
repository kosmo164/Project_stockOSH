
sql 테이블 명령어

CREATE TABLE `predict_stock_list` (
	`ticker` VARCHAR(20) NOT NULL COLLATE 'utf8mb4_uca1400_ai_ci',
	`stock_name` VARCHAR(50) NOT NULL COLLATE 'utf8mb4_uca1400_ai_ci',
	`current_price` INT(11) NULL DEFAULT NULL,
	`pred_3m` INT(11) NULL DEFAULT NULL,
	`pred_6m` INT(11) NULL DEFAULT NULL,
	`pred_12m` INT(11) NULL DEFAULT NULL,
	`updated_at` DATETIME NULL DEFAULT NULL,
	PRIMARY KEY (`ticker`) USING BTREE
)
COLLATE='utf8mb4_uca1400_ai_ci'
ENGINE=InnoDB
;

 # 1. yfinance로 최근 3년치 주가 데이터 가져오기
    stock_data = yf.download(ticker_symbol, start="2023-01-01", progress=False)


app.py를 실행하면

update_db.py가 자동실행됩니다.

