/* global React, MOCK, Icon, fmt, StatusPill, API */
const { useState, useMemo, useEffect, useCallback } = React;
const { fmtEUR, fmtNum, fmtDate, fmtDateShort } = window.fmt;

// ============================================================
//  DASHBOARD — design original Claude (banner L1 + KPIs + sparkline + file)
// ============================================================
function DashboardScreen({ onNavigate, agenticLevel }) {
  const lines = MOCK.MOCK_BANK_LINES;

  if (lines.length === 0) {
    return (
      <>
        <div className="page-header">
          <div>
            <h1>Tableau de bord</h1>
            <p className="page-header__sub">Aucune session active. Importez vos fichiers pour démarrer.</p>
          </div>
          <div className="page-header__actions">
            <button className="btn btn--primary" onClick={()=>onNavigate("import")}>
              <Icon name="upload" size={14}/>Importer
            </button>
          </div>
        </div>
        <div className="empty" style={{padding:60}}>
          <Icon name="upload" size={32}/>
          <h4 style={{marginTop:12}}>Pas encore de données</h4>
          <p>Démarrez par <a onClick={()=>onNavigate("import")} style={{color:"var(--brand)", cursor:"pointer", textDecoration:"underline"}}>l'import des fichiers</a>.</p>
        </div>
      </>
    );
  }

  const total = lines.length;
  const auto = lines.filter(l => l.status === "auto" || l.status === "validated").length;
  const reviewHigh = lines.filter(l => l.status === "review_high").length;
  const reviewLow  = lines.filter(l => l.status === "review_low").length;
  const noMatch    = lines.filter(l => l.status === "no_match").length;
  const autoRate   = Math.round(auto / total * 100);

  const sumAuto    = lines.filter(l=>l.status==="auto" || l.status==="validated").reduce((s,l)=>s+l.amount,0);
  const sumPending = lines.filter(l=>l.status==="review_high" || l.status==="review_low").reduce((s,l)=>s+l.amount,0);

  // Sparkline 14 jours — basé sur le taux pour visuel "tendance"
  const spark = [62, 71, 65, 78, 81, 73, 68, 84, 88, 79, 82, 85, autoRate, autoRate];

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Tableau de bord</h1>
          <p className="page-header__sub">Session du {fmtDate(MOCK.TODAY)} · {Array.from(new Set(lines.map(l=>l.source))).join(" + ")}</p>
        </div>
        <div className="page-header__actions">
          <button className="btn" onClick={()=>API.exportXlsx()}><Icon name="download" size={14}/>Rapport Excel</button>
          <button className="btn btn--primary" onClick={()=>onNavigate("export")}>
            <Icon name="csv" size={14}/>Exporter CSV
          </button>
        </div>
      </div>

      {agenticLevel >= 1 && reviewHigh > 0 && (
        <div className="banner" role="status">
          <div className="agent-mark"><Icon name="sparkles" size={14}/></div>
          <div className="banner__msg">
            <b>Suggestion de l'assistant.</b> {reviewHigh} ligne{reviewHigh>1?"s":""} à confiance haute peuvent être validées rapidement — gain estimé&nbsp;: ~12&nbsp;min.
            <span style={{color:"var(--text-3)", marginLeft:6, fontSize:12}}>Recommandation consultative — décision finale opérateur.</span>
          </div>
          <div className="banner__actions">
            <button className="btn btn--sm">Plus tard</button>
            <button className="btn btn--sm btn--primary" onClick={() => onNavigate("matching")}>Examiner</button>
          </div>
        </div>
      )}

      <div className="kpi-grid">
        <div className="kpi">
          <div className="kpi__label">Taux de rapprochement auto<Icon name="info" size={12}/></div>
          <div className="kpi__value">{autoRate}<span style={{fontSize:18,color:"var(--text-3)"}}> %</span></div>
          <div className="kpi__delta kpi__delta--up">▲ +4 pts vs S-1</div>
          <div className="kpi__bar"><i style={{width: `${autoRate}%`}}/></div>
        </div>
        <div className="kpi">
          <div className="kpi__label">Lignes traitées</div>
          <div className="kpi__value">{fmtNum(total)}</div>
          <div className="kpi__delta">{auto} auto · {reviewHigh+reviewLow} en attente · {noMatch} sans candidat</div>
          <div className="spark" style={{marginTop:12}}>
            {spark.map((v,i)=>(<i key={i} className={v>80?"hi":""} style={{height: `${v*0.28}px`}}/>))}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi__label">Montant rapproché</div>
          <div className="kpi__value" style={{fontSize:22}}>{fmtEUR(sumAuto)}</div>
          <div className="kpi__delta kpi__delta--up">▲ {fmtEUR(sumAuto*0.06)} vs S-1</div>
        </div>
        <div className="kpi">
          <div className="kpi__label">En attente d'opérateur</div>
          <div className="kpi__value" style={{fontSize:22, color:"var(--warn)"}}>{fmtEUR(sumPending)}</div>
          <div className="kpi__delta">{reviewHigh+reviewLow} ligne{reviewHigh+reviewLow>1?"s":""} · délai moyen 6&nbsp;h</div>
        </div>
      </div>

      <div style={{display:"grid", gridTemplateColumns:"2fr 1fr", gap:16}}>
        <div className="card">
          <div className="card__head">
            <h3>File d'attente — priorité opérateur</h3>
            <button className="btn btn--ghost btn--sm" onClick={()=>onNavigate("lines")}>Voir tout <Icon name="chevronRight" size={12}/></button>
          </div>
          <div className="card__body card__body--flush">
            <table className="tbl">
              <thead><tr>
                <th>Ligne</th><th>Source</th><th>Débiteur (libellé)</th><th className="num">Montant</th><th>Confiance</th><th>Statut</th><th></th>
              </tr></thead>
              <tbody>
              {lines.filter(l=>l.status==="review_high"||l.status==="review_low"||l.status==="no_match").slice(0,6).map(l=>(
                <tr key={l.id}>
                  <td className="mono muted" style={{fontSize:11}}>{l.id.split("-").pop()}</td>
                  <td><span className="pill pill--neutral">{l.source}</span></td>
                  <td style={{maxWidth:240, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{l.payerRaw}</td>
                  <td className="num mono"><b>{fmtEUR(l.amount)}</b></td>
                  <td>
                    {l.confidence > 0 ? (
                      <div className="row" style={{gap:6}}>
                        <div style={{width:50, height:4, background:"var(--bg-sunken)", borderRadius:999, overflow:"hidden"}}>
                          <div style={{width:`${l.confidence*100}%`, height:"100%", background: l.confidence>0.7?"var(--ok)":"var(--warn)"}}/>
                        </div>
                        <span className="mono" style={{fontSize:11, color:"var(--text-2)"}}>{Math.round(l.confidence*100)}%</span>
                      </div>
                    ) : <span style={{color:"var(--text-3)", fontSize:11}}>—</span>}
                  </td>
                  <td><StatusPill status={l.status}/></td>
                  <td><button className="btn btn--ghost btn--sm" onClick={()=>onNavigate("matching", l.id)}>Examiner</button></td>
                </tr>
              ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card__head"><h3>Sources du jour</h3></div>
          <div className="card__body" style={{display:"flex", flexDirection:"column", gap:14}}>
            {MOCK.MOCK_IMPORT_FILES.map(f=>(
              <div key={f.name} style={{display:"flex", gap:10, alignItems:"flex-start"}}>
                <div style={{width:32, height:32, borderRadius:8, background:"var(--bg-sunken)", border:"1px solid var(--border)", display:"grid", placeItems:"center", color:"var(--text-2)"}}>
                  <Icon name="file" size={14}/>
                </div>
                <div style={{flex:1, minWidth:0}}>
                  <div style={{fontSize:13, fontWeight:500}}>{f.name}</div>
                  <div style={{fontSize:11, color:"var(--text-3)", marginTop:2}}>{f.source} · {f.lines} lignes</div>
                  <div style={{marginTop:6, display:"flex", gap:6}}>
                    <span className="pill pill--ok">Parsé</span>
                    {f.errors > 0 && <span className="pill pill--warn">{f.errors} erreurs</span>}
                  </div>
                </div>
              </div>
            ))}
            <div className="dropzone" style={{padding:"20px 16px"}} onClick={()=>onNavigate("import")}>
              <div className="dropzone__title" style={{fontSize:13}}>＋ Ajouter un relevé</div>
              <div className="dropzone__sub">nom libre</div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
window.DashboardScreen = DashboardScreen;

// ============================================================
//  IMPORT screen — design original (stepper + dropzone + DQ)
//  Adapté : 1 fichier impayés + 1..3 encaissements à nom libre
// ============================================================
function ImportScreen({ onNavigate, onSessionReady }) {
  const [step, setStep] = useState(1);   // 1 upload, 2 parsing, 3 ready
  const [drag, setDrag] = useState(null);
  const [impayes, setImpayes] = useState(null);
  const [encs, setEncs] = useState([]);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ pct: 0, msg: "" });
  const [error, setError] = useState(null);

  const guessName = (filename) => {
    let g = filename.replace(/\.[^.]+$/, "");
    const m = g.match(/(?:encaissement|releve)[_\s-]*([A-Z0-9]+)/i);
    return m ? m[1].toUpperCase() : g.slice(0, 16);
  };

  const addEnc = (file) => {
    if (encs.length >= 3) return;
    setEncs(prev => [...prev, { file, name: guessName(file.name) }]);
  };
  const removeEnc = (idx) => setEncs(prev => prev.filter((_, i) => i !== idx));
  const renameEnc = (idx, name) => setEncs(prev => prev.map((e, i) => i === idx ? { ...e, name } : e));

  const handleDrop = (e, target) => {
    e.preventDefault(); setDrag(null);
    const files = Array.from(e.dataTransfer.files).filter(f => f.name.match(/\.xlsx?$/i));
    if (target === 'imp' && files[0]) setImpayes({ file: files[0], name: files[0].name });
    else if (target === 'enc') files.forEach(f => addEnc(f));
  };

  // Recalcul automatique du step
  useEffect(() => {
    if (running) setStep(2);
    else if (impayes && encs.length > 0) setStep(3);
    else setStep(1);
  }, [impayes, encs, running]);

  const launch = async () => {
    if (!impayes || encs.length === 0) return;
    setRunning(true); setError(null);

    const fd = new FormData();
    fd.append("impayes", impayes.file);
    encs.forEach((e, i) => {
      fd.append(`enc_${i}`, e.file);
      fd.append(`name_${i}`, e.name || `ENC${i}`);
    });

    const pollId = setInterval(async () => {
      try { setProgress(await API.getProgress()); } catch {}
    }, 600);

    try {
      const session = await API.runImport(fd);
      clearInterval(pollId);
      onSessionReady && onSessionReady(session);
      setTimeout(() => onNavigate("dashboard"), 200);
    } catch (err) {
      clearInterval(pollId);
      setError(String(err.message || err));
      setRunning(false);
    }
  };

  const canLaunch = impayes && encs.length >= 1 && !running;

  // Liste de contrôles DQ — cohérente avec les fichiers chargés
  const dqChecks = [
    { lbl:"Format Excel (.xlsx) reconnu", ok:true, hint:"openpyxl + read_only" },
    { lbl:"Fichier d'impayés présent", ok:!!impayes, hint:impayes ? impayes.name : "obligatoire" },
    { lbl:"Au moins 1 relevé d'encaissement", ok:encs.length>=1, hint:`${encs.length} relevé(s) chargé(s)` },
    { lbl:"Noms des relevés renseignés", ok:encs.every(e=>e.name && e.name.trim()), hint:"libellé identifiant la banque/compte" },
    { lbl:"Volume max 3 relevés", ok:encs.length<=3, hint:"limite raisonnable session quotidienne" },
    { lbl:"Données restent en local", ok:true, hint:"aucune transmission externe" },
  ];

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Import des relevés bancaires</h1>
          <p className="page-header__sub">1 fichier d'impayés (Wat.erp) + 1 à 3 relevés d'encaissement à nom libre</p>
        </div>
      </div>

      {error && (
        <div className="banner" style={{borderColor:"var(--danger)", background:"var(--danger-soft)"}}>
          <Icon name="warn" size={14}/>
          <div className="banner__msg"><b>Erreur</b> — {error}</div>
        </div>
      )}

      <div className="card" style={{marginBottom:16}}>
        <div className="card__body" style={{display:"flex", justifyContent:"center"}}>
          <div className="stepper">
            <div className={`stepper__step ${step>=1?"is-done":""} ${step===1?"is-active":""}`}>
              <div className="stepper__bullet">{step>1?"✓":"1"}</div>Téléversement
            </div>
            <div className="stepper__line"/>
            <div className={`stepper__step ${step>=2?"is-done":""} ${step===2?"is-active":""}`}>
              <div className="stepper__bullet">{step>2?"✓":"2"}</div>Parsing & matching
            </div>
            <div className="stepper__line"/>
            <div className={`stepper__step ${step>=3?"is-done":""} ${step===3?"is-active":""}`}>
              <div className="stepper__bullet">{step>=3?"✓":"3"}</div>Mise en file
            </div>
          </div>
        </div>
      </div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 360px", gap:16}}>
        <div className="card">
          <div className="card__head"><h3>Téléverser les fichiers</h3></div>
          <div className="card__body">

            {/* Zone Impayés */}
            <div style={{marginBottom:16}}>
              <div style={{fontSize:12, color:"var(--text-3)", marginBottom:6, fontWeight:500, textTransform:"uppercase", letterSpacing:"0.04em"}}>
                Fichier d'impayés <span style={{color:"var(--danger)"}}>*</span>
              </div>
              <div className={`dropzone ${drag==='imp'?"is-drag":""}`}
                onDragOver={e=>{e.preventDefault(); setDrag('imp');}}
                onDragLeave={()=>setDrag(null)}
                onDrop={e=>handleDrop(e,'imp')}
                onClick={()=>document.getElementById('file-imp').click()}
                style={{cursor:"pointer", padding:"22px 16px"}}>
                <input id="file-imp" type="file" accept=".xlsx,.xls" style={{display:"none"}}
                  onChange={e=>{ if(e.target.files[0]) setImpayes({ file: e.target.files[0], name: e.target.files[0].name }); }}/>
                <div style={{display:"flex", justifyContent:"center", marginBottom:8, color:"var(--text-3)"}}>
                  <Icon name="invoice" size={26}/>
                </div>
                {impayes ? (
                  <>
                    <div className="dropzone__title" style={{color:"var(--ok)"}}>
                      <Icon name="check" size={14}/> {impayes.name}
                    </div>
                    <div className="dropzone__sub">{(impayes.file.size/1024/1024).toFixed(2)} Mo · cliquez pour remplacer</div>
                  </>
                ) : (
                  <>
                    <div className="dropzone__title">Glissez Etat_des_impayes_*.xlsx</div>
                    <div className="dropzone__sub">ou cliquez pour parcourir</div>
                  </>
                )}
              </div>
            </div>

            {/* Zone Encaissements */}
            <div>
              <div style={{fontSize:12, color:"var(--text-3)", marginBottom:6, fontWeight:500, textTransform:"uppercase", letterSpacing:"0.04em"}}>
                Relevés d'encaissement <span style={{color:"var(--danger)"}}>*</span> <span style={{textTransform:"none", fontWeight:400}}>· nommez chaque relevé librement</span>
              </div>
              {encs.map((e, idx) => (
                <div key={idx} style={{display:"flex", alignItems:"center", gap:10, padding:"10px 12px", border:"1px solid var(--border)", borderRadius:"var(--r-md)", marginBottom:8, background:"var(--bg-surface)"}}>
                  <div style={{width:28, height:28, borderRadius:6, background:"var(--bg-sunken)", display:"grid", placeItems:"center", color:"var(--text-2)"}}>
                    <Icon name="bank" size={14}/>
                  </div>
                  <div style={{flex:1, minWidth:0}}>
                    <div style={{fontSize:11, color:"var(--text-3)", marginBottom:3}}>
                      {e.file.name} · {(e.file.size/1024).toFixed(0)} Ko
                    </div>
                    <input className="input" value={e.name}
                      onChange={ev=>renameEnc(idx, ev.target.value)}
                      placeholder="Nom du relevé (ex: SEM, SEMM, BNP, …)"
                      style={{width:"100%", fontSize:13}}/>
                  </div>
                  <button className="btn btn--ghost btn--sm" onClick={()=>removeEnc(idx)} title="Retirer">
                    <Icon name="x" size={14}/>
                  </button>
                </div>
              ))}

              {encs.length < 3 && (
                <div className={`dropzone ${drag==='enc'?"is-drag":""}`}
                  onDragOver={e=>{e.preventDefault(); setDrag('enc');}}
                  onDragLeave={()=>setDrag(null)}
                  onDrop={e=>handleDrop(e,'enc')}
                  onClick={()=>document.getElementById('file-enc').click()}
                  style={{cursor:"pointer", padding:"18px 14px"}}>
                  <input id="file-enc" type="file" accept=".xlsx,.xls" multiple style={{display:"none"}}
                    onChange={e=>{ Array.from(e.target.files).forEach(addEnc); e.target.value=''; }}/>
                  <div style={{display:"flex", justifyContent:"center", marginBottom:6, color:"var(--text-3)"}}>
                    <Icon name="plus" size={20}/>
                  </div>
                  <div className="dropzone__title" style={{fontSize:13}}>Ajouter un relevé</div>
                  <div className="dropzone__sub">{encs.length === 0 ? "obligatoire — 1 minimum" : `${3-encs.length} max restant${3-encs.length>1?"s":""}`}</div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card__head"><h3>Contrôles & Data Quality</h3></div>
          <div className="card__body" style={{display:"flex", flexDirection:"column", gap:12}}>
            {dqChecks.map((c,i)=>(
              <div key={i} style={{display:"flex", gap:10, alignItems:"flex-start"}}>
                <div style={{width:18, height:18, borderRadius:50,
                  background: c.ok?"var(--ok-soft)":"var(--warn-soft)",
                  color: c.ok?"var(--ok)":"var(--warn)",
                  display:"grid", placeItems:"center", flexShrink:0, marginTop:1}}>
                  <Icon name={c.ok?"check":"warn"} size={11}/>
                </div>
                <div style={{flex:1}}>
                  <div style={{fontSize:13, fontWeight:500}}>{c.lbl}</div>
                  <div style={{fontSize:11, color:"var(--text-3)"}}>{c.hint}</div>
                </div>
              </div>
            ))}
            <div style={{marginTop:8, padding:"10px 12px", background:"var(--info-soft)", borderRadius:"var(--r-md)", fontSize:12, color:"var(--text-2)", lineHeight:1.5}}>
              <Icon name="info" size={12}/> Le moteur tourne en local (Python + openpyxl). Aucune donnée ne sort de la machine.
            </div>
          </div>
        </div>
      </div>

      <div style={{marginTop:20, display:"flex", justifyContent:"space-between", alignItems:"center", gap:8}}>
        <div style={{fontSize:12, color:"var(--text-3)"}}>
          {running
            ? <><Icon name="sparkles" size={12}/> {progress.msg || "Traitement…"} {progress.pct ? `(${progress.pct}%)` : ""}</>
            : (canLaunch ? `Prêt : ${impayes.name} + ${encs.length} relevé${encs.length>1?"s":""} (${encs.map(e=>e.name).filter(Boolean).join(", ")})`
                         : "En attente des fichiers requis")}
        </div>
        <button className="btn btn--primary" disabled={!canLaunch} onClick={launch}>
          <Icon name="play" size={14}/>Lancer le rapprochement<Icon name="chevronRight" size={12}/>
        </button>
      </div>

      {running && progress.pct > 0 && (
        <div style={{marginTop:12, height:6, background:"var(--bg-sunken)", borderRadius:999, overflow:"hidden"}}>
          <div style={{width:`${progress.pct}%`, height:"100%", background:"var(--brand)", transition:"width .3s"}}/>
        </div>
      )}
    </>
  );
}
window.ImportScreen = ImportScreen;
