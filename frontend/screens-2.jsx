/* global React, MOCK, Icon, fmt, StatusPill, API */
const { useState, useMemo, useEffect, useCallback } = React;
const { fmtEUR, fmtNum, fmtDate, fmtDateShort } = window.fmt;

// ============================================================
//  STATUS PILL — bucket React (auto/review_high/review_low/no_match/validated/rejected)
// ============================================================
const STATUS_META = {
  auto:        { cls: "pill--ok",      label: "Rapproché auto" },
  validated:   { cls: "pill--ok",      label: "Validé" },
  review_high: { cls: "pill--warn",    label: "À valider" },
  review_low:  { cls: "pill--warn",    label: "À investiguer" },
  no_match:    { cls: "pill--danger",  label: "Sans candidat" },
  rejected:    { cls: "pill--neutral", label: "Rejeté" },
  exclu:       { cls: "pill--neutral", label: "Exclu" },
};
window.StatusPill = ({ status }) => {
  const m = STATUS_META[status] || STATUS_META.review_low;
  return <span className={`pill ${m.cls}`}>{m.label}</span>;
};

// ============================================================
//  LISTE DES LIGNES — Niveau agentique L1
// ============================================================
function ListeLignesScreen({ onNavigate, agenticLevel }) {
  const [filtreStatut, setFiltreStatut] = useState("tous");
  const [recherche, setRecherche] = useState("");
  const [selection, setSelection] = useState(new Set());

  const lignes = MOCK.MOCK_BANK_LINES;

  const lignesFiltrees = useMemo(() => {
    let r = lignes;
    if (filtreStatut !== "tous") {
      if (filtreStatut === "en_attente") r = r.filter(l => l.status === "review_high" || l.status === "review_low");
      else r = r.filter(l => l.status === filtreStatut);
    }
    if (recherche.trim()) {
      const q = recherche.toLowerCase();
      r = r.filter(l =>
        (l.payerRaw || "").toLowerCase().includes(q) ||
        (l.refBank || "").toLowerCase().includes(q) ||
        (l.libelle || "").toLowerCase().includes(q) ||
        (l.id || "").toLowerCase().includes(q)
      );
    }
    return r;
  }, [lignes, filtreStatut, recherche]);

  const compteurs = useMemo(() => ({
    tous: lignes.length,
    auto: lignes.filter(l => l.status === "auto").length,
    en_attente: lignes.filter(l => l.status === "review_high" || l.status === "review_low").length,
    no_match: lignes.filter(l => l.status === "no_match").length,
    validated: lignes.filter(l => l.status === "validated").length,
    rejected: lignes.filter(l => l.status === "rejected").length,
    exclu: lignes.filter(l => l.status === "exclu").length,
  }), [lignes]);

  const toggleSelection = (id) => {
    setSelection(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };
  const toggleTous = () => {
    if (selection.size === lignesFiltrees.length) setSelection(new Set());
    else setSelection(new Set(lignesFiltrees.map(l => l.id)));
  };

  const filtres = [
    { id: "tous",       label: "Tous" },
    { id: "auto",       label: "Auto" },
    { id: "en_attente", label: "En attente" },
    { id: "no_match",   label: "Sans candidat" },
    { id: "validated",  label: "Validés" },
    { id: "rejected",   label: "Rejetés" },
    { id: "exclu",      label: "Exclus" },
  ];

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Lignes bancaires à rapprocher</h1>
          <p className="page-header__sub">
            {fmtNum(lignes.length)} lignes · session {fmtDate(MOCK.TODAY)} ·
            {" "}{Array.from(new Set(lignes.map(l=>l.source))).join(" + ") || "aucune source"}
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn"><Icon name="filter" size={14}/>Filtres avancés</button>
          <button className="btn btn--primary" onClick={()=>onNavigate("export")}>
            <Icon name="csv" size={14}/>Générer CSV Wat.erp
          </button>
        </div>
      </div>

      {agenticLevel >= 1 && compteurs.en_attente > 0 && (
        <div className="banner">
          <div className="agent-mark"><Icon name="sparkles" size={14}/></div>
          <div className="banner__msg">
            <b>{compteurs.en_attente} ligne{compteurs.en_attente>1?"s":""} en attente.</b>
            {" "}L'assistant suggère de commencer par les confiances hautes (≥ 70%) — gain estimé ~8 min.
          </div>
          <div className="banner__actions">
            <button className="btn btn--sm btn--primary" onClick={()=>{
              const premier = lignes.find(l=>l.status==="review_high"||l.status==="review_low"||l.status==="no_match");
              if (premier) onNavigate("matching", premier.id);
            }}>Lancer le tri assisté</button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="toolbar">
          <input className="input input--search" placeholder="Rechercher débiteur, référence…"
                 value={recherche} onChange={e=>setRecherche(e.target.value)} style={{width:280}}/>
          <div className="chips">
            {filtres.map(f=>(
              <button key={f.id} className={`chip ${filtreStatut===f.id?"is-on":""}`}
                      onClick={()=>setFiltreStatut(f.id)}>
                {f.label} <span className="mono" style={{opacity:0.7}}>{compteurs[f.id] || 0}</span>
              </button>
            ))}
          </div>
          <div className="spacer"/>
          {selection.size > 0 && (
            <>
              <span style={{fontSize:12, color:"var(--text-2)"}}>{selection.size} sélectionnée{selection.size>1?"s":""}</span>
              <button className="btn btn--sm" onClick={async()=>{
                for (const id of selection) {
                  const l = lignes.find(x=>x.id===id);
                  if (l && l.matched) await API.validateLine(l._idx);
                }
                location.reload();
              }}>Valider en lot</button>
              <button className="btn btn--sm btn--danger" onClick={async()=>{
                for (const id of selection) {
                  const l = lignes.find(x=>x.id===id);
                  if (l) await API.rejectLine(l._idx);
                }
                location.reload();
              }}>Rejeter</button>
            </>
          )}
        </div>

        <div style={{maxHeight:"calc(100vh - 320px)", overflow:"auto"}}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{width:36}}>
                  <input type="checkbox" checked={selection.size === lignesFiltrees.length && lignesFiltrees.length>0} onChange={toggleTous}/>
                </th>
                <th>Date</th>
                <th>Réf.</th>
                <th>Source</th>
                <th>Débiteur (libellé brut)</th>
                <th className="num">Montant</th>
                <th>Confiance</th>
                <th>Statut</th>
                <th>Facture matchée</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lignesFiltrees.map(l => (
                <tr key={l.id} className={selection.has(l.id)?"is-selected":""} onDoubleClick={()=>onNavigate("matching", l.id)}>
                  <td><input type="checkbox" checked={selection.has(l.id)} onChange={()=>toggleSelection(l.id)}/></td>
                  <td className="muted">{fmtDateShort(l.date)}</td>
                  <td className="mono" style={{fontSize:11, color:"var(--text-3)"}}>{l.id.split("-").pop()}</td>
                  <td><span className="pill pill--neutral">{l.source}</span></td>
                  <td style={{maxWidth:280, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}} title={l.libelle}>{l.payerRaw}</td>
                  <td className="num mono"><b>{fmtEUR(l.amount)}</b></td>
                  <td>
                    {l.confidence > 0 ? (
                      <div className="row" style={{gap:6}}>
                        <div style={{width:60, height:4, background:"var(--bg-sunken)", borderRadius:999, overflow:"hidden"}}>
                          <div style={{width:`${l.confidence*100}%`, height:"100%",
                            background: l.confidence>0.7?"var(--ok)":l.confidence>0.5?"var(--warn)":"var(--danger)"}}/>
                        </div>
                        <span className="mono" style={{fontSize:11, color:"var(--text-2)"}}>{Math.round(l.confidence*100)}%</span>
                      </div>
                    ) : <span style={{color:"var(--text-3)", fontSize:11}}>—</span>}
                  </td>
                  <td><StatusPill status={l.status}/></td>
                  <td className="mono" style={{fontSize:11}}>{l.matched ? l.matched.invoice : <span style={{color:"var(--text-3)"}}>—</span>}</td>
                  <td>
                    <button className="btn btn--ghost btn--sm" onClick={()=>onNavigate("matching", l.id)}>Examiner →</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {lignesFiltrees.length === 0 && (
          <div className="empty"><h4>Aucune ligne</h4><p>Ajustez vos filtres pour afficher des résultats.</p></div>
        )}
      </div>
    </>
  );
}
window.ListeLignesScreen = ListeLignesScreen;

// ============================================================
//  MATCHING SCREEN — design original avec co-pilote latéral L2
// ============================================================
function MatchingScreen({ onNavigate, ligneId, agenticLevel, onAfterDecision }) {
  const lignes = MOCK.MOCK_BANK_LINES;
  const idCible = ligneId || MOCK.FOCUS_LINE_ID || (lignes[0] && lignes[0].id);
  const idxCourant = lignes.findIndex(l => l.id === idCible);
  const ligne = lignes[idxCourant] || lignes[0];

  // Candidat unique construit à partir du match Python (ou recherche libre)
  const [candidates, setCandidates] = useState(() => ligne ? window.buildSingleCandidate(ligne) : []);
  const [candidatChoisi, setCandidatChoisi] = useState(candidates[0]?.id || null);
  const [rechercheLibre, setRechercheLibre] = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [decisionPrise, setDecisionPrise] = useState(null);
  const [busy, setBusy] = useState(false);

  // Reset au changement de ligne
  useEffect(() => {
    if (!ligne) return;
    const cs = window.buildSingleCandidate(ligne);
    setCandidates(cs);
    setCandidatChoisi(cs[0]?.id || null);
    setDecisionPrise(null);
    setRechercheLibre(false);
    setSearchQ(""); setSearchResults([]);
  }, [ligne && ligne.id]);

  const allerSuivante = useCallback(() => {
    const suivante = lignes.findIndex((l, i) => i > idxCourant &&
      (l.status === "review_high" || l.status === "review_low" || l.status === "no_match"));
    if (suivante >= 0) onNavigate("matching", lignes[suivante].id);
    else onNavigate("lines");
  }, [idxCourant, lignes, onNavigate]);

  const allerPrecedente = useCallback(() => {
    for (let i = idxCourant - 1; i >= 0; i--) {
      if (lignes[i].status === "review_high" || lignes[i].status === "review_low" || lignes[i].status === "no_match") {
        onNavigate("matching", lignes[i].id); return;
      }
    }
  }, [idxCourant, lignes, onNavigate]);

  const valider = async () => {
    if (busy || !ligne || !candidatChoisi) return;
    setBusy(true);
    try {
      await API.validateLine(ligne._idx);
      ligne.status = "validated";
      setDecisionPrise("validee");
      onAfterDecision && onAfterDecision();
      setTimeout(allerSuivante, 700);
    } finally { setBusy(false); }
  };

  const rejeter = async () => {
    if (busy || !ligne) return;
    setBusy(true);
    try {
      await API.rejectLine(ligne._idx);
      ligne.status = "rejected";
      setDecisionPrise("rejetee");
      onAfterDecision && onAfterDecision();
      setTimeout(allerSuivante, 700);
    } finally { setBusy(false); }
  };

  const lancerRecherche = async (q) => {
    setSearchQ(q);
    if (q.trim().length < 3) { setSearchResults([]); return; }
    const res = await API.searchInvoices(q);
    setSearchResults(res || []);
  };

  const choisirCandidatLibre = async (c) => {
    if (busy || !ligne) return;
    setBusy(true);
    try {
      await API.modifyLine(ligne._idx, c.ref, c.contrat);
      ligne.status = "validated";
      ligne.matched = { invoice: c.ref, customer: c.nom, customerId: c.contrat };
      ligne.solde = c.solde;
      setDecisionPrise("modifiee");
      onAfterDecision && onAfterDecision();
      setTimeout(allerSuivante, 700);
    } finally { setBusy(false); }
  };

  // Raccourcis clavier
  useEffect(() => {
    const h = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "ArrowRight" || e.key === "j") allerSuivante();
      if (e.key === "ArrowLeft" || e.key === "k") allerPrecedente();
      if (e.key === "Enter") valider();
      if (e.key === "Escape") rejeter();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [allerSuivante, allerPrecedente, candidatChoisi, ligne]);

  if (!ligne) {
    return <div className="empty" style={{padding:60}}><h4>Aucune ligne</h4><p>Lancez d'abord un import.</p></div>;
  }

  const enAttente = lignes.filter(l => l.status === "review_high" || l.status === "review_low" || l.status === "no_match");
  const positionDansFile = enAttente.findIndex(l => l.id === ligne.id) + 1;

  return (
    <div className="match-layout">
      <div className="match-main">
        <div className="match-toolbar">
          <button className="btn btn--ghost btn--sm" onClick={()=>onNavigate("lines")}>
            <Icon name="chevronLeft" size={14}/> Retour à la liste
          </button>
          <div className="match-toolbar__nav">
            <button onClick={allerPrecedente} title="Précédente (←)"><Icon name="chevronLeft" size={14}/></button>
            <button onClick={allerSuivante} title="Suivante (→)"><Icon name="chevronRight" size={14}/></button>
          </div>
          <span className="match-counter">
            <b>{positionDansFile || idxCourant+1}</b> / {enAttente.length || lignes.length} en attente
          </span>
          <div className="spacer-flex"/>
          <span style={{fontSize:11, color:"var(--text-3)"}}>Raccourcis :</span>
          <span className="kbd-hint">← →</span>
          <span style={{fontSize:11, color:"var(--text-3)"}}>nav ·</span>
          <span className="kbd-hint">⏎</span>
          <span style={{fontSize:11, color:"var(--text-3)"}}>valider ·</span>
          <span className="kbd-hint">esc</span>
          <span style={{fontSize:11, color:"var(--text-3)"}}>rejeter</span>
        </div>

        <div className="match-content">

          {/* === Ligne bancaire === */}
          <div className="bankline">
            <div className="bankline__head">
              <div>
                <div className="bankline__title">Ligne bancaire · {ligne.id}</div>
                <div style={{display:"flex", alignItems:"center", gap:8, marginTop:6}}>
                  <StatusPill status={ligne.status}/>
                  <span className="pill pill--neutral">{ligne.source}</span>
                  {ligne.confidence > 0 && (
                    <span className="pill pill--info">Confiance moteur {Math.round(ligne.confidence*100)}%</span>
                  )}
                </div>
              </div>
              <div style={{textAlign:"right"}}>
                <div style={{fontSize:11, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:"0.04em"}}>Montant crédité</div>
                <div className="bankline__amount">{fmtEUR(ligne.amount)}</div>
              </div>
            </div>

            <div className="bankline__grid">
              <div className="bankline__cell">
                <span className="lbl">Date opération</span>
                <span className="val">{fmtDate(ligne.date)}</span>
              </div>
              <div className="bankline__cell">
                <span className="lbl">Annotation / Réf.</span>
                <span className="val mono" style={{fontSize:12}}>{ligne.refBank}</span>
              </div>
              <div className="bankline__cell">
                <span className="lbl">Débiteur (extrait du libellé)</span>
                <span className="val">{ligne.payerRaw}</span>
              </div>
              <div className="bankline__cell">
                <span className="lbl">Source</span>
                <span className="val">{ligne.source}</span>
              </div>
            </div>

            <div className="bankline__libelle">{ligne.libelle}</div>
          </div>

          {/* === Liste des candidats === */}
          <div>
            <div style={{display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:10}}>
              <div>
                <h3 style={{margin:0, fontSize:14, fontWeight:600}}>Factures candidates</h3>
                <span style={{fontSize:12, color:"var(--text-3)"}}>
                  {candidates.length > 0 ? `${candidates.length} candidat(s) proposé(s) par le moteur` : "Aucun candidat trouvé"}
                </span>
              </div>
              <button className="btn btn--ghost btn--sm" onClick={()=>setRechercheLibre(r=>!r)}>
                <Icon name="search" size={12}/> {rechercheLibre ? "Masquer" : "Recherche libre dans les impayés"}
              </button>
            </div>

            {rechercheLibre && (
              <div style={{marginBottom:12, padding:12, background:"var(--bg-sunken)", borderRadius:"var(--r-md)", border:"1px solid var(--border)"}}>
                <input className="input input--search"
                  placeholder="N° facture, contrat, débiteur, montant…"
                  value={searchQ} onChange={e=>lancerRecherche(e.target.value)}
                  style={{width:"100%"}}/>
                <div style={{fontSize:11, color:"var(--text-3)", marginTop:6}}>
                  Recherche dans le référentiel impayés chargé en session (réf 14 chiffres, contrat 5-7 chiffres, nom partiel ≥ 4 car., montant exact).
                </div>
                {searchResults.length > 0 && (
                  <div style={{marginTop:10, display:"flex", flexDirection:"column", gap:6, maxHeight:300, overflow:"auto"}}>
                    {searchResults.map((c,i)=>(
                      <div key={i} className="cand" onClick={()=>choisirCandidatLibre(c)}>
                        <div className="cand__main">
                          <div className="name">
                            <span className="mono" style={{fontSize:12}}>{c.ref}</span>
                            <span style={{margin:"0 6px", color:"var(--text-3)"}}>·</span>
                            contrat <span className="ref">{c.contrat}</span>
                          </div>
                          <div className="meta">
                            <span>{c.nom}</span>
                            <span>· {c.societe}</span>
                          </div>
                        </div>
                        <div className="cand__amount">{fmtEUR(c.solde)}</div>
                      </div>
                    ))}
                  </div>
                )}
                {searchQ.length >= 3 && searchResults.length === 0 && (
                  <div style={{marginTop:8, fontSize:12, color:"var(--text-3)"}}>Aucun résultat.</div>
                )}
              </div>
            )}

            <div className="candidates">
              {candidates.length === 0 ? (
                <div className="empty">
                  <Icon name="search" size={24}/>
                  <h4 style={{marginTop:12}}>Aucun candidat dans le périmètre</h4>
                  <p>Utilisez la recherche libre ci-dessus, ou rejetez la ligne.</p>
                </div>
              ) : candidates.map((c, idx) => {
                const estChoisi = candidatChoisi === c.id;
                const meilleur = idx === 0;
                return (
                  <React.Fragment key={c.id}>
                    <div
                      className={`cand ${estChoisi?"is-selected":""}`}
                      onClick={()=>setCandidatChoisi(c.id)}
                      role="button" tabIndex={0}
                    >
                      <div className="cand__rank">#{idx+1}</div>
                      <div className="cand__main">
                        <div className="name">
                          <span className="mono" style={{color:"var(--text-2)", fontSize:12}}>{c.id}</span>
                          <span style={{margin:"0 6px", color:"var(--text-3)"}}>·</span>
                          {c.customer}
                          {meilleur && <span className="pill pill--agent" style={{marginLeft:8, fontSize:10}}><Icon name="sparkles" size={9}/> Meilleur match</span>}
                        </div>
                        <div className="meta">
                          <span><span className="ref">contrat {c.contract}</span></span>
                        </div>
                      </div>
                      <div className={`cand__amount ${Math.abs(c.amount - ligne.amount) < 0.01 ? "matches" : ""}`}>
                        {fmtEUR(c.amount)}
                        {Math.abs(c.amount - ligne.amount) >= 0.01 && (
                          <div style={{fontSize:11, color:"var(--warn)", fontWeight:400, textAlign:"right"}}>
                            Δ {fmtEUR(c.amount - ligne.amount)}
                          </div>
                        )}
                      </div>
                      <div className="cand__score-col">
                        <span className="pct" style={{color: c.score>0.75?"var(--ok)":c.score>0.5?"var(--warn)":"var(--danger)"}}>
                          {Math.round(c.score*100)}%
                        </span>
                        <div className="gauge"><i style={{width:`${c.score*100}%`, background: c.score>0.75?"var(--ok)":c.score>0.5?"var(--warn)":"var(--danger)"}}/></div>
                      </div>
                    </div>
                    {estChoisi && c.evidence && c.evidence.length > 0 && (
                      <div className="evidence">
                        {c.evidence.map((e,i)=>(
                          <div key={i} className={`evidence__item ${e.match?"match":"miss"}`}>
                            <Icon name={e.match?"check":"warn"} size={12}/>
                            {e.label}
                          </div>
                        ))}
                      </div>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* === Décision === */}
          <div style={{
            position:"sticky", bottom:0,
            background:"var(--bg-surface)",
            border:"1px solid var(--border)",
            borderRadius:"var(--r-lg)",
            padding:"14px 18px",
            display:"flex", alignItems:"center", gap:12,
            boxShadow:"var(--shadow-md)", zIndex:5
          }}>
            <div style={{flex:1}}>
              <div style={{fontSize:12, color:"var(--text-3)"}}>Décision opérateur — autorité finale</div>
              <div style={{fontSize:13, marginTop:2}}>
                {candidatChoisi
                  ? <>Rapprocher <b>{ligne.id}</b> avec <b className="mono">{candidatChoisi}</b></>
                  : <span style={{color:"var(--text-3)"}}>Sélectionnez un candidat ou rejetez la ligne</span>}
              </div>
            </div>
            <button className="btn btn--danger" onClick={rejeter} disabled={busy}>
              <Icon name="x" size={14}/>Rejeter <span className="kbd-hint">esc</span>
            </button>
            <button className="btn btn--primary" disabled={!candidatChoisi || busy} onClick={valider}>
              <Icon name="check" size={14}/>Valider le rapprochement <span className="kbd-hint">⏎</span>
            </button>
          </div>
        </div>
      </div>

      {/* === CO-PILOTE LATÉRAL — niveau agentique L2 === */}
      {agenticLevel >= 2 && (
        <aside className="copilot" aria-label="Co-pilote">
          <div className="copilot__head">
            <div className="agent-mark"><Icon name="sparkles" size={14}/></div>
            <div style={{flex:1}}>
              <div className="copilot__title">Co-pilote rapprochement</div>
              <div className="copilot__sub">Analyse en lecture · raisonnement règles</div>
            </div>
          </div>

          <div className="copilot__body">
            {candidates.length > 0 ? (
              <>
                <div style={{fontSize:11, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:"0.04em", fontWeight:600}}>
                  Synthèse
                </div>
                <div style={{
                  fontSize:13, lineHeight:1.55, color:"var(--text-1)",
                  padding:"12px 14px", background:"var(--agent-soft)",
                  border:"1px solid var(--agent-border)",
                  borderRadius:"var(--r-md)"
                }}>
                  {ligne.matched ? (
                    <>
                      Virement <b>{ligne.payerRaw}</b> de <b>{fmtEUR(ligne.amount)}</b>.
                      Candidat <b className="mono">{ligne.matched.invoice}</b> avec score moteur <b>{Math.round((ligne.confidence||0)*100)}%</b>.
                      {ligne._justif && ligne._justif.note && <> {ligne._justif.note}</>}
                    </>
                  ) : (
                    <>Aucun candidat ne dépasse le seuil. Recommandation : recherche libre ou rejet.</>
                  )}
                </div>

                <div style={{fontSize:11, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:"0.04em", fontWeight:600, marginTop:6}}>
                  Détail du raisonnement
                </div>
                {candidates.slice(0,3).map((c,idx)=>(
                  <div key={c.id} className={`sugg ${idx===0?"is-best":""}`}>
                    <div className="sugg__head">
                      <span className="sugg__rank">#{idx+1}</span>
                      <div className="sugg__score">
                        <div className="gauge"><i style={{width:`${c.score*100}%`}}/></div>
                        <span><b>{Math.round(c.score*100)}%</b></span>
                      </div>
                    </div>
                    <div className="sugg__detail">
                      <div className="ref">{c.id}</div>
                      <div style={{fontSize:13, marginTop:2}}>{c.customer}</div>
                      <div style={{fontSize:12, color:"var(--text-2)", marginTop:2}}>{fmtEUR(c.amount)}</div>
                    </div>
                    <div className="sugg__rationale">{c.rationale}</div>
                    <div className="sugg__actions">
                      <button className="btn btn--sm" onClick={()=>setCandidatChoisi(c.id)}>Sélectionner</button>
                      {idx===0 && <button className="btn btn--sm btn--primary" onClick={()=>{setCandidatChoisi(c.id); valider();}}>Accepter & valider</button>}
                    </div>
                  </div>
                ))}
              </>
            ) : (
              <div className="empty">
                <Icon name="search" size={24}/>
                <h4>Aucune piste</h4>
                <p>Le moteur n'a trouvé aucun candidat plausible. Recherche libre recommandée.</p>
              </div>
            )}
          </div>

          <div className="copilot__advisory">
            <Icon name="info" size={12}/>
            Suggestions consultatives — l'autorité de validation reste à l'opérateur. Aucune écriture en base sans validation.
          </div>
        </aside>
      )}

      {decisionPrise && (
        <div className="toast">
          <Icon name={decisionPrise==="rejetee"?"x":"check"} size={14}/>
          {decisionPrise==="validee" && "Rapprochement validé"}
          {decisionPrise==="rejetee" && "Ligne rejetée"}
          {decisionPrise==="modifiee" && "Rapprochement modifié et validé"}
          {" — passage à la suivante…"}
        </div>
      )}
    </div>
  );
}
window.MatchingScreen = MatchingScreen;
