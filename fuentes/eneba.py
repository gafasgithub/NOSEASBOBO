"""Eneba (tienda de claves): precio más barato de la clave del juego, si la venden.

Eneba no tiene API pública. Se usan sus páginas públicas, despacio y respetando su robots.txt:
- Índice: los sitemaps de productos (~110.000 URL) dicen qué claves existen. Se rehace cada semana y
  se guarda en .cache/ (pesa unos 350 MB de descarga, no se sube al repo).
- Precio: la ficha de cada producto lleva incrustadas sus ofertas (Apollo state); se toma la más
  barata con existencias. Sin la comisión de pago que Eneba suma al final de la compra.
"""
import datetime as dt
import json
import re
import unicodedata

from .comun import descargar

WEB = "https://www.eneba.com/es/"
# Regiones que se pueden activar en España, de preferida a menos preferida.
REGIONES = ["global", "europe", "emea", "eu", "spain"]
PATRONES = {
    "steam": re.compile(r"steam-(.+?)-(?:standard-edition-)?(?:pc-steam-key|steam-key-pc|steam-pc-key)-(.+)$"),
    "switch": re.compile(r"nintendo-(.+?)-(?:standard-edition-)?nintendo-switch(?:-2)?-eshop-key-(.+)$"),
}
RE_LOC = re.compile(r"<loc>https://www\.eneba\.com/es/([^<]+)</loc>")


def slug(titulo):
    """'Baldur's Gate 3' -> 'baldurs-gate-3', como escribe Eneba sus URL."""
    t = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode().lower()
    t = t.replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def crear_indice():
    """{"steam:nombre": [slug de producto, ...]} con las claves activables en España."""
    portada = descargar(WEB + "sitemap.xml")
    indice = {}
    for fichero in sorted(set(re.findall(r"sitemap/products\d+\.xml", portada))):
        for producto in RE_LOC.findall(descargar(WEB + fichero)):
            for plataforma, patron in PATRONES.items():
                m = patron.match(producto)
                if m and m.group(2) in REGIONES:
                    indice.setdefault(f"{plataforma}:{m.group(1)}", []).append((REGIONES.index(m.group(2)), producto))
    return {nombre: [p for _, p in sorted(productos)] for nombre, productos in indice.items()}


def cargar_indice(ruta, dias=7):
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if (dt.date.today() - dt.date.fromisoformat(datos["fecha"])).days < dias:
            return datos["indice"]
    except (FileNotFoundError, ValueError, KeyError):
        pass
    print("Eneba: rehaciendo el índice de productos (sitemaps)")
    indice = crear_indice()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps({"fecha": dt.date.today().isoformat(), "indice": indice}), encoding="utf-8")
    return indice


def producto(juego, indice):
    """Slug del producto de Eneba para el juego, o None si no venden su clave."""
    productos = indice.get(f"{juego['plataforma']}:{slug(juego['titulo'])}")
    return productos[0] if productos else None


def precio(producto):
    """Precio más bajo (euros) entre las ofertas con existencias, o None si no hay ninguna."""
    texto = descargar(WEB + producto)
    i = texto.find("__APOLLO_STATE__")
    if i < 0:
        return None
    estado, _ = json.JSONDecoder().raw_decode(texto[texto.index("{", i):])
    precios = []
    for clave, oferta in estado.items():
        if not clave.startswith("Auction:") or not oferta.get("isInStock") or oferta.get("isPreOrder"):
            continue
        for campo in ('promotionalPrice({"currency":"EUR"})', 'price({"currency":"EUR"})'):
            dinero = oferta.get(campo)
            if dinero and dinero.get("currency") == "EUR":
                precios.append(dinero["amount"] / 100)
                break
    return min(precios) if precios else None
