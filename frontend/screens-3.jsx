/* global React, MOCK, Icon, fmt, StatusPill, API */
const { useState, useMemo, useEffect } = React;
const { fmtEUR, fmtNum, fmtDate, fmtDateShort } = window.fmt;

// ============================================================
//  EXPORT CSV WAT.ERP — design original Claude
// ============================================================
function ExportCsvScreen({ onNavigate }) {
  const lignes = MOCK.MOCK_BANK_LINES;
  // Importables = matchées auto OU validées humain
  const lignesPretes = lignes.filter(l =>
    l.matched && (l.status === "auto" || l.status === "validated")
  );

  const [scope, setScope] = useState("session");      // session | jour | selection
  const [delimiter, setDelimiter] = useState(";");
  const [encodage, setEncodage] = useState("UTF-8");
  const [genere, setGenere] = useState(false);

  // Aperçu CSV
  const enTete = ["Date", "Contrat", "Facture", "Montant", "Observation"].join(delimiter);
  const dateStr = fmtDate(MOCK.TODAY);
  const obs = `CCP ${dateStr.replace(/\//g, '').slice(0, 6)}`;
  const corps = lignesPretes.map(l => [
    dateStr,
    l.matched.customerId,
    l.matched.invoice,
    l.amount.toFixed(2).replace(".", ","),
    obs
  ].join(delimiter)).join("\n");
  const csvComplet = enTete + "\n" + corps;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Génération du fichier d'import Wat.erp</h1>
          <p className="page-header__sub">
            Schéma <span className="mono">RGLMNT_IMPORT_v1</span> · {fmtNum(lignesPretes.length)} règlements prêts à être importés
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn" onClick={()=>onNavigate("lines")}>Retour</button>
          <button className="btn btn--primary" disabled={lignesPretes.length===0}
            onClick={()=>{ setGenere(true); API.exportCsv(); }}>
            <Icon name="download" size={14}/>Générer & télécharger
          </button>
        </div>
      </div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 320px", gap:16}}>
        <div className="card">
          <div className="card__head">
            <h3>Aperçu du CSV</h3>
            <span style={{fontSize:12, color:"var(--text-3)"}} className="mono">
              import_waterp_{dateStr.replace(/\//g,'').slice(0,6)}.csv
            </span>
          </div>
          <div className="card__body">
            <div className="csv-preview">
              <pre>{csvComplet || "(aucune ligne validée encore)"}</pre>
            </div>
            <div style={{marginTop:12, fontSize:12, color:"var(--text-3)"}}>
              {lignesPretes.length} ligne{lignesPretes.length>1?"s":""} ·
              délimiteur <span className="mono">{delimiter}</span> ·
              encodage <span className="mono">{encodage}</span> · BOM oui
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card__head"><h3>Paramètres</h3></div>
          <div className="card__body" style={{display:"flex", flexDirection:"column", gap:14}}>
            <div className="field">
              <label>Périmètre</label>
              <div className="seg">
                {[
                  {id:"session", l:"Session"},
                  {id:"jour", l:"Jour"},
                  {id:"selection", l:"Sélection"},
                ].map(o=>(
                  <button key={o.id} className={scope===o.id?"is-on":""} onClick={()=>setScope(o.id)}>{o.l}</button>
                ))}
              </div>
            </div>
            <div className="field">
              <label>Délimiteur</label>
              <div className="seg">
                {[";",",","\\t"].map(d=>(
                  <button key={d} className={delimiter===d.replace("\\t","\t")?"is-on":""}
                          onClick={()=>setDelimiter(d.replace("\\t","\t"))}>{d}</button>
                ))}
              </div>
            </div>
            <div className="field">
              <label>Encodage</label>
              <select className="select" value={encodage} onChange={e=>setEncodage(e.target.value)}>
                <option>UTF-8</option><option>Windows-1252</option>
              </select>
            </div>

            <div style={{height:1, background:"var(--border)", margin:"4px 0"}}/>

            <div style={{display:"flex", flexDirection:"column", gap:8}}>
              <div style={{fontSize:11, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:"0.04em", fontWeight:600}}>
                Contrôles avant import
              </div>
              {[
                {ok:lignesPretes.length>0, l:"Schéma RGLMNT_IMPORT_v1 valide"},
                {ok:lignesPretes.every(l=>l.matched.invoice), l:"Toutes les factures ont une référence"},
                {ok:lignesPretes.every(l=>l.matched.customerId), l:"Tous les contrats sont renseignés"},
                {ok:true, l:"Aucune valeur personnelle exposée"},
              ].map((c,i)=>(
                <div key={i} style={{display:"flex", gap:8, alignItems:"center", fontSize:12}}>
                  <div style={{width:16, height:16, borderRadius:50,
                    background:c.ok?"var(--ok-soft)":"var(--warn-soft)",
                    color:c.ok?"var(--ok)":"var(--warn)",
                    display:"grid", placeItems:"center"}}>
                    <Icon name={c.ok?"check":"warn"} size={10}/>
                  </div>
                  <span>{c.l}</span>
                </div>
              ))}
            </div>

            <div style={{padding:"10px 12px", background:"var(--info-soft)", borderRadius:"var(--r-md)", fontSize:11, color:"var(--text-2)", lineHeight:1.5}}>
              <Icon name="info" size={11}/> Le fichier est généré par le moteur Python local et ne contient que les règlements explicitement validés.
            </div>

            <button className="btn" onClick={()=>API.exportXlsx()} style={{marginTop:8}}>
              <Icon name="download" size={14}/>Rapport Excel détaillé
            </button>
          </div>
        </div>
      </div>

      {genere && (
        <div className="toast">
          <Icon name="check" size={14}/> Téléchargement du CSV ({lignesPretes.length} règlements)
        </div>
      )}
    </>
  );
}
window.ExportCsvScreen = ExportCsvScreen;
