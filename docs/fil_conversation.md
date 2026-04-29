plusieurs remarques : 
- dans les colonnes du fichiers excel nous avons : 
Source	Ligne	Date	Libellé	Mt Enc.	Annotation	Statut	Score	Ref impayé	Contrat	Nom	Solde TTC	Delta	Import	Justification
dans le tableau : Afficher les détails de la page Web nous avons : 
Source	Statut Libellé	Mt Enc.	Ref/Contrat	Nom	Solde Score

quelles colonnes pourrait on rajouter dans la page Web qui serait utile pour un comptable dans une logique d'analyse, de tri, d'investigation.
L'idée étant qu'il n'ai pas neccessairement besoin tout de suite d'ouvrir le fichier excel pour faire ces tâches, et que la page web lui satisfasse une partie de ces besoins. 


Cotés UX Design : 
- nous avons un header + un bandeau à 3 lignes: double usage. Le bandeau n'apporte pas grand chose. C'était mieux fait en version 4
- le bandeau Tri est mal fait à mon sens
- je voudrais mettre le logo veolia. Tenir compte du fond blanc du logo. 
https://www.somei.fr/site2017/wp-content/uploads/2025/11/Capsule-Veolia-RVB-x0.5.png
- sur le tableau, mettre le fond une ligne sur 2 avec des couleurs différentes permettrait peut être une meilleure lisibilité. 
- Est-il possible de trouver une police des lignes du tableau plus douce ? Il s'agit de "courrier" je crois et c'est un peu hostère


UX Design : 
- est-il possible de reprendre le look et l'organisation de cette page : 
https://www.somei.fr/solutions/wat-erp-gestion-clientele/
		=> header sur une ligne : uniquement à gauche : SEM + SEMM — CCP 16/12/2025 Fermer
		=> logo sur le fond blanc Puis : Copilote d'Encaissement - Softwares Solutions 
- bouton Fermé : ne pas mettre de X
- Remplacer (Heander & Footer) SOMEI par Softwares Solutions 
- Supprimer : — Division Encaissement — Wat.erp

UX Design :
redimentionner le tableau pour qu'il s'adapte à toute la largeur de la fenêtre du navigateur. 

dans le tableau Détails : 
- Rajouter colonne : date dans le tableau Détails 
- possibilité de redimentionner la largeur les colonnes 
- bouton Tri vericales : trop petit

- Organisation des colonnes avec chevron vertical qui ouvre un popup contextuelle : 
Tel que : https://lira.somei.fr/wm/app-Assets/search-page/7d474490-f9f8-ef11-5d86-8c0d7446f618
- Filtrer par colonnes 
- rechercher par colonne : contient  , ne contient pas, commence, ne commence pas, est égale, est différent de, est définie, non définie 
- Texte de recherche 
- Trier par colonne A-Z 
- Trier par colonne Z-A

- remplace SRC par SOURCE
- remplace MT ENC. Par MONTANT ENCAISSE  
- le Footer doit être à la même largeur que l'en-tête du Tableau de détails 
- les 3 "vignettes" Impayés / Encaissement SEM / Encaissement SEMM : sont trop haute. Peut être mettre les numéros 1,2,3 à gauche de l'icone. Idem le bouton vert à gauche de l'icone. 
- inverser Softwares Solutions avec Copilote d'Encaissement : au final Logo Softwares Solutions - Copilote d'Encaissement (ne rien changer sur les couleurs de police) 
- dans le footer : prévoir un icone Légende + Documentation à droite => à l'identique du site https://www.somei.fr/
- concerver le bouton Fermer 

- supprimer : SEM + SEMM — CCP dans le header 
- le footer doit être positionné en bas de page et s'adapter à la taille tu navigateur en prennant toute la largeur
- lorsque le navigateur est trop réduit en largeur, ilfaudra rajouter une barre de scrolling pour le tableau des données


- Rajouter une colonne avec case à cocher : à l'identique de https://lira.somei.fr/wm/app-Assets/search-page/7d474490-f9f8-ef11-5d86-8c0d7446f618
cette fonctionnalité sera utiliser pour l'export vers WatErp dans un second temps 
les filtres semblent ne pas fonctionner pour montant Encaissé 
la fenêtre "popup" de recherche a un bug lorsqu'on scrool down (elle reste coller au footer). Il faudrait bloquer le scroll vertical en cas d'utilisation des filtres 
- reprend exactement la même couleur pour le hearder et footer que le site : https://www.somei.fr/
- reprend exactement les mêmes polices aussi et les couleurs bleu des menu et bleu plus clair pour les grand menus 
- les 3 logos impayés encaissement SEM et encaissement SEMM ne me plaise pas
- Sous la ligne des en-tête : ajouter une ligne : Filtrer par colonne. A l'identique sur site : https://lira.somei.fr/wm/app-Assets/search-page/7d474490-f9f8-ef11-5d86-8c0d7446f618
  il faut qu'en cas de click sur la loupe,un popup apparaisse avec : filtrer par colonne : (contient, ne contient pas, commence par, Se termine par etc...) Puis un Texte de recherche 
  bouton EFFACER  APPLIQUER 
  Pour certaine colonne (tel que Source, Statut, Contrat : il soit possible de voir la liste des valeurs : à l'identique de la colonne Type de la page : https://lira.somei.fr/wm/app-Assets/search-page/7d474490-f9f8-ef11-5d86-8c0d7446f618
  

- au dessus de Sur la ligne FILTRES ACTIFS : 
	* ajoute un bouton refresh (comme : https://lira.somei.fr/wm/app-Assets/search-page/7d474490-f9f8-ef11-5d86-8c0d7446f618  )- même icone
	* ajoute un bouton favoris - même icone
	* ajoute un bouton download (format .xlsx ou .csv séparateur ";") - même icone
	* ajoute un bouton paramètres : pour cocher / afficher les colonnes souhaités  - même icone
	
- sur la rubrique Import : possibilité de réduire le paragraphe avec un bouton discret 
- sur la rubrique Résultats & montant : possibilité de réduire le paragraphe avec un bouton discret 

=> il y a 3 rubriqus rétractables : 
	1. imports des fichier
	2. R\u00e9sultats & Montant (corrige le Pb de format : \u00e9
	3. Tableau des écritures 

- rajouter Un favicon  icone dans la barre de navigation tel que https://www.somei.fr/
- est il possible de remplacer l'icone map monde, pour trouver un icone Documentation. 
- Et renvoyer sur une nouvelle page, avec le même look like. 
- avec la présentation : Rapprochement Bancaire Augmenté
- et l'image : https://notebooklm.google.com/notebook/82f7a47c-9af0-4cca-9a64-f28ce64e9fd0
- suivis de l'image :  https://notebooklm.google.com/notebook/82f7a47c-9af0-4cca-9a64-f28ce64e9fd0
- suivis de la présentation : https://notebooklm.google.com/notebook/82f7a47c-9af0-4cca-9a64-f28ce64e9fd0?artifactId=932cad2f-b6f6-4e98-bdef-96b3b30ce359

- dans le footer : met à jour le liens pour pointer vers la page documentation 
- dans le header : la date doit être à droite 



- Est-il possible de rajouter une légendes (Page supplémentaire)
	- explication sur les différents statuts
	- les règles de "matching"

- pour la doc. Commence par le Analyse technique du rapprochement
- integre un chapitre 10 avec les 2 images
-  integre un chapitre 11 avec la présentation PDF 

dans le header 2, je voudrais un bouton refresh permettant de reload l'application
dans le tableau, possible de changer la position des colonnes? (en glissé/déplacer), garder en mémoire ls paramètres/préférénces d'affichage de l'utilisateur
mettre le score entre Source et Statut
je trouve le tableau compliqué à lire à cause du scrolling horizontale. Comment améliorer, ou simplifier sans perdre les informations indispensables ?

