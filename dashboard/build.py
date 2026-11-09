"""Génère le dashboard eSIM Insights à partir des CSV fournisseurs.

Usage : python dashboard/build.py [dossier_csv] [dossier_sortie]

Étapes :
  1. lit tous les fichiers *.csv du dossier (par défaut : data/)
  2. contrôle qualité (dashboard/quality.py) : en cas d'erreur, arrêt sans publier
  3. intègre les données et les logos (dashboard/logos/<Fournisseur>.png) dans la page
  4. écrit <sortie>/index.html, <sortie>/artifact.html et <sortie>/quality.json

Aucune ligne n'est modifiée ni supprimée : chaque SKU distinct est conservé.
Aucune dépendance : Python 3.9+ suffit.
"""
import base64
import datetime
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import quality  # noqa: E402

ROOT = os.path.dirname(HERE)


def build(src, out, date=None):
    files = sorted(glob.glob(os.path.join(src, "*.csv")))
    if not files:
        raise SystemExit(f"Aucun fichier CSV dans {src}")
    rows, report = quality.check_files(files)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "quality.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(quality.markdown(report))
    if report["errors"]:
        print(quality.markdown(report))
        raise SystemExit(f"Contrôle qualité : {report['errors']} erreur(s), publication bloquée.")

    # Date affichée : DATA_DATE=AAAA-MM-JJ, sinon date du jour (UTC)
    d = date or os.environ.get("DATA_DATE") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    updated = datetime.date.fromisoformat(d).strftime("%d/%m/%Y")

    P = sorted({r["provider"] for r in rows})
    C = sorted({r["country_name"] for r in rows})
    pi, ci = {p: i for i, p in enumerate(P)}, {c: i for i, c in enumerate(C)}
    R = [[pi[r["provider"]], ci[r["country_name"]],
          int(float(r["data_gb"])) if r["data_gb"] else -1,     # -1 = Illimité (data vide)
          int(r["validity_days"]), round(float(r["price"]), 2),
          1 if r["network"].upper() == "5G" else 0,
          1 if r["top_up"].lower() == "oui" else 0] for r in rows]

    def uri(path):
        return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()

    logos = os.path.join(HERE, "logos")
    L = {p: uri(os.path.join(logos, p + ".png")) for p in P if os.path.exists(os.path.join(logos, p + ".png"))}
    B = uri(os.path.join(logos, "_mybestsim.png"))
    Q = {"e": report["errors"], "w": report["warnings"],
         "c": [[c["label"], c["level"], c["count"]] for c in report["checks"]]}
    data = json.dumps({"P": P, "C": C, "R": R, "L": L, "B": B, "U": updated, "F": len(files), "Q": Q},
                      ensure_ascii=False, separators=(",", ":"))

    page = open(os.path.join(HERE, "template.html"), encoding="utf-8").read().replace("/*__DATA__*/", data)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    # version « rapport BI » (même données), publiée sous /powerbi/
    bi = os.path.join(HERE, "powerbi.html")
    if os.path.exists(bi):
        os.makedirs(os.path.join(out, "powerbi"), exist_ok=True)
        with open(os.path.join(out, "powerbi", "index.html"), "w", encoding="utf-8") as fh:
            fh.write(open(bi, encoding="utf-8").read().replace("/*__DATA__*/", data))
    # version sans <html>/<head>/<body>, pour une publication en Artifact claude.ai
    head = re.search(r"<head>([\s\S]*?)</head>", page).group(1)
    body = re.search(r"<body>([\s\S]*)</body>", page).group(1)
    head = re.sub(r'<meta (charset|name="viewport")[^>]*>\n?', "", head)
    with open(os.path.join(out, "artifact.html"), "w", encoding="utf-8") as fh:
        fh.write(head + body)

    pr = [x[4] for x in R]
    gb = [x[2] for x in R if x[2] >= 0]
    stats = {"cards": len(R), "over100": sum(p > 100 for p in pr), "min": min(pr), "max": max(pr),
             "avg_price": round(sum(pr) / len(pr), 2), "avg_data": round(sum(gb) / len(gb), 1),
             "providers": len(P), "logos": len(L)}
    return stats, report


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "site")
    s, rep = build(src, out)
    print(f"{rep['files']} fichiers · {s['cards']} cartes · {s['over100']} à plus de 100 € · "
          f"{s['min']:.2f}–{s['max']:.2f} € · prix moyen {s['avg_price']:.2f} € · data moyenne "
          f"{s['avg_data']:.1f} Go · {rep['errors']} erreur(s), {rep['warnings']} alerte(s) · "
          f"logos {s['logos']}/{s['providers']}")
