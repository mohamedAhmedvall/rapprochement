# Guide d'Étude : Automatisation du Rapprochement Bancaire (IA/ML)

Ce guide d'étude est conçu pour approfondir la compréhension du projet de transition d'un processus de rapprochement bancaire manuel vers une solution automatisée basée sur l'intelligence artificielle et le machine learning.

## I. Quiz de Révision

Répondez aux questions suivantes en vous basant sur les documents fournis. Chaque réponse doit comporter 2 à 3 phrases.

1. **Quel est l'objectif principal du projet de "Lettrage automatique des virements CCP" ?**
2. **Quelles sont les trois composantes de l'architecture technique hybride préconisée ?**
3. **Pourquoi l'équipe projet a-t-elle explicitement exclu l'utilisation de LLM externes comme ChatGPT ?**
4. **Décrivez le fonctionnement du système de "Scoring de confiance" et ses seuils.**
5. **Quelles sont les deux sources de données principales comparées lors du rapprochement ?**
6. **En quoi consiste le "Niveau 1" des règles de matching ?**
7. **Quels sont les deux fichiers générés en sortie après le processus de rapprochement ?**
8. **Comment le système gère-t-il les "sous-lignes de ventilation" (D/E sans B) ?**
9. **Quel est le gain de performance attendu entre la version actuelle et l'application des optimisations futures ?**
10. **Quelle est la fonction de la "File HITL comptable" dans le scénario de traitement ?**

---

## II. Corrigé du Quiz

1. **Objectif principal :** L'objectif est de réduire drastiquement le temps de traitement manuel du rapprochement des impayés, qui mobilise actuellement cinq personnes chaque matin. L'outil sert d'aide à la décision ("copilote") pour automatiser le lettrage tout en conservant une supervision humaine.
2. **Architecture hybride :** La solution utilise des scripts Python pour les règles métier simples (ID contrat, montants exacts), des modèles NLP pour les comparaisons sémantiques (noms, adresses) et du Machine Learning spécialisé pour les comportements complexes comme les virements groupés.
3. **Exclusion des LLM externes :** Pour des raisons de souveraineté et de conformité au RGPD, seuls des modèles locaux sont autorisés. Cela garantit la sécurité des données bancaires et financières sensibles qui ne doivent pas transiter par des serveurs tiers.
4. **Scoring de confiance :** Chaque rapprochement reçoit un indice de fiabilité ; si cet indice est supérieur à 95 % (seuil à affiner), la validation est automatique. En dessous de ce seuil, une validation manuelle par un comptable est requise.
5. **Sources de données :** Le système compare les relevés bancaires SEM/SEMM (environ 200 lignes) aux états des impayés provenant du logiciel Waterp (plus de 2 000 lignes). L'historique utilisé pour l'analyse s'étend de 2013 à 2025.
6. **Niveau 1 du matching :** Il s'agit de la recherche de la référence de facture exacte ou par préfixe (clé primaire) via des expressions régulières (Regex). Le système cherche des motifs de 14 chiffres commençant par des préfixes spécifiques comme 10 (SEM) ou 40 (SEMM).
7. **Fichiers de sortie :** Le système génère un fichier d'import Waterp au format CSV pour l'intégration directe dans l'ERP, ainsi qu'un rapport de rapprochement détaillé au format XLSX pour le suivi comptable.
8. **Sous-lignes de ventilation :** Lorsqu'un organisme paie un montant global pour plusieurs contrats, le système identifie les sous-lignes détaillant chaque référence et montant. La règle est de traiter chaque sous-ligne comme un match individuel vers l'impayé correspondant.
9. **Gain de performance :** L'objectif de performance initial est de 50 à 60 % d'automatisation. Avec les améliorations identifiées (gestion des zéros manquants, recherche élargie), ce taux pourrait passer de 65 % à environ 82 %.
10. **File HITL comptable :** La file "Human-In-The-Loop" est destinée aux cas minoritaires complexes ou aux rapprochements dont le score de confiance est moyen. Elle permet aux comptables d'intervenir manuellement pour valider ou corriger les propositions de l'IA.

---

## III. Sujets de Réflexion (Format Essai)

*Les questions suivantes sont destinées à une analyse approfondie. Aucun corrigé n'est fourni.*

1. **Analyse de l'approche "Copilote" :** Analysez l'importance de maintenir une supervision humaine dans un processus financier automatisé par l'IA. Comment le score de confiance et la file HITL contribuent-ils à la fiabilité du système ?
2. **Souveraineté des données et IA :** Discutez des enjeux de sécurité et de conformité (RGPD) qui imposent l'utilisation de modèles de langage locaux plutôt que des solutions cloud grand public dans le secteur bancaire.
3. **Évolutivité de l'algorithme :** Examinez la hiérarchie des niveaux de matching (de la référence exacte au matching probabiliste). Comment cette structure permet-elle de gérer progressivement l'incertitude des données ?
4. **Traitement des anomalies de saisie :** En vous basant sur les "pièges identifiés" (troncations, fautes de frappe, dyslexie), expliquez comment les technologies NLP et les expressions régulières (Regex) transforment des données brutes "sales" en informations exploitables.
5. **Impact organisationnel de l'automatisation :** Étudiez comment le passage d'un processus manuel impliquant cinq personnes vers une solution automatisée modifie le rôle des équipes comptables au quotidien.

---

## IV. Glossaire des Termes Clés

| Terme                                       | Définition                                                                                                                                                                  |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Encaissement**                      | Flux bancaire entrant correspondant au paiement d'une facture par un client.                                                                                                 |
| **HITL (Human-In-The-Loop)**          | Modèle d'interaction où l'intelligence artificielle effectue le travail préparatoire mais nécessite l'intervention humaine pour la validation finale ou les cas ambigus. |
| **Impayé**                           | Facture émise dans le système Waterp qui n'a pas encore été réconciliée avec un paiement bancaire.                                                                     |
| **Lettrage**                          | Action comptable consistant à associer un règlement à une ou plusieurs factures pour solder un compte.                                                                    |
| **ML (Machine Learning)**             | Branche de l'IA permettant aux ordinateurs d'apprendre des motifs complexes à partir de données historiques pour effectuer des prédictions ou des classifications.        |
| **NLP (Natural Language Processing)** | Traitement automatique du langage naturel, utilisé ici pour comparer sémantiquement les noms et libellés malgré les erreurs de saisie.                                   |
| **POC (Proof of Concept)**            | Phase de test expérimentale visant à démontrer la faisabilité technique d'une solution sur des données réelles avant son déploiement à grande échelle.              |
| **Rapprochement Bancaire**            | Processus de vérification de la concordance entre les relevés de compte bancaire et la comptabilité interne de l'entreprise.                                              |
| **Regex (Expression Régulière)**    | Séquence de caractères formant un motif de recherche, utilisée pour extraire des numéros de contrat ou de facture dans les libellés de virement.                        |
| **Waterp**                            | Logiciel de gestion (ERP) utilisé comme référentiel pour les factures, les impayés et l'intégration des fichiers de lettrage.                                           |
