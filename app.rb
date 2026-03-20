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
require 'db_reader'
require 'python_runner'
require 'auth'

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
  @strategies       = db.strategies(sort:           params[:sort] || 'roi',
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
