"""Steam (tienda española): los juegos más vendidos y mejor valorados que salieron cada mes.

El servicio de consultas de la tienda (IStoreQueryService/Query, el que usa su buscador; no pide
clave) no filtra por fecha, pero devuelve 1000 juegos por petición con su fecha de salida, reseñas,
precio e imágenes. Se recorren los primeros puestos de dos clasificaciones (más vendidos y mejor
valorados) y de cada mes se quedan los que más reseñas tienen: en Steam, cuantas más reseñas, más
ventas. Son unas 30 peticiones en total.
"""
import datetime as dt
import json

from .comun import descargar_json

CONSULTA = "https://api.steampowered.com/IStoreQueryService/Query/v1/"
TIENDA = "https://store.steampowered.com/"
IMAGENES = "https://shared.akamai.steamstatic.com/store_item_assets/"
CLASIFICACIONES = {10: "más vendidos", 23: "mejor valorados"}  # valores de "sort" de la consulta
PROFUNDIDAD = 15000   # puestos que se leen de cada clasificación
BLOQUE = 1000


def _pagina(orden, inicio):
    entrada = {
        "query": {"start": inicio, "count": BLOQUE, "sort": orden,
                  "filters": {"released_only": True, "type_filters": {"include_games": True}}},
        "context": {"language": "spanish", "country_code": "ES"},
        "data_request": {"include_release": True, "include_reviews": True, "include_assets": True},
    }
    return descargar_json(CONSULTA, {"input_json": json.dumps(entrada)})["response"].get("store_items", [])


def _imagenes(x, appid):
    """De mejor a peor para la ficha; la web pasa a la siguiente si una no carga."""
    a = x.get("assets", {})
    formato = a.get("asset_url_format", "")
    propias = [IMAGENES + formato.replace("${FILENAME}", a[k]) for k in ("header", "main_capsule", "small_capsule")
               if a.get(k) and formato]
    fijas = [f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
             f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/capsule_616x353.jpg"]
    return list(dict.fromkeys(propias + fijas))


def _ficha(x):
    appid = x["appid"]
    fecha = dt.date.fromtimestamp(x["release"]["steam_release_date"])
    r = x.get("reviews", {}).get("summary_filtered", {})
    compra = x.get("best_purchase_option") or {}
    if "final_price_in_cents" in compra:
        precio = int(compra["final_price_in_cents"]) / 100
        pvp = int(compra.get("original_price_in_cents", compra["final_price_in_cents"])) / 100
    else:
        precio = pvp = None
    return {
        "plataforma": "steam",
        "id": f"steam:{appid}",
        "titulo": x.get("name", "").replace("™", "").replace("®", "").strip(),
        "fecha": fecha.isoformat(),
        "imagenes": _imagenes(x, appid),
        "url": TIENDA + x.get("store_url_path", f"app/{appid}"),
        "gratis": bool(x.get("is_free")),
        "acceso_anticipado": bool(x.get("is_early_access")),
        "resenas": {"total": r.get("review_count", 0), "pct": r.get("percent_positive"), "desc": r.get("review_score_label")},
        "pvp": pvp,
        "precio": precio,
    }


def lanzamientos(meses, hoy, por_mes=40):
    """Los `por_mes` juegos con más reseñas de cada (año, mes) de `meses`, ya salidos."""
    vistos = {}
    for orden, nombre in CLASIFICACIONES.items():
        for inicio in range(0, PROFUNDIDAD, BLOQUE):
            pagina = _pagina(orden, inicio)
            for x in pagina:
                fecha = x.get("release", {}).get("steam_release_date")
                if not x.get("appid") or x.get("type") not in (0, None) or not fecha:
                    continue
                f = dt.date.fromtimestamp(fecha)
                if (f.year, f.month) in meses and f <= hoy:
                    vistos[x["appid"]] = x
            if len(pagina) < BLOQUE:
                break
        print(f"  Steam {nombre}: {len(vistos)} juegos de esos meses hasta ahora")

    por_mes_juegos = {}
    for x in vistos.values():
        f = dt.date.fromtimestamp(x["release"]["steam_release_date"])
        por_mes_juegos.setdefault((f.year, f.month), []).append(_ficha(x))
    juegos = []
    for lista in por_mes_juegos.values():
        lista.sort(key=lambda j: -(j["resenas"]["total"] or 0))
        juegos += lista[:por_mes]
    return juegos
