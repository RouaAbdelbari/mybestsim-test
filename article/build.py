"""Génère l'article « Internet en croisière : quelle eSIM choisir ? ».

Usage : python article/build.py [dossier_sortie]
  - insère la FAQ (HTML visible + données structurées FAQPage identiques)
  - intègre le logo en data URI (page autonome, sans fichier externe)
  - ajoute les espaces insécables de la typographie française
Variable optionnelle SITE_URL : URL publique du site, pour la balise canonical.
"""
import base64, html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "site")

FAQ=[
("Une eSIM fonctionne-t-elle sur un bateau de croisière ?",
 ["Oui, mais pas partout. Une eSIM de voyage classique fonctionne au port et près des côtes, sur les antennes du pays d'escale. En pleine mer, seule une eSIM croisière compatible avec votre navire, comme celles de GigSky, Saily ou Red Bull Mobile, peut se connecter au réseau mobile du bord."]),
("Une eSIM marche-t-elle en pleine mer ?",
 ["Seulement si c'est une eSIM croisière et si votre navire est couvert. Saily indique que son offre s'active au-delà d'environ 12 milles nautiques des côtes, sur 28 compagnies. GigSky annonce plus de 290 navires compatibles. Les eSIM régionales (Europe, Caraïbes) ne fonctionnent pas au large."]),
("Combien coûte le wifi sur un bateau de croisière ?",
 ["Les relevés de 2026 donnent 32,99 $ par jour et par appareil à bord chez Royal Caribbean (février 2026) et de 30,99 $ à 32,99 $ par jour chez MSC (août 2026). Réservé avant le départ, le forfait MSC revenait à environ 140 $ pour 7 jours. Costa ne publie pas ses prix en dehors de l'espace My Costa. Ces tarifs changent souvent."]),
("Faut-il mettre son téléphone en mode avion en croisière ?",
 ["En pleine mer, c'est le réglage le plus sûr : passez en mode avion, puis réactivez uniquement le wifi ou votre eSIM croisière. Désactivez aussi l'itinérance des données de votre ligne française, pour qu'elle ne se connecte pas au réseau maritime, facturé de 9,70 € à 15,84 € par Mo selon l'opérateur."]),
("Peut-on recevoir des appels et des SMS avec une eSIM croisière ?",
 ["Les eSIM croisière vérifiées sont des eSIM data : elles ne fournissent ni numéro ni SMS, mais les appels par WhatsApp, FaceTime ou Telegram fonctionnent. Les appels et SMS reçus sur votre ligne française restent facturés par votre opérateur au tarif maritime, de 1,40 € à 3,96 € la minute pour un appel reçu."]),
("Combien de data faut-il pour une croisière d'une semaine ?",
 ["Cela dépend surtout de la vidéo. Selon Netflix, une heure en haute définition peut consommer jusqu'à 3 Go. Pour la messagerie, les e-mails et les cartes, un forfait de 500 Mo à 1 Go en mer suffit souvent. Le calculateur de data MyBestSim vous aide à estimer votre besoin selon vos usages."]),
("Quand installer son eSIM avant une croisière ?",
 ["Installez-la chez vous, la veille ou quelques jours avant le départ, sur votre wifi : l'installation demande une connexion internet, que vous n'aurez pas gratuitement à bord. Une eSIM croisière ne se connecte pas tout de suite : GigSky indique un délai d'environ une heure après le départ du port."]),
("Quelle eSIM choisir pour une croisière dans les Caraïbes ?",
 ["Choisissez une eSIM Caraïbes qui couvre chacun de vos pays d'escale, ou la formule GigSky Cruise + Land, qui couvre le navire et les escales. Vérifiez les îles privées et certains ports : le forfait Caraïbes d'Holafly ne fonctionne pas à Freeport, CocoCay et Ocean Cay, par exemple."]),
]

h = []
for q, ans in FAQ:
    h.append(f'    <details>\n      <summary>{html.escape(q)}</summary>\n      <div class="a">'
             + "".join(f"<p>{html.escape(a)}</p>" for a in ans) + '</div>\n    </details>')
ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
    {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": " ".join(a)}} for q, a in FAQ]}

site = os.environ.get("SITE_URL", "").rstrip("/")
canon = (f'<link rel="canonical" href="{site}/article/">\n<meta property="og:url" content="{site}/article/">'
         if site else "")
logo = base64.b64encode(open(os.path.join(HERE, "logo.png"), "rb").read()).decode()

s = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
s = (s.replace("__FAQ_HTML__", "\n".join(h))
      .replace("__FAQ_JSONLD__", json.dumps(ld, ensure_ascii=False, indent=1))
      .replace("__CANONICAL__", canon).replace("__LOGO__", logo))

# Espaces insécables avant : ? ! ; » et après « (hors balises, scripts et styles)
parts = re.split(r"(<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>)", s)
for i, t in enumerate(parts):
    if not t.startswith("<"):
        parts[i] = re.sub(r" ([:?!;»])", "\u00a0\\1", t).replace("« ", "«\u00a0")
s = "".join(parts)

os.makedirs(os.path.join(OUT, "article"), exist_ok=True)
open(os.path.join(OUT, "article", "index.html"), "w", encoding="utf-8").write(s)
print("article :", os.path.join(OUT, "article", "index.html"))
