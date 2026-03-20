#!/usr/bin/env ruby
# setup_auth.rb — First-run TOTP provisioning
# Run once: ruby setup_auth.rb <username>
# Prints the TOTP secret + otpauth:// URI + ASCII QR code.

$LOAD_PATH.unshift(File.join(__dir__, 'lib'))
require 'auth'
require 'totp'
require 'rqrcode'

username = ARGV[0]
if username.nil? || username.strip.empty?
  abort "Usage: ruby setup_auth.rb <username> [--reprovision]"
end

reprovision = ARGV.include?('--reprovision')

if Auth.user_exists?(username)
  if reprovision
    Auth.guard.delete(username)
    secret = Auth.provision(username)
    puts "\nUser '#{username}' reprovisioned with new secret."
  else
    secret = Auth.guard.secret_for(username)
    puts "\nShowing existing credentials for '#{username}'."
  end
else
  secret = Auth.provision(username)
  puts "\nUser '#{username}' provisioned."
end
uri    = TOTP.otpauth_uri(secret, account: username, issuer: 'HorseRacing')

puts "Secret: #{secret}"
puts "OTPAuth URI: #{uri}"
puts

begin
  qr = RQRCode::QRCode.new(uri)
  # Compact half-block renderer: uses ▄ (lower half) with fg/bg colours,
  # packing 2 QR rows into 1 terminal line — half the height of as_ansi.
  DARK  = "\e[40m\e[30m"   # bg=black, fg=black
  LIGHT = "\e[47m\e[37m"   # bg=white, fg=white
  RESET = "\e[0m"
  mods  = qr.modules          # 2D array of booleans (true=dark)
  pad   = [[false] * (mods[0].size + 4)]  # quiet-zone row

  rows  = pad * 2 + mods.map { |r| [false, false] + r + [false, false] } + pad * 2

  lines = []
  rows.each_slice(2) do |top_row, bot_row|
    bot_row ||= Array.new(top_row.size, false)
    line = top_row.zip(bot_row).map do |top, bot|
      bg = top ? DARK : LIGHT
      fg = bot ? "\e[30m" : "\e[37m"
      "#{bg}#{fg}▄"
    end.join
    lines << line + RESET
  end
  puts lines.join("\n")
rescue => e
  puts "(QR render failed: #{e.message} — scan the URI above manually)"
end

puts
puts "Scan the QR code with Google Authenticator / Authy, then start the app."
