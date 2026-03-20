require 'sinatra'
require 'sinatra/reloader' if development?

# .presence (ActiveSupport analogue — not pulling in Rails)
# Works on String (blank→nil), NilClass (always nil), and anything else.
class String
  def presence = empty? ? nil : self
end unless String.method_defined?(:presence)

class NilClass
  def presence = nil
end

class Object
  def presence = self
end unless Object.method_defined?(:presence)
require 'sinatra/json'
require 'json'
require 'redcarpet'

$LOAD_PATH.unshift(File.join(__dir__, 'lib'))
require 'cgi'
require 'db_reader'
require 'python_runner'
require 'auth'
require 'sortable_table'
require 'strategy_matcher'

# ── Configuration ────────────────────────────────────────────────────────────

configure do
  enable :sessions
  set :session_secret, ENV.fetch('SESSION_SECRET') { SecureRandom.hex(64) }
  set :views,    File.join(__dir__, 'views')
  set :public_folder, File.join(__dir__, 'public')
  set :db_path,  ENV.fetch('HORSE_DB') { File.expand_path('py/data/horse_racing.db', __dir__) }
end

configure :development do
  also_reload 'lib/*.rb'
end

helpers AuthHelpers
helpers SortableTable

helpers do
  def db
    @_db ||= DBReader.new(settings.db_path)
  end

  def runner
    @_runner ||= PythonRunner.new(db_path: settings.db_path)
  end

  def markdown(text)
    md = Redcarpet::Markdown.new(
      Redcarpet::Render::HTML.new(tables: true, hard_wrap: true),
      tables: true, fenced_code_blocks: true, autolink: true,
      strikethrough: true, no_intra_emphasis: true
    )
    md.render(text)
  end
end

# ── Auth ─────────────────────────────────────────────────────────────────────

get '/login' do
  redirect '/' if logged_in?
  @title = 'Sign In'
  @username = params[:username]
  @error = nil
  erb :login, layout: :layout
end

post '/login' do
  status, msg = Auth.login(params[:username].to_s.strip, params[:code].to_s.strip, session)
  if status == :ok
    redirect(session[:return_to] || '/')
  else
    @title = 'Sign In'
    @username = params[:username]
    @error = msg
    erb :login, layout: :layout
  end
end

get '/logout' do
  Auth.logout(session)
  redirect '/login'
end

# ── Dashboard ─────────────────────────────────────────────────────────────────

get '/' do
  require_login!
  @summary        = db.performance_summary
  @daily_pl       = db.daily_pl_series
  @top_strategies = db.top_strategies(n: 5)
  @sim_days       = db.sim_days
  erb :dashboard
end

# ── Races ─────────────────────────────────────────────────────────────────────

get '/races' do
  require_login!
  @page      = [params[:page].to_i, 1].max
  @races     = db.races(page: @page, per_page: 30,
                         race_type: params[:race_type].presence,
                         sim_day:   params[:sim_day].presence&.to_i)
  @total     = db.races_count
  erb :races
end

get '/races/:id' do
  require_login!
  @race         = db.race(params[:id].to_i)
  halt 404, 'Race not found' unless @race
  @runners      = db.race_runners(params[:id].to_i)
  @odds_history = db.race_odds_history(params[:id].to_i)
  erb :race
end

# ── Horses ────────────────────────────────────────────────────────────────────

get '/horses' do
  require_login!
  @page   = [params[:page].to_i, 1].max
  @horses = db.horses(page: @page, per_page: 40, search: params[:search].presence)
  erb :horses
end

get '/horses/:id' do
  require_login!
  @horse       = db.horse(params[:id].to_i)
  halt 404, 'Horse not found' unless @horse
  @recent_runs = db.horse_recent_runs(params[:id].to_i, limit: 15)
  @h2h         = db.horse_h2h(params[:id].to_i)
  erb :horse
end

# ── Strategies ────────────────────────────────────────────────────────────────

get '/strategies' do
  require_login!
  @page             = [params[:page].to_i, 1].max
  @sort_col         = params[:sort] || 'roi'
  @sort_dir         = params[:dir]  || 'desc'
  @strategies       = db.strategies(sort:           @sort_col,
                                     dir:            @sort_dir,
                                     page:           @page,
                                     per_page:       50,
                                     strategy_class: params[:strategy_class].presence)
  @strategy_classes = db.strategy_classes
  erb :strategies
end

get '/strategies/:id' do
  require_login!
  @strategy   = db.strategy(params[:id].to_i)
  halt 404, 'Strategy not found' unless @strategy
  @daily_pl   = db.strategy_daily_pl(params[:id].to_i)
  @recent_bets = db.strategy_recent_bets(params[:id].to_i, limit: 30)
  erb :strategy
end

# ── Correlations ──────────────────────────────────────────────────────────────

get '/correlations' do
  require_login!
  type         = params[:type].presence
  type         = nil if type == 'all'
  @hypotheses  = db.hypothesis(type: type, min_evidence: 3, limit: 100)
  @beta_horses = db.beta_horses(min_meetings: 3)
  @trainer_jockey = db.top_trainer_jockey(limit: 20)
  erb :correlations
end

# ── Rota ──────────────────────────────────────────────────────────────────────

get '/rota' do
  require_login!
  rota_path  = File.join(__dir__, 'ROTA.md')
  rota_text  = File.exist?(rota_path) ? File.read(rota_path, encoding: 'UTF-8') : '# ROTA.md not found'
  @rota_html = markdown(rota_text)
  erb :rota
end

# ── Calendar ─────────────────────────────────────────────────────────────────

get '/calendar' do
  require_login!
  # Default to the month containing the most recent sim race, not wall-clock today.
  @db_latest = Date.parse(db.latest_race_date)
  if params[:year] || params[:month]
    @year  = params[:year].to_i.nonzero?  || @db_latest.year
    @month = params[:month].to_i.nonzero? || @db_latest.month
  else
    @year, @month = @db_latest.year, @db_latest.month
  end
  @year, @month = @db_latest.year, @db_latest.month unless (1..12).include?(@month)
  @race_days = db.calendar_month(year: @year, month: @month)
  erb :calendar
end

get '/calendar/:date' do
  require_login!
  begin
    @date = Date.parse(params[:date])
  rescue ArgumentError
    halt 400, 'Invalid date'
  end
  @races     = db.races_on_date(@date.iso8601)
  @db_latest = Date.parse(db.latest_race_date)
  @is_latest = @date == @db_latest   # latest sim day — also run strategy matcher
  @is_real   = @date > @db_latest    # beyond sim data — real-world race day

  # Load strategy P&L for sim dates that have data
  @race_strategies = {}
  @races.each do |race|
    @race_strategies[race[:id]] = db.race_strategy_performance(race[:id])
  end

  # On the latest sim day, run strategy matcher
  if @is_latest
    hypos = db.hypothesis(min_evidence: 3, limit: 300)
    @match_results = {}
    @races.each do |race|
      runners = db.race_runners(race[:id])
      @match_results[race[:id]] = StrategyMatcher.new(runners, hypos).suggestions
    end
  end

  # Always load real-race predictions for the date (sim or real)
  @predictions = db.real_race_predictions(date: @date.iso8601)

  erb :calendar_day
end

# ── Predictions API ──────────────────────────────────────────────────────────

post '/api/predictions' do
  require_login!
  body  = JSON.parse(request.body.read) rescue {}
  required = %w[race_date venue race_time horse_name strategy_class bet_type stake_pct]
  missing  = required.reject { |k| body[k].to_s.strip.length > 0 }
  halt 422, json(error: "Missing fields: #{missing.join(', ')}") if missing.any?

  id = db.save_prediction(
    race_date:          body['race_date'],
    venue:              body['venue'],
    race_time:          body['race_time'],
    horse_name:         body['horse_name'],
    strategy_class:     body['strategy_class'],
    bet_type:           body['bet_type'],
    stake_pct:          body['stake_pct'].to_f,
    predicted_position: body['predicted_position']&.to_i,
    confidence:         body['confidence']&.to_f,
    sp_at_tip:          body['sp_at_tip']&.to_f
  )
  json id: id, status: 'saved'
end

post '/api/settle_prediction/:id' do
  require_login!
  body = JSON.parse(request.body.read) rescue {}
  halt 422, json(error: 'actual_position required') unless body['actual_position']
  db.settle_prediction(
    id:               params[:id].to_i,
    actual_position:  body['actual_position'].to_i,
    profit_loss:      body['profit_loss'].to_f
  )
  json status: 'settled'
end

# ── Simulation ────────────────────────────────────────────────────────────────

get '/simulation' do
  require_login!
  erb :simulation
end

# Streaming simulation endpoint — returns chunked text/plain
post '/api/simulate' do
  require_login!
  body_params = JSON.parse(request.body.read) rescue {}
  days = [[body_params['days'].to_i, 1].max, 365].min

  content_type 'text/plain'
  stream do |out|
    out << "Starting #{days}-day simulation…\n"
    result = runner.simulate(days: days) do |line|
      out << line + "\n"
    end
    out << (result[:success] ? "\nSimulation complete." : "\nError: #{result[:error]}")
  end
end

post '/api/reset' do
  require_login!
  result = runner.reset!
  json success: result[:success], error: result[:error]
end

# ── Strategy class descriptions ───────────────────────────────────────────────
STRATEGY_CLASS_INFO = {
  'DutchingEnvelope' => {
    colour: '#0d6efd',
    tagline: 'Cover multiple runners at a guaranteed return',
    description: 'Places proportional stakes across a selection of runners so that any winner returns the same profit. Uses level, proportional, or Kelly stake models. Profitable when the sum of implied probabilities (1/odds) across the covered field is below 1.0. Best suited to races where 2–4 runners dominate the market.',
    params: 'min_runners, max_runners, budget_pct, stake_model, min_field_prob'
  },
  'ExoticPermutation' => {
    colour: '#6f42c1',
    tagline: 'Exacta & trifecta permutation bets',
    description: 'Generates exacta (1st + 2nd) and trifecta (1st + 2nd + 3rd) combination bets using probability-ranked selections. Applies a market-efficiency factor (~0.70) to correct theoretical exotic payouts toward realistic bookmaker returns. High variance, high ceiling.',
    params: 'bet_type, top_n, market_efficiency, min_prob_edge'
  },
  'BayesianCorrelation' => {
    colour: '#20c997',
    tagline: 'Bayesian win-probability signals from priors',
    description: 'Maintains Beta-distribution priors (α, β) per trainer, jockey, going, and course combination. Updates after each race: α += 1 on win, β += 1 on loss. Bets when the posterior mean exceeds a configurable confidence threshold. Requires sufficient prior data (90+ days recommended).',
    params: 'confidence_threshold, min_evidence, hypothesis_type'
  },
  'OddsMovement' => {
    colour: '#fd7e14',
    tagline: 'Trade on significant pre-race odds drift',
    description: 'Monitors the odds_history table for runners whose price has shortened or drifted significantly in the hours before race-off. A shortening price (steam) suggests informed money; a drifting price suggests market weakness. Bets in the direction of the movement when the change exceeds a minimum threshold.',
    params: 'movement_threshold, hours_window, direction, min_sp'
  },
  'PatternRecognition' => {
    colour: '#ffc107',
    tagline: 'Form-cycle and rest-period pattern matching',
    description: 'Identifies horses whose recent form sequence and days-since-last-run match historically profitable patterns. Looks for improving sequences (e.g. 3rd → 2nd → win) and optimal freshness windows. Combines multiple pattern signals into a composite score.',
    params: 'pattern_type, days_since_run_min, days_since_run_max, min_form_score'
  },
  'FavouriteCover' => {
    colour: '#dc3545',
    tagline: 'Target short-priced course specialists',
    description: 'Focuses on runners priced at or below a maximum SP threshold (typically ≤ 3.0) who have demonstrated course-winning form. Offers win, each-way, or dutched top-2 bet types. Highest average simulated ROI (+78%) of all strategy classes — best used in fields of 8 or fewer.',
    params: 'max_sp, min_sp, bet_type, require_course_win'
  },
  'HandicapExploit' => {
    colour: '#6c757d',
    tagline: 'Weight sweet-spot in handicap races',
    description: 'Targets handicap runners carrying between 5 and 15 lbs below the top weight — a range empirically associated with favourable mark relative to ability. Filters by minimum official rating and race class. Currently under recalibration (ROI –49% in sim; issue #19).',
    params: 'weight_below_top_min, weight_below_top_max, min_rating, max_class'
  },
  'TrainerGoing' => {
    colour: '#17a2b8',
    tagline: 'Dual Bayesian signal: trainer × going × jockey',
    description: 'Combines two Bayesian hypotheses: (1) trainer win-rate on a specific going type, and (2) trainer–jockey partnership win-rate. The require_both flag controls whether both signals must fire (AND) or either is sufficient (OR). Needs 90+ days of data to build reliable posteriors.',
    params: 'min_confidence, require_both, min_evidence'
  }
}.freeze

# JSON endpoint — strategy class info for modal display
get '/api/strategy_class/:name' do
  require_login!
  info = STRATEGY_CLASS_INFO[params[:name]]
  halt 404, json(error: 'Unknown class') unless info
  json({ name: params[:name] }.merge(info))
end

# ── Health / API ──────────────────────────────────────────────────────────────

get '/health' do
  json(
    status: 'ok',
    db_connected: db.connected?,
    timestamp: Time.now.iso8601
  )
end

# Generic 404
not_found do
  status 404
  '<h1 style="font-family:monospace;padding:2rem;color:#999">404 — Not Found</h1>'
end
