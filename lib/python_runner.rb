# lib/python_runner.rb
# Open3 wrapper for invoking the Python CLI.
# Only used for write/compute operations (simulate, reset).
# Read operations go directly through DBReader.

require 'open3'
require 'json'

class PythonRunner
  PY   = File.expand_path('../../py/cli.py', __FILE__)
  VENV = File.expand_path('../../py/.venv/bin/python3', __FILE__)

  def initialize(db_path: nil)
    @db_path = db_path
    @python  = File.exist?(VENV) ? VENV : 'python3'
  end

  # Run a simulation for +days+ days. Streams stdout lines to an optional block.
  # Returns { success: bool, output: String, error: String }
  def simulate(days: 30, &block)
    run_command(*db_args, 'simulate', '--days', days.to_s, &block)
  end

  # Reset the database (destructive — requires explicit confirmation).
  def reset!(&block)
    run_command(*db_args, 'reset', '--confirm', &block)
  end

  # Emit a JSON performance report.
  def report(format: 'json')
    result = run_command(*db_args, 'report', '--format', format)
    return nil unless result[:success]
    JSON.parse(result[:output]) rescue nil
  end

  # Export CSV.
  def export(output_path:)
    run_command(*db_args, 'export', '--output', output_path)
  end

  private

  def db_args = @db_path ? ['--db', @db_path] : []

  def run_command(*args, &block)
    cmd = [@python, PY, *args]
    stdout_acc = +''
    stderr_acc = +''

    Open3.popen3(*cmd) do |_stdin, stdout, stderr, wait_thr|
      stdout_thread = Thread.new do
        stdout.each_line do |line|
          stdout_acc << line
          block&.call(line.chomp)
        end
      end
      stderr_thread = Thread.new { stderr_acc << stderr.read }
      stdout_thread.join
      stderr_thread.join
      exit_status = wait_thr.value
      { success: exit_status.success?, output: stdout_acc, error: stderr_acc }
    end
  rescue => e
    { success: false, output: '', error: e.message }
  end
end
