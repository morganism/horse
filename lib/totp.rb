#!/usr/bin/env ruby
# 
# frozen_string_literal: true
#
# totp.rb - RFC 6238 TOTP implementation compatible with Google Authenticator
#
# USAGE AS MODULE:
#   require_relative 'totp'
#   secret = TOTP.generate_secret
#   TOTP.validate(secret, user_input)  # => true/false
#
# USAGE AS STANDALONE:
#   ruby totp.rb --setup alice@example.com --issuer "MyApp"
#   ruby totp.rb --current --secret JBSWY3DPEHPK3PXP
#   ruby totp.rb --validate 123456 --secret JBSWY3DPEHPK3PXP

require 'openssl'
require 'uri'

module TOTP
  VERSION  = '1.0.0'
  ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'

  class Error < StandardError; end

  # ---------------------------------------------------------------------------
  # Base32 (RFC 4648) – pure Ruby, no gem required
  # ---------------------------------------------------------------------------

  def self.encode_base32(bytes)
    bytes  = bytes.bytes if bytes.is_a?(String)
    output = +''
    buf    = 0
    bits   = 0

    bytes.each do |byte|
      buf   = (buf << 8) | byte
      bits += 8
      while bits >= 5
        bits  -= 5
        output << ALPHABET[(buf >> bits) & 0x1f]
      end
    end

    output << ALPHABET[(buf << (5 - bits)) & 0x1f] if bits > 0
    output
  end

  def self.decode_base32(str)
    str  = str.upcase.tr('=', '').gsub(/[^A-Z2-7]/, '')
    out  = []
    buf  = 0
    bits = 0

    str.each_char do |ch|
      val = ALPHABET.index(ch)
      raise Error, "Invalid Base32 character: #{ch.inspect}" unless val

      buf   = (buf << 5) | val
      bits += 5
      if bits >= 8
        bits -= 8
        out << ((buf >> bits) & 0xff)
      end
    end

    out.pack('C*')
  end

  # ---------------------------------------------------------------------------
  # Secret generation
  # ---------------------------------------------------------------------------

  # Returns a random Base32-encoded secret (160 bits / 20 bytes by default).
  def self.generate_secret(byte_length = 20)
    encode_base32(OpenSSL::Random.random_bytes(byte_length))
  end

  # ---------------------------------------------------------------------------
  # HOTP (RFC 4226) & TOTP (RFC 6238)
  # ---------------------------------------------------------------------------

  # HMAC-based OTP for a given counter value.
  def self.hotp(secret, counter, digits: 6)
    key  = decode_base32(secret)
    msg  = [counter].pack('Q>') # 8-byte big-endian unsigned
    hmac = OpenSSL::HMAC.digest('SHA1', key, msg).bytes

    offset = hmac[-1] & 0x0f
    code   = ((hmac[offset]     & 0x7f) << 24) |
             ((hmac[offset + 1] & 0xff) << 16) |
             ((hmac[offset + 2] & 0xff) << 8)  |
              (hmac[offset + 3] & 0xff)

    (code % (10**digits)).to_s.rjust(digits, '0')
  end

  # Current (or any) TOTP value.
  def self.totp(secret, time: Time.now, digits: 6, interval: 30)
    hotp(secret, time.to_i / interval, digits: digits)
  end

  # Validate a user-supplied code. Returns true/false.
  # `drift` allows ±N windows to compensate for clock skew (default 1 = ±30 s).
  def self.validate(secret, code, time: Time.now, digits: 6, interval: 30, drift: 1)
    code    = code.to_s.strip
    counter = time.to_i / interval

    (-drift..drift).any? do |offset|
      hotp(secret, counter + offset, digits: digits) == code
    end
  end

  # ---------------------------------------------------------------------------
  # otpauth URI & QR code
  # ---------------------------------------------------------------------------

  # Builds the otpauth:// URI understood by Google Authenticator and compatible apps.
  def self.otpauth_uri(secret, account:, issuer: nil, digits: 6, interval: 30)
    enc_account = URI.encode_www_form_component(account)
    label       = issuer ? "#{URI.encode_www_form_component(issuer)}:#{enc_account}" : enc_account

    params = { secret: secret, algorithm: 'SHA1', digits: digits, period: interval }
    params[:issuer] = URI.encode_www_form_component(issuer) if issuer

    "otpauth://totp/#{label}?#{params.map { |k, v| "#{k}=#{v}" }.join('&')}"
  end

  # Attempts to render an ANSI QR code to the terminal using the rqrcode gem.
  # Returns the rendered string, or nil if the gem is not available.
  def self.qr_ansi(uri)
    require 'rqrcode'
    qr = RQRCode::QRCode.new(uri, level: :m)
    qr.as_ansi(
      light:           "\e[47m",
      dark:            "\e[40m",
      fill_character:  '  ',
      quiet_zone_size: 1
    )
  rescue LoadError
    nil
  end

  # ---------------------------------------------------------------------------
  # Setup helper – returns an info hash and optionally prints a setup banner
  # ---------------------------------------------------------------------------

  def self.setup(account:, issuer: nil, secret: nil, digits: 6, interval: 30)
    secret ||= generate_secret
    {
      secret:   secret,
      uri:      otpauth_uri(secret, account: account, issuer: issuer,
                            digits: digits, interval: interval),
      account:  account,
      issuer:   issuer,
      digits:   digits,
      interval: interval
    }
  end

  def self.display_setup(account:, issuer: nil, secret: nil, out: $stdout)
    info = setup(account: account, issuer: issuer, secret: secret)
    bar  = '=' * 54

    out.puts "\n#{bar}"
    out.puts " TOTP Setup"
    out.puts bar
    out.puts " Account : #{info[:account]}"
    out.puts " Issuer  : #{info[:issuer]}" if info[:issuer]
    out.puts bar

    out.puts "\n Step 1 – Open Google Authenticator (or any TOTP app)"
    out.puts "          and choose 'Enter a setup key'.\n"
    out.puts " Account name : #{info[:account]}"
    out.puts " Your key     : #{info[:secret]}"
    out.puts " Type         : Time based"

    qr = qr_ansi(info[:uri])
    if qr
      out.puts "\n Step 2 – Or scan this QR code:\n\n"
      out.puts qr
    else
      out.puts "\n Step 2 – Or install the 'rqrcode' gem for QR display:"
      out.puts "          gem install rqrcode\n"
      out.puts "          otpauth URI (copy into your app):"
      out.puts "          #{info[:uri]}"
    end

    out.puts "\n Current code : #{totp(info[:secret])}"
    out.puts "#{bar}\n"

    info
  end

  # ---------------------------------------------------------------------------
  # Standalone CLI
  # ---------------------------------------------------------------------------

  def self.run_cli(argv = ARGV)
    require 'optparse'

    options = { action: :help }
    secret  = nil

    parser = OptionParser.new do |o|
      o.banner = "Usage: ruby totp.rb [command] [options]"
      o.separator ""
      o.separator "Commands:"
      o.on('--setup ACCOUNT',
           'Generate a new secret and show setup instructions') do |acct|
        options[:action]  = :setup
        options[:account] = acct
      end
      o.on('--current',
           'Print the current TOTP code for a secret') do
        options[:action] = :current
      end
      o.on('--validate CODE',
           'Validate a 6-digit code against a secret') do |code|
        options[:action] = :validate
        options[:code]   = code
      end
      o.separator ""
      o.separator "Options:"
      o.on('--secret SECRET', 'Base32 secret (or set TOTP_SECRET env var)') do |s|
        secret = s
      end
      o.on('--issuer ISSUER', 'Issuer label shown in the authenticator app') do |i|
        options[:issuer] = i
      end
      o.on('-h', '--help', 'Show this help') do
        puts o
        exit
      end
    end

    begin
      parser.parse!(argv)
    rescue OptionParser::InvalidOption => e
      warn e.message
      puts parser
      exit 1
    end

    secret ||= ENV['TOTP_SECRET']

    case options[:action]

    when :setup
      display_setup(account: options[:account], issuer: options[:issuer],
                    secret: secret)
      puts "Keep your secret key safe – treat it like a password.\n\n"

    when :current
      secret = prompt_secret if secret.nil?
      puts totp(secret)

    when :validate
      secret      = prompt_secret if secret.nil?
      code        = options[:code]
      code        = prompt("Enter TOTP code: ") if code.nil?
      if validate(secret, code)
        puts "✓  Code is valid."
        exit 0
      else
        puts "✗  Code is invalid."
        exit 1
      end

    else
      puts parser
    end
  end

  def self.prompt_secret
    require 'io/console' rescue nil
    print "Enter TOTP secret: "
    $stdin.gets.to_s.chomp
  end

  def self.prompt(msg)
    print msg
    $stdin.gets.to_s.chomp
  end

  private_class_method :prompt_secret, :prompt
end

# Run as standalone script when executed directly
TOTP.run_cli if __FILE__ == $PROGRAM_NAME
