/* global React */
// ============================================================
//  Couche d'adaptation API ↔ shape MOCK attendu par les écrans
//  Le frontend Claude Design utilise une shape `{id, date, source,
//  refBank, payerRaw, amount, status, confidence, matched, libelle}`.
//  Le backend Python retourne `{src, dt, s, lib, mt, ann, ref, ctr,
//  nom, sol, score, j}`. On expose `window.MOCK` peuplé dynamiquement.
// ============================================================

// Shape par défaut — sera remplacé par l'appel à API.loadSession()
window.MOCK = {
  TODAY: new Date(),
  MOCK_BANK_LINES: [],
  MOCK_CANDIDATES: [],   // candidats pour la ligne en cours d'examen
  MOCK_IMPORT_FILES: [], // fichiers importés (pour Dashboard "Sources du jour")
  FOCUS_LINE_ID: null,
  session: null,         // payload brut backend
};

// ── Mapping statut Python → bucket React ──
const PY_TO_GROUP = {
  MATCH_REF_EXACT: "auto", MATCH_REF_PREFIX: "auto", MATCH_EFICASH: "auto",
  MATCH_CONTRAT_UNIQUE: "auto", MATCH_CONTRAT_MONTANT: "auto",
  MATCH_CONTRAT_LIB: "auto", MATCH_GC_REF: "auto",
  SUGGEST_REF_EXTENDED: "review_high", SUGGEST_CONTRAT_LIBRE: "review_high",
  SUGGEST_NUM_CONTRAT: "review_high", SUGGEST_MONTANT_UNIQUE: "review_low",
  SUGGEST_NOM_CLIENT: "review_low",
  RECOUVREMENT_MANUEL: "review_high", CROSS_SOCIETE_MANUEL: "review_high",
  GC_MANUEL: "review_high",
  NON_RAPPROCHE: "no_match", SUB_NO_MATCH: "no_match",
  EXCLU_TOTAL: "exclu", SAGE_HORS_PERIMETRE: "exclu",
  VALIDATED: "validated", REJECTED: "rejected",
};
window.PY_TO_GROUP = PY_TO_GROUP;

// ── Parser date dd/MM/yyyy ──
function parseFrDate(s) {
  if (!s) return new Date();
  const m = String(s).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
  const d = new Date(s);
  return isNaN(d) ? new Date() : d;
}

// ── Extraire le payeur du libellé brut ──
function extractPayer(lib, nom) {
  if (nom && nom.trim()) return nom.trim();
  if (!lib) return "—";
  const m = lib.match(/VIREMENT\s+(?:INSTANTANE\s+)?DE\s+(.{4,40}?)(?:\s+\d|\s+VIR|\s+REF|$)/i);
  return m ? m[1].trim() : (lib.slice(0, 40));
}

// ── Mapper une ligne backend → shape MOCK_BANK_LINES ──
function mapLine(d, idx) {
  return {
    id: `BL-${d.src}-${String(idx).padStart(4, "0")}`,
    _idx: idx,
    _pyStatus: d.s,
    _justif: d.j || {},
    date: parseFrDate(d.dt),
    source: d.src,
    refBank: d.ann || "—",
    payerRaw: extractPayer(d.lib, d.nom),
    amount: d.mt || 0,
    currency: "EUR",
    status: PY_TO_GROUP[d.s] || "no_match",
    confidence: (d.score || 0) / 100,
    matched: d.ref ? {
      invoice: d.ref,
      customer: d.nom || "",
      customerId: d.ctr || "",
    } : null,
    libelle: d.lib || "",
    delta: d.delta,
    solde: d.sol || 0,
  };
}

// ── Convertit le payload session en MOCK_BANK_LINES + agrégats fichiers ──
function applySession(session) {
  if (!session || session.empty) {
    window.MOCK.MOCK_BANK_LINES = [];
    window.MOCK.MOCK_IMPORT_FILES = [];
    window.MOCK.session = null;
    return null;
  }
  window.MOCK.session = session;
  window.MOCK.MOCK_BANK_LINES = (session.details || []).map(mapLine);

  // Une "carte fichier" par source nommée
  const bySource = {};
  for (const l of session.details || []) {
    bySource[l.src] = bySource[l.src] || { name: l.src, source: "Relevé encaissement", lines: 0, errors: 0, parsed: true, size: "—" };
    bySource[l.src].lines++;
  }
  window.MOCK.MOCK_IMPORT_FILES = Object.values(bySource);

  // Date du jour = date d'encaissement
  if (session.date_enc) window.MOCK.TODAY = parseFrDate(session.date_enc);

  // Première ligne en attente = focus par défaut
  const focus = window.MOCK.MOCK_BANK_LINES.find(l =>
    l.status === "review_high" || l.status === "review_low" || l.status === "no_match"
  );
  window.MOCK.FOCUS_LINE_ID = focus ? focus.id : (window.MOCK.MOCK_BANK_LINES[0]?.id || null);

  return session;
}

// ── Construit un candidat unique pour une ligne (pour MatchingScreen) ──
function buildSingleCandidate(line) {
  if (!line.matched) return [];
  const j = line._justif || {};
  return [{
    id: line.matched.invoice,
    customer: line.matched.customer || "—",
    customerId: line.matched.customerId || "—",
    issuedAt: line.date,
    dueAt: line.date,
    amount: line.solde || line.amount,
    contract: line.matched.customerId || "—",
    status: "Impayée",
    score: line.confidence || 0,
    evidence: buildEvidenceFromJustif(j, line),
    rationale: j.note || "Match proposé par le moteur de règles.",
  }];
}

function buildEvidenceFromJustif(j, line) {
  const ev = [];
  const sameAmt = Math.abs((line.solde || 0) - line.amount) < 0.01;
  ev.push({ kind: "amount", match: sameAmt,
    label: sameAmt ? "Montant identique" : `Écart ${(line.solde - line.amount).toFixed(2)} €` });
  if (j.champ_source) ev.push({ kind: "ref", match: true, label: `${j.champ_source} : ${j.valeur_source}` });
  if (j.champ_cible) ev.push({ kind: "ref", match: true, label: `→ ${j.champ_cible} : ${j.valeur_cible}` });
  (j.transformations || []).forEach(t => ev.push({ kind: "history", match: true, label: t }));
  return ev;
}

// ============================================================
//  API CLIENT
// ============================================================
window.API = {
  async loadSession() {
    const r = await fetch("/api/session");
    const s = await r.json();
    return applySession(s);
  },

  async runImport(formData) {
    const r = await fetch("/api/run", { method: "POST", body: formData });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.error || `Import échoué (HTTP ${r.status})`);
    }
    const s = await r.json();
    if (s.error) throw new Error(s.error);
    applySession(s);
    return s;
  },

  async getProgress() {
    try { return await (await fetch("/api/progress")).json(); }
    catch { return { pct: 0, msg: "" }; }
  },

  async validateLine(idx) {
    return (await fetch("/api/validate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ line_id: idx }),
    })).json();
  },

  async rejectLine(idx, reason = "") {
    return (await fetch("/api/reject", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ line_id: idx, reason }),
    })).json();
  },

  async modifyLine(idx, ref, contrat) {
    return (await fetch("/api/modify", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ line_id: idx, ref, contrat }),
    })).json();
  },

  async searchInvoices(q) {
    const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    return (await r.json()).results || [];
  },

  exportCsv() { window.location.href = "/api/export/csv"; },
  exportXlsx() { window.location.href = "/api/export/xlsx"; },

  async shutdown() { await fetch("/api/shutdown", { method: "POST" }); },
};

window.applySession = applySession;
window.buildSingleCandidate = buildSingleCandidate;
