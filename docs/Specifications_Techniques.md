Voici une synthèse structurée au format **Markdown** pour votre document de spécification  **BMAD** . Ce document consolide vos notes de brainstorming, l'analyse technologique et les règles de gestion détaillées.

---

# Spécifications Techniques : Système de Rapprochement Intelligent (BMAD)

## 1. Introduction et Objectifs

Le projet vise à automatiser le rapprochement entre les factures d'impayés (clients/fournisseurs d'eau) et les flux de paiements bancaires.

* **Problématique :** Processus manuel chronophage, hétérogénéité des données, absence de standardisation des libellés.
* **Objectif :** Atteindre un taux de rapprochement automatique de **60-75%** dès la phase initiale.
* **Approche :** Architecture hybride combinant règles déterministes, Machine Learning et LLM (Human-In-The-Loop).

---

## 2. Architecture Multi-Modèles

Le système repose sur quatre couches technologiques successives, activées selon le score de confiance :

### A. Moteur de Règles Python (Socle Déterministe)

* **Rôle :** Traitement des cas simples et indexation.
* **Technologie :** Python, Expressions Régulières (Regex), `openpyxl`, `pandas`.
* **Performance :** Utilisation de dictionnaires Python pour une recherche en complexité **$O(1)$**.

### B. Machine Learning Spécialisé (Confiance Moyenne)

* **Rôle :** Matching probabiliste pour les cas ambigus (virements groupés, patterns bailleurs sociaux).
* **Modèles :** XGBoost, Sentence-BERT ou modèles de similarité de séquences.
* **Suivi :** Gestion de l'entraînement via  **ML Flow** .

### C. NLP & Secure GPT (Cas Complexes)

* **Rôle :** Analyse sémantique des libellés hétérogènes et génération d'explications pour l'humain.
* **Contrainte Souveraineté :** Utilisation exclusive de **modèles locaux** (interdiction de LLM externes type ChatGPT) pour garantir la conformité RGPD.

### D. Interface & Sorties

* **Dashboard :** Interface HTML locale pour la revue comptable.
* **Export :** Génération de fichiers **CSV** compatibles avec l'ERP  **Water+** .

---

## 3. Logique du Moteur de Règles (Niveaux de Priorité)

Le moteur traite les données séquentiellement selon les paliers suivants :

### Niveau 1 : Match par Référence Facture

1. **Extraction Regex :** Recherche de numéros à 14 chiffres (débutant par 10, 40 ou 33).
2. **Cas Particuliers :** * **EFICASH :** Extraction après la balise `REF: 00`.
   * **GC (Gestion Comptable) :** Gestion des références collées au texte.
3. **Recherche par Préfixe (13 chiffres) :** * Si la banque tronque la référence, recherche dans `idx_ref_prefix`.
   * **Sécurité :** Validation uniquement si le candidat est **unique** et si le **$Ratio = \frac{Montant}{Solde} \le 5.0$**.

### Niveau 2 : Match par Numéro de Contrat

* **Normalisation :** Extraction de 5 à 7 chiffres avec application de `zfill(7)`.
* **Décision :** * Si contrat unique : Validation automatique.
  * Si contrats multiples : Sélection de la facture dont le solde est le plus proche du paiement (tolérance de  **±0,02 €** ).

### Niveau 3 : Matching Probabiliste (ML)

* **Fuzzy Matching :** Comparaison sémantique entre le nom du payeur et la raison sociale (seuil d'acceptation  **> 80%** ).
* **Validation financière :** Vérification de cohérence avec une tolérance de **± 0,5%** du montant TTC.

---

## 4. Sécurisation et Exclusions (HITL)

Certains scénarios forcent systématiquement un passage en revue manuelle ( **Statut MANUEL** ) :

* **Cross-société :** Paiement reçu sur le compte bancaire d'une autre entité du groupe (ex: SEM vs SEMM).
* **Recouvrement de masse :** Flux provenant d'agences spécialisées ( **INTRUM, SOGEDI, SARP** ) nécessitant une ventilation complexe.
* **Écarts significatifs :** Tout delta supérieur à la tolérance configurée.

---

## 5. Flux de Données (Data Pipeline)

[Image d'un diagramme de flux ETL de données financières]

1. **Pré-traitement :** Nettoyage des montants négatifs et exclusions des factures "SAGE".
2. **Ventilation :** Éclatement des "sous-lignes" pour les paiements globaux (tolérance d'arrondi de 0,12 € sur la somme).
3. **Scoring :** Attribution d'un score de confiance.
4. **Audit Trail :** Inscription de la justification du rapprochement (ex: `MATCH_REF_PREFIX`) dans le fichier de sortie.

---

## 6. Prochaines Étapes

* **Analyse d'échantillon :** Audit de 200 à 500 cas historiques pour calibrer les seuils du moteur de règles.
* **POC :** Test du moteur Python sur l'index de 112 000 lignes d'impayés.
* **Entraînement :** Labellisation des données issues du moteur de règles pour entraîner le modèle ML.
