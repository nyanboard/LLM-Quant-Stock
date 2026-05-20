## ADDED Requirements

### Requirement: Pre-screening rule engine
The system SHALL provide a `StockScreener` class in `quant/screener.py` that filters a stock list based on configurable rules from `config/quant_rules.yaml` `pre_screen` section, covering 8 dimensions: listing status, market cap, liquidity, valuation, profitability, financial health, price, and limit up/down.

#### Scenario: Filter out ST stocks
- **WHEN** a stock has ST or *ST status and `exclude_st` is true in config
- **THEN** the stock SHALL be excluded from the candidate pool

#### Scenario: Filter by market cap range
- **WHEN** a stock's market cap is below `market_cap.min` (50亿) or above `market_cap.max` (5000亿)
- **THEN** the stock SHALL be excluded from the candidate pool

#### Scenario: Filter by liquidity
- **WHEN** a stock's daily average trading amount is below `liquidity.min_avg_amount` (3000万) or turnover rate is below `liquidity.min_turnover_rate` (0.5%)
- **THEN** the stock SHALL be excluded from the candidate pool

#### Scenario: Filter by valuation
- **WHEN** a stock's PE is outside the range `valuation.pe_min` to `valuation.pe_max`, or PB is outside `valuation.pb_min` to `valuation.pb_max`
- **THEN** the stock SHALL be excluded from the candidate pool

#### Scenario: Filter by profitability
- **WHEN** a stock's latest ROE is below `profitability.min_roe` (3%) or revenue is not positive when `profitability.revenue_positive` is true
- **THEN** the stock SHALL be excluded from the candidate pool

#### Scenario: Filter by financial health
- **WHEN** a stock's debt ratio exceeds `financial_health.max_debt_ratio` (80%) or operating cashflow is not positive when `financial_health.operating_cashflow_positive` is true
- **THEN** the stock SHALL be excluded from the candidate pool

#### Scenario: Filter by minimum price
- **WHEN** a stock's current price is below `price.min` (2元)
- **THEN** the stock SHALL be excluded from the candidate pool

#### Scenario: Filter by limit up/down status
- **WHEN** a stock is at limit up and `exclude_limit_up` is true, or at limit down and `exclude_limit_down` is true
- **THEN** the stock SHALL be excluded from the candidate pool

#### Scenario: Filter by listing duration
- **WHEN** a stock has been listed for fewer than `min_list_days` (250) trading days
- **THEN** the stock SHALL be excluded from the candidate pool

#### Scenario: Filter suspended stocks
- **WHEN** a stock is currently suspended and `exclude_suspended` is true
- **THEN** the stock SHALL be excluded from the candidate pool

### Requirement: Screening result output
The `StockScreener` SHALL return a structured result containing: passed stock list, excluded stock list with exclusion reasons, and per-dimension statistics.

#### Scenario: Full screening result structure
- **WHEN** `screener.screen()` completes for a 300-stock universe
- **THEN** the result SHALL contain `passed` (list of symbols), `excluded` (list of {symbol, reasons[]}), and `stats` ({total, passed_count, excluded_count, dimension_breakdown: {dimension: excluded_count}})

### Requirement: Stock metrics data sync
The system SHALL provide a `MetricsSyncer` class in `data/sync.py` that batch-fetches slow-changing stock metrics (market cap, PE/PB, ROE, debt ratio, cashflow, listing date) from data sources and writes them to SQLite `stock_metrics` table.

#### Scenario: Sync when cache is stale
- **WHEN** `sync_if_stale()` is called and the cached data in `stock_metrics` table has expired (TTL=1 day, configurable)
- **THEN** the system SHALL batch-fetch metrics from data sources and upsert into `stock_metrics` table

#### Scenario: Skip sync when cache is fresh
- **WHEN** `sync_if_stale()` is called and the cached data is within TTL
- **THEN** the system SHALL return cached data without external API calls

#### Scenario: API rate limit protection during sync
- **WHEN** batch-fetching metrics for 300+ stocks
- **THEN** the system SHALL insert a delay (0.3-0.5s) between requests and retry up to 3 times on failure

### Requirement: Stock metrics cache table
The `DataCache` class SHALL maintain a `stock_metrics` table in SQLite with columns: symbol (PK), name, industry, list_date, market_cap, pe, pb, roe, debt_ratio, revenue, operating_cashflow, synced_at.

#### Scenario: Batch query metrics
- **WHEN** `cache.get_metrics(symbols)` is called with a list of symbols
- **THEN** the system SHALL return a DataFrame with all columns for matching symbols, or None if data is stale or missing

#### Scenario: Upsert metrics
- **WHEN** `cache.upsert_metrics(df)` is called with a DataFrame
- **THEN** the system SHALL insert new rows or update existing rows by symbol primary key

### Requirement: Stock pool snapshots
The `DataCache` class SHALL maintain a `stock_pools` table to persist daily stock pool snapshots. Each record is immutable once created.

#### Scenario: Save stock pool snapshot
- **WHEN** the daily sync fetches the stock list for a universe (e.g., "hs300")
- **THEN** the system SHALL insert a new record into `stock_pools` (pool_id, universe, symbols as JSON array, count, synced_at)

#### Scenario: Query latest pool for universe
- **WHEN** `cache.get_latest_pool(universe)` is called
- **THEN** the system SHALL return the most recent `stock_pools` record for that universe

#### Scenario: Query pool by ID
- **WHEN** `cache.get_pool(pool_id)` is called
- **THEN** the system SHALL return the specified pool record with its symbol list

### Requirement: Daily scheduled sync
The system SHALL provide a `DataScheduler` class in `data/scheduler.py` that runs a daily sync job after market close (configurable, default 15:30).

#### Scenario: Daily sync execution
- **WHEN** the scheduled time is reached
- **THEN** the system SHALL execute in sequence: sync stock pool snapshot → sync slow metrics for the pool → run pre-screening → save results to DB

#### Scenario: Pipeline fallback when data is stale
- **WHEN** `pipeline.run()` is called and the latest screening result is older than 1 day
- **THEN** the pipeline SHALL trigger a fresh sync + screening before proceeding

#### Scenario: Manual trigger
- **WHEN** `POST /api/v1/screener/run` is called
- **THEN** the system SHALL execute the same sync + screening flow regardless of schedule

### Requirement: DataSource get_stock_metrics interface
The `DataSource` abstract class SHALL define a `get_stock_metrics(symbols: List[str]) -> DataFrame` method that batch-fetches pre-screening metrics.

#### Scenario: Akshare implementation
- **WHEN** `AkshareSource.get_stock_metrics()` is called
- **THEN** it SHALL return a DataFrame with columns: symbol, name, industry, market_cap, pe, pb, list_date, and financial data from akshare APIs

#### Scenario: Baostock implementation
- **WHEN** `BaostockSource.get_stock_metrics()` is called
- **THEN** it SHALL return a DataFrame with columns: symbol, roe, debt_ratio, revenue, operating_cashflow from baostock profit/cashflow APIs

### Requirement: Pipeline integration
The `StockSelectionPipeline` SHALL call the screener after fetching the stock list and before LLM Agent analysis, and persist screening results to database.

#### Scenario: Pipeline with pre-screening
- **WHEN** `pipeline.run(universe="hs300")` is called
- **THEN** the pipeline SHALL execute: `get_stock_list` → `metrics_sync.sync_if_stale` → `screener.screen` → `save_screening_result to DB` → `agents.analyze(candidates from DB)` → `quant.filter_and_rank`

#### Scenario: Pipeline preserves original flow when screener is disabled
- **WHEN** `pipeline.run(universe="hs300", skip_screener=True)` is called
- **THEN** the pipeline SHALL skip the pre-screening step and pass the full stock list to agents

#### Scenario: LLM reads candidates from database
- **WHEN** agents start analysis after a screening run
- **THEN** the agent layer SHALL read the passed stock list from `screening_stocks` table by `screening_id`, not from in-memory state

#### Scenario: Resume after LLM failure
- **WHEN** LLM analysis fails midway and pipeline is restarted
- **THEN** the pipeline SHALL detect the latest `screening_results` record and reuse it without re-running the screener

### Requirement: Screening results persistence
The `DataCache` class SHALL maintain `screening_results` and `screening_stocks` tables to persist every screening run's outcome.

#### Scenario: Save screening result after run
- **WHEN** `screener.screen()` completes successfully
- **THEN** the system SHALL insert a record into `screening_results` (screening_id, pool_id FK, universe, total_count, passed_count, excluded_count, dimension_breakdown as JSON, created_at) and one record per stock into `screening_stocks` (screening_id, symbol, name, passed, exclusion_reasons as JSON, market_cap, pe, pb, roe, price)

#### Scenario: Query latest screening result
- **WHEN** `cache.get_latest_screening()` is called
- **THEN** the system SHALL return the most recent `screening_results` record with its associated `screening_stocks` records

#### Scenario: Query screening result by ID
- **WHEN** `cache.get_screening(screening_id)` is called
- **THEN** the system SHALL return the specified screening result with all associated stock records

#### Scenario: Query historical screening results
- **WHEN** `cache.list_screenings(limit=10)` is called
- **THEN** the system SHALL return the latest N screening results ordered by created_at DESC, with summary stats (no stock details)

### Requirement: Pre-screening API endpoints
The system SHALL expose REST API endpoints for pre-screening operations.

#### Scenario: Trigger screening
- **WHEN** `POST /api/v1/screener/run` is called with `{universe: "hs300"}`
- **THEN** the system SHALL start an async screening task and return `{task_id, status: "running"}`

#### Scenario: Get screening result
- **WHEN** `GET /api/v1/screener/result` is called (optional query param `screening_id`)
- **THEN** the system SHALL return the specified (or latest if no ID) screening result with passed stocks, excluded stocks with reasons, key metrics, and dimension statistics

#### Scenario: Get screening statistics
- **WHEN** `GET /api/v1/screener/stats` is called
- **THEN** the system SHALL return aggregate statistics: {total, passed_count, excluded_count, dimension_breakdown: {dimension: count}, synced_at}

#### Scenario: Get screening history
- **WHEN** `GET /api/v1/screener/history?limit=10` is called
- **THEN** the system SHALL return a list of recent screening summaries: [{screening_id, universe, total_count, passed_count, created_at}]

### Requirement: Frontend screening page
The system SHALL provide a dedicated Screening page at `web/src/pages/Screening/` with its own navigation entry, displaying pre-screening results including summary cards, dimension breakdown chart, result table, and history.

#### Scenario: Navigation entry for screening page
- **WHEN** the application loads
- **THEN** the navigation bar SHALL include a "预筛分析" entry linking to the Screening page, positioned between "选股看板" and "回测分析"

#### Scenario: Screening page shows summary cards
- **WHEN** user navigates to the Screening page
- **THEN** the page SHALL display 3 summary cards: "原始股票池 (300)", "通过预筛 (80)", "被过滤 (220)"

#### Scenario: Screening page shows dimension breakdown
- **WHEN** screening stats are available
- **THEN** the page SHALL display an ECharts horizontal bar chart showing how many stocks were excluded by each dimension (e.g., "ST: 15, 市值: 30, 流动性: 20...")

#### Scenario: Screening page shows result table
- **WHEN** screening results are loaded
- **THEN** the page SHALL show an Ant Design Table listing all stocks with columns: symbol, name, market_cap, PE, PB, ROE, price, pass/fail status, sortable and filterable by each column

#### Scenario: Screening page shows history
- **WHEN** user clicks the history section
- **THEN** the page SHALL show a list of past screening runs with date, universe, passed/excluded counts, allowing comparison between runs
