-- Horse Racing Strategy Simulation Schema
-- All tables use IF NOT EXISTS for idempotent migrations

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL,          -- "GB" | "IE"
    surface TEXT NOT NULL,          -- "turf" | "aw"
    race_types TEXT NOT NULL,       -- JSON array: ["flat","hurdle","chase"]
    straight_furlongs REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS races (
    id INTEGER PRIMARY KEY,
    venue_id INTEGER NOT NULL REFERENCES venues(id),
    sim_day INTEGER NOT NULL,
    race_date TEXT NOT NULL,        -- ISO8601
    race_time TEXT NOT NULL,        -- "14:30"
    race_name TEXT,
    race_type TEXT NOT NULL,        -- "flat" | "hurdle" | "chase" | "bumper"
    class INTEGER,                  -- 1=Group1 .. 6=seller
    distance_furlongs REAL NOT NULL,
    going TEXT NOT NULL,
    prize_gbp INTEGER,
    runner_count INTEGER NOT NULL,
    is_handicap INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS horses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    age INTEGER,
    sex TEXT,                       -- G/M/F/C/H
    trainer TEXT,
    owner TEXT,
    sire TEXT,
    dam TEXT
);

CREATE TABLE IF NOT EXISTS runners (
    id INTEGER PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(id),
    horse_id INTEGER NOT NULL REFERENCES horses(id),
    jockey TEXT,
    cloth_number INTEGER,
    weight_lbs INTEGER,
    official_rating INTEGER,
    days_since_last_run INTEGER,
    career_wins INTEGER DEFAULT 0,
    career_runs INTEGER DEFAULT 0,
    course_wins INTEGER DEFAULT 0,
    distance_wins INTEGER DEFAULT 0,
    going_wins INTEGER DEFAULT 0,
    latent_ability REAL,            -- true hidden ability (not exposed to strategies)
    morning_price REAL,             -- early fractional decimal odds
    sp REAL,                        -- starting price decimal
    favourite_rank INTEGER          -- 1=favourite
);

CREATE TABLE IF NOT EXISTS race_results (
    id INTEGER PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(id),
    runner_id INTEGER NOT NULL REFERENCES runners(id),
    position INTEGER NOT NULL,
    btn_lengths REAL DEFAULT 0,
    finish_time_secs REAL
);

CREATE TABLE IF NOT EXISTS odds_history (
    id INTEGER PRIMARY KEY,
    runner_id INTEGER NOT NULL REFERENCES runners(id),
    race_id INTEGER NOT NULL REFERENCES races(id),
    recorded_at TEXT NOT NULL,
    hours_before REAL,              -- hours before race_off (4.0 = 4hrs before)
    odds REAL NOT NULL,
    movement TEXT                   -- "drift" | "shorten" | "stable"
);

-- Strategy registry
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY,
    strategy_class TEXT NOT NULL,
    variant_name TEXT NOT NULL UNIQUE,
    params_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Betting ledger
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    race_id INTEGER NOT NULL REFERENCES races(id),
    bet_type TEXT NOT NULL,         -- "win"|"place"|"exacta"|"trifecta"|"dutch"
    runner_ids TEXT NOT NULL,       -- JSON array, order matters for exacta/trifecta
    stake REAL NOT NULL,
    odds_taken REAL NOT NULL,       -- combined odds for the bet
    potential_return REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    payout REAL,
    rationale TEXT,
    placed_at TEXT NOT NULL DEFAULT (datetime('now')),
    settled_at TEXT
);

CREATE TABLE IF NOT EXISTS bankroll_snapshots (
    id INTEGER PRIMARY KEY,
    sim_day INTEGER NOT NULL,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    balance REAL NOT NULL,
    total_staked REAL NOT NULL DEFAULT 0,
    total_returned REAL NOT NULL DEFAULT 0,
    snapshot_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS strategy_performance (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    sim_day INTEGER NOT NULL,
    total_bets INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    roi REAL,
    strike_rate REAL,
    sharpe REAL,
    max_drawdown REAL,
    profit_loss REAL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(strategy_id, sim_day)
);

-- Bayesian knowledge base
CREATE TABLE IF NOT EXISTS horse_relationships (
    id INTEGER PRIMARY KEY,
    horse_a_id INTEGER NOT NULL REFERENCES horses(id),
    horse_b_id INTEGER NOT NULL REFERENCES horses(id),
    meetings INTEGER NOT NULL DEFAULT 0,
    horse_a_ahead INTEGER NOT NULL DEFAULT 0,   -- times A finished ahead of B
    horse_b_ahead INTEGER NOT NULL DEFAULT 0,
    last_updated TEXT,
    UNIQUE(horse_a_id, horse_b_id)
);

CREATE TABLE IF NOT EXISTS trainer_jockey_stats (
    id INTEGER PRIMARY KEY,
    trainer TEXT NOT NULL,
    jockey TEXT NOT NULL,
    wins INTEGER NOT NULL DEFAULT 0,
    runs INTEGER NOT NULL DEFAULT 0,
    win_rate REAL,
    last_updated TEXT,
    UNIQUE(trainer, jockey)
);

CREATE TABLE IF NOT EXISTS hypothesis (
    id INTEGER PRIMARY KEY,
    hypothesis_type TEXT NOT NULL,  -- "trainer_jockey"|"weight_drop"|"h2h"|"course_specialist"
    subject_key TEXT NOT NULL,
    alpha REAL NOT NULL DEFAULT 1.0,
    beta_param REAL NOT NULL DEFAULT 1.0,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    confidence REAL,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(hypothesis_type, subject_key)
);

-- Real-race predictions (live betting tracking — source='real' vs sim bets)
CREATE TABLE IF NOT EXISTS real_race_predictions (
    id INTEGER PRIMARY KEY,
    race_date TEXT NOT NULL,            -- ISO8601 date "YYYY-MM-DD"
    venue TEXT NOT NULL,
    race_time TEXT NOT NULL,            -- "14:30"
    horse_name TEXT NOT NULL,
    strategy_class TEXT NOT NULL,
    bet_type TEXT NOT NULL,             -- "win"|"each_way"|"dutch"
    stake_pct REAL NOT NULL,            -- % of bankroll
    predicted_position INTEGER,         -- expected finish position
    confidence REAL,                    -- 0.0–1.0
    sp_at_tip REAL,                     -- odds when prediction made
    actual_position INTEGER,            -- filled on settlement
    profit_loss REAL,                   -- filled on settlement (£ based on £5 bankroll)
    settled INTEGER NOT NULL DEFAULT 0, -- 0=pending, 1=settled
    source TEXT NOT NULL DEFAULT 'real',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    settled_at TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_real_preds_date ON real_race_predictions(race_date);
CREATE INDEX IF NOT EXISTS idx_races_day    ON races(sim_day);
CREATE INDEX IF NOT EXISTS idx_races_venue  ON races(venue_id);
CREATE INDEX IF NOT EXISTS idx_runners_race ON runners(race_id);
CREATE INDEX IF NOT EXISTS idx_runners_horse ON runners(horse_id);
CREATE INDEX IF NOT EXISTS idx_results_race ON race_results(race_id);
CREATE INDEX IF NOT EXISTS idx_bets_strategy ON bets(strategy_id);
CREATE INDEX IF NOT EXISTS idx_bets_status  ON bets(status);
CREATE INDEX IF NOT EXISTS idx_odds_runner  ON odds_history(runner_id);
CREATE INDEX IF NOT EXISTS idx_perf_strategy ON strategy_performance(strategy_id);
