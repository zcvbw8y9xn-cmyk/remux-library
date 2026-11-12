"""
Generates modern, standalone, ultra-fast dark-theme web dashboard (index.html)
with zero external runtime dependencies, pre-indexed search/sort, and
progressive viewport-aware rendering.
"""
import csv
import json
import os

CSV_FILE = "remux_library.csv"
OUTPUT_HTML = "index.html"

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Remux Vault — Curated 4K UHD & 1080p Cinema Library</title>
  <style>
    :root {
      --bg-950: #080d1a;
      --bg-900: #0f172a;
      --bg-850: #151f32;
      --bg-800: #1e293b;
      --border: #1e293b;
      --border-strong: #334155;
      --text-100: #f1f5f9;
      --text-300: #cbd5e1;
      --text-400: #94a3b8;
      --text-500: #64748b;
      --emerald-400: #34d399;
      --emerald-500: #10b981;
      --amber-300: #fcd34d;
      --amber-400: #fbbf24;
      --purple-300: #d8b4fe;
      --purple-400: #c084fc;
      --blue-400: #60a5fa;
      --indigo-400: #818cf8;
      --yellow-300: #fde047;
      --sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif;
      --mono: "SF Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }

    *, *::before, *::after { box-sizing: border-box; }

    html, body {
      margin: 0;
      padding: 0;
      background: var(--bg-950);
      color: var(--text-100);
      font-family: var(--sans);
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }

    body {
      display: flex;
      flex-direction: column;
    }

    ::selection { background: var(--emerald-500); color: #020617; }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: var(--bg-900); }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #475569; }

    a { color: inherit; text-decoration: none; }
    button, input, select { font-family: inherit; }

    .hidden { display: none !important; }
    .mono { font-family: var(--mono); }

    .icon {
      width: 14px;
      height: 14px;
      display: inline-block;
      vertical-align: -0.15em;
      flex-shrink: 0;
      fill: currentColor;
    }
    .icon-sm { width: 11px; height: 11px; }
    .icon-lg { width: 18px; height: 18px; }
    .icon-xl { width: 24px; height: 24px; }

    @keyframes spin { to { transform: rotate(360deg); } }
    .spin { animation: spin 0.9s linear infinite; }

    .container {
      width: 100%;
      max-width: 1280px;
      margin: 0 auto;
      padding-left: 24px;
      padding-right: 24px;
    }
    @media (max-width: 640px) {
      .container { padding-left: 16px; padding-right: 16px; }
    }

    /* Header (opaque dark surface avoids expensive scroll backdrop re-blurs) */
    .app-header {
      position: sticky;
      top: 0;
      z-index: 40;
      background: rgba(15, 23, 42, 0.96);
      border-bottom: 1px solid rgba(30, 41, 59, 0.9);
    }
    .header-inner {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding-top: 14px;
      padding-bottom: 14px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-mark {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      background: linear-gradient(135deg, #34d399, #0d9488);
      color: #020617;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 20px rgba(16, 185, 129, 0.22);
    }
    .brand-title {
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .brand-sub {
      margin: 2px 0 0;
      font-size: 12px;
      color: var(--text-400);
    }
    .pill-live {
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(16, 185, 129, 0.12);
      color: var(--emerald-400);
      border: 1px solid rgba(16, 185, 129, 0.25);
    }
    .pill-private {
      font-size: 11px;
      font-weight: 500;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--bg-800);
      color: var(--text-300);
      border: 1px solid var(--border-strong);
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 7px 12px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      border: 1px solid transparent;
      cursor: pointer;
      transition: background-color 0.12s ease, border-color 0.12s ease, opacity 0.12s ease;
    }
    .btn:disabled { opacity: 0.7; cursor: wait; }
    .btn-primary {
      background: var(--emerald-500);
      color: #020617;
      font-weight: 700;
      box-shadow: 0 6px 16px rgba(16, 185, 129, 0.2);
    }
    .btn-primary:hover:not(:disabled) { background: var(--emerald-400); }
    .btn-secondary {
      background: var(--bg-800);
      color: var(--text-300);
      border-color: var(--border-strong);
    }
    .btn-secondary:hover { background: #334155; }
    .btn-emerald-soft {
      background: rgba(16, 185, 129, 0.1);
      color: var(--emerald-400);
      border-color: rgba(16, 185, 129, 0.3);
    }
    .btn-emerald-soft:hover { background: rgba(16, 185, 129, 0.2); }
    .btn-indigo-soft {
      background: rgba(99, 102, 241, 0.12);
      color: var(--indigo-400);
      border-color: rgba(99, 102, 241, 0.3);
    }
    .btn-indigo-soft:hover { background: rgba(99, 102, 241, 0.22); }

    .log-drawer { padding-bottom: 12px; }
    .log-box {
      background: var(--bg-950);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
      font-size: 12px;
    }
    .log-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: var(--text-400);
      margin-bottom: 6px;
    }
    .log-pre {
      margin: 0;
      font-family: var(--mono);
      font-size: 11px;
      color: var(--text-300);
      max-height: 176px;
      overflow-y: auto;
      white-space: pre-wrap;
      line-height: 1.55;
    }

    /* Metrics */
    .metrics-section { padding-top: 22px; padding-bottom: 6px; }
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    @media (max-width: 768px) {
      .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    .stat-card {
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(30, 41, 59, 0.9);
      border-radius: 12px;
      padding: 15px 16px;
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .stat-icon {
      width: 40px;
      height: 40px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .stat-icon-blue { background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.25); color: var(--blue-400); }
    .stat-icon-amber { background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.25); color: var(--amber-400); }
    .stat-icon-emerald { background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.25); color: var(--emerald-400); }
    .stat-icon-purple { background: rgba(168, 85, 247, 0.12); border: 1px solid rgba(168, 85, 247, 0.25); color: var(--purple-400); }
    .stat-val { font-size: 24px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.15; }
    .stat-label { font-size: 12px; color: var(--text-400); margin-top: 2px; }

    /* Controls */
    .main-wrap {
      padding-top: 18px;
      padding-bottom: 24px;
      flex: 1;
      display: flex;
      flex-direction: column;
    }
    .controls-panel {
      background: rgba(15, 23, 42, 0.92);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 22px;
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
    }
    .controls-top {
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
    }
    .search-wrap {
      position: relative;
      flex: 1;
      min-width: 240px;
    }
    .search-icon {
      position: absolute;
      left: 13px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-500);
      pointer-events: none;
    }
    .search-input {
      width: 100%;
      background: var(--bg-950);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 9px 14px 9px 38px;
      font-size: 14px;
      color: var(--text-100);
      outline: none;
    }
    .search-input::placeholder { color: var(--text-500); }
    .search-input:focus {
      border-color: var(--emerald-500);
      box-shadow: 0 0 0 1px var(--emerald-500);
    }
    .controls-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .select-dark {
      background: var(--bg-950);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 10px;
      font-size: 12px;
      font-weight: 500;
      color: var(--text-300);
      cursor: pointer;
      outline: none;
    }
    .select-dark:focus { border-color: var(--emerald-500); }
    .view-toggle {
      display: flex;
      align-items: center;
      background: var(--bg-950);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 3px;
    }
    .view-btn {
      border: none;
      background: transparent;
      color: var(--text-400);
      padding: 6px 10px;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .view-btn:hover { color: #fff; }
    .view-btn.active {
      background: var(--bg-800);
      color: var(--emerald-400);
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
    }

    .filters-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid rgba(30, 41, 59, 0.85);
      font-size: 12px;
    }
    .filter-label { color: var(--text-500); margin-right: 4px; }
    .chip {
      padding: 5px 10px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--bg-900);
      color: var(--text-300);
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
    }
    .chip:hover { border-color: var(--border-strong); }
    .chip.active {
      background: var(--emerald-500);
      color: #020617;
      border-color: var(--emerald-500);
      font-weight: 700;
    }
    .result-count {
      margin-left: auto;
      color: var(--text-400);
      font-family: var(--mono);
      font-size: 12px;
    }

    /* Movie Grid & Performance Containment */
    .movies-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }
    @media (max-width: 1024px) {
      .movies-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 640px) {
      .movies-grid { grid-template-columns: 1fr; }
    }

    .movie-card {
      background: var(--bg-900);
      border: 1px solid rgba(30, 41, 59, 0.9);
      border-radius: 12px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.32);
      content-visibility: auto;
      contain-intrinsic-size: auto 220px;
      contain: layout style;
      transition: transform 0.12s ease, border-color 0.12s ease;
    }
    .movie-card:hover {
      border-color: var(--border-strong);
      transform: translateY(-2px);
    }
    .card-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
    }
    .card-badges {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }
    .q-badge {
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 10px;
      font-weight: 700;
      font-family: var(--mono);
    }
    .q-4k { background: var(--amber-400); color: #020617; }
    .q-dvd { background: var(--purple-400); color: #020617; }
    .q-1080 { background: #334155; color: #e2e8f0; }

    .host-pill {
      font-size: 10px;
      font-family: var(--mono);
      color: var(--text-400);
      background: var(--bg-950);
      padding: 2px 8px;
      border-radius: 5px;
      border: 1px solid var(--border);
    }
    .date-label {
      font-size: 10px;
      color: var(--text-500);
      font-family: var(--mono);
      white-space: nowrap;
    }
    .movie-title {
      margin: 0;
      font-size: 14px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.01em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .movie-year {
      font-size: 12px;
      color: var(--text-400);
      font-weight: 500;
      margin: 2px 0 10px;
    }
    .tier-wrap { margin-bottom: 12px; }
    .tier-badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 10px;
      font-weight: 700;
    }
    .tier-uhd { background: rgba(245, 158, 11, 0.14); color: var(--amber-300); border: 1px solid rgba(245, 158, 11, 0.3); }
    .tier-1080 { background: rgba(16, 185, 129, 0.14); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }
    .tier-dvd { background: rgba(168, 85, 247, 0.14); color: var(--purple-300); border: 1px solid rgba(168, 85, 247, 0.3); }
    .tier-warn { background: rgba(234, 179, 8, 0.14); color: var(--yellow-300); border: 1px solid rgba(234, 179, 8, 0.3); }
    .tier-digital { background: rgba(56, 189, 248, 0.14); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.32); }
    .tier-other { background: var(--bg-800); color: var(--text-300); border: 1px solid var(--border-strong); }

    .specs-box {
      font-size: 11px;
      font-family: var(--mono);
      color: var(--text-400);
      background: rgba(8, 13, 26, 0.75);
      padding: 8px;
      border-radius: 8px;
      border: 1px solid rgba(30, 41, 59, 0.75);
      margin-bottom: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .card-actions {
      padding-top: 9px;
      border-top: 1px solid rgba(30, 41, 59, 0.85);
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
    }
    .copy-btn {
      flex: 1;
      padding: 6px 8px;
      border-radius: 8px;
      background: rgba(16, 185, 129, 0.1);
      color: var(--emerald-400);
      border: 1px solid rgba(16, 185, 129, 0.22);
      font-size: 12px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      cursor: pointer;
    }
    .copy-btn:hover { background: rgba(16, 185, 129, 0.2); }
    .icon-btn {
      padding: 6px 10px;
      border-radius: 8px;
      background: var(--bg-800);
      color: var(--text-300);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      border: none;
    }
    .icon-btn:hover { background: #334155; color: #fff; }
    .imdb-btn {
      padding: 6px 8px;
      border-radius: 8px;
      background: rgba(245, 158, 11, 0.12);
      color: var(--amber-400);
      border: 1px solid rgba(245, 158, 11, 0.25);
      font-weight: 900;
      font-size: 10px;
      letter-spacing: -0.02em;
    }
    .imdb-btn:hover { background: rgba(245, 158, 11, 0.22); }

    /* Table View */
    .table-wrap {
      overflow-x: auto;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid var(--border);
      border-radius: 12px;
      box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
    }
    .movies-table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 12px;
    }
    .movies-table thead {
      background: var(--bg-950);
      color: var(--text-400);
      text-transform: uppercase;
      font-size: 10px;
      letter-spacing: 0.06em;
      border-bottom: 1px solid var(--border);
    }
    .movies-table th { padding: 12px 16px; font-weight: 600; }
    .movies-table td { padding: 10px 16px; border-top: 1px solid rgba(30, 41, 59, 0.65); }
    .movies-table tbody tr {
      content-visibility: auto;
      contain-intrinsic-size: auto 44px;
    }
    .movies-table tbody tr:hover { background: rgba(21, 31, 50, 0.7); }
    .td-actions { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
    .t-btn { padding: 4px 8px; border-radius: 6px; font-size: 11px; }

    /* Sentinel & Empty State */
    .scroll-sentinel {
      height: 1px;
      width: 100%;
      margin-top: 8px;
    }
    .empty-state {
      padding: 64px 0;
      text-align: center;
    }
    .empty-icon {
      width: 64px;
      height: 64px;
      border-radius: 16px;
      background: var(--bg-900);
      border: 1px solid var(--border);
      margin: 0 auto 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--text-500);
    }

    /* Toast */
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--bg-900);
      color: #fff;
      border: 1px solid rgba(16, 185, 129, 0.45);
      border-radius: 12px;
      padding: 10px 16px;
      box-shadow: 0 18px 40px rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      gap: 10px;
      z-index: 50;
      transform: translateY(96px);
      opacity: 0;
      pointer-events: none;
      transition: transform 0.2s ease, opacity 0.2s ease;
    }
    .toast.show { transform: translateY(0); opacity: 1; }

    /* Footer */
    .app-footer {
      border-top: 1px solid rgba(30, 41, 59, 0.85);
      padding: 20px 0;
      font-size: 12px;
      color: var(--text-500);
    }
    .footer-inner {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .footer-links { display: flex; align-items: center; gap: 16px; }
    .footer-links a:hover { color: var(--text-300); }
  </style>
</head>
<body>
  <!-- Inline SVG Sprite (zero external font/CSS requests) -->
  <svg xmlns="http://www.w3.org/2000/svg" class="hidden" aria-hidden="true">
    <symbol id="i-film" viewBox="0 0 24 24"><path d="M4 3h16a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm0 2v2h2V5H4zm14 0v2h2V5h-2zM4 9v2h2V9H4zm14 0v2h2V9h-2zM4 13v2h2v-2H4zm14 0v2h2v-2h-2zM4 17v2h2v-2H4zm14 0v2h2v-2h-2zM8 5v14h8V5H8z"/></symbol>
    <symbol id="i-letterboxd" viewBox="0 0 24 24"><circle cx="4.5" cy="12" r="3.4" fill="#40BCF4"/><circle cx="12" cy="12" r="3.4" fill="#00E054"/><circle cx="19.5" cy="12" r="3.4" fill="#FF8000"/></symbol>
    <symbol id="i-sync" viewBox="0 0 24 24"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0 0 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74A7.93 7.93 0 0 0 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/></symbol>
    <symbol id="i-terminal" viewBox="0 0 24 24"><path d="M20 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zM6.7 16.3l-1.4-1.4L8.2 12 5.3 9.1l1.4-1.4L11 12l-4.3 4.3zm11.3.7h-6v-2h6v2z"/></symbol>
    <symbol id="i-table" viewBox="0 0 24 24"><path d="M3 3h18a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm0 6v4h8V9H3zm10 0v4h8V9h-8zM3 15v4h8v-4H3zm10 0v4h8v-4h-8z"/></symbol>
    <symbol id="i-github" viewBox="0 0 24 24"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.55v-1.95c-3.2.69-3.87-1.54-3.87-1.54-.52-1.33-1.28-1.68-1.28-1.68-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.23-1.28-5.23-5.68 0-1.25.45-2.28 1.18-3.08-.12-.29-.51-1.46.11-3.04 0 0 .97-.31 3.16 1.18a10.9 10.9 0 0 1 5.76 0c2.19-1.49 3.16-1.18 3.16-1.18.62 1.58.23 2.75.11 3.04.74.8 1.18 1.83 1.18 3.08 0 4.41-2.69 5.39-5.25 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.55A11.5 11.5 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5z"/></symbol>
    <symbol id="i-download" viewBox="0 0 24 24"><path d="M5 20h14v-2H5v2zm7-18v11.17l3.59-3.58L17 11l-5 5-5-5 1.41-1.41L12 13.17V2z"/></symbol>
    <symbol id="i-clapper" viewBox="0 0 24 24"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V4h-4z"/></symbol>
    <symbol id="i-star" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.77 5.82 21 7 14.14l-5-4.87 6.91-1.01L12 2z"/></symbol>
    <symbol id="i-check" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></symbol>
    <symbol id="i-check-double" viewBox="0 0 24 24"><path d="M18 7l-1.41-1.41-6.34 6.34 1.41 1.41L18 7zm4.24-1.41L11.66 16.17 7.48 12l-1.41 1.41L11.66 19l12-12-1.42-1.41zM.41 13.41L6 19l1.41-1.41L1.83 12 .41 13.41z"/></symbol>
    <symbol id="i-disc" viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 13a3 3 0 1 1 0-6 3 3 0 0 1 0 6z"/></symbol>
    <symbol id="i-cloud" viewBox="0 0 24 24"><path d="M19.35 10.04A7.49 7.49 0 0 0 12 4C9.11 4 6.6 5.64 5.35 8.04A5.994 5.994 0 0 0 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z"/></symbol>
    <symbol id="i-warn" viewBox="0 0 24 24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></symbol>
    <symbol id="i-search" viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0A4.5 4.5 0 1 1 14 9.5 4.49 4.49 0 0 1 9.5 14z"/></symbol>
    <symbol id="i-grid" viewBox="0 0 24 24"><path d="M3 3h8v8H3V3zm10 0h8v8h-8V3zM3 13h8v8H3v-8zm10 0h8v8h-8v-8z"/></symbol>
    <symbol id="i-list" viewBox="0 0 24 24"><path d="M3 5h2v2H3V5zm4 0h14v2H7V5zM3 11h2v2H3v-2zm4 0h14v2H7v-2zM3 17h2v2H3v-2zm4 0h14v2H7v-2z"/></symbol>
    <symbol id="i-copy" viewBox="0 0 24 24"><path d="M16 1H4a2 2 0 0 0-2 2v14h2V3h12V1zm3 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h11v14z"/></symbol>
    <symbol id="i-x" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></symbol>
    <symbol id="i-check-circle" viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.4 14.3L6.4 12.1l1.4-1.4 2.8 2.8 5.6-5.6 1.4 1.4-7 7z"/></symbol>
  </svg>

  <!-- Header -->
  <header class="app-header">
    <div class="container header-inner">
      <div class="brand">
        <div class="brand-mark"><svg class="icon icon-lg"><use href="#i-film"/></svg></div>
        <div>
          <h1 class="brand-title">
            Remux Vault
            <span class="pill-live">Live Library</span>
            <span id="privateBadge" class="hidden pill-private">🔒 Private Local App</span>
          </h1>
          <p class="brand-sub">Curated cinema remuxes — 100% verified alive</p>
        </div>
      </div>

      <div class="header-actions">
        <button id="syncBtn" onclick="triggerSync()" class="hidden btn btn-primary">
          <svg id="syncIcon" class="icon"><use href="#i-sync"/></svg>
          <span id="syncBtnText">Sync Now</span>
        </button>
        <button id="logToggleBtn" onclick="toggleSyncLog()" class="hidden btn btn-secondary">
          <svg class="icon icon-sm"><use href="#i-terminal"/></svg>
          <span id="syncPhasePill">Idle</span>
        </button>
        <a href="https://docs.google.com/spreadsheets/d/1oqYjXc5D9eURyHUGNynR9uW9BDKNKWyGtfDBs8j_j8E" target="_blank" class="btn btn-emerald-soft">
          <svg class="icon"><use href="#i-table"/></svg>
          <span>Google Sheet</span>
        </a>
        <a href="https://github.com/zcvbw8y9xn-cmyk/remux-library" target="_blank" class="btn btn-secondary">
          <svg class="icon"><use href="#i-github"/></svg>
          <span>GitHub</span>
        </a>
        <button onclick="copyAllLinks()" class="btn btn-indigo-soft" title="Copy all active download URLs to clipboard">
          <svg class="icon"><use href="#i-download"/></svg>
          <span>Copy Batch URLs</span>
        </button>
      </div>
    </div>

    <div id="syncLogDrawer" class="hidden container log-drawer">
      <div class="log-box">
        <div class="log-head">
          <span style="font-weight:600;display:flex;align-items:center;gap:6px;"><svg class="icon icon-sm" style="color:var(--emerald-400)"><use href="#i-terminal"/></svg>Local Sync Output</span>
          <span id="syncTimeInfo" class="mono" style="font-size:11px;"></span>
        </div>
        <pre id="syncLogContent" class="log-pre">Ready. Click "Sync Now" to scrape X.com, verify links, and update Google Sheets.</pre>
      </div>
    </div>
  </header>

  <!-- Metrics Bar -->
  <section class="container metrics-section">
    <div class="metrics-grid">
      <div class="stat-card">
        <div class="stat-icon stat-icon-blue"><svg class="icon icon-lg"><use href="#i-clapper"/></svg></div>
        <div>
          <div class="stat-val" id="stat-total" style="color:#fff;">__TOTAL_COUNT__</div>
          <div class="stat-label">Total Active Movies</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon stat-icon-amber"><svg class="icon icon-lg"><use href="#i-star"/></svg></div>
        <div>
          <div class="stat-val" id="stat-uhd" style="color:var(--amber-400);">__UHD_COUNT__</div>
          <div class="stat-label">4K UHD Remuxes</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon stat-icon-emerald"><svg class="icon icon-lg"><use href="#i-check-double"/></svg></div>
        <div>
          <div class="stat-val" id="stat-1080p" style="color:var(--emerald-400);">__1080P_COUNT__</div>
          <div class="stat-label">1080p Definitive Masters</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon stat-icon-purple"><svg class="icon icon-lg"><use href="#i-disc"/></svg></div>
        <div>
          <div class="stat-val" id="stat-dvd" style="color:var(--purple-400);">__DVD_COUNT__</div>
          <div class="stat-label">Rare DVD Remuxes</div>
        </div>
      </div>
    </div>
  </section>

  <!-- Controls Bar & Movies -->
  <main class="container main-wrap">
    <div class="controls-panel">
      <div class="controls-top">
        <div class="search-wrap">
          <svg class="icon search-icon"><use href="#i-search"/></svg>
          <input id="searchInput" type="text" placeholder="Search movie title, year, quality, file host..." class="search-input" />
        </div>

        <div class="controls-right">
          <select id="sortSelect" onchange="renderMovies()" class="select-dark">
            <option value="date-desc">Tweet Date: Newest First</option>
            <option value="title-asc">Movie Title: A → Z</option>
            <option value="year-desc">Movie Year: Newest First</option>
            <option value="year-asc">Movie Year: Oldest First</option>
          </select>

          <div class="view-toggle">
            <button id="viewGridBtn" onclick="setViewMode('grid')" class="view-btn active" title="Grid Card View">
              <svg class="icon"><use href="#i-grid"/></svg>
            </button>
            <button id="viewTableBtn" onclick="setViewMode('table')" class="view-btn" title="Compact Table View">
              <svg class="icon"><use href="#i-list"/></svg>
            </button>
          </div>
        </div>
      </div>

      <div class="filters-row">
        <span class="filter-label">Quality:</span>
        <button onclick="setQualityFilter('all')" class="chip active" data-filter="all">All</button>
        <button onclick="setQualityFilter('4k')" class="chip" data-filter="4k">⭐ 4K UHD</button>
        <button onclick="setQualityFilter('1080p-best')" class="chip" data-filter="1080p-best">🟢 1080p Best</button>
        <button onclick="setQualityFilter('4k-bluray')" class="chip" data-filter="4k-bluray">💿 4K UHD Blu-ray Exists</button>
        <button onclick="setQualityFilter('4k-digital')" class="chip" data-filter="4k-digital">☁️ 4K Digital Only</button>
        <button onclick="setQualityFilter('dvd')" class="chip" data-filter="dvd">📀 DVD Remux</button>

        <span class="filter-label" style="margin-left:10px;">Host:</span>
        <select id="hostFilter" onchange="renderMovies()" class="select-dark" style="padding:4px 8px;">
          <option value="all">All File Hosts</option>
          <option value="transfer.it">transfer.it</option>
          <option value="gofile.io">gofile.io</option>
          <option value="mega.nz">mega.nz</option>
          <option value="pixeldrain.com">pixeldrain.com</option>
          <option value="drive.google.com">Google Drive</option>
        </select>

        <span id="resultCount" class="result-count">Showing __TOTAL_COUNT__ movies</span>
      </div>
    </div>

    <div id="gridContainer" class="movies-grid"></div>

    <div id="tableContainer" class="hidden table-wrap">
      <table class="movies-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Title & Year</th>
            <th>Specs</th>
            <th>Quality Tier</th>
            <th>Host</th>
            <th style="text-align:right;">Actions</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>

    <div id="scrollSentinel" class="scroll-sentinel"></div>

    <div id="emptyState" class="hidden empty-state">
      <div class="empty-icon"><svg class="icon icon-xl"><use href="#i-film"/></svg></div>
      <h3 style="font-size:14px;font-weight:700;color:var(--text-300);margin:0;">No movies match your filters</h3>
      <p style="font-size:12px;color:var(--text-500);margin:4px 0 0;">Try clearing your search terms or picking another quality tier.</p>
    </div>
  </main>

  <!-- Toast -->
  <div id="toast" class="toast">
    <svg class="icon" style="color:var(--emerald-400)"><use href="#i-check-circle"/></svg>
    <span id="toastMsg" style="font-size:12px;font-weight:600;">Copied link to clipboard!</span>
  </div>

  <!-- Footer -->
  <footer class="app-footer">
    <div class="container footer-inner">
      <div>Auto-refreshed twice daily locally &amp; synced to Google Sheets.</div>
      <div class="footer-links">
        <a href="https://letterboxd.com" target="_blank">Letterboxd</a>
        <a href="https://www.imdb.com" target="_blank">IMDb</a>
        <a href="https://docs.google.com/spreadsheets/d/1oqYjXc5D9eURyHUGNynR9uW9BDKNKWyGtfDBs8j_j8E" target="_blank">Google Sheets</a>
        <a href="https://github.com/zcvbw8y9xn-cmyk/remux-library" target="_blank">GitHub Repo</a>
      </div>
    </div>
  </footer>

  <script>
    const BATCH_SIZE = 96;
    const ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    function esc(s) {
      return String(s || '').replace(/[&<>"']/g, c => ESC_MAP[c]);
    }

    function prepareMovies(list) {
      return list.map(m => {
        const title = m['Title'] || 'Unknown';
        const year = m['Year'] || '';
        const quality = m['Quality'] || '';
        const host = m['File Host'] || '';
        const tier = m['Best Quality?'] || '';
        const tweetDate = m['Tweet Date'] || '';
        const qEnc = encodeURIComponent(title + ' ' + year);
        return {
          title,
          year,
          quality,
          host,
          tier,
          tweetDate,
          shortDate: tweetDate.split(' ')[0] || '',
          fileLink: m['File Link'] || '',
          tweetUrl: m['Tweet URL'] || '',
          letterboxd: m['Letterboxd'] || `https://letterboxd.com/search/${qEnc}/`,
          imdb: m['IMDb'] || `https://www.imdb.com/find/?q=${qEnc}&s=tt`,
          _titleEsc: esc(title),
          _yearEsc: esc(year),
          _qualityEsc: esc(quality),
          _hostEsc: esc(host),
          _tierEsc: esc(tier),
          _linkEsc: esc(m['File Link'] || ''),
          _titleLower: title.toLowerCase(),
          _yearInt: parseInt(year, 10) || 0,
          _hostLower: host.toLowerCase(),
          _is4k: quality.includes('4K'),
          _isDvd: quality.includes('DVD'),
          _is1080Best: tier.includes('1080p Best'),
          _is4kBlurayExists: tier.includes('4K UHD Blu-ray Exists'),
          _is4kDigitalOnly: tier.includes('4K Digital Only'),
          _is4kExists: tier.includes('Exists'),
          _searchBlob: (title + ' ' + year + ' ' + quality + ' ' + host + ' ' + tier).toLowerCase()
        };
      });
    }

    let rawMovies = prepareMovies(__MOVIES_JSON__);
    let currentFilter = 'all';
    let currentView = 'grid';
    let currentFiltered = rawMovies;
    let renderedCount = 0;
    let searchTimer = null;

    function getDataSignature(list) {
      if (!list || !list.length) return '0';
      const first = list[0];
      const last = list[list.length - 1];
      return `${list.length}|${first['Title'] || first.title || ''}|${last['Title'] || last.title || ''}`;
    }
    let lastSignature = getDataSignature(rawMovies);

    function updateStats() {
      let uhd = 0, best1080 = 0, dvd = 0;
      for (let i = 0; i < rawMovies.length; i++) {
        const m = rawMovies[i];
        if (m._is4k) uhd++;
        if (m._is1080Best) best1080++;
        if (m._isDvd) dvd++;
      }
      document.getElementById('stat-total').textContent = rawMovies.length;
      document.getElementById('stat-uhd').textContent = uhd;
      document.getElementById('stat-1080p').textContent = best1080;
      document.getElementById('stat-dvd').textContent = dvd;
    }

    function setQualityFilter(tier) {
      currentFilter = tier;
      const chips = document.querySelectorAll('.chip');
      for (let i = 0; i < chips.length; i++) {
        chips[i].classList.toggle('active', chips[i].dataset.filter === tier);
      }
      renderMovies();
    }

    function setViewMode(mode) {
      if (currentView === mode) return;
      currentView = mode;
      const gridBtn = document.getElementById('viewGridBtn');
      const tableBtn = document.getElementById('viewTableBtn');
      const gridContainer = document.getElementById('gridContainer');
      const tableContainer = document.getElementById('tableContainer');

      if (mode === 'grid') {
        gridBtn.classList.add('active');
        tableBtn.classList.remove('active');
        gridContainer.classList.remove('hidden');
        tableContainer.classList.add('hidden');
      } else {
        tableBtn.classList.add('active');
        gridBtn.classList.remove('active');
        gridContainer.classList.add('hidden');
        tableContainer.classList.remove('hidden');
      }
      renderMovies();
    }

    function getFilteredMovies() {
      const query = (document.getElementById('searchInput').value || '').toLowerCase().trim();
      const hostFilter = document.getElementById('hostFilter').value;
      const sort = document.getElementById('sortSelect').value;

      const out = [];
      for (let i = 0; i < rawMovies.length; i++) {
        const m = rawMovies[i];
        if (query && !m._searchBlob.includes(query)) continue;
        if (hostFilter !== 'all' && !m._hostLower.includes(hostFilter)) continue;
        if (currentFilter === '4k' && !m._is4k) continue;
        if (currentFilter === '1080p-best' && !m._is1080Best) continue;
        if (currentFilter === '4k-bluray' && !m._is4kBlurayExists) continue;
        if (currentFilter === '4k-digital' && !m._is4kDigitalOnly) continue;
        if (currentFilter === 'dvd' && !m._isDvd) continue;
        out.push(m);
      }

      if (sort === 'title-asc') {
        out.sort((a, b) => a._titleLower < b._titleLower ? -1 : (a._titleLower > b._titleLower ? 1 : 0));
      } else if (sort === 'year-desc') {
        out.sort((a, b) => b._yearInt - a._yearInt);
      } else if (sort === 'year-asc') {
        out.sort((a, b) => a._yearInt - b._yearInt);
      } else {
        out.sort((a, b) => b.tweetDate < a.tweetDate ? -1 : (b.tweetDate > a.tweetDate ? 1 : 0));
      }
      return out;
    }

    function getTierBadge(m) {
      if (!m.tier) return '';
      if (m._is4k && m.tier.includes('4K UHD')) {
        return '<span class="tier-badge tier-uhd"><svg class="icon icon-sm"><use href="#i-star"/></svg>Yes (4K UHD)</span>';
      } else if (m._is1080Best) {
        return '<span class="tier-badge tier-1080"><svg class="icon icon-sm"><use href="#i-check"/></svg>Yes (1080p Best)</span>';
      } else if (m.tier.includes('DVD is Best')) {
        return '<span class="tier-badge tier-dvd"><svg class="icon icon-sm"><use href="#i-disc"/></svg>Yes (DVD is Best)</span>';
      } else if (m._is4kBlurayExists) {
        return '<span class="tier-badge tier-warn"><svg class="icon icon-sm"><use href="#i-disc"/></svg>4K UHD Blu-ray Exists</span>';
      } else if (m._is4kDigitalOnly) {
        return '<span class="tier-badge tier-digital"><svg class="icon icon-sm"><use href="#i-cloud"/></svg>4K Digital Only (No UHD Disc)</span>';
      } else if (m._is4kExists) {
        return `<span class="tier-badge tier-warn"><svg class="icon icon-sm"><use href="#i-warn"/></svg>${m._tierEsc}</span>`;
      }
      return `<span class="tier-badge tier-other">${m._tierEsc}</span>`;
    }

    function getQualityBadge(m) {
      if (m._is4k) return '<span class="q-badge q-4k">4K UHD</span>';
      if (m._isDvd) return '<span class="q-badge q-dvd">DVD REMUX</span>';
      return '<span class="q-badge q-1080">1080p</span>';
    }

    function buildCardHtml(m) {
      return `
        <div class="movie-card">
          <div>
            <div class="card-top">
              <div class="card-badges">
                ${getQualityBadge(m)}
                <span class="host-pill">${m._hostEsc}</span>
              </div>
              <span class="date-label">${esc(m.shortDate)}</span>
            </div>
            <h3 class="movie-title" title="${m._titleEsc}">${m._titleEsc}</h3>
            <div class="movie-year">${m._yearEsc}</div>
            <div class="tier-wrap">${getTierBadge(m)}</div>
            <div class="specs-box" title="${m._qualityEsc}">${m._qualityEsc}</div>
          </div>
          <div class="card-actions">
            <button type="button" class="copy-btn" data-copy="${m._linkEsc}">
              <svg class="icon icon-sm"><use href="#i-copy"/></svg>
              <span>Copy Link</span>
            </button>
            <a href="${m._linkEsc}" target="_blank" class="icon-btn" title="Open Download Link (${m._hostEsc})"><svg class="icon"><use href="#i-download"/></svg></a>
            <a href="${esc(m.letterboxd)}" target="_blank" class="icon-btn" title="Search on Letterboxd"><svg class="icon"><use href="#i-letterboxd"/></svg></a>
            <a href="${esc(m.imdb)}" target="_blank" class="imdb-btn" title="Search on IMDb">IMDb</a>
            ${m.tweetUrl ? `<a href="${esc(m.tweetUrl)}" target="_blank" class="icon-btn" title="View Tweet"><svg class="icon"><use href="#i-x"/></svg></a>` : ''}
          </div>
        </div>`;
    }

    function buildRowHtml(m) {
      return `
        <tr>
          <td class="mono" style="color:var(--text-400);white-space:nowrap;font-size:11px;">${esc(m.tweetDate)}</td>
          <td style="font-weight:700;color:var(--text-100);">${m._titleEsc} <span style="color:var(--text-400);font-size:11px;font-weight:400;">(${m._yearEsc})</span></td>
          <td class="mono" style="font-size:11px;color:var(--text-300);">${m._qualityEsc}</td>
          <td>${getTierBadge(m)}</td>
          <td class="mono" style="color:var(--text-400);font-size:11px;">${m._hostEsc}</td>
          <td>
            <div class="td-actions">
              <button type="button" class="copy-btn t-btn" style="flex:0;" data-copy="${m._linkEsc}" title="Copy Link"><svg class="icon icon-sm"><use href="#i-copy"/></svg></button>
              <a href="${m._linkEsc}" target="_blank" class="icon-btn t-btn" title="Download (${m._hostEsc})"><svg class="icon icon-sm"><use href="#i-download"/></svg></a>
              <a href="${esc(m.letterboxd)}" target="_blank" class="icon-btn t-btn" title="Letterboxd"><svg class="icon icon-sm"><use href="#i-letterboxd"/></svg></a>
              <a href="${esc(m.imdb)}" target="_blank" class="imdb-btn t-btn" title="IMDb">IMDb</a>
              ${m.tweetUrl ? `<a href="${esc(m.tweetUrl)}" target="_blank" class="icon-btn t-btn" title="Tweet"><svg class="icon icon-sm"><use href="#i-x"/></svg></a>` : ''}
            </div>
          </td>
        </tr>`;
    }

    function appendNextBatch() {
      if (renderedCount >= currentFiltered.length) return;
      const end = Math.min(renderedCount + BATCH_SIZE, currentFiltered.length);
      const chunks = [];
      if (currentView === 'grid') {
        for (let i = renderedCount; i < end; i++) chunks.push(buildCardHtml(currentFiltered[i]));
        document.getElementById('gridContainer').insertAdjacentHTML('beforeend', chunks.join(''));
      } else {
        for (let i = renderedCount; i < end; i++) chunks.push(buildRowHtml(currentFiltered[i]));
        document.getElementById('tableBody').insertAdjacentHTML('beforeend', chunks.join(''));
      }
      renderedCount = end;
    }

    function renderMovies() {
      currentFiltered = getFilteredMovies();
      renderedCount = 0;
      document.getElementById('resultCount').textContent = `Showing ${currentFiltered.length} movies`;

      const grid = document.getElementById('gridContainer');
      const tableBody = document.getElementById('tableBody');
      const emptyState = document.getElementById('emptyState');

      grid.innerHTML = '';
      tableBody.innerHTML = '';

      if (currentFiltered.length === 0) {
        emptyState.classList.remove('hidden');
        return;
      }
      emptyState.classList.add('hidden');
      appendNextBatch();
    }

    // Debounced search + Escape to clear
    const searchEl = document.getElementById('searchInput');
    searchEl.addEventListener('input', () => {
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(renderMovies, 45);
    });
    searchEl.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && searchEl.value) {
        searchEl.value = '';
        renderMovies();
      }
    });

    // Event delegation for Copy Link buttons
    function handleCopyDelegation(e) {
      const btn = e.target.closest('[data-copy]');
      if (!btn) return;
      copyToClipboard(btn.dataset.copy);
    }
    document.getElementById('gridContainer').addEventListener('click', handleCopyDelegation);
    document.getElementById('tableBody').addEventListener('click', handleCopyDelegation);

    // Seamless infinite batching via IntersectionObserver
    const sentinel = document.getElementById('scrollSentinel');
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          appendNextBatch();
        }
      }, { rootMargin: '650px 0px' });
      io.observe(sentinel);
    }

    let toastTimer = null;
    function showToast(msg) {
      const toast = document.getElementById('toast');
      document.getElementById('toastMsg').textContent = msg;
      toast.classList.add('show');
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('show'), 2400);
    }

    function copyToClipboard(text) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('Direct download link copied to clipboard!');
      }).catch(() => showToast('Link copied!'));
    }

    function copyAllLinks() {
      const urls = currentFiltered.map(m => m.fileLink).filter(Boolean).join('\n');
      navigator.clipboard.writeText(urls).then(() => {
        showToast(`Copied ${currentFiltered.length} batch URLs for JDownloader / Debrid!`);
      }).catch(() => showToast('Copied batch links!'));
    }

    const IS_LOCAL_APP = (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost') && window.location.protocol.startsWith('http');
    let syncPollTimer = null;

    function initLocalAppControls() {
      if (!IS_LOCAL_APP) return;
      document.getElementById('privateBadge').classList.remove('hidden');
      document.getElementById('syncBtn').classList.remove('hidden');
      document.getElementById('logToggleBtn').classList.remove('hidden');
      refreshLocalLibrary(true);
      pollSyncStatus();
    }

    function toggleSyncLog() {
      document.getElementById('syncLogDrawer').classList.toggle('hidden');
    }

    function refreshLocalLibrary(skipIfUnchanged) {
      if (!IS_LOCAL_APP) return;
      fetch('/api/data', { credentials: 'same-origin' })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (!data || !Array.isArray(data.movies)) return;
          const sig = getDataSignature(data.movies);
          if (skipIfUnchanged && sig === lastSignature) return;
          lastSignature = sig;
          rawMovies = prepareMovies(data.movies);
          document.getElementById('stat-total').textContent = data.total;
          document.getElementById('stat-uhd').textContent = data.uhd;
          document.getElementById('stat-1080p').textContent = data.best_1080p;
          document.getElementById('stat-dvd').textContent = data.dvd;
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
          if (!r.ok && r.status !== 409) throw new Error('HTTP ' + r.status);
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

          pill.textContent = st.phase || 'Idle';
          if (st.log_tail && st.log_tail.length) {
            logEl.textContent = st.log_tail.join('\n');
            logEl.scrollTop = logEl.scrollHeight;
          }
          if (st.started_at) {
            timeEl.textContent = st.finished_at ? `Started ${st.started_at} · Finished ${st.finished_at}` : `Started ${st.started_at}`;
          }

          if (st.running) {
            btn.disabled = true;
            icon.classList.add('spin');
            btnText.textContent = 'Syncing...';
            if (!syncPollTimer) startSyncPolling();
          } else {
            const wasPolling = Boolean(syncPollTimer);
            if (syncPollTimer) {
              clearInterval(syncPollTimer);
              syncPollTimer = null;
            }
            btn.disabled = false;
            icon.classList.remove('spin');
            btnText.textContent = 'Sync Now';
            if (wasPolling) {
              refreshLocalLibrary(false);
              showToast(st.exit_code === 0 ? 'Sync complete! Library & Google Sheet updated.' : 'Sync finished with warnings — check log.');
            }
          }
        }).catch(() => {});
    }

    renderMovies();
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

    movies_json = json.dumps(movies, ensure_ascii=False, separators=(",", ":"))
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
