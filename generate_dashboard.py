"""
Generates modern, standalone dark-theme web dashboard (index.html)
with embedded data fallback + dynamic CSV auto-fetch.
"""
import csv
import json
import os

CSV_FILE = "remux_library.csv"
OUTPUT_HTML = "index.html"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Remux Vault — Curated 4K UHD & 1080p Cinema Library</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#f0fdf4',
              500: '#10b981',
              600: '#059669',
            },
            slate: {
              850: '#151f32',
              900: '#0f172a',
              950: '#080d1a',
            }
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');
    body {
      font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .mono {
      font-family: 'JetBrains Mono', monospace;
    }
    ::-webkit-scrollbar {
      width: 8px;
      height: 8px;
    }
    ::-webkit-scrollbar-track {
      background: #0f172a;
    }
    ::-webkit-scrollbar-thumb {
      background: #334155;
      border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #475569;
    }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col antialiased selection:bg-emerald-500 selection:text-black">

  <!-- Header -->
  <header class="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur sticky top-0 z-40">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-slate-950 text-lg font-black">
          <i class="fa-solid fa-film"></i>
        </div>
        <div>
          <h1 class="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            Remux Vault
            <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">Live Library</span>
            <span id="privateBadge" class="hidden text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-medium">🔒 Private Local App</span>
          </h1>
          <p class="text-xs text-slate-400">Curated cinema remuxes — 100% verified alive</p>
        </div>
      </div>

      <!-- Quick Action Links -->
      <div class="flex items-center gap-2.5 flex-wrap">
        <button id="syncBtn" onclick="triggerSync()" class="hidden px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold flex items-center gap-2 transition shadow-lg shadow-emerald-500/20">
          <i id="syncIcon" class="fa-solid fa-rotate"></i>
          <span id="syncBtnText">Sync Now</span>
        </button>
        <button id="logToggleBtn" onclick="toggleSyncLog()" class="hidden px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition border border-slate-700">
          <i class="fa-solid fa-terminal text-[11px]"></i>
          <span id="syncPhasePill">Idle</span>
        </button>
        <a href="https://docs.google.com/spreadsheets/d/1oqYjXc5D9eURyHUGNynR9uW9BDKNKWyGtfDBs8j_j8E" target="_blank" class="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-semibold flex items-center gap-2 transition border border-emerald-500/30">
          <i class="fa-solid fa-table"></i>
          <span>Google Sheet</span>
        </a>
        <a href="https://github.com/zcvbw8y9xn-cmyk/remux-library" target="_blank" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-2 transition border border-slate-700">
          <i class="fa-brands fa-github"></i>
          <span>GitHub</span>
        </a>
        <button onclick="copyAllLinks()" class="px-3 py-1.5 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 text-xs font-semibold flex items-center gap-2 transition border border-indigo-500/30" title="Copy all active download URLs to clipboard">
          <i class="fa-solid fa-download"></i>
          <span>Copy Batch URLs</span>
        </button>
      </div>
    </div>
    <!-- Collapsible Local Sync Log Drawer -->
    <div id="syncLogDrawer" class="hidden max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-3">
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs">
        <div class="flex items-center justify-between mb-1.5 text-slate-400">
          <span class="font-semibold"><i class="fa-solid fa-terminal mr-1.5 text-emerald-400"></i>Local Sync Output</span>
          <span id="syncTimeInfo" class="font-mono text-[11px]"></span>
        </div>
        <pre id="syncLogContent" class="font-mono text-[11px] text-slate-300 max-h-44 overflow-y-auto whitespace-pre-wrap leading-relaxed">Ready. Click "Sync Now" to scrape X.com, verify links, and update Google Sheets.</pre>
      </div>
    </div>
  </header>

  <!-- Metrics Bar -->
  <section class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-2 w-full">
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 flex items-center gap-3.5">
        <div class="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center text-lg">
          <i class="fa-solid fa-clapperboard"></i>
        </div>
        <div>
          <div class="text-2xl font-bold text-white tracking-tight" id="stat-total">__TOTAL_COUNT__</div>
          <div class="text-xs text-slate-400">Total Active Movies</div>
        </div>
      </div>

      <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 flex items-center gap-3.5">
        <div class="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center text-lg">
          <i class="fa-solid fa-star"></i>
        </div>
        <div>
          <div class="text-2xl font-bold text-amber-400 tracking-tight" id="stat-uhd">__UHD_COUNT__</div>
          <div class="text-xs text-slate-400">4K UHD Remuxes</div>
        </div>
      </div>

      <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 flex items-center gap-3.5">
        <div class="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center text-lg">
          <i class="fa-solid fa-check-double"></i>
        </div>
        <div>
          <div class="text-2xl font-bold text-emerald-400 tracking-tight" id="stat-1080p">__1080P_COUNT__</div>
          <div class="text-xs text-slate-400">1080p Definitive Masters</div>
        </div>
      </div>

      <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 flex items-center gap-3.5">
        <div class="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center text-lg">
          <i class="fa-solid fa-compact-disc"></i>
        </div>
        <div>
          <div class="text-2xl font-bold text-purple-400 tracking-tight" id="stat-dvd">__DVD_COUNT__</div>
          <div class="text-xs text-slate-400">Rare DVD Remuxes</div>
        </div>
      </div>
    </div>
  </section>

  <!-- Controls Bar: Search, Filters, View Modes -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 w-full flex-1 flex flex-col">
    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 mb-6 shadow-xl space-y-3.5">
      <!-- Search Input + Sort + View Toggles -->
      <div class="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div class="relative flex-1">
          <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
          <input
            id="searchInput"
            type="text"
            placeholder="Search movie title, year, quality, file host..."
            class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition"
            oninput="handleSearch()"
          />
        </div>

        <div class="flex items-center gap-2">
          <!-- Sort dropdown -->
          <select id="sortSelect" onchange="renderMovies()" class="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-medium text-slate-300 focus:outline-none focus:border-emerald-500 cursor-pointer">
            <option value="date-desc">Tweet Date: Newest First</option>
            <option value="title-asc">Movie Title: A → Z</option>
            <option value="year-desc">Movie Year: Newest First</option>
            <option value="year-asc">Movie Year: Oldest First</option>
          </select>

          <!-- View toggles -->
          <div class="flex items-center bg-slate-950 border border-slate-800 rounded-xl p-0.5">
            <button id="viewGridBtn" onclick="setViewMode('grid')" class="p-1.5 px-2.5 rounded-lg text-xs font-semibold text-emerald-400 bg-slate-800 shadow transition" title="Grid Card View">
              <i class="fa-solid fa-grip"></i>
            </button>
            <button id="viewTableBtn" onclick="setViewMode('table')" class="p-1.5 px-2.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition" title="Compact Table View">
              <i class="fa-solid fa-list"></i>
            </button>
          </div>
        </div>
      </div>

      <!-- Filter Chips -->
      <div class="flex flex-wrap items-center gap-1.5 text-xs font-medium pt-1 border-t border-slate-800/80">
        <span class="text-slate-500 mr-1 text-xs">Quality:</span>
        <button onclick="setQualityFilter('all')" class="chip active-chip px-2.5 py-1 rounded-lg border text-xs transition" data-filter="all">All</button>
        <button onclick="setQualityFilter('4k')" class="chip px-2.5 py-1 rounded-lg border text-xs transition" data-filter="4k">⭐ 4K UHD</button>
        <button onclick="setQualityFilter('1080p-best')" class="chip px-2.5 py-1 rounded-lg border text-xs transition" data-filter="1080p-best">🟢 1080p Best</button>
        <button onclick="setQualityFilter('4k-exists')" class="chip px-2.5 py-1 rounded-lg border text-xs transition" data-filter="4k-exists">⚠️ 4K Exists</button>
        <button onclick="setQualityFilter('dvd')" class="chip px-2.5 py-1 rounded-lg border text-xs transition" data-filter="dvd">📀 DVD Remux</button>

        <span class="text-slate-500 ml-3 mr-1 text-xs hidden sm:inline">Host:</span>
        <select id="hostFilter" onchange="renderMovies()" class="bg-slate-950 border border-slate-800 rounded-lg px-2 py-0.5 text-xs text-slate-300 focus:outline-none focus:border-emerald-500 cursor-pointer">
          <option value="all">All File Hosts</option>
          <option value="transfer.it">transfer.it</option>
          <option value="gofile.io">gofile.io</option>
          <option value="mega.nz">mega.nz</option>
          <option value="pixeldrain.com">pixeldrain.com</option>
          <option value="drive.google.com">Google Drive</option>
        </select>

        <span id="resultCount" class="ml-auto text-slate-400 text-xs font-mono">Showing __TOTAL_COUNT__ movies</span>
      </div>
    </div>

    <!-- Movie Container (Grid View) -->
    <div id="gridContainer" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"></div>

    <!-- Movie Container (Table View) -->
    <div id="tableContainer" class="hidden overflow-x-auto bg-slate-900/80 border border-slate-800 rounded-xl shadow-xl">
      <table class="w-full text-left text-xs">
        <thead class="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
          <tr>
            <th class="py-3 px-4">Date</th>
            <th class="py-3 px-4">Title & Year</th>
            <th class="py-3 px-4">Specs</th>
            <th class="py-3 px-4">Quality Tier</th>
            <th class="py-3 px-4">Host</th>
            <th class="py-3 px-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody id="tableBody" class="divide-y divide-slate-800/60 font-medium"></tbody>
      </table>
    </div>

    <!-- Empty State -->
    <div id="emptyState" class="hidden py-16 text-center">
      <div class="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 mx-auto flex items-center justify-center text-slate-600 text-2xl mb-3">
        <i class="fa-solid fa-film"></i>
      </div>
      <h3 class="text-sm font-bold text-slate-300">No movies match your filters</h3>
      <p class="text-xs text-slate-500 mt-1">Try clearing your search terms or picking another quality tier.</p>
    </div>
  </main>

  <!-- Toast Notification -->
  <div id="toast" class="fixed bottom-6 right-6 bg-slate-900 text-white border border-emerald-500/40 rounded-xl px-4 py-2.5 shadow-2xl flex items-center gap-2.5 transform translate-y-24 opacity-0 transition duration-300 z-50">
    <i class="fa-solid fa-circle-check text-emerald-400"></i>
    <span id="toastMsg" class="text-xs font-semibold">Copied link to clipboard!</span>
  </div>

  <!-- Footer -->
  <footer class="border-t border-slate-800/80 py-6 text-center text-xs text-slate-500">
    <div class="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
      <div>Auto-refreshed daily via Raspberry Pi & GitHub Actions.</div>
      <div class="flex items-center gap-4">
        <a href="https://letterboxd.com" target="_blank" class="hover:text-slate-300 transition">Letterboxd</a>
        <a href="https://www.imdb.com" target="_blank" class="hover:text-slate-300 transition">IMDb</a>
        <a href="https://docs.google.com/spreadsheets/d/1oqYjXc5D9eURyHUGNynR9uW9BDKNKWyGtfDBs8j_j8E" target="_blank" class="hover:text-slate-300 transition">Google Sheets</a>
        <a href="https://github.com/zcvbw8y9xn-cmyk/remux-library" target="_blank" class="hover:text-slate-300 transition">GitHub Repo</a>
      </div>
    </div>
  </footer>

  <script>
    let rawMovies = __MOVIES_JSON__;
    let currentFilter = 'all';
    let currentView = 'grid';

    // Attempt to dynamically fetch fresh CSV if served over non-local HTTP (e.g. GitHub Pages)
    if (window.location.protocol.startsWith('http') && window.location.hostname !== '127.0.0.1' && window.location.hostname !== 'localhost') {
      fetch('remux_library.csv?t=' + Date.now())
        .then(res => res.text())
        .then(text => {
          const parsed = parseCSV(text);
          if (parsed && parsed.length > 0) {
            rawMovies = parsed;
            updateStats();
            renderMovies();
          }
        })
        .catch(() => {});
    }

    function parseCSV(text) {
      const lines = text.trim().split('\\n');
      if (lines.length < 2) return null;
      const headers = lines[0].split(',').map(h => h.trim());
      const data = [];
      for (let i = 1; i < lines.length; i++) {
        const row = parseCSVRow(lines[i]);
        if (row.length === headers.length) {
          const item = {};
          headers.forEach((h, idx) => item[h] = row[idx]);
          data.push(item);
        }
      }
      return data;
    }

    function parseCSVRow(line) {
      const result = [];
      let current = '';
      let inQuotes = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') {
          inQuotes = !inQuotes;
        } else if (ch === ',' && !inQuotes) {
          result.push(current.trim());
          current = '';
        } else {
          current += ch;
        }
      }
      result.push(current.trim());
      return result;
    }

    function updateStats() {
      const total = rawMovies.length;
      const uhd = rawMovies.filter(m => (m['Quality'] || '').includes('4K')).length;
      const best1080 = rawMovies.filter(m => (m['Best Quality?'] || '').includes('1080p Best')).length;
      const dvd = rawMovies.filter(m => (m['Quality'] || '').includes('DVD')).length;
      document.getElementById('stat-total').innerText = total;
      document.getElementById('stat-uhd').innerText = uhd;
      document.getElementById('stat-1080p').innerText = best1080;
      document.getElementById('stat-dvd').innerText = dvd;
    }

    function setQualityFilter(tier) {
      currentFilter = tier;
      document.querySelectorAll('.chip').forEach(btn => {
        if (btn.dataset.filter === tier) {
          btn.classList.add('bg-emerald-500', 'text-slate-950', 'border-emerald-500', 'font-bold');
          btn.classList.remove('bg-slate-900', 'text-slate-300', 'border-slate-800');
        } else {
          btn.classList.remove('bg-emerald-500', 'text-slate-950', 'border-emerald-500', 'font-bold');
          btn.classList.add('bg-slate-900', 'text-slate-300', 'border-slate-800');
        }
      });
      renderMovies();
    }

    function setViewMode(mode) {
      currentView = mode;
      const gridBtn = document.getElementById('viewGridBtn');
      const tableBtn = document.getElementById('viewTableBtn');
      const gridContainer = document.getElementById('gridContainer');
      const tableContainer = document.getElementById('tableContainer');

      if (mode === 'grid') {
        gridBtn.className = 'p-1.5 px-2.5 rounded-lg text-xs font-semibold text-emerald-400 bg-slate-800 shadow transition';
        tableBtn.className = 'p-1.5 px-2.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition';
        gridContainer.classList.remove('hidden');
        tableContainer.classList.add('hidden');
      } else {
        tableBtn.className = 'p-1.5 px-2.5 rounded-lg text-xs font-semibold text-emerald-400 bg-slate-800 shadow transition';
        gridBtn.className = 'p-1.5 px-2.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition';
        gridContainer.classList.add('hidden');
        tableContainer.classList.remove('hidden');
      }
    }

    function handleSearch() {
      renderMovies();
    }

    function getFilteredMovies() {
      const query = (document.getElementById('searchInput').value || '').toLowerCase().trim();
      const hostFilter = document.getElementById('hostFilter').value;
      const sort = document.getElementById('sortSelect').value;

      return rawMovies.filter(m => {
        const title = (m['Title'] || '').toLowerCase();
        const year = (m['Year'] || '');
        const quality = (m['Quality'] || '').toLowerCase();
        const host = (m['File Host'] || '').toLowerCase();
        const tier = (m['Best Quality?'] || '').toLowerCase();

        const matchesQuery = !query || title.includes(query) || year.includes(query) || quality.includes(query) || host.includes(query);
        const matchesHost = hostFilter === 'all' || host.includes(hostFilter);

        let matchesTier = true;
        if (currentFilter === '4k') {
          matchesTier = quality.includes('4k');
        } else if (currentFilter === '1080p-best') {
          matchesTier = tier.includes('1080p best');
        } else if (currentFilter === '4k-exists') {
          matchesTier = tier.includes('exists');
        } else if (currentFilter === 'dvd') {
          matchesTier = quality.includes('dvd');
        }

        return matchesQuery && matchesHost && matchesTier;
      }).sort((a, b) => {
        if (sort === 'title-asc') {
          return (a['Title'] || '').localeCompare(b['Title'] || '');
        } else if (sort === 'year-desc') {
          return parseInt(b['Year'] || 0) - parseInt(a['Year'] || 0);
        } else if (sort === 'year-asc') {
          return parseInt(a['Year'] || 0) - parseInt(b['Year'] || 0);
        } else {
          return (b['Tweet Date'] || '').localeCompare(a['Tweet Date'] || '');
        }
      });
    }

    function getTierBadge(tier) {
      if (!tier) return '';
      if (tier.includes('4K UHD')) {
        return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1"><i class="fa-solid fa-star text-[9px]"></i> Yes (4K UHD)</span>`;
      } else if (tier.includes('1080p Best')) {
        return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1"><i class="fa-solid fa-check text-[9px]"></i> Yes (1080p Best)</span>`;
      } else if (tier.includes('DVD is Best')) {
        return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30 flex items-center gap-1"><i class="fa-solid fa-compact-disc text-[9px]"></i> Yes (DVD is Best)</span>`;
      } else if (tier.includes('4K UHD Exists')) {
        return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-yellow-500/15 text-yellow-300 border border-yellow-500/30 flex items-center gap-1"><i class="fa-solid fa-triangle-exclamation text-[9px]"></i> 4K UHD Exists</span>`;
      } else {
        return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">${tier}</span>`;
      }
    }

    function getQualityBadge(quality) {
      if ((quality || '').includes('4K')) {
        return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-400 text-slate-950 font-mono">4K UHD</span>`;
      } else if ((quality || '').includes('DVD')) {
        return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-400 text-slate-950 font-mono">DVD REMUX</span>`;
      } else {
        return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-700 text-slate-200 font-mono">1080p</span>`;
      }
    }

    function renderMovies() {
      const movies = getFilteredMovies();
      document.getElementById('resultCount').innerText = `Showing ${movies.length} movies`;

      const grid = document.getElementById('gridContainer');
      const tableBody = document.getElementById('tableBody');
      const emptyState = document.getElementById('emptyState');

      if (movies.length === 0) {
        grid.innerHTML = '';
        tableBody.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
      }
      emptyState.classList.add('hidden');

      // Render Grid
      grid.innerHTML = movies.map(m => {
        const title = m['Title'] || 'Unknown';
        const year = m['Year'] || '';
        const quality = m['Quality'] || '';
        const tier = m['Best Quality?'] || '';
        const host = m['File Host'] || '';
        const fileLink = m['File Link'] || '';
        const tweetUrl = m['Tweet URL'] || '';
        const letterboxd = m['Letterboxd'] || `https://letterboxd.com/search/${encodeURIComponent(title + ' ' + year)}/`;
        const imdb = m['IMDb'] || `https://www.imdb.com/find/?q=${encodeURIComponent(title + ' ' + year)}&s=tt`;
        const tweetDate = m['Tweet Date'] || '';

        return `
          <div class="bg-slate-900 border border-slate-800/80 hover:border-slate-700 rounded-xl p-4 flex flex-col justify-between transition hover:-translate-y-0.5 hover:shadow-lg shadow-black/40">
            <div>
              <div class="flex items-start justify-between gap-2 mb-2">
                <div class="flex items-center gap-1.5 flex-wrap">
                  ${getQualityBadge(quality)}
                  <span class="text-[10px] font-mono text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">${host}</span>
                </div>
                <span class="text-[10px] text-slate-500 font-mono">${(tweetDate.split(' ')[0] || '')}</span>
              </div>

              <h3 class="text-sm font-bold text-white tracking-tight line-clamp-1">${title}</h3>
              <div class="text-xs text-slate-400 mb-2.5 font-medium">${year}</div>

              <div class="mb-3">
                ${getTierBadge(tier)}
              </div>

              <div class="text-[11px] font-mono text-slate-400 bg-slate-950/70 p-2 rounded-lg border border-slate-800/60 mb-3 truncate" title="${quality}">
                ${quality}
              </div>
            </div>

            <div class="pt-2 border-t border-slate-800/80 flex items-center justify-between gap-1.5 text-xs">
              <button onclick="copyToClipboard('${fileLink}')" class="flex-1 py-1.5 px-2 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 font-semibold flex items-center justify-center gap-1.5 transition">
                <i class="fa-regular fa-copy text-[11px]"></i>
                <span>Copy Link</span>
              </button>

              <a href="${fileLink}" target="_blank" class="p-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition" title="Open Download Link (${host})">
                <i class="fa-solid fa-download text-xs"></i>
              </a>

              <a href="${letterboxd}" target="_blank" class="p-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition" title="Search on Letterboxd">
                <i class="fa-solid fa-film text-xs"></i>
              </a>

              <a href="${imdb}" target="_blank" class="p-1.5 px-2 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 font-black text-[10px] tracking-tight transition" title="Search on IMDb">
                IMDb
              </a>

              ${tweetUrl ? `<a href="${tweetUrl}" target="_blank" class="p-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition" title="View Tweet"><i class="fa-brands fa-x-twitter text-xs"></i></a>` : ''}
            </div>
          </div>
        `;
      }).join('');

      // Render Table
      tableBody.innerHTML = movies.map(m => {
        const title = m['Title'] || 'Unknown';
        const year = m['Year'] || '';
        const quality = m['Quality'] || '';
        const tier = m['Best Quality?'] || '';
        const host = m['File Host'] || '';
        const fileLink = m['File Link'] || '';
        const tweetUrl = m['Tweet URL'] || '';
        const letterboxd = m['Letterboxd'] || `https://letterboxd.com/search/${encodeURIComponent(title + ' ' + year)}/`;
        const imdb = m['IMDb'] || `https://www.imdb.com/find/?q=${encodeURIComponent(title + ' ' + year)}&s=tt`;
        const tweetDate = m['Tweet Date'] || '';

        return `
          <tr class="hover:bg-slate-850/60 transition">
            <td class="py-2.5 px-4 font-mono text-slate-400 whitespace-nowrap text-[11px]">${tweetDate}</td>
            <td class="py-2.5 px-4">
              <div class="font-bold text-slate-100 flex items-center gap-1.5">
                ${title}
                <span class="text-slate-400 text-[11px] font-normal">(${year})</span>
              </div>
            </td>
            <td class="py-2.5 px-4 font-mono text-[11px] text-slate-300">${quality}</td>
            <td class="py-2.5 px-4">${getTierBadge(tier)}</td>
            <td class="py-2.5 px-4 font-mono text-slate-400 text-[11px]">${host}</td>
            <td class="py-2.5 px-4 text-right">
              <div class="flex items-center justify-end gap-1.5">
                <button onclick="copyToClipboard('${fileLink}')" class="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs font-semibold transition" title="Copy Link">
                  <i class="fa-regular fa-copy"></i>
                </button>
                <a href="${fileLink}" target="_blank" class="px-2 py-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs transition" title="Download (${host})">
                  <i class="fa-solid fa-download"></i>
                </a>
                <a href="${letterboxd}" target="_blank" class="px-2 py-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs transition" title="Letterboxd">
                  <i class="fa-solid fa-film"></i>
                </a>
                <a href="${imdb}" target="_blank" class="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[10px] font-black transition" title="IMDb">
                  IMDb
                </a>
                ${tweetUrl ? `<a href="${tweetUrl}" target="_blank" class="px-2 py-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs transition" title="Tweet"><i class="fa-brands fa-x-twitter"></i></a>` : ''}
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    function copyToClipboard(text) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('Direct download link copied to clipboard!');
      }).catch(() => {
        showToast('Link copied!');
      });
    }

    function copyAllLinks() {
      const movies = getFilteredMovies();
      const urls = movies.map(m => m['File Link']).filter(Boolean).join('\\n');
      navigator.clipboard.writeText(urls).then(() => {
        showToast(`Copied ${movies.length} batch URLs for JDownloader / Debrid!`);
      }).catch(() => {
        showToast('Copied batch links!');
      });
    }

    function showToast(msg) {
      const toast = document.getElementById('toast');
      document.getElementById('toastMsg').innerText = msg;
      toast.classList.remove('translate-y-24', 'opacity-0');
      toast.classList.add('translate-y-0', 'opacity-100');
      setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-24', 'opacity-0');
      }, 2600);
    }

    const IS_LOCAL_APP = (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost') && window.location.protocol.startsWith('http');
    let syncPollTimer = null;

    function initLocalAppControls() {
      if (!IS_LOCAL_APP) return;
      document.getElementById('privateBadge').classList.remove('hidden');
      document.getElementById('syncBtn').classList.remove('hidden');
      document.getElementById('logToggleBtn').classList.remove('hidden');
      refreshLocalLibrary();
      pollSyncStatus();
    }

    function toggleSyncLog() {
      const drawer = document.getElementById('syncLogDrawer');
      drawer.classList.toggle('hidden');
    }

    function refreshLocalLibrary() {
      if (!IS_LOCAL_APP) return;
      fetch('/api/data', { credentials: 'same-origin' })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (!data || !Array.isArray(data.movies)) return;
          rawMovies = data.movies;
          document.getElementById('stat-total').innerText = data.total;
          document.getElementById('stat-uhd').innerText = data.uhd;
          document.getElementById('stat-1080p').innerText = data.best_1080p;
          document.getElementById('stat-dvd').innerText = data.dvd;
          renderMovies();
        }).catch(() => {});
    }

    function triggerSync() {
      if (!IS_LOCAL_APP) return;
      const btn = document.getElementById('syncBtn');
      btn.disabled = true;
      document.getElementById('syncLogDrawer').classList.remove('hidden');
      fetch('/api/sync', { method: 'POST', credentials: 'same-origin' })
        .then(async r => {
          if (!r.ok && r.status !== 409) {
            throw new Error('HTTP ' + r.status);
          }
          return r.json();
        })
        .then(res => {
          showToast(res.started ? 'Sync started! Scraping X.com & updating Google Sheet...' : (res.message || 'Sync running'));
          startSyncPolling();
        })
        .catch(() => {
          btn.disabled = false;
          showToast('Failed to start sync');
        });
    }

    function startSyncPolling() {
      if (syncPollTimer) clearInterval(syncPollTimer);
      pollSyncStatus();
      syncPollTimer = setInterval(pollSyncStatus, 2000);
    }

    function pollSyncStatus() {
      if (!IS_LOCAL_APP) return;
      fetch('/api/sync/status', { credentials: 'same-origin' })
        .then(r => r.ok ? r.json() : null)
        .then(st => {
          if (!st) return;
          const btn = document.getElementById('syncBtn');
          const icon = document.getElementById('syncIcon');
          const btnText = document.getElementById('syncBtnText');
          const pill = document.getElementById('syncPhasePill');
          const logEl = document.getElementById('syncLogContent');
          const timeEl = document.getElementById('syncTimeInfo');

          pill.innerText = st.phase || 'Idle';
          if (st.log_tail && st.log_tail.length) {
            logEl.textContent = st.log_tail.join('\n');
            logEl.scrollTop = logEl.scrollHeight;
          }
          if (st.started_at) {
            timeEl.innerText = st.finished_at ? `Started ${st.started_at} · Finished ${st.finished_at}` : `Started ${st.started_at}`;
          }

          if (st.running) {
            btn.disabled = true;
            btn.classList.add('opacity-75');
            icon.classList.add('fa-spin');
            btnText.innerText = 'Syncing...';
            if (!syncPollTimer) startSyncPolling();
          } else {
            const wasPolling = Boolean(syncPollTimer);
            if (syncPollTimer) {
              clearInterval(syncPollTimer);
              syncPollTimer = null;
            }
            btn.disabled = false;
            btn.classList.remove('opacity-75');
            icon.classList.remove('fa-spin');
            btnText.innerText = 'Sync Now';
            if (wasPolling) {
              refreshLocalLibrary();
              showToast(st.exit_code === 0 ? 'Sync complete! Library & Google Sheet updated.' : 'Sync finished with warnings — check log.');
            }
          }
        }).catch(() => {});
    }

    setQualityFilter('all');
    initLocalAppControls();
  </script>
</body>
</html>
"""

def generate():
    movies = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            movies = list(reader)

    movies_json = json.dumps(movies, ensure_ascii=False)
    total_count = len(movies)
    uhd_count = sum(1 for m in movies if "4K" in m.get("Quality", ""))
    best_1080p_count = sum(1 for m in movies if "1080p Best" in m.get("Best Quality?", ""))
    dvd_count = sum(1 for m in movies if "DVD" in m.get("Quality", ""))

    content = HTML_TEMPLATE.replace("__MOVIES_JSON__", movies_json)
    content = content.replace("__TOTAL_COUNT__", str(total_count))
    content = content.replace("__UHD_COUNT__", str(uhd_count))
    content = content.replace("__1080P_COUNT__", str(best_1080p_count))
    content = content.replace("__DVD_COUNT__", str(dvd_count))

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✨ Dashboard generated successfully: {OUTPUT_HTML} ({total_count} movies embedded)")

if __name__ == "__main__":
    generate()
