# lib/sortable_table.rb
# Sinatra helper for server-side sortable column headers.
#
# Usage in ERB (server-side sort with full-page reload):
#   <%= sort_th('ROI%', 'roi', sort_col: params[:sort], sort_dir: params[:dir],
#               base_url: '/strategies', extra_params: {strategy_class: params[:strategy_class]}) %>
#
# Hierarchy (as per issue #25):
#   SortableTable  (this module)
#     └─ included as a helper → all ERB templates get sort_th
#
# For client-side in-page sort, mark any <table> with class="sortable-table"
# and add data-col="N" to each <th>. app.js picks this up automatically.

module SortableTable
  # SVG icons — line (neutral), up arrow (asc), down arrow (desc)
  SVG_NONE = '<svg class="sort-icon" width="9" height="12" viewBox="0 0 9 12" ' \
             'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">' \
             '<line x1="4.5" y1="2" x2="4.5" y2="10"/>' \
             '</svg>'.freeze

  SVG_ASC  = '<svg class="sort-icon" width="9" height="12" viewBox="0 0 9 12" ' \
             'fill="none" stroke="currentColor" stroke-width="1.5" ' \
             'stroke-linecap="round" stroke-linejoin="round">' \
             '<polyline points="1.5,7 4.5,2 7.5,7"/>' \
             '<line x1="4.5" y1="2" x2="4.5" y2="11"/>' \
             '</svg>'.freeze

  SVG_DESC = '<svg class="sort-icon" width="9" height="12" viewBox="0 0 9 12" ' \
             'fill="none" stroke="currentColor" stroke-width="1.5" ' \
             'stroke-linecap="round" stroke-linejoin="round">' \
             '<polyline points="1.5,5 4.5,10 7.5,5"/>' \
             '<line x1="4.5" y1="1" x2="4.5" y2="10"/>' \
             '</svg>'.freeze

  # Render a sortable <th> with a linked label and SVG direction indicator.
  #
  # @param label       [String]  Column display name
  # @param col         [String]  Sort key passed as ?sort=col
  # @param sort_col    [String]  Currently active sort column (from params)
  # @param sort_dir    [String]  Current direction 'asc'|'desc' (from params, default 'desc')
  # @param base_url    [String]  Route path, e.g. '/strategies'
  # @param extra_params[Hash]   Additional query params to preserve (e.g. filters)
  # @param css         [String]  Extra CSS classes for the <th>
  def sort_th(label, col, sort_col:, base_url:, sort_dir: 'desc', extra_params: {}, css: '')
    col      = col.to_s
    sort_col = sort_col.to_s
    active   = sort_col == col

    # Toggle direction when clicking the active column; default to desc otherwise
    new_dir = (active && sort_dir == 'desc') ? 'asc' : 'desc'
    icon    = active ? (sort_dir == 'asc' ? SVG_ASC : SVG_DESC) : SVG_NONE

    qs = extra_params
           .reject { |_, v| v.nil? || v.to_s.empty? }
           .merge(sort: col, dir: new_dir)
           .map { |k, v| "#{CGI.escape(k.to_s)}=#{CGI.escape(v.to_s)}" }
           .join('&')

    active_css = active ? ' sort-active' : ''
    <<~HTML.strip
      <th class="sortable-col#{active_css} #{css}" style="white-space:nowrap">
        <a href="#{base_url}?#{qs}" class="text-decoration-none text-white d-inline-flex align-items-center gap-1">#{label}#{icon}</a>
      </th>
    HTML
  end
end
