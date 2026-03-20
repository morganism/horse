# lib/db_reader.rb
# Read-only access to the Python simulation SQLite database.
# Sinatra reads directly — no Python subprocess needed for queries.

require 'sqlite3'
require 'json'

class DBReader
  DEFAULT_DB = File.expand_path('../../py/data/horse_racing.db', __FILE__)

  def initialize(db_path = DEFAULT_DB)
    @db_path = db_path
  end

  def connected?
    File.exist?(@db_path)
  end

  # ── Races ──────────────────────────────────────────────────────────────────

  def races(page: 1, per_page: 30, race_type: nil, sim_day: nil)
    where = []
    params = []
    where << 'r.race_type = ?' and params << race_type if race_type
    where << 'r.sim_day = ?'  and params << sim_day    if sim_day
    cond = where.empty? ? '' : "WHERE #{where.join(' AND ')}"
    offset = (page - 1) * per_page
    query(<<~SQL, *params, per_page, offset)
      SELECT r.*, v.name AS venue_name, v.country
      FROM races r JOIN venues v ON r.venue_id = v.id
      #{cond}
      ORDER BY r.sim_day DESC, r.race_time ASC
      LIMIT ? OFFSET ?
    SQL
  end

  def race(id)
    query_one('SELECT r.*, v.name AS venue_name, v.country FROM races r JOIN venues v ON r.venue_id = v.id WHERE r.id = ?', id)
  end

  def race_runners(race_id)
    query(<<~SQL, race_id)
      SELECT ru.*, h.name AS horse_name, h.trainer, h.sire,
             rr.position, rr.btn_lengths
      FROM runners ru
      JOIN horses h ON ru.horse_id = h.id
      LEFT JOIN race_results rr ON rr.runner_id = ru.id
      WHERE ru.race_id = ?
      ORDER BY COALESCE(rr.position, 99), ru.favourite_rank
    SQL
  end

  def race_odds_history(race_id)
    query(<<~SQL, race_id)
      SELECT oh.*, ru.cloth_number, h.name AS horse_name
      FROM odds_history oh
      JOIN runners ru ON oh.runner_id = ru.id
      JOIN horses h ON ru.horse_id = h.id
      WHERE oh.race_id = ?
      ORDER BY ru.cloth_number, oh.hours_before DESC
    SQL
  end

  def races_count
    query_one('SELECT COUNT(*) AS n FROM races')[:n]
  end

  # ── Horses ─────────────────────────────────────────────────────────────────

  def horses(page: 1, per_page: 40, search: nil)
    params = []
    cond = ''
    if search && !search.empty?
      cond = "WHERE h.name LIKE ?"
      params << "%#{search}%"
    end
    offset = (page - 1) * per_page
    query(<<~SQL, *params, per_page, offset)
      SELECT h.*,
             COUNT(DISTINCT ru.id) AS total_runs,
             SUM(CASE WHEN rr.position = 1 THEN 1 ELSE 0 END) AS total_wins
      FROM horses h
      LEFT JOIN runners ru ON ru.horse_id = h.id
      LEFT JOIN race_results rr ON rr.runner_id = ru.id
      #{cond}
      GROUP BY h.id
      ORDER BY total_wins DESC, h.name ASC
      LIMIT ? OFFSET ?
    SQL
  end

  def horse(id)
    query_one(<<~SQL, id)
      SELECT h.*,
             COUNT(DISTINCT ru.id) AS total_runs,
             SUM(CASE WHEN rr.position = 1 THEN 1 ELSE 0 END) AS total_wins
      FROM horses h
      LEFT JOIN runners ru ON ru.horse_id = h.id
      LEFT JOIN race_results rr ON rr.runner_id = ru.id
      WHERE h.id = ?
      GROUP BY h.id
    SQL
  end

  def horse_recent_runs(horse_id, limit: 10)
    query(<<~SQL, horse_id, limit)
      SELECT r.race_date, r.race_time, r.race_type, r.going, r.distance_furlongs,
             v.name AS venue_name, ru.sp, ru.weight_lbs, ru.jockey,
             rr.position, rr.btn_lengths
      FROM runners ru
      JOIN races r ON ru.race_id = r.id
      JOIN venues v ON r.venue_id = v.id
      LEFT JOIN race_results rr ON rr.runner_id = ru.id
      WHERE ru.horse_id = ?
      ORDER BY r.race_date DESC, r.race_time DESC
      LIMIT ?
    SQL
  end

  def horse_h2h(horse_id)
    query(<<~SQL, horse_id, horse_id)
      SELECT ha.name AS horse_a, hb.name AS horse_b,
             hr.meetings, hr.horse_a_ahead, hr.horse_b_ahead
      FROM horse_relationships hr
      JOIN horses ha ON hr.horse_a_id = ha.id
      JOIN horses hb ON hr.horse_b_id = hb.id
      WHERE hr.horse_a_id = ? OR hr.horse_b_id = ?
      ORDER BY hr.meetings DESC
      LIMIT 20
    SQL
  end

  # ── Venues ─────────────────────────────────────────────────────────────────

  def venues
    query(<<~SQL)
      SELECT v.*,
             COUNT(DISTINCT r.id) AS race_count,
             AVG(r.runner_count) AS avg_field_size
      FROM venues v
      LEFT JOIN races r ON r.venue_id = v.id
      GROUP BY v.id
      ORDER BY race_count DESC
    SQL
  end

  # ── Strategies ─────────────────────────────────────────────────────────────

  def strategies(sort: 'roi', dir: nil, page: 1, per_page: 50, strategy_class: nil)
    valid_sorts = %w[roi profit_loss total_bets wins strike_rate sharpe max_drawdown]
    sort = 'roi' unless valid_sorts.include?(sort)
    # Allow caller to override direction; default is DESC for most metrics,
    # ASC for drawdown (lower is better).
    default_dir = sort == 'max_drawdown' ? 'ASC' : 'DESC'
    direction   = %w[asc desc].include?(dir.to_s.downcase) ? dir.upcase : default_dir

    cond = strategy_class ? 'WHERE s.strategy_class = ?' : ''
    params = strategy_class ? [strategy_class] : []
    offset = (page - 1) * per_page

    query(<<~SQL, *params, per_page, offset)
      SELECT sp.*, s.strategy_class, s.variant_name, s.params_json
      FROM strategy_performance sp
      JOIN strategies s ON sp.strategy_id = s.id
      WHERE sp.sim_day = (
        SELECT MAX(sim_day) FROM strategy_performance sp2
        WHERE sp2.strategy_id = sp.strategy_id
      )
      #{cond.empty? ? '' : "AND s.strategy_class = ?"}
      ORDER BY sp.#{sort} #{direction} NULLS LAST
      LIMIT ? OFFSET ?
    SQL
  end

  def strategy(id)
    query_one(<<~SQL, id)
      SELECT sp.*, s.strategy_class, s.variant_name, s.params_json, s.created_at
      FROM strategy_performance sp
      JOIN strategies s ON sp.strategy_id = s.id
      WHERE sp.strategy_id = ?
      ORDER BY sp.sim_day DESC LIMIT 1
    SQL
  end

  def strategy_daily_pl(strategy_id)
    query(<<~SQL, strategy_id)
      SELECT r.sim_day,
             SUM(b.stake) AS staked,
             SUM(COALESCE(b.payout, 0)) AS returned,
             SUM(COALESCE(b.payout, 0)) - SUM(b.stake) AS pl,
             COUNT(*) AS bets,
             SUM(CASE WHEN b.status = 'won' THEN 1 ELSE 0 END) AS wins
      FROM bets b JOIN races r ON b.race_id = r.id
      WHERE b.strategy_id = ? AND b.status != 'pending'
      GROUP BY r.sim_day ORDER BY r.sim_day
    SQL
  end

  def strategy_recent_bets(strategy_id, limit: 20)
    query(<<~SQL, strategy_id, limit)
      SELECT b.*, r.race_date, r.race_type, r.going,
             v.name AS venue_name, s.variant_name
      FROM bets b
      JOIN races r ON b.race_id = r.id
      JOIN venues v ON r.venue_id = v.id
      JOIN strategies s ON b.strategy_id = s.id
      WHERE b.strategy_id = ? AND b.status != 'pending'
      ORDER BY r.sim_day DESC, r.race_time DESC
      LIMIT ?
    SQL
  end

  def strategy_classes
    query('SELECT strategy_class, COUNT(*) AS n FROM strategies GROUP BY strategy_class ORDER BY n DESC')
  end

  # ── Performance Summary ────────────────────────────────────────────────────

  def performance_summary
    query_one(<<~SQL)
      SELECT
        COUNT(DISTINCT s.id) AS total_strategies,
        COUNT(b.id) AS total_bets,
        SUM(b.stake) AS total_staked,
        SUM(COALESCE(b.payout, 0)) AS total_returned,
        SUM(COALESCE(b.payout, 0)) - SUM(b.stake) AS total_pl,
        SUM(CASE WHEN b.status = 'won' THEN 1 ELSE 0 END) AS total_wins,
        MAX(r.sim_day) AS max_day
      FROM bets b
      JOIN races r ON b.race_id = r.id
      JOIN strategies s ON b.strategy_id = s.id
      WHERE b.status != 'pending'
    SQL
  end

  def daily_pl_series
    query(<<~SQL)
      SELECT r.sim_day, r.race_date,
             SUM(b.stake) AS staked,
             SUM(COALESCE(b.payout, 0)) AS returned,
             SUM(COALESCE(b.payout, 0)) - SUM(b.stake) AS pl,
             COUNT(*) AS bets
      FROM bets b JOIN races r ON b.race_id = r.id
      WHERE b.status != 'pending'
      GROUP BY r.sim_day ORDER BY r.sim_day
    SQL
  end

  def top_strategies(n: 5)
    query(<<~SQL, n)
      SELECT sp.roi, sp.profit_loss, sp.total_bets, sp.wins,
             s.strategy_class, s.variant_name
      FROM strategy_performance sp
      JOIN strategies s ON sp.strategy_id = s.id
      WHERE sp.sim_day = (SELECT MAX(sim_day) FROM strategy_performance sp2 WHERE sp2.strategy_id = sp.strategy_id)
        AND sp.total_bets >= 10
      ORDER BY sp.roi DESC NULLS LAST
      LIMIT ?
    SQL
  end

  # ── Bayesian / Correlations ────────────────────────────────────────────────

  def hypothesis(type: nil, min_evidence: 3, limit: 50)
    cond = type ? "AND hypothesis_type = '#{type.gsub("'", '')}'" : ''
    query(<<~SQL, min_evidence, limit)
      SELECT * FROM hypothesis
      WHERE evidence_count >= ? #{cond}
      ORDER BY confidence DESC
      LIMIT ?
    SQL
  end

  def beta_horses(min_meetings: 3)
    query(<<~SQL, min_meetings)
      SELECT hr.meetings, hr.horse_a_ahead, hr.horse_b_ahead,
             ha.name AS horse_a, hb.name AS horse_b,
             ROUND(hr.horse_a_ahead * 1.0 / hr.meetings, 3) AS dominance
      FROM horse_relationships hr
      JOIN horses ha ON hr.horse_a_id = ha.id
      JOIN horses hb ON hr.horse_b_id = hb.id
      WHERE hr.meetings >= ?
        AND (hr.horse_a_ahead * 1.0 / hr.meetings >= 0.8
             OR hr.horse_b_ahead * 1.0 / hr.meetings >= 0.8)
      ORDER BY dominance DESC
      LIMIT 30
    SQL
  end

  def top_trainer_jockey(limit: 20)
    query(<<~SQL, limit)
      SELECT trainer, jockey, wins, runs, win_rate
      FROM trainer_jockey_stats
      WHERE runs >= 5
      ORDER BY win_rate DESC, runs DESC
      LIMIT ?
    SQL
  end

  # ── Simulation metadata ────────────────────────────────────────────────────

  def sim_days
    query_one('SELECT MIN(sim_day) AS first_day, MAX(sim_day) AS last_day, COUNT(DISTINCT sim_day) AS total_days FROM races')
  end

  def bankroll_history(strategy_id)
    query('SELECT * FROM bankroll_snapshots WHERE strategy_id = ? ORDER BY sim_day', strategy_id)
  end

  private

  def db
    @db ||= begin
      raise "Database not found: #{@db_path}" unless File.exist?(@db_path)
      conn = SQLite3::Database.new(@db_path, readonly: true)
      conn.results_as_hash = true
      conn
    end
  end

  def query(sql, *params)
    db.execute(sql, params).map { |row| symbolize(row) }
  rescue SQLite3::Exception => e
    warn "DBReader query error: #{e.message}"
    []
  end

  def query_one(sql, *params)
    row = db.get_first_row(sql, params)
    row ? symbolize(row) : nil
  rescue SQLite3::Exception => e
    warn "DBReader query_one error: #{e.message}"
    nil
  end

  def symbolize(hash)
    hash.transform_keys { |k| k.to_sym rescue k }
  end
end
