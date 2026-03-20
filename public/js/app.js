// app.js — Horse Racing front-end helpers

// ── SortableTable ─────────────────────────────────────────────────────────────
// Client-side in-page sort for tables marked with class="sortable-table".
// Add data-col="N" (0-indexed) to each <th> you want to be sortable.
// Numeric cells are sorted numerically; everything else lexicographically.
// SVG icons: line (unsorted) / up-arrow (asc) / down-arrow (desc).
(function () {
  var SVG = {
    none: '<svg class="sort-icon" width="9" height="12" viewBox="0 0 9 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4.5" y1="2" x2="4.5" y2="10"/></svg>',
    asc:  '<svg class="sort-icon" width="9" height="12" viewBox="0 0 9 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1.5,7 4.5,2 7.5,7"/><line x1="4.5" y1="2" x2="4.5" y2="11"/></svg>',
    desc: '<svg class="sort-icon" width="9" height="12" viewBox="0 0 9 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1.5,5 4.5,10 7.5,5"/><line x1="4.5" y1="1" x2="4.5" y2="10"/></svg>'
  };

  function cellVal(row, col) {
    var td = row.querySelectorAll('td')[col];
    return td ? (td.dataset.sortVal || td.innerText.trim()) : '';
  }

  function sortTable(table, col, dir) {
    var tbody = table.querySelector('tbody');
    var rows  = Array.from(tbody.querySelectorAll('tr'));
    var num   = rows.every(function (r) { return !isNaN(parseFloat(cellVal(r, col))); });

    rows.sort(function (a, b) {
      var av = cellVal(a, col), bv = cellVal(b, col);
      var cmp = num ? (parseFloat(av) - parseFloat(bv)) : av.localeCompare(bv);
      return dir === 'asc' ? cmp : -cmp;
    });
    rows.forEach(function (r) { tbody.appendChild(r); });
  }

  function updateIcons(table, activeCol, dir) {
    table.querySelectorAll('th[data-col]').forEach(function (th) {
      var label = th.dataset.label || th.innerText.replace(/[\u2190-\u21FF]/g, '').trim();
      th.dataset.label = label;
      var icon  = parseInt(th.dataset.col) === activeCol ? SVG[dir] : SVG.none;
      th.innerHTML = label + icon;
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('table.sortable-table').forEach(function (table) {
      table._sortCol = -1;
      table._sortDir = 'asc';

      table.querySelectorAll('th[data-col]').forEach(function (th) {
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.style.whiteSpace = 'nowrap';
        th.innerHTML = (th.dataset.label || th.innerText.trim()) + SVG.none;
        th.dataset.label = th.dataset.label || th.innerText.replace(/<[^>]+>/g, '').trim();

        th.addEventListener('click', function () {
          var col = parseInt(th.dataset.col);
          var dir = (table._sortCol === col && table._sortDir === 'desc') ? 'asc' : 'desc';
          table._sortCol = col;
          table._sortDir = dir;
          sortTable(table, col, dir);
          updateIcons(table, col, dir);
        });
      });
    });
  });
}());

// ── General helpers ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  // Auto-dismiss alerts after 5 s
  document.querySelectorAll('.alert-dismissible').forEach(function (el) {
    setTimeout(function () {
      var bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert && bsAlert.close();
    }, 5000);
  });

  // Colour elements with data-pl attribute
  document.querySelectorAll('[data-pl]').forEach(function (el) {
    var v = parseFloat(el.dataset.pl);
    el.classList.add(v >= 0 ? 'text-success' : 'text-danger');
  });
});
