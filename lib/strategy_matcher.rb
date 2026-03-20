# lib/strategy_matcher.rb
# Applies the top-4 strategy classes to a live race card (runners array from DBReader).
# Returns an array of bet suggestions sorted by confidence DESC.
#
# Usage:
#   runners = db.race_runners(race_id)
#   hypos   = db.hypothesis(min_evidence: 3, limit: 200)
#   bets    = StrategyMatcher.new(runners, hypos).suggestions

class StrategyMatcher
  Suggestion = Struct.new(
    :strategy_class,
    :horse_name,
    :cloth_number,
    :sp,                 # starting price / morning price used for assessment
    :bet_type,
    :stake_pct,
    :confidence,         # 0.0–1.0
    :rationale,
    keyword_init: true
  )

  # stake_pct tiers
  LOW    = 2.0
  MEDIUM = 3.5
  HIGH   = 5.0

  def initialize(runners, hypotheses = [])
    @runners    = runners
    @hypotheses = hypotheses  # array of hashes from db.hypothesis
    @hypo_index = build_hypo_index
  end

  def suggestions
    results = []
    results.concat(favourite_cover_bets)
    results.concat(dutching_envelope_bets)
    results.concat(pattern_recognition_bets)
    results.concat(bayesian_correlation_bets)
    results.sort_by { |s| -s.confidence }.uniq { |s| s.horse_name }
  end

  private

  # ── FavouriteCover ────────────────────────────────────────────────────────
  # Short-priced runners (SP ≤ 3.0) with course-winning form.

  def favourite_cover_bets
    @runners.filter_map do |r|
      sp = best_price(r)
      next unless sp && sp <= 3.0
      next if sp < 1.05  # odds-on banker we can't do much with

      course_wins = r[:course_wins].to_i
      confidence  = calculate_confidence(base: 0.55, boosts: [
        [course_wins >= 1, 0.15],
        [sp <= 2.0,         0.10],
        [r[:favourite_rank].to_i == 1, 0.08]
      ])

      Suggestion.new(
        strategy_class: 'FavouriteCover',
        horse_name:     r[:horse_name],
        cloth_number:   r[:cloth_number],
        sp:             sp,
        bet_type:       course_wins >= 1 ? 'win' : 'each_way',
        stake_pct:      sp <= 2.0 ? HIGH : MEDIUM,
        confidence:     confidence,
        rationale:      "SP #{sp}, course_wins=#{course_wins}, fav_rank=#{r[:favourite_rank]}"
      )
    end
  end

  # ── DutchingEnvelope ──────────────────────────────────────────────────────
  # Cover top-2 runners by favourite_rank if dutch sum < 0.95.

  def dutching_envelope_bets
    top2 = @runners.select { |r| r[:favourite_rank].to_i.between?(1, 2) }
    return [] if top2.size < 2

    prices = top2.map { |r| best_price(r) }.compact
    return [] if prices.size < 2

    dutch_sum = prices.sum { |p| 1.0 / p }
    return [] if dutch_sum >= 0.95  # not profitable to dutch

    confidence = [(0.95 - dutch_sum) * 3.0, 0.90].min  # scales with edge
    confidence = confidence.round(2)

    top2.map do |r|
      sp = best_price(r)
      weight = (1.0 / sp) / dutch_sum  # proportional stake
      Suggestion.new(
        strategy_class: 'DutchingEnvelope',
        horse_name:     r[:horse_name],
        cloth_number:   r[:cloth_number],
        sp:             sp,
        bet_type:       'dutch',
        stake_pct:      (HIGH * weight).round(1),
        confidence:     confidence,
        rationale:      "Dutch sum=#{dutch_sum.round(3)}, weight=#{weight.round(2)}"
      )
    end
  end

  # ── PatternRecognition ────────────────────────────────────────────────────
  # Improving form sequence: form string parsed for 1-2-3 trend.

  def pattern_recognition_bets
    @runners.filter_map do |r|
      score = form_score(r)
      next if score < 2

      sp = best_price(r)
      next unless sp

      confidence = calculate_confidence(base: 0.40, boosts: [
        [score >= 4,                            0.15],
        [r[:days_since_last_run].to_i.between?(14, 28), 0.10],
        [r[:distance_wins].to_i >= 1,           0.08]
      ])
      next if confidence < 0.45

      Suggestion.new(
        strategy_class: 'PatternRecognition',
        horse_name:     r[:horse_name],
        cloth_number:   r[:cloth_number],
        sp:             sp,
        bet_type:       'win',
        stake_pct:      LOW,
        confidence:     confidence,
        rationale:      "Form score=#{score}, days_off=#{r[:days_since_last_run]}, dist_wins=#{r[:distance_wins]}"
      )
    end
  end

  # ── BayesianCorrelation ───────────────────────────────────────────────────
  # Look up trainer × going priors from hypothesis table.

  def bayesian_correlation_bets
    @runners.filter_map do |r|
      trainer = r[:trainer].to_s
      next if trainer.empty?

      key        = "#{trainer}:*"  # trainer-level key
      hypo       = @hypo_index[key]
      next unless hypo

      posterior = hypo[:alpha].to_f / (hypo[:alpha].to_f + hypo[:beta_param].to_f)
      next if posterior < 0.45

      sp = best_price(r)
      next unless sp

      confidence = [posterior * 0.85, 0.80].min.round(2)

      Suggestion.new(
        strategy_class: 'BayesianCorrelation',
        horse_name:     r[:horse_name],
        cloth_number:   r[:cloth_number],
        sp:             sp,
        bet_type:       'win',
        stake_pct:      LOW,
        confidence:     confidence,
        rationale:      "Trainer #{trainer} posterior=#{posterior.round(2)}, evidence=#{hypo[:evidence_count]}"
      )
    end
  end

  # ── Helpers ───────────────────────────────────────────────────────────────

  def best_price(runner)
    sp = runner[:sp] || runner[:morning_price]
    sp&.to_f&.positive? ? sp.to_f : nil
  end

  # Parses a form string like "1-2-3-4" or "1234" — returns improving score.
  def form_score(runner)
    form = runner[:form].to_s.gsub(/[^0-9PFU]/, '-').split('-').reverse
    return 0 if form.size < 2

    score = 0
    form.each_cons(2) do |newer, older|
      n = newer.to_i
      o = older.to_i
      next if n == 0 || o == 0
      score += 1 if n < o  # improving (lower position number = better)
    end
    score
  end

  def calculate_confidence(base:, boosts:)
    total = base
    boosts.each { |condition, value| total += value if condition }
    [total, 0.95].min.round(2)
  end

  def build_hypo_index
    idx = {}
    @hypotheses.each do |h|
      idx[h[:subject_key]] = h
    end
    idx
  end
end
