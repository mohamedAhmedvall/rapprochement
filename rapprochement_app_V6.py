#!/usr/bin/env python3
"""
RAPPROCHEMENT ENCAISSEMENTS — V6
SOMEI / Veolia · Division Encaissement

V6 vs V5 :
  • Import flexible : 1 fichier impayés + 1..3 encaissements à nom libre
  • API REST séparée du HTML (frontend React/Babel servi en static)
  • Validation humaine : valider / rejeter / modifier par ligne
  • Recherche libre dans les impayés pour ré-affecter une ligne
  • Export CSV ne contenant QUE les lignes validées (auto + manuelles)

Le moteur de matching reste celui de V5 (ne pas casser ce qui marche).
"""

import sys, os, re, io, json, time, threading, webbrowser, tempfile, shutil
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, unquote

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    print("ERREUR : openpyxl manquant. Lancer : pip install openpyxl")
    sys.exit(1)

# ── On réutilise le moteur de V5 ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rapprochement_app_V5 import (
    SOCIETES_RECOUVREMENT, RATIO_MAX_PREFIX, STATUTS_IMPORTABLES,
    SCORES_CONFIANCE, STATUTS_SUGGESTIONS,
    detecter_date_encaissement, detecter_header_row,
    charger_impayes, traiter_fichier,
    generer_rapport_xlsx,
)

# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════
PORT = 8765
WORK_DIR = os.path.join(tempfile.gettempdir(), 'rapprochement_v6')
os.makedirs(WORK_DIR, exist_ok=True)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')
STATIC_DIR   = os.path.join(FRONTEND_DIR, 'static')
DOCS_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs')

# ═══════════════════════════════════════════════════════════════════════
# ÉTAT GLOBAL — session en mémoire
# ═══════════════════════════════════════════════════════════════════════
session_state = {
    'date_enc': None,        # datetime
    'date_saisie': None,     # datetime
    'impayes_index': None,   # (idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom)
    'resultats': [],         # liste enrichie avec 'human_decision'
    'sources': [],           # noms libres des relevés
}
progress_state = {'pct': 0, 'msg': 'En attente'}
generated_files = {'csv': None, 'xlsx': None}
_server_ref = None
_shutdown_event = threading.Event()
_browser_proc = None

# ═══════════════════════════════════════════════════════════════════════
# HELPERS — sérialisation JSON
# ═══════════════════════════════════════════════════════════════════════

LABELS = {
    'MATCH_REF_EXACT':'✓ Réf','MATCH_REF_PREFIX':'✓ Préfixe',
    'MATCH_EFICASH':'✓ EFICASH','MATCH_CONTRAT_UNIQUE':'✓ Contrat',
    'MATCH_CONTRAT_MONTANT':'✓ Contrat+mt','MATCH_CONTRAT_LIB':'✓ Contrat lib',
    'MATCH_GC_REF':'✓ GC','EXCLU_TOTAL':'— Exclu','SAGE_HORS_PERIMETRE':'— SAGE',
    'RECOUVREMENT_MANUEL':'⚠ Recouvr.','CROSS_SOCIETE_MANUEL':'⚠ Cross-soc.',
    'GC_MANUEL':'⚠ GC','NON_RAPPROCHE':'✗ Non rapp.','SUB_NO_MATCH':'✗ Sub KO',
    'SUGGEST_REF_EXTENDED':'◇ Réf étendue','SUGGEST_CONTRAT_LIBRE':'◇ Contrat libre',
    'SUGGEST_MONTANT_UNIQUE':'◇ Montant','SUGGEST_NUM_CONTRAT':'◇ Num→Contrat',
    'SUGGEST_NOM_CLIENT':'◇ Nom client',
    'VALIDATED':'✓ Validé','REJECTED':'✗ Rejeté',
}

def _serialize_resultat(r):
    """Convertit un résultat moteur en payload JSON pour le front."""
    j = r.get('justification') or {}
    return {
        'src': r['source'], 'dt': r['date'],
        's': r['status'], 'sl': LABELS.get(r['status'], r['status']),
        'lib': (r['libelle'] or '')[:160], 'mt': r['montant_enc'],
        'ann': r.get('annotation', ''),
        'ref': r.get('ref_imp') or '',
        'ctr': r.get('contrat_imp', ''),
        'nom': (r.get('nom_imp') or '')[:60],
        'sol': r.get('solde_imp', 0) or 0,
        'delta': round(r['montant_enc'] - r['solde_imp'], 2) if r.get('ref_imp') else None,
        'imp': 'OUI' if r['status'] in STATUTS_IMPORTABLES or r['status'] == 'VALIDATED' else '',
        'score': j.get('score', 0),
        'j': j,
    }

def _build_session_payload():
    res = session_state['resultats']
    if not res:
        return None
    total = sum(1 for r in res if 'EXCLU' not in r['status'] and 'PERIMETRE' not in r['status'])
    n_ok   = sum(1 for r in res if r['status'] in STATUTS_IMPORTABLES or r['status'] == 'VALIDATED')
    n_warn = sum(1 for r in res if 'MANUEL' in r['status'] or r['status'] in STATUTS_SUGGESTIONS)
    n_ko   = sum(1 for r in res if r['status'] in {'NON_RAPPROCHE', 'SUB_NO_MATCH', 'REJECTED'})
    mt_ok  = sum(r['montant_enc'] for r in res if r['status'] in STATUTS_IMPORTABLES or r['status'] == 'VALIDATED')
    n_import = sum(1 for r in res if (r['status'] in STATUTS_IMPORTABLES or r['status'] == 'VALIDATED')
                   and r.get('contrat_imp') and r.get('ref_imp'))
    return {
        'total': total, 'n_ok': n_ok, 'n_warn': n_warn, 'n_ko': n_ko,
        'pct_ok': round(n_ok / total * 100) if total else 0,
        'mt_ok': round(mt_ok, 2),
        'n_import': n_import,
        'date_enc': session_state['date_enc'].strftime('%d/%m/%Y') if session_state['date_enc'] else '',
        'sources': session_state['sources'],
        'details': [_serialize_resultat(r) for r in res],
    }

# ═══════════════════════════════════════════════════════════════════════
# RAPPROCHEMENT — flexible (N encaissements, nom libre)
# ═══════════════════════════════════════════════════════════════════════

def run_rapprochement(path_imp, encaissements):
    """encaissements: list of (path, source_name)."""
    global progress_state

    progress_state = {'pct': 5, 'msg': 'Détection des dates...'}
    date_enc = None
    for p, _ in encaissements:
        date_enc = detecter_date_encaissement(p)
        if date_enc:
            break
    if not date_enc:
        raise Exception("Impossible de détecter la date d'encaissement")
    date_saisie = date_enc + timedelta(days=1)

    progress_state = {'pct': 10, 'msg': 'Chargement des impayés...'}
    def prog_cb(n):
        progress_state['pct'] = min(10 + int(n / 1200), 60)
        progress_state['msg'] = f'Chargement impayés... {n:,} lignes'

    idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom, n_imp = charger_impayes(path_imp, prog_cb)

    resultats = []
    step = 30 / max(1, len(encaissements))
    for i, (p, name) in enumerate(encaissements):
        progress_state = {'pct': 65 + int(i * step), 'msg': f'Rapprochement {name}...'}
        res = traiter_fichier(p, name, date_enc, idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom)
        resultats.extend(res)

    # Stocker tout en session
    session_state['date_enc'] = date_enc
    session_state['date_saisie'] = date_saisie
    session_state['impayes_index'] = (idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom)
    session_state['resultats'] = resultats
    session_state['sources'] = [name for _, name in encaissements]

    progress_state = {'pct': 100, 'msg': 'Terminé'}
    return _build_session_payload()

# ═══════════════════════════════════════════════════════════════════════
# CSV — ne contient QUE les lignes auto-importables OU validées humain
# ═══════════════════════════════════════════════════════════════════════

def generer_csv_validees(output_path):
    if not session_state['resultats'] or not session_state['date_saisie']:
        return 0
    date_str = session_state['date_saisie'].strftime('%d/%m/%Y')
    obs = f"CCP {session_state['date_enc'].strftime('%d%m%y')}"
    lines = []
    for r in session_state['resultats']:
        importable = r['status'] in STATUTS_IMPORTABLES or r['status'] == 'VALIDATED'
        if importable and r.get('contrat_imp') and r.get('ref_imp'):
            mt = f"{r['montant_enc']:.2f}".replace('.', ',')
            lines.append(f"{date_str};{r['contrat_imp']};{r['ref_imp']};{mt};{obs}")
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        f.write("Date;Contrat;Facture;Montant;Observation\r\n")
        for ln in lines:
            f.write(ln + "\r\n")
    return len(lines)

# ═══════════════════════════════════════════════════════════════════════
# RECHERCHE LIBRE dans les impayés
# ═══════════════════════════════════════════════════════════════════════

def search_impayes(query, limit=20):
    idx = session_state['impayes_index']
    if not idx:
        return []
    idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom = idx
    q = (query or '').strip()
    if len(q) < 3:
        return []

    results = []
    seen = set()
    def push(info):
        if not info: return
        key = (info.get('ref'), info.get('contrat'))
        if key in seen: return
        seen.add(key)
        results.append({
            'ref': info.get('ref') or '',
            'contrat': info.get('contrat') or '',
            'nom': info.get('nom') or '',
            'societe': info.get('societe') or '',
            'solde': float(info.get('solde') or 0),
            'date': info.get('date') or '',
        })

    # 1) ref exacte (14 chiffres)
    if q in idx_ref:
        push(idx_ref[q])
    # 2) préfixe ref (13 chiffres)
    if q in idx_ref_prefix:
        for r in idx_ref_prefix[q][:5]:
            push(idx_ref.get(r))
    # 3) contrat (5..7 chiffres)
    if q.isdigit():
        for k in {q, q.zfill(7)}:
            if k in idx_contrat:
                for info in idx_contrat[k][:10]:
                    push(info)
    # 4) nom partiel (uppercase) — itération filtrée
    qu = q.upper()
    if len(qu) >= 4 and not qu.isdigit():
        for nom_key, infos in idx_nom.items():
            if qu in nom_key:
                for info in infos[:5]:
                    push(info)
                if len(results) >= limit: break
    # 5) montant
    try:
        mt = float(q.replace(',', '.'))
        mt_key = round(mt, 2)
        if mt_key in idx_montant:
            for info in idx_montant[mt_key][:10]:
                push(info)
    except ValueError:
        pass

    return results[:limit]

# ═══════════════════════════════════════════════════════════════════════
# SERVEUR HTTP
# ═══════════════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # silencer
        pass

    # ---- helpers ----
    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, fpath, default_ct='application/octet-stream'):
        if not os.path.isfile(fpath):
            self.send_response(404); self.end_headers(); return
        ext = os.path.splitext(fpath)[1].lower()
        ct_map = {
            '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8',
            '.js':'application/javascript; charset=utf-8',
            '.jsx':'application/javascript; charset=utf-8',
            '.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg',
            '.svg':'image/svg+xml; charset=utf-8', '.ico':'image/x-icon',
            '.pdf':'application/pdf', '.json':'application/json',
        }
        ct = ct_map.get(ext, default_ct)
        try:
            with open(fpath, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(500); self.end_headers()
            self.wfile.write(str(e).encode())

    def _parse_json_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode('utf-8'))

    # ---- routing ----
    def do_GET(self):
        url = urlparse(self.path)
        path = url.path

        if path == '/' or path == '/index.html':
            self._send_static(os.path.join(FRONTEND_DIR, 'index.html'))
            return

        if path == '/api/progress':
            self._send_json(progress_state); return

        if path == '/api/session':
            payload = _build_session_payload()
            if payload is None:
                self._send_json({'empty': True}); return
            self._send_json(payload); return

        if path == '/api/search':
            qs = parse_qs(url.query)
            q = qs.get('q', [''])[0]
            results = search_impayes(q)
            self._send_json({'results': results}); return

        if path == '/api/export/csv':
            tag = session_state['date_enc'].strftime('%d%m%y') if session_state['date_enc'] else 'export'
            csv_path = os.path.join(WORK_DIR, f'import_waterp_{tag}.csv')
            n = generer_csv_validees(csv_path)
            generated_files['csv'] = csv_path
            try:
                with open(csv_path, 'rb') as f: data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', f'attachment; filename="import_waterp_{tag}.csv"')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_response(500); self.end_headers()
            return

        if path == '/api/export/xlsx':
            if not session_state['resultats']:
                self.send_response(400); self.end_headers(); return
            tag = session_state['date_enc'].strftime('%d%m%y') if session_state['date_enc'] else 'export'
            xlsx_path = os.path.join(WORK_DIR, f'rapport_{tag}.xlsx')
            csv_path = os.path.join(WORK_DIR, f'import_waterp_{tag}.csv')
            n = generer_csv_validees(csv_path)
            generer_rapport_xlsx(session_state['resultats'], session_state['date_enc'],
                                 session_state['date_saisie'], n, xlsx_path)
            generated_files['xlsx'] = xlsx_path
            with open(xlsx_path, 'rb') as f: data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.send_header('Content-Disposition', f'attachment; filename="rapport_{tag}.xlsx"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # Static frontend (CSS, JSX, JS, SVG…)
        if path.startswith('/static/'):
            fname = unquote(path[len('/static/'):])
            # Sans path traversal : on resoud par rapport à FRONTEND_DIR ET STATIC_DIR
            for base in (FRONTEND_DIR, STATIC_DIR):
                candidate = os.path.normpath(os.path.join(base, fname))
                if candidate.startswith(os.path.normpath(base)) and os.path.isfile(candidate):
                    self._send_static(candidate); return
            self.send_response(404); self.end_headers(); return

        # Documentation (réutilise le HTML embarqué de V5 si on l'importe)
        if path == '/documentation':
            try:
                from rapprochement_app_V5 import DOC_PAGE
                body = DOC_PAGE.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(404); self.end_headers()
            return

        if path.startswith('/docs/'):
            fname = unquote(path[len('/docs/'):])
            safe = os.path.basename(fname)
            fpath = os.path.normpath(os.path.join(DOCS_DIR, safe))
            if fpath.startswith(os.path.normpath(DOCS_DIR)):
                self._send_static(fpath); return
            self.send_response(403); self.end_headers(); return

        self.send_response(404); self.end_headers()

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path

        if path == '/api/run':
            try:
                ct = self.headers.get('Content-Type', '')
                boundary = ct.split('boundary=')[-1].encode()
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)

                files = {}   # name → temp path
                fields = {}  # text fields
                for part in body.split(b'--' + boundary):
                    if b'\r\n\r\n' not in part:
                        continue
                    hend = part.find(b'\r\n\r\n')
                    header = part[:hend].decode('utf-8', errors='replace')
                    data = part[hend+4:]
                    if data.endswith(b'\r\n'): data = data[:-2]
                    nm = re.search(r'name="([^"]+)"', header)
                    fn = re.search(r'filename="([^"]+)"', header)
                    if not nm:
                        continue
                    if fn:
                        fpath = os.path.join(WORK_DIR, f"{int(time.time()*1000)}_{fn.group(1)}")
                        with open(fpath, 'wb') as f:
                            f.write(data)
                        files[nm.group(1)] = fpath
                    else:
                        fields[nm.group(1)] = data.decode('utf-8', errors='replace')

                if 'impayes' not in files:
                    self._send_json({'error': "Le fichier d'impayés est requis"}, 400); return

                encs = []
                for i in range(0, 10):
                    key = f'enc_{i}'
                    if key in files:
                        nm = fields.get(f'name_{i}', f'ENC{i}').strip() or f'ENC{i}'
                        encs.append((files[key], nm))
                if not encs:
                    self._send_json({'error': "Au moins un relevé d'encaissement est requis"}, 400); return

                result = run_rapprochement(files['impayes'], encs)
                self._send_json(result)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return

        if path == '/api/validate':
            data = self._parse_json_body()
            idx = int(data.get('line_id', -1))
            if 0 <= idx < len(session_state['resultats']):
                r = session_state['resultats'][idx]
                # Mémorise statut humain mais conserve la trace originale
                r['_status_origine'] = r.get('_status_origine') or r['status']
                r['status'] = 'VALIDATED'
                r.setdefault('justification', {})
                r['justification']['note'] = (r['justification'].get('note', '') + ' | Validé manuellement').strip(' |')
                self._send_json({'ok': True}); return
            self._send_json({'error': 'index hors borne'}, 400); return

        if path == '/api/reject':
            data = self._parse_json_body()
            idx = int(data.get('line_id', -1))
            reason = data.get('reason', '')
            if 0 <= idx < len(session_state['resultats']):
                r = session_state['resultats'][idx]
                r['_status_origine'] = r.get('_status_origine') or r['status']
                r['status'] = 'REJECTED'
                r.setdefault('justification', {})
                r['justification']['note'] = (r['justification'].get('note', '') + f' | Rejeté{(": " + reason) if reason else ""}').strip(' |')
                self._send_json({'ok': True}); return
            self._send_json({'error': 'index hors borne'}, 400); return

        if path == '/api/modify':
            data = self._parse_json_body()
            idx = int(data.get('line_id', -1))
            new_ref = (data.get('ref') or '').strip()
            new_contrat = (data.get('contrat') or '').strip()
            if not (0 <= idx < len(session_state['resultats'])):
                self._send_json({'error': 'index hors borne'}, 400); return
            r = session_state['resultats'][idx]
            # On vérifie que la ref existe vraiment dans l'index
            idx_ref = session_state['impayes_index'][0] if session_state['impayes_index'] else {}
            info = idx_ref.get(new_ref)
            if not info:
                self._send_json({'error': f'Référence {new_ref} introuvable'}, 404); return
            r['_status_origine'] = r.get('_status_origine') or r['status']
            r['status'] = 'VALIDATED'
            r['ref_imp']     = info.get('ref') or new_ref
            r['contrat_imp'] = info.get('contrat') or new_contrat
            r['nom_imp']     = info.get('nom') or ''
            r['solde_imp']   = float(info.get('solde') or 0)
            r.setdefault('justification', {})
            r['justification']['note'] = (
                (r['justification'].get('note', '') + f' | Réaffecté manuellement à {new_ref}').strip(' |')
            )
            self._send_json({'ok': True, 'updated': _serialize_resultat(r)}); return

        if path == '/api/shutdown':
            self._send_json({'status': 'ok'})
            def _stop():
                time.sleep(0.3)
                if _browser_proc and getattr(_browser_proc, 'pid', None):
                    try:
                        import subprocess as _sp
                        _sp.Popen(['taskkill', '/F', '/T', '/PID', str(_browser_proc.pid)],
                                  creationflags=0x08000000)
                    except Exception:
                        try: _browser_proc.terminate()
                        except Exception: pass
                _shutdown_event.set()
                if _server_ref: _server_ref.shutdown()
            threading.Thread(target=_stop, daemon=True).start()
            return

        self.send_response(404); self.end_headers()

# ═══════════════════════════════════════════════════════════════════════
# LANCEMENT
# ═══════════════════════════════════════════════════════════════════════

def main():
    global _server_ref, _browser_proc
    import subprocess

    url = f'http://localhost:{PORT}'
    print()
    print("  ================================================")
    print("  Rapprochement Encaissements — SOMEI / Veolia")
    print("  Version 6.0  (frontend React + API REST)")
    print(f"  -> {url}")
    print("  ================================================")
    print()

    def _open_app(target_url):
        for browser in [
            shutil.which('msedge') or r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            shutil.which('chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        ]:
            if browser and os.path.isfile(browser):
                try:
                    global _browser_proc
                    _browser_proc = subprocess.Popen([browser, f'--app={target_url}', '--start-maximized'])
                    return
                except Exception:
                    pass
        webbrowser.open(target_url)

    server = HTTPServer(('localhost', PORT), Handler)
    _server_ref = server
    threading.Timer(0.8, lambda: _open_app(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Arrêt (Ctrl+C).")

    if _shutdown_event.is_set():
        print("\n  Application arrêtée.")
        if sys.platform == 'win32':
            try:
                subprocess.Popen(['cmd', '/C', f'taskkill /F /PID {os.getpid()}'],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:
                pass
        sys.exit(0)

if __name__ == '__main__':
    main()
