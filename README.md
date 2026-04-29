# Copilote d'Encaissement — Veolia / SOMEI

Application locale de rapprochement bancaire augmenté.
Backend Python 3 + frontend React (CDN, sans build).

## Stack

| Couche       | Tech                                        |
|--------------|---------------------------------------------|
| Backend      | Python ≥ 3.9 · `openpyxl` · stdlib HTTP     |
| Frontend     | React 18 + Babel standalone (via CDN)       |
| Données      | Excel `.xlsx` (Wat.erp impayés + relevés)   |
| Déploiement  | exécution locale, navigateur en mode `--app`|

Pas de framework lourd : `python rapprochement_app_V6.py` lance un serveur HTTP local
sur `localhost:8765` qui sert le frontend et expose une API REST.

## Lancement

```bash
# 1) installer la dépendance unique
pip install openpyxl

# 2) démarrer
python rapprochement_app_V6.py
```

Le navigateur s'ouvre automatiquement sur `http://localhost:8765` (Edge/Chrome en mode app si dispo, sinon le navigateur par défaut).

### Workflow

1. **Import** — déposer 1 fichier d'impayés Wat.erp + 1 à 3 relevés d'encaissement.
   Chaque relevé est nommé librement (`SEM`, `SEMM`, `BNP`, etc.) — ce nom apparaît
   ensuite comme source dans toutes les vues.
2. **Tableau de bord** — KPIs, sparkline, file d'attente prioritaire.
3. **Lignes** — vue tabulaire complète avec filtres et sélection multiple.
4. **Rapprochement** — examen ligne par ligne avec :
   - candidat proposé par le moteur (score + justification)
   - co-pilote latéral (mode L2)
   - actions **Valider / Rejeter / Modifier** (recherche libre)
   - raccourcis : `←`/`→` navigation · `⏎` valider · `Esc` rejeter
5. **Export CSV** — fichier `import_waterp_JJMMAA.csv` ne contenant que les lignes
   matchées auto **OU** validées humainement.

### Niveaux d'assistance (`L0`/`L1`/`L2`)

Sélecteur en bas de la sidebar :

- **L0** — pas de suggestions, vues neutres
- **L1** — bandeaux d'aide ("X lignes à confiance haute…")
- **L2** — co-pilote latéral pendant le rapprochement (synthèse + raisonnement)

L'opérateur garde toujours l'autorité finale : aucun match n'est écrit en base sans validation.

## API REST

| Endpoint             | Méthode | Rôle                                              |
|----------------------|---------|---------------------------------------------------|
| `/api/run`           | POST    | Multipart : `impayes` + `enc_0..N` + `name_0..N`  |
| `/api/progress`      | GET     | `{pct, msg}` pendant le traitement                |
| `/api/session`       | GET     | État courant complet (KPIs + détail des lignes)   |
| `/api/validate`      | POST    | `{line_id}` → marque la ligne validée             |
| `/api/reject`        | POST    | `{line_id, reason}` → marque rejetée              |
| `/api/modify`        | POST    | `{line_id, ref, contrat}` → réaffecte             |
| `/api/search?q=`     | GET     | Recherche libre dans les impayés                  |
| `/api/export/csv`    | GET     | CSV d'import Wat.erp (validées seulement)         |
| `/api/export/xlsx`   | GET     | Rapport Excel 3 onglets                           |
| `/api/shutdown`      | POST    | Arrête le serveur                                 |

## Architecture du dépôt

```
rapprochementv2/
├── rapprochement_app_V6.py     # backend HTTP + API REST
├── rapprochement_app_V5.py     # moteur de matching (réutilisé tel quel)
├── frontend/
│   ├── index.html              # entrée React + Babel
│   ├── app.jsx                 # racine (routing + sidebar + agenticLevel)
│   ├── app-shared.jsx          # icônes + helpers de format
│   ├── app-data.jsx            # client API + adaptation backend → MOCK
│   ├── screens-1.jsx           # Dashboard + Import
│   ├── screens-2.jsx           # Liste + Matching (avec co-pilote)
│   ├── screens-3.jsx           # Export CSV
│   ├── style.css               # design system
│   └── static/
│       ├── veolia-logo.png     # logo officiel
│       └── veolia-logo.svg     # fallback SVG
├── docs/                       # docs métier (Compte rendu, scénario démo, PDF)
└── README.md
```

## Règles de matching (héritées V5)

Hiérarchie 3 niveaux, score 0-100 :

| Niveau | Statut Python              | Score | Décision  |
|--------|----------------------------|-------|-----------|
| 1      | `MATCH_REF_EXACT`          | 100   | auto      |
| 1      | `MATCH_REF_PREFIX`         | 90    | auto      |
| 1      | `MATCH_EFICASH`            | 95    | auto      |
| 2      | `MATCH_CONTRAT_UNIQUE`     | 85    | auto      |
| 2      | `MATCH_CONTRAT_MONTANT`    | 75    | auto      |
| 2      | `MATCH_CONTRAT_LIB`        | 70    | auto      |
| —      | `MATCH_GC_REF`             | 80    | auto      |
| 3      | `SUGGEST_REF_EXTENDED`     | 65    | à valider |
| 3      | `SUGGEST_CONTRAT_LIBRE`    | 60    | à valider |
| 3      | `SUGGEST_NUM_CONTRAT`      | 50    | à valider |
| 3      | `SUGGEST_MONTANT_UNIQUE`   | 55    | à valider |
| 3      | `SUGGEST_NOM_CLIENT`       | 40    | à valider |
| —      | `RECOUVREMENT_MANUEL`      | 0     | manuel    |
| —      | `CROSS_SOCIETE_MANUEL`     | 0     | manuel    |
| —      | `GC_MANUEL`                | 0     | manuel    |
| —      | `NON_RAPPROCHE`            | 0     | KO        |

## Notes connues

- Les Excel d'impayés font ~115k lignes — le chargement initial prend ~25 s.
- Le filtre `Type='FR'` dans `_select_best_impaye` (V5) n'a aucun effet : les vraies
  valeurs sont `AT`/`AC`/etc. Le fallback `solde > 0` prend le relais. Sans impact
  fonctionnel mais à nettoyer dans une V7.
- Aucune donnée ne quitte la machine : `pip install openpyxl` est la seule dépendance
  externe au runtime, et `unpkg.com` sert React/Babel via CDN au démarrage du navigateur.
