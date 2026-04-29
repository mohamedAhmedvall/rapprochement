/* global React */
const { useState, useMemo, useEffect, useCallback } = React;

// ============================================================
//  ICONS — small set, inline SVG, stroke 1.6
// ============================================================
const Icon = ({ name, size = 16 }) => {
  const paths = {
    dashboard: <><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></>,
    upload: <><path d="M12 16V4M12 4l-4 4M12 4l4 4"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></>,
    list: <><path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1.2"/><circle cx="4" cy="12" r="1.2"/><circle cx="4" cy="18" r="1.2"/></>,
    match: <><path d="M9 7H6a3 3 0 0 0 0 6h3"/><path d="M15 7h3a3 3 0 0 1 0 6h-3"/><path d="M9 10h6"/><path d="M9 17h6"/></>,
    csv: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l3 2"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></>,
    sparkles: <><path d="M12 3l1.7 4.6L18 9l-4.3 1.4L12 15l-1.7-4.6L6 9l4.3-1.4z"/><path d="M19 14l.7 1.8L21 16l-1.3.7L19 18l-.7-1.3L17 16l1.3-.7z"/><path d="M5 17l.7 1.8L7 19l-1.3.7L5 21l-.7-1.3L3 19l1.3-.7z"/></>,
    check: <path d="M20 6L9 17l-5-5"/>,
    x: <><path d="M18 6L6 18"/><path d="M6 6l12 12"/></>,
    chevronLeft: <path d="M15 18l-6-6 6-6"/>,
    chevronRight: <path d="M9 18l6-6-6-6"/>,
    chevronDown: <path d="M6 9l6 6 6-6"/>,
    search: <><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></>,
    filter: <path d="M3 5h18l-7 9v6l-4-2v-4z"/>,
    download: <><path d="M12 4v12M12 16l-4-4M12 16l4-4"/><path d="M4 20h16"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 8v.01M12 12v4"/></>,
    warn: <><path d="M12 3l10 18H2z"/><path d="M12 10v4M12 18v.01"/></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></>,
    bolt: <path d="M13 3L4 14h7l-1 7 9-11h-7z"/>,
    bank: <><path d="M3 10h18M5 10v10M19 10v10M3 20h18M12 3l9 5H3z"/></>,
    invoice: <><path d="M6 2h12v20l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6M9 16h3"/></>,
    link: <><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    play: <path d="M5 3l14 9-14 9z"/>,
    edit: <><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></>,
    trash: <><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      {paths[name] || null}
    </svg>
  );
};

// ============================================================
//  Currency / format helpers
// ============================================================
const fmtEUR = (n) => new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(n || 0);
const fmtNum = (n) => new Intl.NumberFormat("fr-FR").format(n || 0);
const fmtDate = (d) => {
  if (!d) return "—";
  const dd = (d instanceof Date) ? d : new Date(d);
  if (isNaN(dd)) return String(d);
  return new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(dd);
};
const fmtDateShort = (d) => {
  if (!d) return "—";
  const dd = (d instanceof Date) ? d : new Date(d);
  if (isNaN(dd)) return String(d);
  return new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit" }).format(dd);
};

window.Icon = Icon;
window.fmt = { fmtEUR, fmtNum, fmtDate, fmtDateShort };
