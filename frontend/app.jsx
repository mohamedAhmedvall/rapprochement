/* global React, ReactDOM, Icon, API, MOCK,
          DashboardScreen, ImportScreen, ListeLignesScreen, MatchingScreen, ExportCsvScreen */
const { useState, useEffect, useCallback } = React;

function App() {
  const [tab, setTab] = useState("import");          // import | dashboard | lines | matching | export
  const [matchingId, setMatchingId] = useState(null);
  const [, setForceRender] = useState(0);
  const [hasSession, setHasSession] = useState(false);
  const [agenticLevel, setAgenticLevel] = useState(2); // 0 off · 1 banner · 2 co-pilote latéral

  const refresh = useCallback(() => setForceRender(x => x + 1), []);

  // Charge la session au démarrage
  useEffect(() => {
    API.loadSession().then(s => {
      if (s) { setHasSession(true); setTab("dashboard"); }
    }).catch(() => {});
  }, []);

  const navigate = useCallback((newTab, payload) => {
    if (newTab === "matching" && payload != null) setMatchingId(payload);
    setTab(newTab);
  }, []);

  const onSessionReady = useCallback(() => {
    setHasSession(true);
    refresh();
  }, [refresh]);

  const navItems = [
    { id: "import",    label: "Import",        icon: "upload",    enabled: true },
    { id: "dashboard", label: "Tableau de bord", icon: "dashboard", enabled: hasSession },
    { id: "lines",     label: "Lignes",        icon: "list",      enabled: hasSession },
    { id: "matching",  label: "Rapprochement", icon: "match",     enabled: hasSession },
    { id: "export",    label: "Export CSV",    icon: "csv",       enabled: hasSession },
  ];

  return (
    <div className="app">
      {/* ═══ SIDEBAR ═══ */}
      <aside className="sidebar">
        <div className="sidebar__brand">
          <img src="/static/veolia-logo.png" alt="Veolia"
               onError={(e) => { e.target.src = '/static/veolia-logo.svg'; }}/>
          <div className="sidebar__brand-text">
            <span className="sidebar__brand-title">Copilote d'Encaissement</span>
            <span className="sidebar__brand-sub">SOMEI · Division Encaissement</span>
          </div>
        </div>

        <nav className="nav">
          {navItems.map(it => (
            <button key={it.id}
              className={`nav__item ${tab === it.id ? "is-active" : ""}`}
              disabled={!it.enabled}
              onClick={() => navigate(it.id)}>
              <Icon name={it.icon} size={16}/>{it.label}
            </button>
          ))}
        </nav>

        <div className="sidebar__footer">
          {/* Niveau agentique */}
          <div style={{padding:"8px 12px", marginBottom:6}}>
            <div style={{fontSize:10, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:".04em", fontWeight:600, marginBottom:6}}>
              Niveau d'assistance
            </div>
            <div className="seg">
              {[
                {id:0, l:"Off"},
                {id:1, l:"L1"},
                {id:2, l:"L2"},
              ].map(o => (
                <button key={o.id} className={agenticLevel===o.id?"is-on":""}
                        onClick={()=>setAgenticLevel(o.id)} title={o.id===0?"Pas de suggestions":o.id===1?"Bandeaux d'aide":"Co-pilote latéral"}>
                  {o.l}
                </button>
              ))}
            </div>
          </div>
          <button className="nav__item" onClick={() => window.open("/documentation", "_blank")}>
            <Icon name="info" size={16}/>Documentation
          </button>
          <button className="nav__item" onClick={async () => {
            if (confirm("Quitter l'application ? Le serveur s'arrêtera.")) {
              await API.shutdown(); setTimeout(() => window.close(), 500);
            }
          }}>
            <Icon name="x" size={16}/>Quitter
          </button>
        </div>
      </aside>

      {/* ═══ MAIN ═══ */}
      <main className="main">
        <header className="topbar">
          <span className="topbar__title">Wat.erp · Cockpit Rapprochement</span>
          {hasSession && MOCK.session && (
            <span className="topbar__chip">{MOCK.session.date_enc}</span>
          )}
          <div className="topbar__spacer"/>
          <span style={{fontSize:11, color:"var(--text-3)"}}>
            v6 · {agenticLevel===0?"manuel":agenticLevel===1?"L1 banner":"L2 co-pilote"}
          </span>
        </header>

        <section className="content">
          {tab === "import"    && <ImportScreen    onNavigate={navigate} onSessionReady={onSessionReady}/>}
          {tab === "dashboard" && <DashboardScreen onNavigate={navigate} agenticLevel={agenticLevel}/>}
          {tab === "lines"     && <ListeLignesScreen onNavigate={navigate} agenticLevel={agenticLevel}/>}
          {tab === "matching"  && <MatchingScreen  onNavigate={navigate} ligneId={matchingId} agenticLevel={agenticLevel} onAfterDecision={refresh}/>}
          {tab === "export"    && <ExportCsvScreen onNavigate={navigate}/>}
        </section>
      </main>
    </div>
  );
}

ReactDOM.render(<App/>, document.getElementById("root"));
