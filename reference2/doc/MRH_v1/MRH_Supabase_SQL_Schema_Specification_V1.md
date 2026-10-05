# MRH (Momentum Rotation Hunter)

# Supabase SQL Schema Specification V1

# 실제 PostgreSQL SQL 생성 명세서

---

# 제1장. DB 생성 철학

## 1.1 핵심 원칙

MRH DB의 핵심은:

```sql id="x7s2mt"
복잡한 퀀트 데이터 웨어하우스가 아니라

매일 발생하는
signal / ranking / portfolio / logs

를 안정적으로 기록하는 것
```

이다.

---

# 제2장. PostgreSQL Extension

## 2.1 UUID Extension

```sql id="6dntn9"
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

---

# 제3장. tickers 테이블

## 3.1 생성 SQL

```sql id="9nm3lu"
CREATE TABLE tickers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    ticker TEXT NOT NULL UNIQUE,
    company_name TEXT,
    sector TEXT,
    industry TEXT,

    market_cap BIGINT,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 3.2 인덱스

```sql id="p6s9lf"
CREATE INDEX idx_tickers_ticker
ON tickers(ticker);
```

---

# 제4장. daily_market_data 테이블

## 4.1 생성 SQL

```sql id="qz3b4g"
CREATE TABLE daily_market_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    ticker TEXT NOT NULL,

    trade_date DATE NOT NULL,

    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,

    volume BIGINT,

    daily_change_pct NUMERIC,
    rvol NUMERIC,
    gap_pct NUMERIC,

    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 4.2 인덱스

```sql id="ml63n8"
CREATE INDEX idx_market_ticker_date
ON daily_market_data(ticker, trade_date);
```

---

# 제5장. candidate_signals 테이블

## 5.1 생성 SQL

```sql id="31gj5y"
CREATE TABLE candidate_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    ticker TEXT NOT NULL,

    trade_date DATE NOT NULL,

    continuation_score NUMERIC,

    daily_momentum_score NUMERIC,
    rvol_score NUMERIC,
    sector_score NUMERIC,
    close_strength_score NUMERIC,

    exhaustion_risk NUMERIC,

    ranking INTEGER,

    signal_type TEXT,

    signal_reason TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5.2 인덱스

```sql id="tkv26u"
CREATE INDEX idx_candidate_date_rank
ON candidate_signals(trade_date, ranking);
```

---

# 제6장. portfolio_positions 테이블

## 6.1 생성 SQL

```sql id="qxtf3z"
CREATE TABLE portfolio_positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    ticker TEXT NOT NULL,

    entry_price NUMERIC,
    current_price NUMERIC,

    quantity NUMERIC,

    stop_loss_pct NUMERIC,

    holding_days INTEGER,

    continuation_strength NUMERIC,

    position_status TEXT,

    created_at TIMESTAMP DEFAULT NOW(),

    closed_at TIMESTAMP
);
```

---

## 6.2 인덱스

```sql id="vhgqvq"
CREATE INDEX idx_portfolio_status
ON portfolio_positions(position_status);
```

---

# 제7장. trade_logs 테이블

## 7.1 생성 SQL

```sql id="hij3nh"
CREATE TABLE trade_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    ticker TEXT NOT NULL,

    action TEXT,

    entry_price NUMERIC,
    exit_price NUMERIC,

    pnl_pct NUMERIC,

    holding_days INTEGER,

    exit_reason TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 7.2 인덱스

```sql id="pmxlj0"
CREATE INDEX idx_trade_logs
ON trade_logs(ticker, created_at);
```

---

# 제8장. notification_logs 테이블

## 8.1 생성 SQL

```sql id="afmrf0"
CREATE TABLE notification_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    ticker TEXT,

    notification_type TEXT,

    message TEXT,

    sent_status BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW()
);
```

---

# 제9장. batch_logs 테이블

## 9.1 생성 SQL

```sql id="2mlt0t"
CREATE TABLE batch_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    batch_date DATE,

    batch_status TEXT,

    total_candidates INTEGER,
    total_signals INTEGER,

    error_message TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);
```

---

# 제10장. system_logs 테이블

## 10.1 생성 SQL

```sql id="7mvz4q"
CREATE TABLE system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    log_type TEXT,

    ticker TEXT,

    description TEXT,

    severity TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);
```

---

# 제11장. 핵심 Enum 구조

## 11.1 Position Status

```sql id="o7p07x"
CREATE TYPE position_status_enum AS ENUM (
    'OPEN',
    'CLOSED'
);
```

---

## 11.2 Signal Type

```sql id="a5z7py"
CREATE TYPE signal_type_enum AS ENUM (
    'BUY',
    'SELL',
    'HOLD'
);
```

---

## 11.3 Batch Status

```sql id="4dmpqj"
CREATE TYPE batch_status_enum AS ENUM (
    'SUCCESS',
    'FAIL',
    'SAFE_MODE'
);
```

---

# 제12장. Row Level Security (RLS)

## 12.1 MVP 정책

초기 MVP:

```sql id="b3j4fi"
RLS 비활성화
```

이유:

* 단일 사용자
* 개인용 앱
* 복잡성 최소화

---

# 제13장. Snapshot 저장 구조

## 13.1 파일 구조

```text id="jlwmrg"
/data/YYYY-MM-DD/
```

---

## 13.2 저장 파일

| 파일 | 목적 |
| :--- | :--- |
| market.parquet | 일봉 저장 |
| candidates.parquet | 후보 저장 |
| scores.parquet | 점수 저장 |
| logs.parquet | 운영 로그 |

---

# 제14장. DB 운영 규칙

## 14.1 삭제 금지 데이터

절대 삭제 금지:

* trade_logs
* stop hit logs
* failed signals
* batch failure logs

---

## 14.2 이유

```sql id="3m2d4y"
실패 로그가
전략 개선의 핵심 데이터
```

이기 때문.

---

# 제15장. MVP에서 하지 않는 것

초기 MVP 제외:

* Tick DB
* 실시간 체결 저장
* 옵션 체인 저장
* 호가창 저장
* Orderbook 저장
* 초고빈도 저장

---

# 제16장. 현재 DB 구조의 진짜 역할

MRH DB는:

```sql id="0e5tpo"
기관급 퀀트 데이터 플랫폼
```

이 아니다.

핵심은:

```sql id="w35e0l"
매일 발생하는

signal
ranking
portfolio
logs

를 단순하고 안정적으로 유지하는 것
```

이다.
