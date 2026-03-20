# lib/auth.rb
# Session authentication helpers using TOTPGuard.
# Exposes helpers for use in Sinatra routes.

require 'fileutils'
require_relative 'totp_guard'
require_relative 'totp'

module Auth
  AUTH_DB = File.expand_path('../../data/auth.db', __FILE__).tap do |path|
    FileUtils.mkdir_p(File.dirname(path))
  end

  def self.guard
    @guard ||= TOTPGuard::Guard.new(db_path: AUTH_DB)
  end

  # Returns the currently logged-in username, or nil.
  def self.current_user(session)
    return nil unless session[:user] && session[:authenticated_at]
    # Expire sessions after 8 hours
    if Time.now.to_i - session[:authenticated_at].to_i > 28_800
      session.clear
      return nil
    end
    session[:user]
  end

  # Attempt TOTP login. Returns [:ok, nil] or [:error, message].
  def self.login(username, code, session)
    result = guard.authenticate(username, code)
    if result.success?
      session[:user]             = username
      session[:authenticated_at] = Time.now.to_i
      [:ok, nil]
    else
      [:error, 'Invalid code or unknown user']
    end
  end

  def self.logout(session)
    session.clear
  end

  # True when at least one user is provisioned.
  def self.any_users?
    guard.count > 0
  end

  # True when username already exists in the store.
  def self.user_exists?(username)
    !guard.secret_for(username).nil?
  end

  # Provision a new user with a fresh TOTP secret. Returns the secret.
  def self.provision(username)
    secret = TOTP.generate_secret
    guard.add(username, secret)
    secret
  end
end

# Sinatra helper mixin
module AuthHelpers
  def current_user
    Auth.current_user(session)
  end

  def logged_in?
    !current_user.nil?
  end

  def require_login!
    unless logged_in?
      session[:return_to] = request.path_info
      redirect '/login'
    end
  end
end
