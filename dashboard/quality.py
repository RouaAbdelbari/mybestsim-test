"""Contrôle qualité des CSV fournisseurs, exécuté à chaque import.

Deux niveaux :
  - erreur   : la donnée fausserait les statistiques -> la publication est bloquée
  - alerte   : la donnée est utilisable mais mérite un coup d'œil -> signalée, publiée

Aucune ligne n'est modifiée ni supprimée : le contrôle décide seulement si l'on publie.
"""
import collections
import csv
import os
import re

REQUIRED = ["sku", "provider", "country_code", "country_name", "data_gb", "data_display",
            "validity_days", "price", "currency", "network", "top_up"]
NUM = re.compile(r"^\d+(\.\d+)?$")
MAX_EXAMPLES = 5

# (clé, libellé affiché, niveau)
CHECKS = [
    ("columns", "Colonnes obligatoires présentes", "error"),
    ("empty_file", "Fichiers non vides", "warning"),
    ("sku", "SKU renseigné et unique", "error"),
    ("provider", "Fournisseur renseigné, un seul par fichier", "error"),
    ("price", "Prix numérique et positif", "error"),
    ("validity", "Durée de validité entière et positive", "error"),
    ("data_gb", "Volume de data numérique (vide = illimité)", "error"),
    ("currency", "Prix en EUR", "warning"),
    ("network", "Réseau 4G ou 5G", "warning"),
    ("top_up", "Recharge « oui » ou « non »", "warning"),
    ("data_display", "Volume cohérent avec son libellé", "warning"),
    ("country", "Un seul nom par code pays", "warning"),
    ("spaces", "Pas d'espaces parasites", "warning"),
    ("outlier", "Pas de prix aberrant (> 1 000 €)", "warning"),
]


def check_files(paths):
    """Lit les CSV et retourne (lignes, rapport)."""
    issues = {k: [] for k, _, _ in CHECKS}
    rows = []

    def flag(key, file, line, msg):
        issues[key].append({"file": file, "line": line, "msg": msg})

    for path in paths:
        name = os.path.basename(path)
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rd = csv.DictReader(fh)
            missing = [c for c in REQUIRED if c not in (rd.fieldnames or [])]
            if missing:
                flag("columns", name, 1, "colonnes manquantes : " + ", ".join(missing))
                continue
            file_rows = list(rd)
        if not file_rows:
            flag("empty_file", name, 1, "aucune ligne de données")
        provs = {r["provider"].strip() for r in file_rows}
        if len(provs) > 1:
            flag("provider", name, 2, "plusieurs fournisseurs : " + ", ".join(sorted(provs)))
        for i, r in enumerate(file_rows, start=2):  # ligne 1 = en-tête
            if any(isinstance(v, str) and v != v.strip() for v in r.values()):
                flag("spaces", name, i, "espace en début ou fin de cellule")
            r = {k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
            r["_file"], r["_line"] = name, i
            if not r["provider"]:
                flag("provider", name, i, "fournisseur vide")
            if not NUM.match(r["price"]) or float(r["price"]) <= 0:
                flag("price", name, i, f"prix invalide « {r['price']} »")
            if not r["validity_days"].isdigit() or int(r["validity_days"]) <= 0:
                flag("validity", name, i, f"durée invalide « {r['validity_days']} »")
            if r["data_gb"] and not NUM.match(r["data_gb"]):
                flag("data_gb", name, i, f"volume invalide « {r['data_gb']} »")
            if r["currency"] != "EUR":
                flag("currency", name, i, f"devise « {r['currency']} »")
            if r["network"].upper() not in ("4G", "5G"):
                flag("network", name, i, f"réseau « {r['network']} »")
            if r["top_up"].lower() not in ("oui", "non"):
                flag("top_up", name, i, f"recharge « {r['top_up']} »")
            if NUM.match(r["data_gb"] or "x"):
                expected = f"{float(r['data_gb']):g} Go"
                if r["data_display"] != expected:
                    flag("data_display", name, i, f"{r['data_gb']} Go affiché « {r['data_display']} »")
            elif not r["data_gb"] and r["data_display"] != "Illimité":
                flag("data_display", name, i, f"data vide mais affiché « {r['data_display']} »")
            if NUM.match(r["price"]) and float(r["price"]) > 1000:
                flag("outlier", name, i, f"prix de {r['price']} €")
            rows.append(r)

    seen = {}
    for r in rows:
        if not r["sku"]:
            flag("sku", r["_file"], r["_line"], "SKU vide")
        elif r["sku"] in seen:
            flag("sku", r["_file"], r["_line"], f"SKU « {r['sku']} » déjà présent ({seen[r['sku']]})")
        else:
            seen[r["sku"]] = f"{r['_file']} ligne {r['_line']}"
    names = collections.defaultdict(set)
    for r in rows:
        names[r["country_code"]].add(r["country_name"])
    for code, ns in sorted(names.items()):
        if len(ns) > 1:
            flag("country", "—", 0, f"{code} : " + " / ".join(sorted(ns)))

    report = {"files": len(paths), "rows": len(rows), "checks": []}
    for key, label, level in CHECKS:
        found = issues[key]
        report["checks"].append({"key": key, "label": label, "level": level,
                                 "count": len(found), "examples": found[:MAX_EXAMPLES]})
    report["errors"] = sum(c["count"] for c in report["checks"] if c["level"] == "error")
    report["warnings"] = sum(c["count"] for c in report["checks"] if c["level"] == "warning")
    return rows, report


def markdown(report):
    """Résumé lisible (affiché dans l'onglet Actions de GitHub)."""
    status = "Publication bloquée" if report["errors"] else "Données publiées"
    out = [f"## Contrôle qualité des CSV · {status}", "",
           f"{report['files']} fichiers · {report['rows']} lignes · "
           f"{report['errors']} erreur(s) · {report['warnings']} alerte(s)", "",
           "| Contrôle | Niveau | Anomalies |", "| --- | --- | --- |"]
    for c in report["checks"]:
        out.append(f"| {c['label']} | {'bloquant' if c['level'] == 'error' else 'alerte'} | {c['count']} |")
    for c in report["checks"]:
        for ex in c["examples"]:
            out.append(f"- **{c['label']}** · {ex['file']} ligne {ex['line']} : {ex['msg']}")
    return "\n".join(out) + "\n"
