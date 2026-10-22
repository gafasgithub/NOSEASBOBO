"""Xbox (tienda española): juegos que salieron cada mes, su precio de hoy y si están en Game Pass.

Se usa el buscador de xbox.com (emerald.xboxservices.com/xboxcomfd/browse, sin clave), ordenado por
fecha de salida. Da 25 juegos por página (unos 275 al mes) con fecha, valoraciones, precio, imágenes y
los pases que lo incluyen hoy. La página se pide con un "token de continuación" en base64 que solo
lleva la posición, así que se puede saltar a cualquier punto: se busca dónde empieza cada tramo de
meses y se leen sus páginas en paralelo (cada una tarda unos 4 s). Las ediciones (Deluxe, Premium,
packs...) son productos aparte, pero comparten xboxTitleId y valoraciones con el juego: se agrupan
y se queda el juego base. Si no tienen xboxTitleId (no están en la nube), se agrupan por editor,
número de valoraciones y nota media, que también son los mismos.
"""
import base64
import datetime as dt
import json
import re
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from .comun import descargar_json, normalizar

BUSCADOR = "https://emerald.xboxservices.com/xboxcomfd/browse?locale=es-ES"
CABECERAS = {"Content-Type": "application/json", "x-ms-api-version": "1.1", "MS-CV": "noseasbobo.0"}
TIENDA = "https://www.xbox.com/es-ES/games/store/"
POR_PAGINA = 25
HILOS = 6
# Pases de los que dice "includedWithPassesProductIds". Ultimate los incluye todos (también EA Play);
# Ubisoft+ (CFQ7TTC0QH5H) no es Game Pass.
PASES = {"CFQ7TTC0KHS0": "Ultimate", "CFQ7TTC0K6L8": "Ultimate", "CFQ7TTC0KGQ8": "PC",
         "CFQ7TTC0P85B": "Premium", "CFQ7TTC0K5DJ": "Essential", "CFQ7TTC0K5DH": "EA Play"}
ORDEN_PASES = ["Ultimate", "PC", "Premium", "Essential", "EA Play"]
# Reediciones de juegos que ya estaban en la tienda: salen con fecha nueva pero no son lanzamientos.
RE_REEDICION = re.compile(
    r"game of the year|\bgoty\b|edici[oó]n (definitiva|de lujo|deluxe|completa|oro|gold|premium|ultimate)"
    r"|(deluxe|gold|ultimate|premium|complete|definitive|anniversary|legendary|elite) edition"
    r"|\bbundle\b|\blote\b|\bpack\b|paquete|\bbonus\b|pre-?order|reserva|upgrade|mejora|season pass|pase de temporada"
    r"|collection|colecci[oó]n|trilog|antholog|antolog|\[deluxe\]|- windows$", re.I)


def _pagina(posicion, total):
    filtros = {"orderby": {"id": "orderby", "choices": [{"id": "ReleaseDate desc"}]}}
    token = {"HasMore": True, "SkipCount": posicion, "TotalCount": total, "PreviousPageProductIds": []}
    cuerpo = {"Filters": base64.b64encode(json.dumps(filtros).encode()).decode(), "ReturnFilters": False,
              "ChannelKeyToBeUsedInResponse": "X", "EncodedCT": base64.b64encode(json.dumps(token).encode()).decode()}
    datos = descargar_json(BUSCADOR, cuerpo=cuerpo, cabeceras=CABECERAS)
    return datos["channels"]["X"].get("totalItems", 0), datos.get("productSummaries", [])


def _fecha(p):
    """Día de salida en España: la tienda da la medianoche española en UTC (22:00 o 23:00 del día antes)."""
    if not p.get("releaseDate"):
        return None
    return (dt.datetime.fromisoformat(p["releaseDate"][:19]) + dt.timedelta(hours=2)).date()


def _pagina_o_nada(total, posicion):
    """La página, o vacía si sigue fallando tras los reintentos (a veces da 500 sin motivo)."""
    try:
        return _pagina(posicion, total)[1]
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        print(f"  Xbox: se salta la posición {posicion} ({error})", flush=True)
        return []


def _paginas(posiciones, total):
    with ThreadPoolExecutor(HILOS) as hilos:
        return dict(zip(posiciones, hilos.map(partial(_pagina_o_nada, total), posiciones)))


def _inicio_tramo(fin, total):
    """Primera página con algún juego de fecha <= fin. Las páginas van de más nueva a más antigua, así
    que se busca por tanteo: HILOS páginas repartidas a la vez, y luego entre las dos que lo rodean."""
    bajo, alto = 0, total // POR_PAGINA
    while alto - bajo > 1:
        paso = max(1, (alto - bajo) // (HILOS + 1))
        posiciones = list(range(bajo + paso, alto, paso))[:HILOS]
        leidas = _paginas([n * POR_PAGINA for n in posiciones], total)
        for n in posiciones:
            fechas = [f for f in map(_fecha, leidas[n * POR_PAGINA]) if f]
            if fechas and min(fechas) <= fin:
                alto = n
                break
            bajo = n
    return alto


def _tramo(inicio, fin, total):
    """Productos con salida entre inicio y fin (fechas incluidas)."""
    pagina = max(0, _inicio_tramo(fin, total) - 1)  # una de margen: el orden no es perfecto
    productos = []
    while pagina * POR_PAGINA < total:
        leidas = _paginas([(pagina + i) * POR_PAGINA for i in range(HILOS)], total)
        pagina += HILOS
        for ps in leidas.values():
            productos += [p for p in ps if _fecha(p) and inicio <= _fecha(p) <= fin]
        fechas = [f for ps in leidas.values() for f in map(_fecha, ps) if f]
        if not fechas or max(fechas) < inicio:
            break
    return productos


def _precio(p):
    """(PVP, precio de hoy) sin requisitos de suscripción, o (None, None) si no se vende."""
    opciones = [x for x in (p.get("specificPrices") or {}).get("purchaseable", [])
                if (x.get("eligibilityInfo") or {}).get("eligibility") in (None, "None") and x.get("currency") == "EUR"]
    if not opciones:
        return None, None
    x = min(opciones, key=lambda x: x.get("listPrice", 1e9))
    return x.get("msrp", x.get("listPrice")), x.get("listPrice")


def _imagenes(p):
    """De mejor a peor para una portada apaisada, reducidas (las originales son de 4K)."""
    im = p.get("images") or {}
    return [im[k]["url"] + "?w=640" for k in ("superHeroArt", "boxArt", "featurePromotionalSquareArt", "poster")
            if isinstance(im.get(k), dict) and im[k].get("url")]


def _ficha(p):
    pvp, precio = _precio(p)
    titulo = p.get("title", "").replace("™", "").replace("®", "").strip()
    pases = {PASES[x] for x in p.get("includedWithPassesProductIds") or [] if x in PASES}
    if pases:
        pases.add("Ultimate")
    return {
        "plataforma": "xbox",
        "id": f"xbox:{p['productId']}",
        "titulo": titulo,
        "fecha": _fecha(p).isoformat(),
        "imagenes": _imagenes(p),
        "url": TIENDA + (normalizar(titulo).replace(" ", "-") or "juego") + "/" + p["productId"],
        "editor": p.get("publisherName"),
        "gratis": pvp == 0,
        "resenas": {"total": p.get("ratingCount") or 0, "nota": p.get("averageRating") or None},
        "gamepass": [x for x in ORDEN_PASES if x in pases],
        "pvp": pvp,
        "precio": precio,
    }


def _clave_juego(p):
    nube = p.get("xCloudProperties") or p.get("xCloudPropertiesV2") or {}
    if nube.get("xboxTitleId"):
        return nube["xboxTitleId"]
    if (p.get("ratingCount") or 0) >= 5:
        return (p.get("publisherName"), p["ratingCount"], p.get("averageRating"))
    return p["productId"]


def _juego_base(ediciones):
    """De las ediciones de un juego, la que está en Game Pass o, si no, la más barata."""
    return min(ediciones, key=lambda p: (not p["gamepass"], p["pvp"] is None, p["pvp"] or 0, len(p["titulo"])))


def lanzamientos(meses, hoy, por_mes=40):
    """Los `por_mes` juegos con más valoraciones de cada (año, mes) de `meses`, ya salidos, más todos
    los que están hoy en Game Pass."""
    total, _ = _pagina(0, 99999)
    meses = sorted(meses)
    # Tramos de meses seguidos (p. ej. agosto-octubre de cada año).
    tramos = []
    for anio, mes in meses:
        inicio = dt.date(anio, mes, 1)
        fin = (inicio + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
        if tramos and (tramos[-1][1] + dt.timedelta(days=1)) == inicio:
            tramos[-1][1] = fin
        else:
            tramos.append([inicio, fin])

    grupos = {}
    for inicio, fin in tramos:
        productos = _tramo(inicio, min(fin, hoy), total)
        for p in productos:
            if p.get("productKind") != "Game" or not p.get("productId") or RE_REEDICION.search(p.get("title", "")):
                continue
            clave = _clave_juego(p)
            grupos.setdefault(clave, {})[p["productId"]] = _ficha(p)
        print(f"  Xbox {inicio:%m/%Y}-{fin:%m/%Y}: {len(productos)} productos", flush=True)

    por_mes_juegos = {}
    for ediciones in grupos.values():
        j = _juego_base(list(ediciones.values()))
        por_mes_juegos.setdefault(j["fecha"][:7], []).append(j)
    juegos = []
    for lista in por_mes_juegos.values():
        lista.sort(key=lambda j: -j["resenas"]["total"])
        juegos += lista[:por_mes] + [j for j in lista[por_mes:] if j["gamepass"]]
    return juegos
