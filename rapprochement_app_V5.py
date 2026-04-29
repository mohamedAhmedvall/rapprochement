#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  RAPPROCHEMENT ENCAISSEMENTS / IMPAYÉS                             ║
║  Application web locale — Interface graphique                       ║
║  SOMEI — Division Encaissement                                      ║
║  Version 4.2  — Justification détaillée + Score de confiance        ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys, os, re, io, json, time, threading, webbrowser, tempfile, shutil, signal
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    print("=" * 50)
    print("  ERREUR : openpyxl n'est pas installé")
    print("  Lancer : pip install openpyxl")
    print("=" * 50)
    input("Appuyez sur Entrée pour fermer...")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════
PORT = 8765
SOCIETES_RECOUVREMENT = {'INTRUM', 'SOGEDI', 'SARP'}
RATIO_MAX_PREFIX = 5.0
STATUTS_IMPORTABLES = {
    'MATCH_REF_EXACT', 'MATCH_REF_PREFIX', 'MATCH_EFICASH',
    'MATCH_CONTRAT_UNIQUE', 'MATCH_CONTRAT_MONTANT', 'MATCH_CONTRAT_LIB',
    'MATCH_GC_REF'
}

# Score de confiance par type de match (0-100)
SCORES_CONFIANCE = {
    'MATCH_REF_EXACT': 100,
    'MATCH_REF_PREFIX': 90,
    'MATCH_EFICASH': 95,
    'MATCH_CONTRAT_UNIQUE': 85,
    'MATCH_CONTRAT_MONTANT': 75,
    'MATCH_CONTRAT_LIB': 70,
    'MATCH_GC_REF': 80,
    # ── Règles non-déterministes (à valider manuellement) ──
    'SUGGEST_REF_EXTENDED': 65,
    'SUGGEST_CONTRAT_LIBRE': 60,
    'SUGGEST_MONTANT_UNIQUE': 55,
    'SUGGEST_NUM_CONTRAT': 50,
    'SUGGEST_NOM_CLIENT': 40,
}

# Statuts considérés comme des suggestions (à valider)
STATUTS_SUGGESTIONS = {
    'SUGGEST_REF_EXTENDED', 'SUGGEST_CONTRAT_LIBRE',
    'SUGGEST_MONTANT_UNIQUE', 'SUGGEST_NUM_CONTRAT', 'SUGGEST_NOM_CLIENT',
}

WORK_DIR = os.path.join(tempfile.gettempdir(), 'rapprochement_encaissements')
os.makedirs(WORK_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════
# HELPERS — SÉLECTION DU MEILLEUR CANDIDAT
# ═══════════════════════════════════════════════════════════════════════

def _parse_date_key(info):
    """Convertit la date d'un impayé en tuple (Y,M,D) pour tri, ou (0,0,0) si invalide."""
    d = info.get('date', '') if info else ''
    if not d:
        return (0, 0, 0)
    try:
        # Format YYYY-MM-DD (depuis str(datetime)[:10])
        parts = d.split('-')
        if len(parts) == 3:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
    except:
        pass
    try:
        # Format DD/MM/YYYY
        parts = d.split('/')
        if len(parts) == 3:
            return (int(parts[2]), int(parts[1]), int(parts[0]))
    except:
        pass
    return (0, 0, 0)

def _select_best_impaye(candidates, montant_enc=None):
    """Sélectionne le meilleur candidat parmi une liste d'impayés.
    Priorité : 1) Type='FR' et Solde>0, 2) Date la plus récente, 3) Montant le plus proche."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # 1. Filtrer par Type='FR' et Solde > 0
    fr_candidates = [c for c in candidates if str(c.get('type', '')).strip() == 'FR' and c.get('solde', 0) > 0]
    if fr_candidates:
        working = list(fr_candidates)
    else:
        # Prendre ceux avec Solde > 0
        pos_candidates = [c for c in candidates if c.get('solde', 0) > 0]
        working = list(pos_candidates) if pos_candidates else list(candidates)

    # 2. Trier par date la plus récente
    working.sort(key=_parse_date_key, reverse=True)

    # 3. Si montant fourni, prendre le plus proche en montant parmi les récents
    if montant_enc and montant_enc > 0:
        best_by_date = working[0]
        if abs(best_by_date.get('solde', 0) - montant_enc) <= montant_enc * 0.1:
            return best_by_date
        return min(working, key=lambda x: abs(x.get('solde', 0) - montant_enc))

    return working[0]

# ═══════════════════════════════════════════════════════════════════════
# MOTEUR DE RAPPROCHEMENT (identique à v1)
# ═══════════════════════════════════════════════════════════════════════

def detecter_date_encaissement(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    for row in ws.iter_rows(max_row=10, max_col=2, values_only=True):
        if row[0] and 'imput' in str(row[0]).lower():
            m = re.search(r'(\d{2}/\d{2}/\d{4})', str(row[1]))
            if m:
                wb.close(); return datetime.strptime(m.group(1), '%d/%m/%Y')
    for row in ws.iter_rows(min_row=8, max_row=20, max_col=1, values_only=True):
        if isinstance(row[0], datetime):
            wb.close(); return row[0]
    wb.close(); return None

def detecter_header_row(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    for row_idx, row in enumerate(ws.iter_rows(max_row=15, max_col=4, values_only=True), 1):
        vals = [str(v).lower() if v else '' for v in row]
        if 'date' in vals and any('lib' in v for v in vals):
            wb.close(); return row_idx
    wb.close(); return 7

def charger_impayes(path, progress_cb=None):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[wb.sheetnames[0]]
    idx_ref = {}; idx_ref_prefix = defaultdict(list); idx_contrat = defaultdict(list)
    idx_montant = defaultdict(list); idx_nom = defaultdict(list)
    count = 0
    for row in ws.iter_rows(min_row=2, max_col=26, values_only=True):
        count += 1
        ref = str(row[14]).strip() if row[14] else None
        contrat = str(row[2]).strip() if row[2] else None
        info = {
            'ref': ref, 'contrat': contrat,
            'client': str(row[4]).strip() if row[4] else '',
            'nom': str(row[9]).strip() if row[9] else '',
            'montant': float(row[18]) if row[18] else 0,
            'solde': float(row[19]) if row[19] else 0,
            'date': str(row[16])[:10] if row[16] else '',
            'type': str(row[17]).strip() if row[17] else '',
            'societe': str(row[25]) if row[25] else ''
        }
        if ref and len(ref) >= 13:
            idx_ref[ref] = info; idx_ref_prefix[ref[:13]].append(ref)
        if contrat:
            for key in {contrat, contrat.zfill(7)}: idx_contrat[key].append(info)
        # Index montant (arrondi à 2 décimales)
        solde = round(info['solde'], 2)
        if solde > 0:
            idx_montant[solde].append(info)
        # Index nom (mots ≥ 4 lettres, uppercased)
        nom = info['nom'].strip().upper()
        if nom and len(nom) >= 4:
            idx_nom[nom].append(info)
        if progress_cb and count % 10000 == 0: progress_cb(count)
    wb.close()
    return idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom, count

def extraire_refs(texte):
    if not texte: return []
    refs = re.findall(r'(?:10|40|33|32|41|42)\d{12}', texte)
    if not refs: refs = re.findall(r'(?:10|40|33)\d{11}', texte)
    return refs

def extraire_ref_eficash(texte):
    m = re.findall(r'REF:\s*00?((?:40|10|33)\d{11,13})', str(texte))
    return m[0] if m else None

def extraire_contrats(texte):
    if not texte: return []
    return re.findall(r'[Cc]ont(?:rat)?\s*(\d{5,7})', texte)

def est_recouvrement(lib, ann):
    text = (str(lib) + ' ' + str(ann)).upper()
    return any(s in text for s in SOCIETES_RECOUVREMENT)

def est_cross_societe(lib):
    if not lib: return False
    return any(p in str(lib).upper() for p in ['SEMM / SEM', 'SEM / APE', 'SEMM/SEM', 'APE / SAE', 'SAOM'])

def _justif(status, champ_src, val_src, champ_cible, val_cible, transformations=None, note=''):
    """Construit un dict de justification pour un match."""
    return {
        'score': SCORES_CONFIANCE.get(status, 0),
        'champ_source': champ_src,
        'valeur_source': str(val_src)[:60],
        'champ_cible': champ_cible,
        'valeur_cible': str(val_cible)[:60],
        'transformations': transformations or [],
        'note': note
    }

def match_ligne(lib, mt, ann, idx_ref, idx_ref_prefix, idx_contrat, idx_montant=None, idx_nom=None):
    a = str(ann).strip() if ann else ''
    if a in ('#N/A', 'None', 'nan', 'NaN'): a = ''  # Nettoyage annotations invalides
    l = str(lib) if lib else ''
    m = float(mt) if mt else 0
    nj = {'score': 0, 'champ_source': '', 'valeur_source': '', 'champ_cible': '', 'valeur_cible': '', 'transformations': [], 'note': ''}
    if a == 'TOTAL' or m < 0: return None, 'EXCLU_TOTAL', '', nj
    if a == 'SAGE': return None, 'SAGE_HORS_PERIMETRE', l[:60], {**nj, 'note': 'Écriture SAGE hors périmètre CCP'}
    if est_recouvrement(l, a): return None, 'RECOUVREMENT_MANUEL', f'{a} — {l[:60]}', {**nj, 'note': f'Société de recouvrement détectée dans annotation/libellé'}
    if est_cross_societe(l): return None, 'CROSS_SOCIETE_MANUEL', l[:80], {**nj, 'note': 'Virement inter-société détecté dans le libellé'}
    # ── Annotation = référence facture ──
    if re.match(r'^(?:10|40|33|32|41|42)\d{11,12}$', a):
        if a in idx_ref:
            info = idx_ref[a]
            return info, 'MATCH_REF_EXACT', a, _justif('MATCH_REF_EXACT', 'Annotation', a, 'Référence impayé (col O)', info['ref'], note='Correspondance exacte 14 chiffres')
        if len(a) == 13 and a in idx_ref_prefix:
            cands = idx_ref_prefix[a]
            infos = [idx_ref[r] for r in cands if idx_ref[r]['solde'] > 0 and m / idx_ref[r]['solde'] <= RATIO_MAX_PREFIX]
            if infos:
                info = _select_best_impaye(infos, m)
                nb = f'{len(cands)} candidats → ' if len(cands) > 1 else ''
                return info, 'MATCH_REF_PREFIX', cands[0], _justif('MATCH_REF_PREFIX', 'Annotation (13 car.)', a, 'Préfixe référence impayé', info['ref'], transformations=['Troncature à 13 caractères', f'Ratio montant/solde = {m/info["solde"]:.2f} ≤ {RATIO_MAX_PREFIX}'], note=nb + 'Match par préfixe 13 chiffres')
    # ── EFICASH ──
    if a == 'EFICASH':
        ref = extraire_ref_eficash(l)
        if ref and ref in idx_ref:
            return idx_ref[ref], 'MATCH_EFICASH', ref, _justif('MATCH_EFICASH', 'Libellé (regex REF:)', ref, 'Référence impayé', idx_ref[ref]['ref'], transformations=['Extraction regex REF: dans libellé', 'Suppression préfixe 00'], note='Paiement EFICASH — référence extraite du libellé')
    # ── Références dans le libellé ──
    for r in extraire_refs(l):
        if r in idx_ref:
            return idx_ref[r], 'MATCH_REF_EXACT', r, _justif('MATCH_REF_EXACT', 'Libellé (regex)', r, 'Référence impayé', idx_ref[r]['ref'], transformations=['Extraction regex référence dans libellé'], note='Référence trouvée dans le texte du libellé')
        if len(r) == 13 and r in idx_ref_prefix:
            cands = idx_ref_prefix[r]
            if len(cands) == 1:
                info = idx_ref[cands[0]]
                if info['solde'] > 0 and m / info['solde'] <= RATIO_MAX_PREFIX:
                    return info, 'MATCH_REF_PREFIX', cands[0], _justif('MATCH_REF_PREFIX', 'Libellé (regex, 13 car.)', r, 'Préfixe référence impayé', cands[0], transformations=['Extraction regex dans libellé', 'Troncature à 13 caractères'], note='Préfixe 13 trouvé dans le libellé — candidat unique')
    # ── Annotation = contrat ──
    if re.match(r'^\d{5,7}$', a):
        ck = a.zfill(7)
        if ck in idx_contrat:
            ent = idx_contrat[ck]
            transf = [f'Normalisation contrat : {a} → {ck} (zfill 7)'] if a != ck else []
            if len(ent) == 1:
                return ent[0], 'MATCH_CONTRAT_UNIQUE', a, _justif('MATCH_CONTRAT_UNIQUE', 'Annotation (contrat)', ck, 'N° contrat impayé', ent[0]['contrat'], transformations=transf, note='Contrat unique dans le référentiel')
            best = min(ent, key=lambda x: abs(x['solde'] - m))
            transf.append(f'Sélection par montant le plus proche : delta = {abs(best["solde"] - m):.2f}€')
            return best, 'MATCH_CONTRAT_MONTANT', a, _justif('MATCH_CONTRAT_MONTANT', 'Annotation (contrat)', ck, 'N° contrat impayé', best['contrat'], transformations=transf, note=f'Contrat trouvé {len(ent)} fois — sélection par montant')
    # ── Contrat dans le libellé ──
    for c in extraire_contrats(l):
        ck = c.zfill(7)
        if ck in idx_contrat:
            ent = idx_contrat[ck]
            transf = [f'Extraction regex "contrat NNNNN" dans libellé', f'Normalisation : {c} → {ck}']
            if len(ent) == 1:
                return ent[0], 'MATCH_CONTRAT_LIB', c, _justif('MATCH_CONTRAT_LIB', 'Libellé (regex contrat)', ck, 'N° contrat impayé', ent[0]['contrat'], transformations=transf, note='Contrat extrait du libellé — unique')
            best = min(ent, key=lambda x: abs(x['solde'] - m))
            transf.append(f'Sélection par montant : delta = {abs(best["solde"] - m):.2f}€')
            return best, 'MATCH_CONTRAT_LIB', c, _justif('MATCH_CONTRAT_LIB', 'Libellé (regex contrat)', ck, 'N° contrat impayé', best['contrat'], transformations=transf, note=f'Contrat extrait du libellé — {len(ent)} occurrences')
    # ── GC ──
    if a == 'GC':
        for r in re.findall(r'((?:40|10)\d{10,13})', l):
            r14 = r[:14] if len(r) >= 14 else r
            if r14 in idx_ref:
                return idx_ref[r14], 'MATCH_GC_REF', r14, _justif('MATCH_GC_REF', 'Libellé (regex GC)', r, 'Référence impayé', idx_ref[r14]['ref'], transformations=['Annotation GC + extraction référence dans libellé', f'Troncature à 14 car. : {r} → {r14}'] if len(r) > 14 else ['Annotation GC + extraction référence dans libellé'], note='Gestion Contentieuse — référence identifiée')
        return None, 'GC_MANUEL', l[:80], {**nj, 'note': 'GC sans référence identifiable dans le libellé'}

    # ══════════════════════════════════════════════════════════════
    # RÈGLES NON-DÉTERMINISTES (suggestions à valider)
    # ══════════════════════════════════════════════════════════════

    # ── R1 : Ref étendue — annotation 14 chiffres non trouvée, essayer +1 chiffre ──
    if re.match(r'^(?:10|40|33|32|41|42)\d{12}$', a) and a not in idx_ref:
        for digit in '0123456789':
            extended = a + digit
            if extended in idx_ref:
                info = idx_ref[extended]
                return info, 'SUGGEST_REF_EXTENDED', extended, _justif(
                    'SUGGEST_REF_EXTENDED', 'Annotation (14 car.)', a,
                    'Référence impayé (15 car.)', extended,
                    transformations=[f'Annotation 14 chiffres non trouvée directement',
                                    f'Recherche étendue : {a} + [0-9] → {extended} trouvé'],
                    note='⚠ Référence probable — l\'annotation est un préfixe à 14 car. de la réf complète')

    # ── R2 : Contrat format libre dans libellé ──
    # Patterns: CONT638389, contrat 1168591, Numero contrat, N contrat, co 7561403
    contrats_libres = re.findall(
        r'(?:CONT(?:RAT)?\s*|N(?:UMERO)?\s+CONTRAT\s*|co(?:ntrat)?\s+)(\d{5,7})',
        l, re.IGNORECASE
    )
    for c in contrats_libres:
        ck = c.zfill(7)
        if ck in idx_contrat:
            ent = idx_contrat[ck]
            transf = [f'Extraction format libre dans libellé : « …{c}… »',
                      f'Normalisation : {c} → {ck}']
            if len(ent) == 1:
                return ent[0], 'SUGGEST_CONTRAT_LIBRE', c, _justif(
                    'SUGGEST_CONTRAT_LIBRE', 'Libellé (contrat format libre)', ck,
                    'N° contrat impayé', ent[0]['contrat'],
                    transformations=transf,
                    note=f'⚠ Contrat trouvé en texte libre — candidat unique, nom : {ent[0]["nom"][:30]}')
            best = min(ent, key=lambda x: abs(x['solde'] - m))
            transf.append(f'Sélection par montant le plus proche : delta = {abs(best["solde"] - m):.2f}€')
            return best, 'SUGGEST_CONTRAT_LIBRE', c, _justif(
                'SUGGEST_CONTRAT_LIBRE', 'Libellé (contrat format libre)', ck,
                'N° contrat impayé', best['contrat'],
                transformations=transf,
                note=f'⚠ Contrat trouvé en texte libre — {len(ent)} candidats, sélection par montant')

    # ── R3 : Numéro isolé 5-7 chiffres dans libellé = potentiel contrat ──
    # Ex: "L'EAU DES COLLINES 16553", "164 CANTINI ... 1212336"
    nums_isoles = re.findall(r'(?<!\d)(\d{5,7})(?!\d)', l)
    for n in nums_isoles:
        if n == a: continue  # Déjà testé comme annotation
        ck = n.zfill(7)
        if ck in idx_contrat:
            ent = idx_contrat[ck]
            if len(ent) == 1:
                return ent[0], 'SUGGEST_NUM_CONTRAT', n, _justif(
                    'SUGGEST_NUM_CONTRAT', 'Libellé (numéro isolé)', n,
                    'N° contrat impayé', ent[0]['contrat'],
                    transformations=[f'Numéro {n} trouvé dans le libellé (pas dans annotation)',
                                    f'Normalisation : {n} → {ck}'],
                    note=f'⚠ Numéro isolé = contrat — candidat unique, nom : {ent[0]["nom"][:30]}')
            # Plusieurs candidats : vérifier si montant discrimine
            best = min(ent, key=lambda x: abs(x['solde'] - m))
            if abs(best['solde'] - m) < m * 0.1:  # delta < 10%
                return best, 'SUGGEST_NUM_CONTRAT', n, _justif(
                    'SUGGEST_NUM_CONTRAT', 'Libellé (numéro isolé)', n,
                    'N° contrat impayé', best['contrat'],
                    transformations=[f'Numéro {n} trouvé dans le libellé',
                                    f'{len(ent)} candidats — sélection par montant (delta {abs(best["solde"]-m):.2f}€ < 10%)'],
                    note=f'⚠ Numéro isolé + montant concordant — nom : {best["nom"][:30]}')

    # ── R4 : Match par montant exact + candidat unique ──
    if idx_montant and m > 0:
        mt_key = round(m, 2)
        if mt_key in idx_montant:
            cands = idx_montant[mt_key]
            if len(cands) == 1:
                info = cands[0]
                return info, 'SUGGEST_MONTANT_UNIQUE', f'{m:.2f}€', _justif(
                    'SUGGEST_MONTANT_UNIQUE', 'Montant encaissé', f'{m:.2f}€',
                    'Solde impayé', f'{info["solde"]:.2f}€',
                    transformations=[f'Montant {m:.2f}€ = solde impayé (correspondance exacte)',
                                    f'Candidat unique sur {len(idx_montant)} montants distincts'],
                    note=f'⚠ Match par montant exact — un seul impayé à ce montant. Contrat {info["contrat"]}, nom : {info["nom"][:30]}')

    # ── R5 : Nom client dans libellé ──
    if idx_nom:
        l_upper = l.upper()
        best_nom_match = None
        best_nom_len = 0
        for nom, infos in idx_nom.items():
            if len(nom) >= 6 and nom in l_upper and len(nom) > best_nom_len:
                best_nom_match = (nom, infos)
                best_nom_len = len(nom)
        if best_nom_match:
            nom, infos = best_nom_match
            if len(infos) == 1:
                info = infos[0]
                return info, 'SUGGEST_NOM_CLIENT', nom, _justif(
                    'SUGGEST_NOM_CLIENT', 'Libellé (nom client)', nom,
                    'Nom impayé (col J)', info['nom'],
                    transformations=[f'Nom « {nom} » détecté dans le libellé (match exact, {len(nom)} car.)',
                                    f'Candidat unique dans le référentiel impayés'],
                    note=f'⚠ Match par nom client — contrat {info["contrat"]}, solde {info["solde"]:.2f}€')
            elif len(infos) <= 5 and m > 0:
                best = min(infos, key=lambda x: abs(x['solde'] - m))
                if abs(best['solde'] - m) < m * 0.2:
                    return best, 'SUGGEST_NOM_CLIENT', nom, _justif(
                        'SUGGEST_NOM_CLIENT', 'Libellé (nom client)', nom,
                        'Nom impayé (col J)', best['nom'],
                        transformations=[f'Nom « {nom} » détecté dans le libellé',
                                        f'{len(infos)} impayés pour ce nom — sélection par montant (delta {abs(best["solde"]-m):.2f}€)'],
                        note=f'⚠ Match par nom + montant — contrat {best["contrat"]}, solde {best["solde"]:.2f}€')

    return None, 'NON_RAPPROCHE', l[:80], {**nj, 'note': 'Aucune règle de matching applicable'}

def traiter_fichier(path, source, date_enc, idx_ref, idx_ref_prefix, idx_contrat, idx_montant=None, idx_nom=None):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    header_row = detecter_header_row(path)
    resultats = []; current_main = None; current_main_mt = 0
    TOLERANCE_SOUS_LIGNES = 0.12  # € — tolérance d'arrondi sur la somme des sous-lignes

    def _flush_sub_lines(sub_batch, main_row, main_mt):
        """Vérifie la cohérence de la somme des sous-lignes et ajoute une note si écart."""
        if not sub_batch:
            return
        somme_sub = sum(r['montant_enc'] for r in sub_batch)
        ecart = abs(main_mt - somme_sub)
        if ecart > TOLERANCE_SOUS_LIGNES:
            note_ecart = f'⚠ Somme sous-lignes = {somme_sub:.2f}€ ≠ montant principal {main_mt:.2f}€ (écart {ecart:.2f}€ > tolérance {TOLERANCE_SOUS_LIGNES}€)'
            for r in sub_batch:
                if r.get('justification'):
                    r['justification']['note'] = (r['justification'].get('note', '') + ' | ' + note_ecart).strip(' | ')
        resultats.extend(sub_batch)

    for ri in range(header_row + 1, ws.max_row + 1):
        a = ws.cell(row=ri, column=1).value; b = ws.cell(row=ri, column=2).value
        c = ws.cell(row=ri, column=3).value; d = ws.cell(row=ri, column=4).value
        e = ws.cell(row=ri, column=5).value
        if a is None and b is None and c is None and d is None: continue
        if b is None and d is not None and e is not None:
            # Sous-ligne : on accumule dans un batch temporaire
            if not hasattr(traiter_fichier, '_sub_batch'):
                traiter_fichier._sub_batch = []
            ref_sub = str(d).strip(); mt_sub = float(e) if e else 0
            info = idx_ref.get(ref_sub)
            # Utiliser _select_best_impaye si plusieurs candidats pour la même ref
            if not info and ref_sub in idx_ref_prefix:
                cands = idx_ref_prefix[ref_sub]
                if len(cands) == 1:
                    info = idx_ref[cands[0]]
                elif len(cands) > 1:
                    info = _select_best_impaye([idx_ref[r] for r in cands], mt_sub)
            sub_status = 'MATCH_REF_EXACT' if info else 'SUB_NO_MATCH'
            sub_justif = _justif(sub_status, 'Sous-ligne col D', ref_sub, 'Référence impayé', info['ref'] if info else '', note='Sous-ligne de ventilation' + (' — match direct' if info else ' — aucun match')) if info else {'score': 0, 'champ_source': 'Sous-ligne col D', 'valeur_source': ref_sub, 'champ_cible': '', 'valeur_cible': '', 'transformations': [], 'note': 'Sous-ligne non matchée'}
            traiter_fichier._sub_batch.append({'source': source, 'row': ri, 'date': date_enc.strftime('%d/%m/%Y'),
                'libelle': f'[Sous-ligne de row {current_main}]', 'montant_enc': mt_sub,
                'annotation': ref_sub, 'status': sub_status,
                'detail': ref_sub, 'ref_imp': info['ref'] if info else '',
                'contrat_imp': info['contrat'] if info else '',
                'nom_imp': info['nom'] if info else '',
                'solde_imp': info['solde'] if info else 0, 'type': 'SOUS_LIGNE',
                'justification': sub_justif})
            continue
        if b is None: continue
        # Nouvelle ligne principale : flusher les sous-lignes du batch précédent
        if hasattr(traiter_fichier, '_sub_batch') and traiter_fichier._sub_batch:
            _flush_sub_lines(traiter_fichier._sub_batch, current_main, current_main_mt)
            traiter_fichier._sub_batch = []
        current_main = ri
        current_main_mt = float(c) if c else 0
        info, status, detail, justif = match_ligne(b, c, d, idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom)
        resultats.append({'source': source, 'row': ri, 'date': date_enc.strftime('%d/%m/%Y'),
            'libelle': str(b)[:120], 'montant_enc': current_main_mt,
            'annotation': str(d).strip() if d else '', 'status': status, 'detail': detail,
            'ref_imp': info['ref'] if info else '',
            'contrat_imp': info['contrat'] if info else '',
            'nom_imp': info['nom'] if info else '',
            'solde_imp': info['solde'] if info else 0, 'type': 'PRINCIPAL',
            'justification': justif})
    # Flusher les sous-lignes en fin de fichier
    if hasattr(traiter_fichier, '_sub_batch') and traiter_fichier._sub_batch:
        _flush_sub_lines(traiter_fichier._sub_batch, current_main, current_main_mt)
        traiter_fichier._sub_batch = []
    wb.close(); return resultats

def generer_csv(resultats, date_saisie, date_enc, output_path):
    date_str = date_saisie.strftime('%d/%m/%Y'); obs = f"CCP {date_enc.strftime('%d%m%y')}"
    lines = []
    for r in resultats:
        if r['status'] in STATUTS_IMPORTABLES and r['contrat_imp'] and r['ref_imp']:
            mt_str = f"{r['montant_enc']:.2f}".replace('.', ',')
            lines.append(f"{date_str};{r['contrat_imp']};{r['ref_imp']};{mt_str};{obs}")
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        f.write("Date;Contrat;Facture;Montant;Observation\r\n")
        for l in lines: f.write(l + "\r\n")
    return len(lines)

def generer_rapport_xlsx(resultats, date_enc, date_saisie, n_import, output_path):
    wb = openpyxl.Workbook()
    hf = Font(name='Arial', bold=True, size=10, color='FFFFFF'); hfl = PatternFill('solid', fgColor='2C3E50')
    ok_fill = PatternFill('solid', fgColor='D5F5E3'); wn_fill = PatternFill('solid', fgColor='FEF9E7')
    ko_fill = PatternFill('solid', fgColor='FADBD8'); ex_fill = PatternFill('solid', fgColor='D6DBDF')
    bd = Border(*(Side(style='thin', color='D5D8DC'),) * 4)
    labels = {
        'MATCH_REF_EXACT': '✓ Ref exacte', 'MATCH_REF_PREFIX': '✓ Ref préfixe',
        'MATCH_EFICASH': '✓ EFICASH', 'MATCH_CONTRAT_UNIQUE': '✓ Contrat unique',
        'MATCH_CONTRAT_MONTANT': '✓ Contrat+montant', 'MATCH_CONTRAT_LIB': '✓ Contrat libellé',
        'MATCH_GC_REF': '✓ GC ref', 'EXCLU_TOTAL': '— Exclu', 'SAGE_HORS_PERIMETRE': '— SAGE',
        'RECOUVREMENT_MANUEL': '⚠ Recouvrement', 'CROSS_SOCIETE_MANUEL': '⚠ Cross-société',
        'GC_MANUEL': '⚠ GC manuel', 'NON_RAPPROCHE': '✗ Non rapproché', 'SUB_NO_MATCH': '✗ Sous-ligne KO',
        'SUGGEST_REF_EXTENDED': '◇ Ref étendue', 'SUGGEST_CONTRAT_LIBRE': '◇ Contrat libre',
        'SUGGEST_MONTANT_UNIQUE': '◇ Montant unique', 'SUGGEST_NUM_CONTRAT': '◇ Num→Contrat',
        'SUGGEST_NOM_CLIENT': '◇ Nom client',
    }

    def style_header(ws, headers, widths):
        for c, (h, w) in enumerate(zip(headers, widths), 1):
            cl = ws.cell(row=1, column=c, value=h)
            cl.font, cl.fill, cl.border = hf, hfl, bd
            cl.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            ws.column_dimensions[get_column_letter(c)].width = w
        ws.freeze_panes = 'A2'

    def fill_for(r):
        if r['status'] in STATUTS_IMPORTABLES: return ok_fill
        if 'EXCLU' in r['status'] or 'PERIMETRE' in r['status']: return ex_fill
        if 'MANUEL' in r['status']: return wn_fill
        return ko_fill

    # ── Onglet 1 : Synthèse ──
    ws1 = wb.active; ws1.title = "Synthèse"
    total = len(resultats)
    n_ok = sum(1 for r in resultats if r['status'] in STATUTS_IMPORTABLES)
    n_warn = sum(1 for r in resultats if 'MANUEL' in r['status'] or r['status'] in STATUTS_SUGGESTIONS)
    n_ko = sum(1 for r in resultats if r['status'] in {'NON_RAPPROCHE', 'SUB_NO_MATCH'})
    n_exclu = total - n_ok - n_warn - n_ko
    mt_ok = sum(r['montant_enc'] for r in resultats if r['status'] in STATUTS_IMPORTABLES)

    kpis = [
        ('Date encaissement', date_enc.strftime('%d/%m/%Y')),
        ('Date saisie', date_saisie.strftime('%d/%m/%Y')),
        ('', ''),
        ('Lignes traitées', total),
        ('Matchées (importables)', f'{n_ok} ({round(n_ok/total*100)}%)' if total else '0'),
        ('Manuelles', n_warn),
        ('Non rapprochées', n_ko),
        ('Exclues', n_exclu),
        ('', ''),
        ('Montant importé', f'{mt_ok:,.2f} €'.replace(',', ' ')),
        ('Lignes dans fichier CSV', n_import),
    ]
    ws1.column_dimensions['A'].width = 28; ws1.column_dimensions['B'].width = 22
    ws1.cell(row=1, column=1, value='Rapport de rapprochement').font = Font(name='Arial', bold=True, size=14)
    ws1.merge_cells('A1:B1')
    for i, (k, v) in enumerate(kpis, 3):
        if k:
            ws1.cell(row=i, column=1, value=k).font = Font(name='Arial', size=10, bold=True)
            ws1.cell(row=i, column=2, value=v).font = Font(name='Arial', size=10)

    # Tableau des statuts détaillés
    row_start = len(kpis) + 5
    ws1.cell(row=row_start, column=1, value='Détail par type de match').font = Font(name='Arial', bold=True, size=11)
    counter = Counter(r['status'] for r in resultats)
    for i, (st, cnt) in enumerate(sorted(counter.items(), key=lambda x: -x[1]), row_start + 1):
        ws1.cell(row=i, column=1, value=labels.get(st, st)).font = Font(name='Arial', size=9)
        ws1.cell(row=i, column=2, value=cnt).font = Font(name='Arial', size=9)

    # ── Onglet 2 : Détail des rapprochements ──
    ws2 = wb.create_sheet("Détail")
    hdrs = ['Source','Ligne','Date','Libellé','Mt Enc.','Annotation','Statut','Score','Ref impayé','Contrat','Nom','Solde TTC','Delta','Import','Justification']
    ws_w = [6,6,11,50,13,18,22,8,18,12,25,14,14,7,45]
    style_header(ws2, hdrs, ws_w)
    ws2.auto_filter.ref = f"A1:O{len(resultats)+1}"
    for i, r in enumerate(resultats, 2):
        fl = fill_for(r)
        delta = round(r['montant_enc'] - r['solde_imp'], 2) if r['ref_imp'] else ''
        iok = r['status'] in STATUTS_IMPORTABLES
        j = r.get('justification', {})
        justif_txt = j.get('note', '')
        if j.get('transformations'):
            justif_txt += ' | ' + ' → '.join(j['transformations'])
        vals = [r['source'], r['row'], r['date'], r['libelle'], r['montant_enc'],
                r['annotation'], labels.get(r['status'], r['status']),
                j.get('score', 0),
                r['ref_imp'], r['contrat_imp'], r['nom_imp'],
                r['solde_imp'] if r['solde_imp'] else '', delta,
                'OUI' if iok else '', justif_txt[:120]]
        for c, v in enumerate(vals, 1):
            cl = ws2.cell(row=i, column=c, value=v); cl.font = Font(name='Arial', size=9)
            cl.border, cl.fill = bd, fl
            if c in (5, 12, 13): cl.number_format = '#,##0.00'
            if c == 14 and v == 'OUI': cl.font = Font(name='Arial', size=9, bold=True, color='0D7C3E')

    # ── Onglet 3 : Non rapprochés ──
    ws3 = wb.create_sheet("Non rapprochés")
    non_rapp = [r for r in resultats if r['status'] not in STATUTS_IMPORTABLES and 'EXCLU' not in r['status'] and 'PERIMETRE' not in r['status']]
    hdrs3 = ['Source','Ligne','Libellé','Mt Enc.','Annotation','Catégorie','Raison']
    ws3_w = [6,6,55,13,18,22,50]
    style_header(ws3, hdrs3, ws3_w)
    ws3.auto_filter.ref = f"A1:G{len(non_rapp)+1}"
    for i, r in enumerate(non_rapp, 2):
        fl = wn_fill if 'MANUEL' in r['status'] else ko_fill
        j = r.get('justification', {})
        vals = [r['source'], r['row'], r['libelle'], r['montant_enc'],
                r['annotation'], labels.get(r['status'], r['status']),
                j.get('note', '')]
        for c, v in enumerate(vals, 1):
            cl = ws3.cell(row=i, column=c, value=v); cl.font = Font(name='Arial', size=9)
            cl.border, cl.fill = bd, fl
            if c == 4: cl.number_format = '#,##0.00'

    wb.save(output_path)


# ═══════════════════════════════════════════════════════════════════════
# INTERFACE WEB v4.2 — Colonnes réordonnables + Score repositionné + refresh
# ═══════════════════════════════════════════════════════════════════════

HTML_PAGE = r"""<!DOCTYPE html>
<html class="light" lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Copilote d'Encaissement — Veolia</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='16' fill='%2300396b'/%3E%3Cpath d='M16 6c0 0-6 8-6 14a6 6 0 1012 0c0-6-6-14-6-14z' fill='%23fff'/%3E%3C/svg%3E">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com" rel="preconnect">
<link crossorigin href="https://fonts.gstatic.com" rel="preconnect">
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/style.css">
<script>
tailwind.config = {
  theme: {
    extend: {
      fontFamily: { sans: ['Public Sans', 'system-ui', 'sans-serif'] }
    }
  }
}
</script>
</head>
<body class="bg-slate-50 text-slate-800 flex h-screen w-full overflow-hidden font-sans text-[13px]">

<!-- ═══ SIDEBAR NAV ═══ -->
<nav class="bg-white text-blue-900 text-[13px] font-medium fixed left-0 top-0 h-screen w-[240px] border-r border-slate-200 flex flex-col py-4 z-20">
  <div class="px-6 mb-8 flex items-center gap-3">
    <div class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
      <span class="material-symbols-outlined text-blue-900" style="font-size:20px">water_drop</span>
    </div>
    <div>
      <h1 class="text-blue-900 font-bold tracking-tight text-[15px] leading-tight">Reconciliation</h1>
      <p class="text-slate-400 text-[11px] leading-tight mt-0.5">Veolia — SOMEI</p>
    </div>
  </div>

  <ul class="flex-1 flex flex-col gap-0.5 px-3">
    <li>
      <a class="nav-link flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-all cursor-pointer" data-tab="import" onclick="switchTab('import')">
        <span class="material-symbols-outlined text-[20px]">upload_file</span>
        Import
      </a>
    </li>
    <li>
      <a class="nav-link flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-all cursor-pointer" data-tab="progress" onclick="switchTab('progress')">
        <span class="material-symbols-outlined text-[20px]">hourglass_top</span>
        Progression
      </a>
    </li>
    <li>
      <a class="nav-link flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-all cursor-pointer" data-tab="results" onclick="switchTab('results')">
        <span class="material-symbols-outlined text-[20px]">assessment</span>
        Resultats
      </a>
    </li>
    <li>
      <a class="nav-link active flex items-center gap-3 px-3 py-2.5 rounded-lg text-blue-900 bg-blue-50 border-r-2 border-blue-900 transition-all cursor-pointer" data-tab="details" onclick="switchTab('details')">
        <span class="material-symbols-outlined text-[20px]" style="font-variation-settings:'FILL' 1">compare_arrows</span>
        Matching
      </a>
    </li>
    <li>
      <a class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-all cursor-pointer" href="/documentation" target="_blank">
        <span class="material-symbols-outlined text-[20px]">menu_book</span>
        Documentation
      </a>
    </li>
  </ul>

  <div class="mt-auto px-3 border-t border-slate-100 pt-4">
    <ul class="flex flex-col gap-0.5">
      <li>
        <a class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-all cursor-pointer" onclick="demanderFermeture()">
          <span class="material-symbols-outlined text-[20px]">power_settings_new</span>
          Quitter
        </a>
      </li>
    </ul>
  </div>
</nav>

<!-- ═══ MAIN CONTENT ═══ -->
<div class="flex-1 flex flex-col ml-[240px] h-screen overflow-hidden">

  <!-- TOP BAR -->
  <header class="bg-white text-slate-800 text-sm font-medium border-b border-slate-200 flex justify-between items-center h-14 px-6 w-full shrink-0 z-10">
    <div class="flex items-center gap-3">
      <span class="text-[17px] font-bold text-blue-900">Copilote d'Encaissement</span>
      <span class="hidden md:inline-flex items-center gap-1.5 bg-blue-50 text-blue-800 text-[11px] font-semibold px-3 py-1 rounded-full" id="chip-status" style="display:none">
        <span class="w-2 h-2 rounded-full bg-green-500 inline-block" id="dot-status"></span>
        <b id="chip-date"></b>
      </span>
    </div>
    <div class="flex items-center gap-4">
      <div class="relative w-56 hidden lg:block">
        <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-300 text-[18px]">search</span>
        <input class="w-full bg-slate-50 border border-slate-200 rounded-lg py-1.5 pl-9 pr-3 text-[13px] focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400" placeholder="Rechercher..." type="text">
      </div>
      <button class="w-8 h-8 flex items-center justify-center text-slate-400 hover:bg-slate-50 rounded-full transition-colors" onclick="window.open('/documentation','_blank')">
        <span class="material-symbols-outlined text-[20px]">help_outline</span>
      </button>
    </div>
  </header>

  <!-- MAIN CANVAS -->
  <main class="flex-1 overflow-auto bg-slate-50 p-6 flex flex-col gap-5">

    <!-- PAGE HEADER -->
    <div class="flex items-center justify-between shrink-0">
      <div>
        <h2 class="text-2xl font-semibold text-slate-800" id="page-title">Import des fichiers</h2>
        <p class="text-sm text-slate-400 mt-1" id="page-subtitle">Chargez vos fichiers d'impayes et d'encaissements pour lancer le rapprochement automatique.</p>
      </div>
      <div class="hidden md:flex items-center gap-2 bg-white px-4 py-2 border border-slate-200 rounded-lg" id="batch-info" style="display:none">
        <span class="material-symbols-outlined text-sky-600 text-[20px]">info</span>
        <span class="text-[13px] font-mono text-slate-500" id="batch-info-text"></span>
      </div>
    </div>

    <!-- ═══ TAB 1: IMPORT ═══ -->
    <div class="tab-panel active" id="tab-import">
      <div class="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div class="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
          <h3 class="text-[15px] font-semibold text-slate-700 flex items-center gap-2">
            <span class="material-symbols-outlined text-sky-600 text-[20px]">folder_open</span>
            Fichiers source
          </h3>
          <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 bg-slate-100 px-2.5 py-1 rounded">3 fichiers requis</span>
        </div>
        <div class="p-6">
          <div class="upload-grid">
            <label class="upload-zone" id="zone-imp" ondragover="dragOver(event,'imp')" ondragleave="dragLeave(event,'imp')" ondrop="dropFile(event,'imp')">
              <span class="material-symbols-outlined zone-icon text-[32px]">description</span>
              <div class="zone-label">Impayes</div>
              <div class="zone-hint">Etat_des_impayes_au_*.xlsx</div>
              <div class="zone-file" id="name-imp"></div>
              <input type="file" id="file-imp" accept=".xlsx" onchange="fileSelected('imp')">
            </label>
            <label class="upload-zone" id="zone-sem" ondragover="dragOver(event,'sem')" ondragleave="dragLeave(event,'sem')" ondrop="dropFile(event,'sem')">
              <span class="material-symbols-outlined zone-icon text-[32px]">account_balance</span>
              <div class="zone-label">Encaissement SEM</div>
              <div class="zone-hint">Releve_encaissement_SEM_*.xlsx</div>
              <div class="zone-file" id="name-sem"></div>
              <input type="file" id="file-sem" accept=".xlsx" onchange="fileSelected('sem')">
            </label>
            <label class="upload-zone" id="zone-semm" ondragover="dragOver(event,'semm')" ondragleave="dragLeave(event,'semm')" ondrop="dropFile(event,'semm')">
              <span class="material-symbols-outlined zone-icon text-[32px]">account_balance</span>
              <div class="zone-label">Encaissement SEMM</div>
              <div class="zone-hint">Releve_encaissement_SEMM_*.xlsx</div>
              <div class="zone-file" id="name-semm"></div>
              <input type="file" id="file-semm" accept=".xlsx" onchange="fileSelected('semm')">
            </label>
          </div>
          <button class="btn-primary flex items-center justify-center gap-2" id="btn-run" disabled onclick="lancer()">
            <span class="material-symbols-outlined text-[18px]">play_arrow</span>
            Lancer le rapprochement
          </button>
          <button class="btn-secondary" id="btn-resume" disabled onclick="restoreSession()">
            <span class="flex items-center justify-center gap-2">
              <span class="material-symbols-outlined text-[16px]">restore</span>
              Reprendre la derniere session
            </span>
            <div class="resume-info">Aucune session sauvegardee</div>
          </button>
        </div>
      </div>
    </div>

    <!-- ═══ TAB 2: PROGRESS ═══ -->
    <div class="tab-panel" id="tab-progress">
      <div class="bg-white border border-slate-200 rounded-xl p-12 text-center">
        <div class="w-16 h-16 rounded-full bg-blue-50 flex items-center justify-center mx-auto mb-6">
          <span class="material-symbols-outlined text-blue-900 text-[32px] animate-spin" style="animation-duration:2s">sync</span>
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-4">Rapprochement en cours...</h3>
        <div id="progress-section" style="display:block">
          <div class="progress-bar-wrap"><div class="progress-bar-fill" id="progress-bar-fill"></div></div>
          <div class="progress-text" id="progress-text">Preparation...</div>
        </div>
      </div>
    </div>

    <!-- ═══ TAB 3: RESULTS ═══ -->
    <div class="tab-panel" id="tab-results">
      <div class="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div class="p-8">
          <div class="results-header">
            <div class="results-check"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg></div>
            <h2>Rapprochement termine</h2>
            <p id="res-sub">—</p>
          </div>
          <div class="kpi-grid">
            <div class="kpi"><div class="kpi-value" id="k-total">—</div><div class="kpi-label">Lignes traitees</div></div>
            <div class="kpi ok"><div class="kpi-value" id="k-ok">—</div><div class="kpi-label">Matchees (import)</div></div>
            <div class="kpi warn"><div class="kpi-value" id="k-warn">—</div><div class="kpi-label">Manuelles</div></div>
            <div class="kpi err"><div class="kpi-value" id="k-err">—</div><div class="kpi-label">Non rapprochees</div></div>
          </div>
          <div class="amount-box">
            <div class="lbl">Montant importe</div>
            <div class="val" id="k-montant">—</div>
          </div>
          <div class="dl-row">
            <a class="dl-link" id="dl-csv" href="#">
              <span class="material-symbols-outlined text-sky-600 text-[24px]">download</span>
              <div><div class="dl-name">Fichier d'import</div><div class="dl-desc">import_waterp_JJMMAA.csv</div></div>
            </a>
            <a class="dl-link" id="dl-xlsx" href="#">
              <span class="material-symbols-outlined text-green-600 text-[24px]">table_chart</span>
              <div><div class="dl-name">Rapport de rapprochement</div><div class="dl-desc">rapport_JJMMAA.xlsx — 3 onglets</div></div>
            </a>
          </div>
          <button class="btn-details flex items-center justify-center gap-2" id="btn-goto-details" onclick="switchTab('details')">
            <span class="material-symbols-outlined text-[16px]">visibility</span>
            Voir le detail des lignes
          </button>
        </div>
      </div>
    </div>

    <!-- ═══ TAB 4: DETAIL ═══ -->
    <div class="tab-panel" id="tab-details">
      <div class="toolbar">
        <div class="filter-pills">
          <button class="pill active" data-sf="all" onclick="setStatusFilter('all')">Tous</button>
          <button class="pill ok" data-sf="ok" onclick="setStatusFilter('ok')">
            <span class="inline-block w-2 h-2 rounded-full bg-green-500 mr-1"></span>OK
          </button>
          <button class="pill warn" data-sf="suggest" onclick="setStatusFilter('suggest')">
            <span class="inline-block w-2 h-2 rounded-full bg-yellow-500 mr-1"></span>Suggestions
          </button>
          <button class="pill warn" data-sf="warn" onclick="setStatusFilter('warn')">
            <span class="inline-block w-2 h-2 rounded-full bg-orange-500 mr-1"></span>Manuel
          </button>
          <button class="pill err" data-sf="err" onclick="setStatusFilter('err')">
            <span class="inline-block w-2 h-2 rounded-full bg-red-500 mr-1"></span>Non rapproche
          </button>
          <button class="pill" data-sf="exclu" onclick="setStatusFilter('exclu')">Exclu</button>
        </div>
        <div class="toolbar-spacer"></div>
        <span class="toolbar-count" id="tbl-count">0 / 0 lignes</span>
        <button class="toolbar-btn" onclick="exportSelection()" title="Exporter">
          <span class="material-symbols-outlined text-[16px]">download</span>
        </button>
        <button class="toolbar-btn" onclick="refreshTable()" title="Actualiser">
          <span class="material-symbols-outlined text-[16px]">refresh</span>
        </button>
        <div style="position:relative;">
          <button class="toolbar-btn" onclick="toggleColumns(event)" title="Colonnes">
            <span class="material-symbols-outlined text-[16px]">view_column</span>
          </button>
          <div class="col-chooser" id="col-chooser" style="display:none;position:absolute;top:34px;right:0;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 0;min-width:180px;box-shadow:0 10px 25px rgba(0,0,0,.1);z-index:100;"></div>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr id="header-row"></tr><tr id="filter-row" style="background:#f8fafc;"></tr></thead>
          <tbody id="detail-body"></tbody>
        </table>
      </div>
    </div>

  </main>

  <!-- FOOTER -->
  <footer class="bg-slate-800 text-slate-400 px-6 py-2.5 text-[10px] flex items-center justify-between shrink-0">
    <div>Veolia | Software Solutions — Copilote d'Encaissement v5.0</div>
    <div>Somei S.A. — Groupe Eaux de Marseille</div>
  </footer>
</div>

<!-- ═══ MODAL ═══ -->
<div class="modal-overlay" id="modal-close">
  <div class="modal-box">
    <div class="mb-4">
      <span class="material-symbols-outlined text-red-500 text-[48px]">power_settings_new</span>
    </div>
    <h3>Quitter l'application ?</h3>
    <p>Le serveur va s'arreter. Toute session non sauvegardee sera perdue.</p>
    <div class="modal-btns">
      <button class="modal-btn-cancel" onclick="document.getElementById('modal-close').classList.remove('active')">Annuler</button>
      <button class="modal-btn-quit" onclick="confirmerFermeture()">Quitter</button>
    </div>
  </div>
</div>

<script src="/static/app.js"></script>
</body></html>"""
# SERVEUR HTTP
# ═══════════════════════════════════════════════════════════════════════

progress_state = {'pct': 0, 'msg': 'En attente'}
generated_files = {'csv': None, 'xlsx': None}
_server_ref = None          # référence globale pour shutdown
_shutdown_event = threading.Event()   # signale au thread principal de quitter
_browser_proc = None        # PID du navigateur lancé en mode --app

# Dossier docs (images + PDF)
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

DOC_PAGE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Documentation &#8212; Copilote d'Encaissement</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='16' fill='%232a3058'/%3E%3Cpath d='M16 6c0 0-6 8-6 14a6 6 0 1012 0c0-6-6-14-6-14z' fill='%23fff'/%3E%3C/svg%3E">
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{--navy:#2a3058;--blue:#0069b4;--blue-light:#d9e9f4;--bg:#f1f5f9;--surface:#fff;--text:#0f172a;--text-muted:#64748b;--border:#e2e8f0;--radius:12px;
    --green:#0d7c3e;--green-bg:#e6f4ec;--orange:#c05600;--orange-bg:#fef3e6;--red:#c62828;--red-bg:#fce8e8;--purple:#6a1b9a;--purple-bg:#f3e5f5;--sem:#1565c0;--semm:#c62828}
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Roboto',Arial,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column;line-height:1.65}
  .top-strip{background:var(--navy);color:rgba(255,255,255,.6);font-size:11px;padding:6px 20px;display:flex;align-items:center;justify-content:space-between;font-weight:400}
  .top-strip a{color:rgba(255,255,255,.6);text-decoration:none}.top-strip a:hover{color:#fff}
  .logo-bar{background:var(--surface);padding:10px 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);box-shadow:0 1px 3px rgba(0,0,0,.04)}
  .logo-brand{display:flex;align-items:center;gap:14px}.logo-img{height:28px}
  .logo-title{font-size:16px;font-weight:600;color:var(--text);letter-spacing:-.01em}
  .nav-icons{display:flex;gap:2px}
  .nav-icon{display:flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:6px;color:var(--text-muted);transition:all .15s;text-decoration:none}
  .nav-icon:hover{background:var(--blue-light);color:var(--blue)}
  .nav-icon svg{width:18px;height:18px}
  .main{flex:1;max-width:1000px;margin:0 auto;padding:40px 20px;width:100%}
  h1{font-size:24px;font-weight:700;color:var(--navy);margin-bottom:8px}
  .subtitle{font-size:14px;color:var(--text-muted);margin-bottom:32px}
  .doc-card{background:var(--surface);border-radius:var(--radius);border:1px solid var(--border);overflow:hidden;margin-bottom:24px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
  .doc-card img{width:100%;height:auto;display:block}
  .doc-card-body{padding:16px 20px}
  .doc-card-title{font-size:15px;font-weight:600;margin-bottom:4px}
  .doc-card-desc{font-size:12px;color:var(--text-muted)}
  .pdf-link{display:inline-flex;align-items:center;gap:10px;padding:14px 24px;background:var(--navy);color:#fff;text-decoration:none;border-radius:var(--radius);font-size:14px;font-weight:500;transition:all .2s;margin-top:8px}
  .pdf-link:hover{background:var(--blue);transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,105,180,.3)}
  .pdf-link svg{width:20px;height:20px;flex-shrink:0}
  .footer{background:var(--navy);color:rgba(255,255,255,.35);padding:12px 20px;font-size:10px;display:flex;align-items:center;justify-content:space-between;margin-top:auto}
  .footer a{color:rgba(255,255,255,.5);text-decoration:none}.footer a:hover{color:rgba(255,255,255,.8)}

  /* ── Technical chapter ── */
  .tech-sep{margin:48px 0 32px;border:none;border-top:2px solid var(--border)}
  .section{margin-bottom:28px}
  .section-title{font-size:17px;font-weight:700;margin-bottom:14px;display:flex;align-items:center;gap:8px}
  .section-title .num{background:var(--blue);color:#fff;width:26px;height:26px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px;margin-bottom:14px}
  .card h3{font-size:14px;font-weight:700;margin-bottom:10px}
  .card p,.card li{font-size:13px;color:var(--text-muted);margin-bottom:6px}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
  @media(max-width:800px){.grid2,.grid3{grid-template-columns:1fr}}
  .stat-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px;text-align:center}
  .stat-card .value{font-size:28px;font-weight:700;color:var(--blue)}
  .stat-card .label{font-size:12px;color:var(--text-muted);margin-top:3px}
  .stat-card.sem .value{color:var(--sem)}.stat-card.semm .value{color:var(--semm)}.stat-card.ok .value{color:var(--green)}
  table.tech{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}
  table.tech th{background:var(--bg);font-weight:600;text-align:left;padding:8px 10px;border-bottom:2px solid var(--border)}
  table.tech td{padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:top}
  table.tech tr:hover td{background:#fafbfc}
  .tag{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:4px}
  .tag-sem{background:#e3f2fd;color:var(--sem)}.tag-semm{background:var(--red-bg);color:var(--semm)}
  .tag-match{background:var(--green-bg);color:var(--green)}.tag-warn{background:var(--orange-bg);color:var(--orange)}
  .tag-critical{background:var(--red-bg);color:var(--red)}.tag-info{background:var(--purple-bg);color:var(--purple)}
  .rule-box{border-left:4px solid var(--blue);padding:14px 18px;background:var(--blue-light);border-radius:0 8px 8px 0;margin-bottom:10px}
  .rule-box.green{border-color:var(--green);background:var(--green-bg)}
  .rule-box.orange{border-color:var(--orange);background:var(--orange-bg)}
  .rule-box.purple{border-color:var(--purple);background:var(--purple-bg)}
  .rule-box.red{border-color:var(--red);background:var(--red-bg)}
  .rule-box .rule-title{font-size:13px;font-weight:700;margin-bottom:3px}
  .rule-box .rule-desc{font-size:12px;color:var(--text-muted)}
  code{font-family:'JetBrains Mono',monospace;font-size:11px;background:#f0f2f5;padding:1px 5px;border-radius:3px}
  .highlight{background:#fffde7;padding:10px 14px;border-radius:7px;border:1px solid #f9e44c;font-size:12px;margin:10px 0}
  .cycle-box{display:flex;gap:0;margin:16px 0;flex-wrap:wrap}
  .cycle-step{flex:1;min-width:160px;padding:14px;text-align:center;font-size:12px}
  .cycle-step:nth-child(1){background:#e3f2fd;border-radius:8px 0 0 8px}
  .cycle-step:nth-child(2){background:#fff3e0}
  .cycle-step:nth-child(3){background:#e8f5e9}
  .cycle-step:nth-child(4){background:#fce4ec}
  .cycle-step:nth-child(5){background:#f3e5f5;border-radius:0 8px 8px 0}
  .cycle-step .step-num{font-weight:700;font-size:18px;opacity:.3;display:block}
  .cycle-step .step-title{font-weight:600;font-size:12px;margin:4px 0 2px}
  .cycle-step .step-detail{font-size:11px;color:var(--text-muted)}
  pre.algo{background:#1a1d23;color:#e8eaed;padding:18px;border-radius:8px;overflow-x:auto;font-family:'JetBrains Mono',monospace;font-size:11px;line-height:1.7}
  .progress-bar{background:#eee;border-radius:20px;height:22px;position:relative;overflow:hidden;margin:8px 0}
  .progress-bar .fill{height:100%;border-radius:20px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:600}
  .toc{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px 24px;margin-bottom:32px}
  .toc-title{font-size:14px;font-weight:700;margin-bottom:10px;color:var(--navy)}
  .toc a{display:block;font-size:13px;color:var(--blue);text-decoration:none;padding:3px 0;transition:color .15s}
  .toc a:hover{color:var(--navy);text-decoration:underline}
  .toc .toc-num{display:inline-block;width:22px;color:var(--text-muted);font-weight:600;font-size:12px}
</style>
</head>
<body>

<div class="top-strip">
  <span>Veolia &#8212; Eau &amp; Assainissement</span>
  <a href="/">&#8592; Retour au Copilote</a>
</div>

<div class="logo-bar">
  <div class="logo-brand">
    <img src="https://www.somei.fr/site2017/wp-content/uploads/2025/11/Capsule-Veolia-RVB-x0.5.png" alt="Veolia" class="logo-img">
    <div class="logo-title">Veolia | Software Solutions <span style="color:var(--text-muted);font-weight:400">&#8212; Documentation</span></div>
  </div>
  <div class="nav-icons">
    <a class="nav-icon" href="/" title="Retour au Copilote"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg></a>
  </div>
</div>

<div class="main">
  <h1>Documentation du Copilote d&#8217;Encaissement</h1>
  <p class="subtitle">Analyse technique du moteur de rapprochement bancaire automatis&#233; &#8212; SOMEI / Veolia</p>

  <!-- Table of contents -->
  <div class="toc">
    <div class="toc-title">Sommaire</div>
    <a href="#s1"><span class="toc-num">1.</span> Cycle de vie d&#8217;un encaissement</a>
    <a href="#s2"><span class="toc-num">2.</span> Structure des donn&#233;es</a>
    <a href="#s3"><span class="toc-num">3.</span> R&#232;gles de matching</a>
    <a href="#s4"><span class="toc-num">4.</span> Cas sp&#233;ciaux et pi&#232;ges identifi&#233;s</a>
    <a href="#s5"><span class="toc-num">5.</span> Patterns d&#8217;extraction (regex Python)</a>
    <a href="#s6"><span class="toc-num">6.</span> Algorithme de rapprochement</a>
    <a href="#s7"><span class="toc-num">7.</span> R&#233;sultats du test</a>
    <a href="#s8"><span class="toc-num">8.</span> Format de sortie &#8212; Import Waterp</a>
    <a href="#s9"><span class="toc-num">9.</span> Recommandations techniques</a>
    <a href="#s10"><span class="toc-num">10.</span> Sch&#233;mas &#8212; L&#8217;IA au service du rapprochement</a>
    <a href="#s11"><span class="toc-num">11.</span> Pr&#233;sentation compl&#232;te (PDF)</a>
  </div>

  <!-- ── S1: Cycle de vie ── -->
  <div class="section" id="s1">
    <div class="section-title"><span class="num">1</span> Cycle de vie d&#8217;un encaissement</div>
    <div class="card">
      <h3>Parcours valid&#233; &#8212; Ref 40251200016320 &#8212; 57 761,88 &#8364;</h3>
      <div class="cycle-box">
        <div class="cycle-step"><span class="step-num">1</span><div class="step-title">Encaissement bancaire</div><div class="step-detail">Relev&#233; SEMM du 16/12/2025<br>Virement de SOGIMA<br>57 761,88 &#8364;</div></div>
        <div class="cycle-step"><span class="step-num">2</span><div class="step-title">Impay&#233; en attente</div><div class="step-detail">Fichier impay&#233;s du 17/12<br>Ligne 4669<br>Ref: 40251200016320<br>Contrat: 1089100</div></div>
        <div class="cycle-step"><span class="step-num">3</span><div class="step-title">Saisie Waterp</div><div class="step-detail">Le 17/12/2025 (J+1)<br>Code soc: 40<br>Lettrage: 40251200016320<br>REGLEMENT 09 / CCP</div></div>
        <div class="cycle-step"><span class="step-num">4</span><div class="step-title">Impay&#233; sold&#233;</div><div class="step-detail">Fichier du 18/12<br>Ref 40251200016320<br><strong>n&#8217;appara&#238;t plus</strong></div></div>
        <div class="cycle-step"><span class="step-num">5</span><div class="step-title">Waterp lettr&#233;</div><div class="step-detail">D&#233;bit: 57 761,88 &#8364;<br>Cr&#233;dit: 57 761,88 &#8364;<br><strong>Solde: 0,00 &#8364;</strong></div></div>
      </div>
      <div class="highlight">
        <strong>Enseignement cl&#233; :</strong> La colonne &#171; Lettrage &#187; dans Waterp = la <strong>R&#233;f&#233;rence facture</strong> (col O des impay&#233;s). Le &#171; Num&#233;ro d &#187; = le <strong>N&#176; de Contrat</strong> (col C). Le Code soci&#233;t&#233; = les 2 premiers chiffres de la r&#233;f&#233;rence. La saisie se fait toujours &#224; <strong>J+1</strong>. Type d&#8217;&#233;criture : <code>REGLEMENT 09</code> / mode <code>CCP VIREMENTS DIVERS</code>.
      </div>
    </div>
  </div>

  <!-- ── S2: Structure ── -->
  <div class="section" id="s2">
    <div class="section-title"><span class="num">2</span> Structure des donn&#233;es</div>
    <div class="grid3">
      <div class="stat-card"><div class="value">112 489</div><div class="label">Lignes impay&#233;s (2013-2025)</div></div>
      <div class="stat-card sem"><div class="value">56</div><div class="label">Encaissements SEM du 16/12</div></div>
      <div class="stat-card semm"><div class="value">172 + 23</div><div class="label">Encaissements SEMM + sous-lignes</div></div>
    </div>
    <div class="card" style="margin-top:14px">
      <h3>Correspondance colonnes Encaissement &#8596; Impay&#233;s &#8596; Waterp</h3>
      <table class="tech">
        <tr><th>Donn&#233;e</th><th>Encaissement</th><th>Impay&#233;s</th><th>Saisie Waterp</th></tr>
        <tr><td><strong>R&#233;f&#233;rence facture</strong></td><td>Col D (regex)</td><td>Col O (14 chiffres)</td><td>&#171; Lettrage &#187;</td></tr>
        <tr><td><strong>N&#176; de contrat</strong></td><td>Col D (5-7 chiffres) ou libell&#233; B</td><td>Col C</td><td>&#171; Num&#233;ro d &#187;</td></tr>
        <tr><td><strong>Code soci&#233;t&#233;</strong></td><td>Pr&#233;fixe ref: 10=SEM, 40=SEMM</td><td>Col Z + pr&#233;fixe col O</td><td>&#171; Code soci&#233;t&#233; &#187;</td></tr>
        <tr><td><strong>Montant</strong></td><td>Col C (total) ou Col E (ventil&#233;)</td><td>Col T (Solde TTC restant)</td><td>&#171; Encaissement &#187;</td></tr>
        <tr><td><strong>Date encaissement</strong></td><td>Col A (16/12/2025)</td><td>&#8212;</td><td>&#171; Date &#187; (J+1)</td></tr>
        <tr><td><strong>Nom payeur</strong></td><td>Libell&#233; B (apr&#232;s &#171; VIREMENT DE &#187;)</td><td>Col J (Raison Sociale)</td><td>&#8212;</td></tr>
        <tr><td><strong>Mode r&#232;glement</strong></td><td>CCP (virements postaux)</td><td>Col Y (code mode)</td><td>&#171; CCP VIREMENTS DIVERS &#187;</td></tr>
      </table>
    </div>
  </div>

  <!-- ── S3: Règles de matching ── -->
  <div class="section" id="s3">
    <div class="section-title"><span class="num">3</span> R&#232;gles de matching &#8212; par niveau de fiabilit&#233;</div>
    <div class="card">
      <div class="rule-box green">
        <div class="rule-title">&#128273; NIVEAU 1 &#8212; R&#233;f&#233;rence facture (col D &#8594; col O)</div>
        <div class="rule-desc">
          Cl&#233; primaire. <strong>SEM :</strong> pattern <code>10\d{12}</code> &#8226; <strong>SEMM :</strong> <code>40\d{12}</code> &#8226; <strong>EFICASH :</strong> ref 40xxx apr&#232;s <code>REF: 00</code><br>
          <strong>R&#233;sultat :</strong> 26/27 SEM &#10003; &#8226; 105/118 SEMM &#10003; &#8226; 4/4 EFICASH &#10003;
        </div>
      </div>
      <div class="rule-box">
        <div class="rule-title">&#128273; NIVEAU 2 &#8212; N&#176; de Contrat (col D &#8594; col C)</div>
        <div class="rule-desc">
          Quand col D contient un num&#233;ro 5-7 chiffres. <strong>&#9888; Padding z&#233;ros :</strong> Le contrat dans les impay&#233;s fait 7 caract&#232;res (<code>447068 &#8594; 0447068</code>).<br>
          <strong>R&#233;sultat :</strong> 6 SEM &#10003; &#8226; 27 SEMM &#10003;
        </div>
      </div>
      <div class="rule-box orange">
        <div class="rule-title">&#128273; NIVEAU 3 &#8212; Nom + Montant (libell&#233; B &#8594; col J + col T)</div>
        <div class="rule-desc">
          Extraction du nom apr&#232;s &#171; VIREMENT DE &#187; + comparaison avec Solde TTC.<br>
          <strong>Fiabilit&#233; :</strong> Moyenne &#8212; noms souvent tronqu&#233;s (25 car. max dans libell&#233; bancaire).
        </div>
      </div>
      <div class="rule-box purple">
        <div class="rule-title">&#128273; NIVEAU 4 &#8212; Recherche cross-soci&#233;t&#233;</div>
        <div class="rule-desc">
          Certains payeurs versent sur un compte SEMM pour des factures SEM (ref 10xxx) ou VIVAIGO (ref 33xxx).<br>
          <strong>R&#232;gle :</strong> Toujours chercher dans TOUT l&#8217;index des refs, pas seulement la soci&#233;t&#233; du fichier.
        </div>
      </div>
    </div>
  </div>

  <!-- ── S4: Cas spéciaux ── -->
  <div class="section" id="s4">
    <div class="section-title"><span class="num">4</span> Cas sp&#233;ciaux et pi&#232;ges identifi&#233;s</div>
    <div class="grid2">
      <div class="card">
        <h3>Sous-lignes de ventilation</h3>
        <p>Un organisme paye un montant global pour N contrats. Les lignes suivantes d&#233;taillent chaque ref (D) et montant (E).</p>
        <p><strong>23 sous-lignes</strong> dans SEMM. R&#232;gle : chaque sous-ligne = un match individuel D&#8594;col O.</p>
      </div>
      <div class="card">
        <h3>R&#233;f&#233;rences tronqu&#233;es (13 chiffres)</h3>
        <p>Certaines refs en col D font 13 au lieu de 14 chiffres (dernier chiffre coup&#233;).</p>
        <p><strong>R&#232;gle :</strong> Si ref fait 13 chiffres &#8594; match par pr&#233;fixe dans l&#8217;index des refs.</p>
      </div>
      <div class="card">
        <h3>Paiement cross-soci&#233;t&#233;</h3>
        <p>Libell&#233;s contenant &#171; REGLEMENT SEMM / SEM / APE &#187; = virements regroup&#233;s pour plusieurs soci&#233;t&#233;s.</p>
        <p><strong>R&#232;gle :</strong> Marquage &#171; ventilation manuelle requise &#187;.</p>
      </div>
      <div class="card">
        <h3>SGC / GC (Service Gestion Comptable)</h3>
        <p>Les refs sont coll&#233;es dans le texte sans espace. Regex &#233;largie <code>r'(40\d{11,13})'</code> pour capter les refs coll&#233;es.</p>
      </div>
      <div class="card">
        <h3>SAGE (travaux / maintenance)</h3>
        <p>9 lignes SEM avec annotation SAGE. Refs type <code>72-AIX2512-0015</code>. Factures travaux hors p&#233;rim&#232;tre impay&#233;s eau &#8594; circuit s&#233;par&#233;.</p>
      </div>
      <div class="card">
        <h3>INTRUM (recouvrement)</h3>
        <p>Paiements globaux sans d&#233;tail de ref. Marquage &#171; recouvrement INTRUM &#8212; ventilation manuelle &#187;.</p>
      </div>
    </div>
    <div class="card">
      <h3>Lignes &#224; exclure du rapprochement</h3>
      <table class="tech">
        <tr><th>Crit&#232;re</th><th>Raison</th><th>Exemple</th></tr>
        <tr><td>Col D = <code>TOTAL</code></td><td>Virement sortant (solde du compte)</td><td>-113 694 &#8364; (SEM) / -521 395 &#8364; (SEMM)</td></tr>
        <tr><td>Montant C &lt; 0</td><td>Transfert interne</td><td>M&#234;mes lignes</td></tr>
        <tr><td>Col D = <code>SAGE</code></td><td>Factures travaux hors p&#233;rim&#232;tre</td><td>72-AIX2512-0015</td></tr>
      </table>
    </div>
  </div>

  <!-- ── S5: Regex ── -->
  <div class="section" id="s5">
    <div class="section-title"><span class="num">5</span> Patterns d&#8217;extraction (regex Python)</div>
    <div class="card">
      <table class="tech">
        <tr><th>Cible</th><th>Regex</th><th>Priorit&#233;</th></tr>
        <tr><td>Ref SEM (14 chif.)</td><td><code>r'(10\d{12})'</code></td><td>1</td></tr>
        <tr><td>Ref SEMM (14 chif.)</td><td><code>r'(40\d{12})'</code></td><td>1</td></tr>
        <tr><td>Ref VIVAIGO (14 chif.)</td><td><code>r'(33\d{12})'</code></td><td>1 (cross-soc.)</td></tr>
        <tr><td>Ref tronqu&#233;e (13 chif.)</td><td><code>r'((?:10|40|33)\d{11})'</code></td><td>1bis (pr&#233;fixe)</td></tr>
        <tr><td>Ref EFICASH</td><td><code>r'REF:\s*00(40\d{11,13})'</code></td><td>1</td></tr>
        <tr><td>N&#176; de contrat</td><td><code>r'[Cc]ontrat\s*(\d{5,7})'</code></td><td>2</td></tr>
        <tr><td>N&#176; client</td><td><code>r'[Cc]lient\s*(\d{5,7})'</code></td><td>3</td></tr>
        <tr><td>Facture SAGE</td><td><code>r'(72-[A-Z]{3}\d{4}-\d{4})'</code></td><td>&#8212; (SAGE)</td></tr>
        <tr><td>Nom &#233;metteur</td><td><code>r'VIREMENT (?:INSTANTANE )?DE\s+(.{5,35}?)(?:\s+\d|\s+VIR|\s+REF)'</code></td><td>3</td></tr>
      </table>
    </div>
  </div>

  <!-- ── S6: Algorithme ── -->
  <div class="section" id="s6">
    <div class="section-title"><span class="num">6</span> Algorithme de rapprochement</div>
    <div class="card">
      <pre class="algo"><span style="color:#64b5f6">// PR&#201;PARATION</span>
1. Charger impay&#233;s &#8594; index_par_ref[col_O] + index_par_contrat[col_C.zfill(7)]
2. Charger encaissements SEM + SEMM &#8594; filtrer vides, &#233;clater sous-lignes
3. Exclure: TOTAL, montant n&#233;gatif

<span style="color:#64b5f6">// POUR CHAQUE LIGNE D'ENCAISSEMENT</span>
<span style="color:#81c784">NIVEAU 1 &#8212; Match par R&#233;f&#233;rence</span>
  a) Col D = pattern 10/40/33 + 12 chiffres (14 total) ?
     &#8594; lookup exact dans index_par_ref
     &#8594; si trouv&#233;: <span style="color:#81c784">MATCH_REF</span> + v&#233;rifier montant C &#8776; Solde T
  b) Col D = EFICASH ? &#8594; extraire ref du libell&#233; via REF: 00(40xxx)
  c) Col D = GC/vide ? &#8594; extraire ref(s) du libell&#233; B (regex &#233;largie)
  d) Ref fait 13 chiffres ? &#8594; match par PR&#201;FIXE dans index

<span style="color:#81c784">NIVEAU 2 &#8212; Match par Contrat</span>
  a) Col D = 5-7 chiffres ? &#8594; padder &#224; 7 avec zfill &#8594; lookup index_par_contrat
  b) Extraire contrat du libell&#233; B &#8594; m&#234;me lookup
  c) Si multi-match &#8594; d&#233;partager par montant C vs Solde T

<span style="color:#81c784">NIVEAU 3 &#8212; Match par Nom + Montant</span>
  a) Extraire nom du libell&#233; B (apr&#232;s &#171; VIREMENT DE &#187;)
  b) Fuzzy match sur col J (threshold &gt; 80%)
  c) Confirmer par montant C &#8776; Solde T (tol&#233;rance &#177;0.5%)
  &#8594; <span style="color:#ffa726">MATCH_PROBABLE</span> (flag pour validation)

<span style="color:#ef5350">NIVEAU 4 &#8212; Non rapproch&#233;</span>
  &#8594; Cat&#233;goriser: INTRUM | CROSS-SOCIETE | NOM_SEUL | INCONNU
  &#8594; Marquer pour traitement manuel

<span style="color:#64b5f6">// SORTIE</span>
Fichier d'import Waterp + Rapport de rapprochement avec statut par ligne</pre>
    </div>
  </div>

  <!-- ── S7: Résultats ── -->
  <div class="section" id="s7">
    <div class="section-title"><span class="num">7</span> R&#233;sultats du test de rapprochement</div>
    <div class="grid2">
      <div class="card">
        <h3><span class="tag tag-sem">SEM</span> &#8212; 55 lignes (hors TOTAL)</h3>
        <table class="tech">
          <tr><td>Match Ref 10xxx</td><td><strong>26</strong></td><td><span class="tag tag-match">47%</span></td></tr>
          <tr><td>Match Contrat</td><td><strong>6</strong></td><td><span class="tag tag-match">11%</span></td></tr>
          <tr><td>SAGE (hors p&#233;rim&#232;tre)</td><td><strong>9</strong></td><td><span class="tag tag-info">16%</span></td></tr>
          <tr><td>INTRUM (manuel)</td><td><strong>1</strong></td><td><span class="tag tag-warn">2%</span></td></tr>
          <tr><td>Non rapproch&#233;</td><td><strong>13</strong></td><td><span class="tag tag-critical">24%</span></td></tr>
        </table>
        <div class="progress-bar"><div class="fill" style="width:58%;background:var(--green)">58% auto</div></div>
      </div>
      <div class="card">
        <h3><span class="tag tag-semm">SEMM</span> &#8212; 194 lignes (hors TOTAL)</h3>
        <table class="tech">
          <tr><td>Match Ref 40xxx (principal)</td><td><strong>86</strong></td><td><span class="tag tag-match">44%</span></td></tr>
          <tr><td>Match Ref 40xxx (sous-lignes)</td><td><strong>19</strong></td><td><span class="tag tag-match">10%</span></td></tr>
          <tr><td>Match Contrat</td><td><strong>27</strong></td><td><span class="tag tag-match">14%</span></td></tr>
          <tr><td>EFICASH</td><td><strong>4</strong></td><td><span class="tag tag-match">2%</span></td></tr>
          <tr><td>INTRUM (manuel)</td><td><strong>2</strong></td><td><span class="tag tag-warn">1%</span></td></tr>
          <tr><td>Non rapproch&#233;</td><td><strong>56</strong></td><td><span class="tag tag-critical">29%</span></td></tr>
        </table>
        <div class="progress-bar"><div class="fill" style="width:70%;background:var(--green)">70% auto</div></div>
      </div>
    </div>
    <div class="card">
      <h3>Potentiel d&#8217;am&#233;lioration sur les non-rapproch&#233;s</h3>
      <table class="tech">
        <tr><th>Cat&#233;gorie</th><th>Volume</th><th>Am&#233;lioration</th></tr>
        <tr><td>Contrat avec z&#233;ros manquants</td><td>~3</td><td><span class="tag tag-match">Auto &#8594; zfill(7)</span></td></tr>
        <tr><td>Ref tronqu&#233;e 13 chiffres</td><td>~8</td><td><span class="tag tag-match">Auto &#8594; match pr&#233;fixe</span></td></tr>
        <tr><td>Ref cross-soci&#233;t&#233;</td><td>~5</td><td><span class="tag tag-match">Auto &#8594; recherche &#233;largie</span></td></tr>
        <tr><td>SGC/GC avec ref coll&#233;e</td><td>~4</td><td><span class="tag tag-match">Auto &#8594; regex &#233;largie</span></td></tr>
        <tr><td>Contrat dans libell&#233;</td><td>~8</td><td><span class="tag tag-match">Auto &#8594; regex contrat</span></td></tr>
        <tr><td>Cross-soci&#233;t&#233; multi</td><td>~5</td><td><span class="tag tag-warn">Manuel &#8594; ventilation</span></td></tr>
        <tr><td>INTRUM</td><td>3</td><td><span class="tag tag-warn">Manuel</span></td></tr>
        <tr><td>Nom seul</td><td>~25</td><td><span class="tag tag-warn">Fuzzy &#8594; validation</span></td></tr>
        <tr><td>AJAssocies sans ventilation</td><td>~5</td><td><span class="tag tag-critical">Manuel</span></td></tr>
      </table>
      <div class="highlight">
        <strong>Estimation avec am&#233;liorations :</strong> Le taux de match automatique passerait de ~65% &#224; <strong>~82%</strong> en appliquant le padding, le match pr&#233;fixe, la recherche cross-soci&#233;t&#233; et l&#8217;extraction &#233;largie du libell&#233;. Les ~18% restants n&#233;cessitent du fuzzy matching ou un traitement manuel.
      </div>
    </div>
  </div>

  <!-- ── S8: Format sortie ── -->
  <div class="section" id="s8">
    <div class="section-title"><span class="num">8</span> Format de sortie &#8212; Fichier d&#8217;import Waterp</div>
    <div class="card">
      <h3>Colonnes requises (d&#233;duites de la saisie manuelle)</h3>
      <table class="tech">
        <tr><th>Colonne</th><th>Source</th><th>Exemple</th></tr>
        <tr><td>Code soci&#233;t&#233;</td><td>Pr&#233;fixe 2 chiffres de la ref</td><td><code>40</code></td></tr>
        <tr><td>Num&#233;ro de contrat</td><td>Col C impay&#233;s (via match ref)</td><td><code>1089100</code></td></tr>
        <tr><td>Lettrage</td><td>R&#233;f&#233;rence facture = col O impay&#233;s</td><td><code>40251200016320</code></td></tr>
        <tr><td>Type d&#8217;&#233;criture</td><td>Fixe</td><td><code>REGLEMENT 09</code></td></tr>
        <tr><td>Mode r&#232;glement</td><td>Fixe pour CCP</td><td><code>CCP VIREMENTS DIVERS</code></td></tr>
        <tr><td>Montant</td><td>Col C encaissement (ou col E si ventil&#233;)</td><td><code>57761.88</code></td></tr>
        <tr><td>Date</td><td>J+1 par rapport &#224; la date encaissement</td><td><code>17/12/2025</code></td></tr>
        <tr><td>Mois de comptabilisation</td><td>Mois de la date</td><td><code>12</code></td></tr>
      </table>
    </div>
  </div>

  <!-- ── S9: Recommandations ── -->
  <div class="section" id="s9">
    <div class="section-title"><span class="num">9</span> Recommandations techniques</div>
    <div class="card">
      <ol style="font-size:13px;color:var(--text-muted);padding-left:22px;line-height:2">
        <li><strong>Formules REGEXEXTRACT :</strong> Proviennent de Google Sheets. En Python : lire avec <code>data_only=True</code> pour les valeurs cached, ou r&#233;-appliquer la regex sur le libell&#233;.</li>
        <li><strong>Index performant :</strong> Charger les 112K lignes d&#8217;impay&#233;s en dictionnaires Python (ref&#8594;infos, contrat&#8594;infos) pour des lookups O(1).</li>
        <li><strong>Types string obligatoires :</strong> Lire col C (contrat), col E (client), col O (ref) en <code>dtype=str</code> pour conserver les z&#233;ros en t&#234;te.</li>
        <li><strong>Tol&#233;rance montant :</strong> Accepter un delta &#8804; 0,02 &#8364; sur les montants (arrondis centimes).</li>
        <li><strong>Multi-match ref :</strong> Si une ref a plusieurs lignes dans les impay&#233;s, prendre celle dont le Type R = <code>FR</code> (facture relev&#233;) et le Solde TTC &gt; 0.</li>
        <li><strong>Fichier d&#8217;import :</strong> La cible finale est de g&#233;n&#233;rer le fichier d&#8217;import Waterp pour supprimer la saisie manuelle des ~250 lignes quotidiennes.</li>
      </ol>
    </div>
  </div>

  <!-- ── S10: Schémas ── -->
  <div class="section" id="s10">
    <div class="section-title"><span class="num">10</span> Sch&#233;mas &#8212; L&#8217;IA au service du rapprochement</div>
    <div class="doc-card">
      <img src="/docs/l'IA au service de la comptabilit%C3%A9.png" alt="L'IA au service de la comptabilit&#233;">
      <div class="doc-card-body">
        <div class="doc-card-title">L&#8217;IA au service de la comptabilit&#233;</div>
        <div class="doc-card-desc">Vue d&#8217;ensemble de l&#8217;approche IA pour l&#8217;automatisation des processus comptables</div>
      </div>
    </div>
    <div class="doc-card">
      <img src="/docs/l'IA Hybride au service du rapprochement bancaire.png" alt="L'IA Hybride au service du rapprochement bancaire">
      <div class="doc-card-body">
        <div class="doc-card-title">L&#8217;IA Hybride au service du rapprochement bancaire</div>
        <div class="doc-card-desc">Architecture hybride combinant r&#232;gles m&#233;tier et intelligence artificielle</div>
      </div>
    </div>
  </div>

  <!-- ── S11: Présentation PDF ── -->
  <div class="section" id="s11">
    <div class="section-title"><span class="num">11</span> Pr&#233;sentation compl&#232;te</div>
    <div class="card">
      <p>Le document PDF ci-dessous pr&#233;sente en d&#233;tail le projet de rapprochement bancaire augment&#233;, incluant l&#8217;architecture g&#233;n&#233;rale, les r&#233;sultats attendus et la feuille de route.</p>
      <div style="margin-top:14px">
        <a class="pdf-link" href="/docs/Rapprochement Bancaire Augment%C3%A9.pdf" target="_blank">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          T&#233;l&#233;charger &#171; Rapprochement Bancaire Augment&#233; &#187; (PDF)
        </a>
      </div>
    </div>
  </div>

</div>

<div class="footer">
  <span>Veolia | Software Solutions &#8212; Copilote d'Encaissement v3.9</span>
  <span>&#169; Somei S.A. &#8212; Groupe Eaux de Marseille</span>
</div>

</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))

        elif self.path == '/progress':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(progress_state).encode())

        elif self.path.startswith('/download/'):
            ftype = self.path.split('/')[-1]
            fpath = generated_files.get(ftype)
            if fpath and os.path.exists(fpath):
                self.send_response(200)
                fname = os.path.basename(fpath)
                ct = 'text/csv; charset=utf-8' if ftype == 'csv' else \
                     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                self.send_header('Content-Type', ct)
                self.send_header('Content-Disposition', f'attachment; filename="{fname}"')
                self.end_headers()
                with open(fpath, 'rb') as f: self.wfile.write(f.read())
            else:
                self.send_response(404); self.end_headers()

        elif self.path == '/documentation':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(DOC_PAGE.encode('utf-8'))

        elif self.path.startswith('/static/'):
            from urllib.parse import unquote
            fname = unquote(self.path[8:])  # strip '/static/'
            safe = os.path.basename(fname)
            fpath = os.path.normpath(os.path.join(STATIC_DIR, safe))
            if not fpath.startswith(os.path.normpath(STATIC_DIR)):
                self.send_response(403); self.end_headers(); return
            if os.path.isfile(fpath):
                self.send_response(200)
                ext = os.path.splitext(fpath)[1].lower()
                ct_map = {'.css': 'text/css; charset=utf-8', '.js': 'application/javascript',
                          '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml',
                          '.ico': 'image/x-icon'}
                self.send_header('Content-Type', ct_map.get(ext, 'application/octet-stream'))
                self.end_headers()
                with open(fpath, 'rb') as f: self.wfile.write(f.read())
            else:
                self.send_response(404); self.end_headers()

        elif self.path.startswith('/docs/'):
            from urllib.parse import unquote
            fname = unquote(self.path[6:])  # strip '/docs/'
            # Sécurité : pas de path traversal
            safe = os.path.basename(fname)
            fpath = os.path.normpath(os.path.join(DOCS_DIR, safe))
            if not fpath.startswith(os.path.normpath(DOCS_DIR)):
                self.send_response(403); self.end_headers(); return
            if os.path.isfile(fpath):
                self.send_response(200)
                ext = os.path.splitext(fpath)[1].lower()
                ct_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                          '.gif': 'image/gif', '.svg': 'image/svg+xml',
                          '.pdf': 'application/pdf', '.ico': 'image/x-icon'}
                self.send_header('Content-Type', ct_map.get(ext, 'application/octet-stream'))
                if ext == '.pdf':
                    self.send_header('Content-Disposition', f'inline; filename="{safe}"')
                self.end_headers()
                with open(fpath, 'rb') as f: self.wfile.write(f.read())
            else:
                self.send_response(404); self.end_headers()

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == '/run':
            ct = self.headers.get('Content-Type', '')
            boundary = ct.split('boundary=')[-1].encode()
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            files_data = {}
            for part in body.split(b'--' + boundary):
                if b'filename="' not in part: continue
                hend = part.find(b'\r\n\r\n')
                header = part[:hend].decode('utf-8', errors='replace')
                data = part[hend+4:]
                if data.endswith(b'\r\n'): data = data[:-2]
                nm = re.search(r'name="(\w+)"', header)
                fn = re.search(r'filename="([^"]+)"', header)
                if nm and fn:
                    fpath = os.path.join(WORK_DIR, fn.group(1))
                    with open(fpath, 'wb') as f: f.write(data)
                    files_data[nm.group(1)] = fpath
            try:
                result = run_rapprochement(files_data['imp'], files_data['sem'], files_data['semm'])
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
            except Exception as e:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        elif self.path == '/shutdown':
            # 1. Répondre au navigateur AVANT d'arrêter
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

            # 2. Déclencher l'arrêt dans un thread séparé
            #    (on ne peut pas appeler server.shutdown() depuis un handler)
            def _stop():
                time.sleep(0.3)   # laisse le temps à la réponse d'être envoyée
                # Fermer la fenêtre navigateur (arbre de processus complet)
                if _browser_proc and _browser_proc.pid:
                    try:
                        import subprocess as _sp
                        _sp.Popen(
                            ['taskkill', '/F', '/T', '/PID', str(_browser_proc.pid)],
                            creationflags=0x08000000  # CREATE_NO_WINDOW
                        )
                    except Exception:
                        try:
                            _browser_proc.terminate()
                        except Exception:
                            pass
                _shutdown_event.set()           # réveille le thread principal
                if _server_ref:
                    _server_ref.shutdown()      # débloque serve_forever()

            threading.Thread(target=_stop, daemon=True).start()

        else:
            self.send_response(404); self.end_headers()


def run_rapprochement(path_imp, path_sem, path_semm):
    global progress_state, generated_files

    progress_state = {'pct': 5, 'msg': 'Détection des dates...'}
    date_enc = detecter_date_encaissement(path_sem) or detecter_date_encaissement(path_semm)
    if not date_enc:
        raise Exception("Impossible de détecter la date d'encaissement")
    date_saisie = date_enc + timedelta(days=1)
    date_tag = date_enc.strftime('%d%m%y')

    progress_state = {'pct': 10, 'msg': 'Chargement des impayés (peut prendre 30s)...'}
    def prog_cb(n):
        pct = min(10 + int(n / 1200), 60)
        progress_state['pct'] = pct
        progress_state['msg'] = f'Chargement des impayés... {n:,} lignes'

    idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom, n_imp = charger_impayes(path_imp, prog_cb)

    progress_state = {'pct': 65, 'msg': 'Rapprochement SEM...'}
    res_sem = traiter_fichier(path_sem, 'SEM', date_enc, idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom)

    progress_state = {'pct': 75, 'msg': 'Rapprochement SEMM...'}
    res_semm = traiter_fichier(path_semm, 'SEMM', date_enc, idx_ref, idx_ref_prefix, idx_contrat, idx_montant, idx_nom)

    resultats = res_sem + res_semm

    progress_state = {'pct': 85, 'msg': "Génération du fichier d'import..."}
    csv_path = os.path.join(WORK_DIR, f'import_waterp_{date_tag}.csv')
    n_import = generer_csv(resultats, date_saisie, date_enc, csv_path)
    generated_files['csv'] = csv_path

    progress_state = {'pct': 92, 'msg': 'Génération du rapport Excel...'}
    xlsx_path = os.path.join(WORK_DIR, f'rapport_{date_tag}.xlsx')
    generer_rapport_xlsx(resultats, date_enc, date_saisie, n_import, xlsx_path)
    generated_files['xlsx'] = xlsx_path

    progress_state = {'pct': 100, 'msg': 'Terminé !'}

    total = sum(1 for r in resultats if 'EXCLU' not in r['status'] and 'PERIMETRE' not in r['status'])
    n_ok   = sum(1 for r in resultats if r['status'] in STATUTS_IMPORTABLES)
    n_warn = sum(1 for r in resultats if 'MANUEL' in r['status'] or r['status'] in STATUTS_SUGGESTIONS)
    n_ko   = sum(1 for r in resultats if r['status'] in {'NON_RAPPROCHE', 'SUB_NO_MATCH'})
    mt_ok  = sum(r['montant_enc'] for r in resultats if r['status'] in STATUTS_IMPORTABLES)

    labels = {
        'MATCH_REF_EXACT':'✓ Ref','MATCH_REF_PREFIX':'✓ Préfixe',
        'MATCH_EFICASH':'✓ EFICASH','MATCH_CONTRAT_UNIQUE':'✓ Contrat',
        'MATCH_CONTRAT_MONTANT':'✓ Contrat','MATCH_CONTRAT_LIB':'✓ Contrat',
        'MATCH_GC_REF':'✓ GC','EXCLU_TOTAL':'— Exclu','SAGE_HORS_PERIMETRE':'— SAGE',
        'RECOUVREMENT_MANUEL':'⚠ Recouvr.','CROSS_SOCIETE_MANUEL':'⚠ Cross-soc.',
        'GC_MANUEL':'⚠ GC','NON_RAPPROCHE':'✗ Non rapp.','SUB_NO_MATCH':'✗ Sub KO',
        'SUGGEST_REF_EXTENDED':'◇ Ref étendue','SUGGEST_CONTRAT_LIBRE':'◇ Contrat libre',
        'SUGGEST_MONTANT_UNIQUE':'◇ Montant','SUGGEST_NUM_CONTRAT':'◇ Num→Contrat',
        'SUGGEST_NOM_CLIENT':'◇ Nom client',
    }

    details = [{
        'src': r['source'], 'dt': r['date'],
        's': r['status'], 'sl': labels.get(r['status'], r['status']),
        'lib': r['libelle'][:120], 'mt': r['montant_enc'],
        'ann': r.get('annotation', ''),
        'ref': r['ref_imp'] or r['contrat_imp'] or r['detail'][:20],
        'ctr': r.get('contrat_imp', ''),
        'nom': r['nom_imp'][:30], 'sol': r['solde_imp'],
        'delta': round(r['montant_enc'] - r['solde_imp'], 2) if r['ref_imp'] else None,
        'imp': 'OUI' if r['status'] in STATUTS_IMPORTABLES else '',
        'score': r.get('justification', {}).get('score', 0),
        'j': r.get('justification', {})
    } for r in resultats]

    return {
        'total': total, 'n_ok': n_ok, 'n_warn': n_warn, 'n_ko': n_ko,
        'pct_ok': round(n_ok / total * 100) if total else 0,
        'mt_ok': round(mt_ok, 2), 'n_import': n_import,
        'date_enc': date_enc.strftime('%d/%m/%Y'),
        'details': details
    }


# ═══════════════════════════════════════════════════════════════════════
# LANCEMENT
# ═══════════════════════════════════════════════════════════════════════

def main():
    global _server_ref
    import subprocess

    url = f'http://localhost:{PORT}'
    print()
    print("  ================================================")
    print("  Rapprochement Encaissements — SOMEI")
    print("  Version 5.0")
    print(f"  -> {url}")
    print("  ================================================")
    print()
    print("  L'application s'ouvre dans le navigateur...")
    print("  Cliquez sur [Quitter] dans l'interface pour fermer.")
    print()

    def _open_app_window(target_url):
        """Open in app-mode (Edge/Chrome) so window.close() works, fallback to webbrowser."""
        import shutil as _sh, subprocess as _sp
        for browser in [
            _sh.which('msedge') or r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            _sh.which('chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        ]:
            if os.path.isfile(browser):
                try:
                    global _browser_proc
                    _browser_proc = _sp.Popen([browser, f'--app={target_url}', '--start-maximized'])
                    return
                except Exception:
                    pass
        webbrowser.open(target_url)

    server = HTTPServer(('localhost', PORT), Handler)
    _server_ref = server
    threading.Timer(1.0, lambda: _open_app_window(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Arrêt (Ctrl+C).")

    # ── Ici on arrive soit après shutdown() soit après Ctrl+C ──
    if _shutdown_event.is_set():
        # Arrêt demandé depuis l'interface web
        print()
        print("  ╔════════════════════════════════════════════╗")
        print("  ║  Application arrêtée. Fermeture en cours.  ║")
        print("  ╚════════════════════════════════════════════╝")
        print()
        # Fermer la fenêtre CMD sur Windows
        if sys.platform == 'win32':
            try:
                # Ferme la fenêtre console courante
                subprocess.Popen(
                    ['cmd', '/C', f'taskkill /F /PID {os.getpid()}'],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass
        sys.exit(0)

if __name__ == '__main__':
    main()