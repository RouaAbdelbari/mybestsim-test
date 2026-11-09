"""Tests de la chaîne d'import : python -m unittest discover -s tests -v"""
import csv
import glob
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "dashboard"))
import build  # noqa: E402

DATA = os.path.join(ROOT, "data")


def copy_data(tmp, edit=None):
    """Copie les CSV de test ; `edit(nom, lignes)` peut modifier un fichier."""
    src = os.path.join(tmp, "data")
    os.makedirs(src)
    for f in sorted(glob.glob(os.path.join(DATA, "*.csv"))):
        name = os.path.basename(f)
        with open(f, encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        if edit:
            rows = edit(name, rows)
        with open(os.path.join(src, name), "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh).writerows(rows)
    return src


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "site")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_statistiques_de_reference(self):
        stats, report = build.build(DATA, self.out, date="2026-10-14")
        self.assertEqual(report["errors"], 0)
        self.assertEqual(stats["cards"], 5056)
        self.assertEqual(stats["over100"], 56)
        self.assertEqual((stats["min"], stats["max"]), (5.36, 154.63))
        self.assertEqual(stats["avg_price"], 29.30)
        self.assertEqual(stats["avg_data"], 14.5)          # offres illimitées exclues
        self.assertEqual(stats["providers"], 18)
        self.assertTrue(os.path.exists(os.path.join(self.out, "index.html")))

    def test_prix_invalide_bloque_la_publication(self):
        def edit(name, rows):
            if name == "airalo.csv":
                rows[1][rows[0].index("price")] = "abc"
            return rows
        with self.assertRaises(SystemExit):
            build.build(copy_data(self.tmp, edit), self.out)
        self.assertFalse(os.path.exists(os.path.join(self.out, "index.html")))
        report = json.load(open(os.path.join(self.out, "quality.json"), encoding="utf-8"))
        self.assertEqual(report["errors"], 1)

    def test_sku_en_double_bloque(self):
        def edit(name, rows):
            if name == "saily.csv":
                rows.append(rows[1])
            return rows
        with self.assertRaises(SystemExit):
            build.build(copy_data(self.tmp, edit), self.out)

    def test_colonne_manquante_bloque(self):
        def edit(name, rows):
            if name == "yesim.csv":
                i = rows[0].index("price")
                rows = [r[:i] + r[i + 1:] for r in rows]
            return rows
        with self.assertRaises(SystemExit):
            build.build(copy_data(self.tmp, edit), self.out)

    def test_alerte_sans_blocage(self):
        def edit(name, rows):
            if name == "nomad.csv":
                rows[1][rows[0].index("currency")] = "USD"
            return rows
        stats, report = build.build(copy_data(self.tmp, edit), self.out)
        self.assertEqual(report["errors"], 0)
        self.assertEqual(report["warnings"], 1)
        self.assertEqual(stats["cards"], 5056)

    def test_nouveau_fichier_pris_en_compte(self):
        src = copy_data(self.tmp)
        with open(os.path.join(src, "nouveau.csv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["sku", "provider", "product_name", "country_code", "country_name", "data_gb",
                        "data_display", "validity_days", "price", "currency", "network", "top_up"])
            w.writerow(["nouveau-1", "Nouveau", "eSIM France 5 Go 7 jours", "FR", "France", "5", "5 Go",
                        "7", "120", "EUR", "5G", "oui"])
        stats, report = build.build(src, self.out)
        self.assertEqual(stats["cards"], 5057)
        self.assertEqual(stats["providers"], 19)
        self.assertEqual(stats["over100"], 57)


if __name__ == "__main__":
    unittest.main()
