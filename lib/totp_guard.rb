# frozen_string_literal: true
#
# totp_guard.rb — 2FA authentication library
# Ruby port + enhancement of validator bash script
# Morgan / morganism  —  unix philosophy: do one thing well
#
# Ruby idioms demonstrated:
#   Blocks / yield       — Store#each, Authenticator#authenticate, Guard#protect
#   Proc / Lambda        — on_success/on_failure/on_missing callbacks, policy enforcement
#   method_missing       — Store dynamic account lookup  (store.github_morgan)
#   respond_to_missing?  — companion to method_missing
#   ObjectSpace          — live instance registry for Guard and Store
#   const_missing        — TOTPGuard::AppName auto-provisions a named Guard
#   Struct               — AuthResult immutable value object
#   Comparable           — AuthResult#<=> by timestamp
#   Enumerable           — Store collection protocol (map, select, min, count ...)
#   Refinements          — String#base32? predicate, String#account_key normaliser
#   Forwardable          — Guard cleanly delegates to Authenticator + Store
#   tap / then           — fluent pipeline chaining
#   Endless methods      — one-liner readers (Ruby 3.0+)
#   Numbered block param — _1 / _2 in short closures (Ruby 2.7+)
#
# USAGE:
#   require 'totp_guard'
#
#   guard = TOTPGuard.new
#   guard.add('alice@example.com', 'JBSWY3DPEHPK3PXP')
#   guard.on_success { |r| logger.info "2FA ok: #{r.account}" }
#   guard.on_failure { |r| logger.warn "2FA fail: #{r.account}" }
#   ok = guard.authenticate('alice@example.com', params[:code])
#
#   # Block form — result routed via yield:
#   guard.protect('alice@example.com', params[:code]) { |ok| ok ? serve : halt(401) }
#
#   # Bang form — raises on failure:
#   guard.authenticate!('alice@example.com', params[:code])
#
#   # DSL via const_missing:
#   TOTPGuard::MyApp.add('alice', secret)
#   TOTPGuard::MyApp.valid?('alice', code)

require 'sqlite3'
require 'openssl'
require 'fileutils'
require 'forwardable'
require 'time'

module TOTPGuard
  VERSION    = '1.0.0'
  DEFAULT_DB = File.join(Dir.home, '.local', 'share', 'totp', 'totp.db')

  # ── Refinements ─────────────────────────────────────────────────────────────
  # Activated per-file with `using TOTPGuard::StringRefinements`
  # Keeps String monkey-patching scoped — no global pollution.
  module StringRefinements
    BASE32_RE = /\A[A-Z2-7]+=*\z/i.freeze

    refine String do

      # Is this string a plausible TOTP base32 secret?
      def base32?
        length >= 16 && match?(BASE32_RE)
      end

      # Convert method-name identifiers back to account keys
      # github_morgan  →  github:morgan
      # aws_root       →  aws:root
      def account_key = gsub('_', ':')
    end
  end

  # ── TOTP Core ────────────────────────────────────────────────────────────────
  # Inlined so the library has zero non-stdlib/sqlite3 dependencies.
  # Mirrors the RFC 6238 implementation from the companion totp.rb.
  module Core
    ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'

    # Lambda — pure function, strict arity, frozen for safety
    decode_base32 = lambda do |str|
      str = str.upcase.tr('=', '')
      raise ArgumentError, "Not valid Base32" unless str.match?(/\A[A-Z2-7]*\z/)
      out, buf, bits = [], 0, 0
      str.each_char do |ch|
        val = ALPHABET.index(ch) or raise ArgumentError, "Invalid Base32 char: #{ch.inspect}"
        buf   = (buf << 5) | val
        bits += 5
        if bits >= 8
          bits -= 8
          out << ((buf >> bits) & 0xff)
        end
      end
      out.pack('C*')
    end

    # Store as a module constant lambda — callable everywhere in the module
    DECODE_BASE32 = decode_base32.freeze

    # Proc — looser, used internally only; intentionally different from the lambda above
    # to illustrate the distinction: proc returns from caller, lambda returns from itself
    generate_secret_proc = proc do |byte_length = 20|
      raw        = OpenSSL::Random.random_bytes(byte_length)
      out, buf, bits = +'', 0, 0
      raw.bytes.each do |b|
        buf = (buf << 8) | b
        bits += 8
        while bits >= 5
          bits -= 5
          out << ALPHABET[(buf >> bits) & 0x1f]
        end
      end
      out << ALPHABET[(buf << (5 - bits)) & 0x1f] if bits.positive?
      out
    end

    GENERATE_SECRET = generate_secret_proc.freeze

    def self.generate_secret(bytes = 20) = GENERATE_SECRET.call(bytes)

    def self.hotp(secret, counter, digits: 6)
      key  = DECODE_BASE32.call(secret)
      msg  = [counter].pack('Q>')                     # 8-byte big-endian
      hmac = OpenSSL::HMAC.digest('SHA1', key, msg).bytes

      offset = hmac[-1] & 0x0f
      code   = ((hmac[offset]     & 0x7f) << 24) |
               ((hmac[offset + 1] & 0xff) << 16) |
               ((hmac[offset + 2] & 0xff) << 8)  |
                (hmac[offset + 3] & 0xff)

      (code % (10**digits)).to_s.rjust(digits, '0')
    end

    def self.totp(secret, time: Time.now, digits: 6, interval: 30)
      hotp(secret, time.to_i / interval, digits: digits)
    end

    def self.validate(secret, code, time: Time.now, digits: 6, interval: 30, drift: 1)
      counter = time.to_i / interval
      code    = code.to_s.strip
      (-drift..drift).any? { hotp(secret, counter + _1, digits: digits) == code }
    end
  end

  # ── AuthResult ───────────────────────────────────────────────────────────────
  # Struct gives us: ==, members, to_a, to_h, deconstruct(_keys) for free.
  # Comparable adds: <, <=, >=, >, between?, clamp.
  # Frozen on creation — value objects must be immutable.
  AuthResult = Struct.new(:account, :success, :timestamp, :drift_window, :code_length) do
    include Comparable

    def initialize(account, success, timestamp = Time.now, drift_window = 1, code_length = 6)
      super
      freeze
    end

    # Comparable — sort by recency; newer result > older result
    def <=>(other) = timestamp <=> other.timestamp

    # Predicate sugar
    def success?  = success == true
    def failure?  = !success?

    # Pattern-matching support (deconstruct already provided by Struct)
    def deconstruct_keys(keys)
      h = to_h
      keys ? h.slice(*keys) : h
    end

    def to_s
      flag = success? ? '✓ AUTHENTICATED' : '✗ DENIED'
      "[#{timestamp.iso8601}] #{flag} — #{account}"
    end

    alias inspect to_s
  end

  # ── Store ────────────────────────────────────────────────────────────────────
  # SQLite3 backend.  Includes Enumerable — yields [account, secret] pairs,
  # making the full Enumerable API (map, select, min, count, group_by...) available.
  class Store
    include Enumerable
    extend  Forwardable
    using   TOTPGuard::StringRefinements

    attr_reader :db_path

    def initialize(db_path: TOTPGuard::DEFAULT_DB)
      @db_path = db_path
      init_db
    end

    # ── Enumerable contract ───────────────────────────────────────────────────
    # Yields [account, secret] rows.  Without a block returns an Enumerator —
    # required for Enumerable to work correctly (lazy chains etc.).
    def each
      return to_enum(:each) unless block_given?

      @db.execute('SELECT account, secret FROM totp ORDER BY account') do |row|
        yield row
      end
    end

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add(account, secret)
      raise ArgumentError, "secret '#{secret[0, 8]}...' is not valid Base32" \
        unless secret.base32?                                      # refinement

      @db.execute('INSERT OR REPLACE INTO totp (account, secret) VALUES (?, ?)',
                  [account, secret])
      self    # return self for method chaining
    end
    alias []= add

    def delete(account)
      @db.execute('DELETE FROM totp WHERE account = ?', [account])
      @db.changes.positive?
    end

    # Returns secret or nil
    def secret_for(account)
      @db.get_first_value('SELECT secret FROM totp WHERE account = ? LIMIT 1', [account])
    end
    alias [] secret_for

    # Returns account name or nil
    def account_for(secret)
      @db.get_first_value('SELECT account FROM totp WHERE secret = ? LIMIT 1', [secret])
    end

    def exists?(account)
      @db.get_first_value('SELECT COUNT(*) FROM totp WHERE account = ?', [account]).positive?
    end

    # LIKE pattern search — returns array of [account, secret]
    def search(pattern)
      @db.execute('SELECT account, secret FROM totp WHERE account LIKE ?',
                  ["%#{pattern}%"])
    end

    # Block form convenience — only account names
    def each_account
      return to_enum(:each_account) unless block_given?
      each { |account, _| yield account }
    end

    # Yields account + redacted secret hint — safe for terminal display
    def each_with_hint
      return to_enum(:each_with_hint) unless block_given?
      each { |account, secret| yield account, "#{secret[0, 4]}..." }
    end

    # ── method_missing — dynamic account lookup ───────────────────────────────
    # Converts Ruby identifier conventions back to account key format:
    #
    #   store.github_morgan      → secret for 'github:morgan'  (or nil)
    #   store.github_morgan?     → true/false exists?
    #   store.github_morgan!     → secret or raises KeyError
    #
    # The underscore→colon transform lives in the StringRefinements module.
    def method_missing(name, *_args)
      str  = name.to_s
      bang = str.delete_suffix!('!')  # mutates str, returns suffix or nil
      pred = str.delete_suffix!('?')

      key  = str.account_key          # refinement: github_morgan → github:morgan

      return pred ? exists?(key) : secret_for(key) unless bang

      secret_for(key).tap { |s| raise KeyError, "No TOTP account: #{key}" if s.nil? }
    end

    def respond_to_missing?(name, include_private = false)
      key = name.to_s.delete_suffix('!').delete_suffix('?').account_key
      exists?(key) || super
    end

    # ── ObjectSpace — count live Store instances ───────────────────────────────
    # Useful for test hygiene and connection leak detection.
    def self.live_count = ObjectSpace.each_object(self).count

    def close
      @db.close
    rescue SQLite3::Exception
      nil
    end

    private

    def init_db
      dir = File.dirname(@db_path)
      FileUtils.mkdir_p(dir)
      FileUtils.chmod(0o700, dir) rescue nil

      @db = SQLite3::Database.new(@db_path).tap do |d|
        d.results_as_hash = false
        d.execute(<<~SQL)
          CREATE TABLE IF NOT EXISTS totp (
            account TEXT NOT NULL UNIQUE,
            secret  TEXT NOT NULL
          );
        SQL
      end

      FileUtils.chmod(0o600, @db_path) rescue nil
    end
  end

  # ── Authenticator ────────────────────────────────────────────────────────────
  # Validates codes against the Store.  Fires Proc callbacks on every outcome.
  # Accepts a Lambda policy — inject rate-limiting, IP bans, account lock-out, etc.
  class Authenticator
    attr_reader :store, :drift, :digits, :interval

    NOOP = proc {}.freeze   # shared sentinel no-op proc

    def initialize(store:, drift: 1, digits: 6, interval: 30)
      @store    = store
      @drift    = drift
      @digits   = digits
      @interval = interval

      # Lambda policy: account → bool.  Replace to add rate-limiting, banning, etc.
      # Lambda chosen (not Proc) because we want strict arity enforcement.
      @policy = ->(_account) { true }

      @on_success = NOOP.dup
      @on_failure = NOOP.dup
      @on_missing = NOOP.dup
    end

    # ── Callback setters — block API + tap for fluent chaining ───────────────

    def on_success(&block) = tap { @on_success = block }
    def on_failure(&block) = tap { @on_failure = block }
    def on_missing(&block) = tap { @on_missing = block }

    # Policy must be a callable with arity 1 (lambda preferred, enforced here)
    def policy=(callable)
      raise ArgumentError, 'policy must respond to #call' unless callable.respond_to?(:call)
      @policy = callable
    end

    # ── Core authentication ───────────────────────────────────────────────────
    # Yields AuthResult to block if given; always returns AuthResult.
    # This lets callers choose between:
    #   result = auth.authenticate(account, code)          # value return
    #   auth.authenticate(account, code) { |r| r.success? }  # block dispatch
    def authenticate(account, code, time: Time.now)
      result = build_result(account, code, time)
      block_given? ? yield(result) : result
    end

    # Bang — raises AuthenticationError on failure, returns result on success
    def authenticate!(account, code, **opts)
      authenticate(account, code, **opts).tap do |r|
        raise AuthenticationError, "2FA failed for #{account}" if r.failure?
      end
    end

    # Convenience predicate — no callbacks fired, pure boolean
    def valid?(account, code, time: Time.now)
      secret = store.secret_for(account)
      return false if secret.nil?

      Core.validate(secret, code, time: time, drift: @drift,
                    digits: @digits, interval: @interval)
    end

    private

    # Single-exit result construction — keeps authenticate clean
    def build_result(account, code, time)
      unless @policy.call(account)
        return make_result(account, false, time).tap { @on_failure.call(_1) }
      end

      secret = store.secret_for(account)

      if secret.nil?
        make_result(account, false, time).tap { @on_missing.call(_1) }
      elsif Core.validate(secret, code, time: time, drift: @drift,
                          digits: @digits, interval: @interval)
        make_result(account, true, time).tap  { @on_success.call(_1) }
      else
        make_result(account, false, time).tap { @on_failure.call(_1) }
      end
    end

    def make_result(account, success, time)
      AuthResult.new(account, success, time, @drift, @digits)
    end
  end

  # ── Guard ─────────────────────────────────────────────────────────────────── 
  # Top-level facade.  Forwardable delegates to both Store and Authenticator
  # so callers only need one object.  const_missing (below) creates named Guards
  # on first access — TOTPGuard::MyApp is a fully wired Guard instance.
  class Guard
    extend Forwardable

    # Delegate store operations
    def_delegators :@store,
      :add, :delete, :search, :exists?,
      :secret_for, :account_for,
      :each, :each_account, :each_with_hint, :to_a, :count

    # Delegate auth operations
    def_delegators :@authenticator,
      :valid?, :authenticate!, :drift, :digits, :interval,
      :on_success, :on_failure, :on_missing, :policy=

    def initialize(db_path: TOTPGuard::DEFAULT_DB, **auth_opts)
      @store         = Store.new(db_path: db_path)
      @authenticator = Authenticator.new(store: @store, **auth_opts)
    end

    # authenticate needs explicit delegation to pass keyword args through
    def authenticate(account, code, time: Time.now, &block)
      @authenticator.authenticate(account, code, time: time, &block)
    end

    # Block-form guard: yields boolean success/failure
    # guard.protect('alice', code) { |ok| ok ? serve : halt(401) }
    def protect(account, code, time: Time.now, &block)
      result = authenticate(account, code, time: time)
      block_given? ? yield(result.success?) : result
    end

    # Provision multiple accounts at once from a Hash or array of pairs.
    # Returns self for further chaining.
    # guard.provision('alice' => secret_a, 'bob' => secret_b)
    def provision(accounts)
      accounts.each_with_object(self) { |(account, secret), g| g.add(account, secret) }
    end

    # [] sugar — guard['alice'] returns secret or nil
    def [](account) = @store.secret_for(account)

    # Operator-style add — guard['alice'] = secret
    def []=(account, secret)
      @store.add(account, secret)
    end

    def close = @store.close

    # ObjectSpace — enumerate every live Guard instance
    # Useful for test hygiene assertions and leak detection
    def self.instances = ObjectSpace.each_object(self).to_a
  end

  # ── Module-level API + const_missing ─────────────────────────────────────────

  # TOTPGuard.new → Guard.new with optional block-based config
  def self.new(db_path: DEFAULT_DB, **opts, &block)
    Guard.new(db_path: db_path, **opts).tap { block&.call(_1) }
  end

  # const_missing — intercepts PascalCase constant lookups and auto-provisions
  # a named Guard instance, then caches it as a real constant so lookup is O(1)
  # on subsequent accesses.
  #
  #   TOTPGuard::GitHub  → Guard instance (created once, cached forever)
  #   TOTPGuard::AWS     → another Guard instance
  #
  # Falls through to super for anything that doesn't look like an app name,
  # preserving normal NameError semantics for genuine missing constants.
  @_named_guards = {}

  def self.const_missing(name)
    guard_name = name.to_s

    # Only intercept PascalCase identifiers — leave ALL_CAPS and lower_snake alone
    return super unless guard_name.match?(/\A[A-Z][A-Za-z0-9]*\z/)

    @_named_guards[guard_name] ||= Guard.new.tap do |g|
      const_set(name, g)    # promote to real constant → subsequent accesses are direct
    end
  end

  # Enumerate all auto-provisioned named guards
  def self.named_guards = @_named_guards.dup

  # ── Errors ──────────────────────────────────────────────────────────────────
  class AuthenticationError < StandardError; end
  class ConfigurationError  < StandardError; end
end
