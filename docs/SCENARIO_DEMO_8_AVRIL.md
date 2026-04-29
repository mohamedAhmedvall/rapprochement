# Scénario de Démo — 8 avril 2026

## Copilote d'Encaissement — Rapprochement Bancaire Augmenté

**Durée estimée : 10–15 min**
**Présentateur :** Luc Theven
**Fichiers de démo :** dossier `datas/`

---

## AVANT LA DÉMO

- [ ] Fermer toutes les fenêtres Edge/Chrome inutiles
- [ ] Poser les 3 fichiers Excel sur le bureau ou dans un dossier facile d'accès :
  - `Etat_des_impayes_au_171225.xlsx`
  - `Releve_encaissement_SEM_161225.xlsx`
  - `Releve_encaissement_SEMM_161225.xlsx`
- [ ] Double-cliquer le raccourci **Copilote Encaissement** sur le bureau
- [ ] Vérifier que l'appli s'ouvre en plein écran (mode application, sans barre d'adresse)

---

## ACTE 1 — Contexte (2 min – sans l'appli)

> **Message clé :** « Aujourd'hui le rapprochement des encaissements est 100% manuel.
> On reçoit des relevés bancaires (SEM, SEMM), on les croise avec les impayés dans Wat.erp,
> ligne par ligne. C'est long, répétitif et source d'erreurs.
> L'idée : un copilote IA qui fait le rapprochement automatique et propose un fichier d'import prêt pour Wat.erp. »

---

## ACTE 2 — Lancement & Import (2 min)

### Étape 1 : Présenter l'interface
- Montrer les **3 zones de dépôt** (Impayés, Encaissement SEM, Encaissement SEMM)
- Souligner le **look SOMEI/LIRA** (même charte graphique que nos apps de production)

### Étape 2 : Glisser-déposer les fichiers
1. **Impayés** → `Etat_des_impayes_au_171225.xlsx` → la carte passe au vert ✓
2. **Encaissement SEM** → `Releve_encaissement_SEM_161225.xlsx` → vert ✓
3. **Encaissement SEMM** → `Releve_encaissement_SEMM_161225.xlsx` → vert ✓

> « Trois fichiers, trois glisser-déposer. C'est tout ce que l'utilisateur a à faire. »

### Étape 3 : Lancer le rapprochement
- Cliquer **▶ Lancer le rapprochement**
- Montrer la **barre de progression** en temps réel :
  - Détection automatique des dates
  - Chargement des impayés (~600+ lignes)
  - Rapprochement SEM puis SEMM
  - Génération des fichiers d'export

> « Le moteur tourne en local, aucune donnée ne sort du poste. »

---

## ACTE 3 — Résultats & KPIs (3 min)

### Étape 4 : Les indicateurs clés
- Montrer les **4 cartes KPI** :
  - 📊 **Lignes traitées** (~251)
  - ✅ **Matchées** (~171, soit ~68%) → « 68% de rapprochement automatique, zéro intervention humaine »
  - ⚠️ **Manuelles** → à valider par le comptable
  - ❌ **Non rapprochées** → cas sans correspondance
- Montrer le **montant importable** en euros
- Montrer le **graphique en anneau**

> « Sur ce jeu réel, on passe de 0% à 68% d'automatisation. L'objectif first target est 60%, on l'atteint dès le premier essai. »

### Étape 5 : Télécharger les exports
- Cliquer **Télécharger l'import .csv** → montrer le fichier généré
- Cliquer **Télécharger le rapport .xlsx** → ouvrir et montrer les 3 onglets :
  - Onglet 1 : Synthèse
  - Onglet 2 : Détail complet
  - Onglet 3 : Lignes importables

---

## ACTE 4 — Exploration du détail (3 min)

### Étape 6 : Le tableau des écritures
- Déplier la section **Tableau des écritures**
- Montrer les **13 colonnes** : Source, Date, Statut, Libellé, Montant, Réf impayé, Contrat, Nom, Solde, Delta, Import, Score

### Étape 7 : Filtrer
- **Filtre rapide** : taper `SEM` dans le filtre Source → ne garder que les SEM
- **Filtre avancé** : cliquer la loupe du Statut → cocher uniquement « ✓ Ref exacte »
- Montrer la **barre de filtres actifs** avec les tags
- **Filtre montant** : ouvrir le filtre Montant Encaissé → opérateur « Supérieur à » → `100` → Appliquer

> « Mêmes filtres que dans LIRA : recherche texte, opérateurs numériques, sélection de valeurs distinctes. »

### Étape 8 : Score de confiance & justification
- Cliquer sur une ligne **score 100** → déplier le panneau justification
  - Montrer : champ source, valeur source, champ cible, valeur cible, transformations
- Cliquer sur une ligne **score 80** → montrer une correspondance partielle
- Cliquer sur une ligne **score 70** → montrer le minimum de confiance

> « Chaque rapprochement est traçable. On sait pourquoi le moteur a matché, et avec quel niveau de confiance. »

---

## ACTE 5 — Export sélectif (1 min)

### Étape 9 : Cocher & exporter
- Réinitialiser les filtres (bouton 🔄)
- Filtrer sur Statut = « ⚠ Recouvr. » (les cas manuels)
- Cocher 3–4 lignes via les cases à cocher
- Cliquer **Exporter sélection** → un CSV `selection_JJMMAA.csv` se télécharge

> « Le comptable peut sélectionner les lignes validées manuellement et les exporter vers Wat.erp. »

---

## ACTE 6 — Documentation intégrée (1 min)

### Étape 10 : Page documentation
- Cliquer le lien **Documentation** dans le pied de page (ou l'icône 📖)
- Montrer les chapitres techniques (1 à 9)
- Scroller jusqu'aux images (chapitre 10) et au PDF (chapitre 11)

> « Toute la documentation est embarquée dans l'application. »

---

## ACTE 7 — Fermeture propre (30 sec)

### Étape 11 : Quitter
- Cliquer **Fermer** (en haut à droite)
- Confirmer dans la modale → **Quitter**
- La fenêtre se ferme automatiquement

> « L'app se comporte comme un logiciel natif : icône bureau, fenêtre dédiée, fermeture propre. Pas de serveur à gérer. »

---

## MESSAGES CLÉS À PLACER

| Thème | Message |
|-------|---------|
| **ROI** | « 68% de rapprochement automatique dès le premier test sur données réelles » |
| **Sécurité** | « 100% local — aucune donnée ne transite sur Internet » |
| **Traçabilité** | « Chaque match a un score de confiance et une justification détaillée » |
| **UX** | « Interface SOMEI/LIRA — pas de formation nécessaire » |
| **Intégration** | « Export CSV compatible Wat.erp, prêt à importer » |
| **Évolutivité** | « Les règles de matching sont paramétrables, on peut en ajouter » |

---

## QUESTIONS ANTICIPÉES

| Question probable | Réponse |
|---|---|
| « Ça tourne sur quel techno ? » | Python pur, pas de serveur externe, pas de base de données. Un seul fichier exécutable. |
| « C'est de l'IA ? » | IA hybride : règles métier + algorithmes de correspondance floue. Pas de LLM/cloud. |
| « Les 32% non matchés ? » | Ce sont des cas atypiques (virements sans référence, etc.) qui nécessitent validation humaine. L'objectif est d'augmenter ce taux itérativement. |
| « Ça marche pour d'autres sociétés ? » | Le moteur est paramétrable. Adapter les règles pour une autre entité = quelques jours. |
| « Et la suite ? » | Ajouter des règles post-démo, intégrer directement dans Wat.erp, étendre à d'autres types de rapprochement. |
