"""Nintendo eShop España: juegos destacados que salieron cada mes y su precio actual.

El buscador de nintendo.es da los juegos por fecha y popularidad, pero entre los populares hay mucho
relleno (packs a 0,99 € con un PVP inflado), así que solo se quedan los que Wikipedia recoge como
lanzamientos de Switch y los más populares del mes. El precio se pide a la API oficial del eShop,
porque el que trae el buscador a veces está desfasado.
"""
import calendar
import datetime as dt

from .comun import descargar_json, normalizar

BUSCADOR = "https://searching.nintendo-europe.com/es/select"
PRECIOS = "https://api.ec.nintendo.com/v1/price"
CONSOLA = {"HAC": "Switch", "BEE": "Switch 2"}
# Imágenes de mejor a peor para una portada apaisada; la web pasa a la siguiente si una no carga.
IMAGENES = ("image_url_h2x1_s", "wishlist_email_banner640w_image_url_s", "image_url_h16x9_s",
            "wishlist_email_banner460w_image_url_s", "image_url_sq_s", "wishlist_email_square_image_url_s")
CAMPOS = "title,dates_released_dts,popularity,nsuid_txt,playable_on_txt,url,publisher,fs_id," + ",".join(IMAGENES)


def _en_wikipedia(titulo, titulos_wiki):
    t = normalizar(titulo)
    return any(t == w or (len(w) >= 6 and t.startswith(w + " ")) for w in titulos_wiki)


def lanzamientos(anio, mes, titulos_wiki, populares=10, hasta="9999"):
    """Juegos cuya primera fecha de salida cae en ese mes (y no después de `hasta`): los que están en
    `titulos_wiki` (normalizados) y los `populares` más populares aunque no estén."""
    ultimo = calendar.monthrange(anio, mes)[1]
    filtro = f"type:GAME AND dates_released_dts:[{anio}-{mes:02d}-01T00:00:00Z TO {anio}-{mes:02d}-{ultimo}T23:59:59Z]"
    datos = descargar_json(BUSCADOR, {"q": "*", "fq": filtro, "sort": "popularity asc", "rows": 250,
                                      "wt": "json", "fl": CAMPOS})
    juegos = []
    for d in datos["response"]["docs"]:
        fecha = min(d.get("dates_released_dts") or ["9999"])[:10]
        if not fecha.startswith(f"{anio}-{mes:02d}") or fecha > hasta or not d.get("nsuid_txt"):
            continue  # salió antes y se ha vuelto a publicar (otra edición, otra región...)
        if len(juegos) >= populares and not _en_wikipedia(d["title"], titulos_wiki):
            continue
        consola = next((CONSOLA[p] for p in ("BEE", "HAC") if p in d.get("playable_on_txt", [])), "Switch")
        juegos.append({
            "plataforma": "switch",
            "consola": consola,
            "id": f"switch:{d['fs_id']}",
            "titulo": d["title"].replace("™", "").replace("®", "").strip(),
            "fecha": fecha,
            "imagenes": list(dict.fromkeys(d[k] for k in IMAGENES if d.get(k))),
            "url": "https://www.nintendo.com" + d["url"] if d.get("url", "").startswith("/") else d.get("url"),
            "editor": d.get("publisher"),
            "popularidad": d.get("popularity"),
            "nsuids": d["nsuid_txt"],
        })
    return juegos


def precios(nsuids):
    """{nsuid: (precio_normal, precio_actual)} de los que están a la venta."""
    resultado = {}
    lista = list(nsuids)
    for i in range(0, len(lista), 50):
        datos = descargar_json(PRECIOS, {"country": "ES", "lang": "es", "ids": ",".join(lista[i:i + 50])})
        for p in datos.get("prices", []):
            if p.get("sales_status") != "onsale" or "regular_price" not in p:
                continue
            normal = float(p["regular_price"]["raw_value"])
            actual = float(p["discount_price"]["raw_value"]) if "discount_price" in p else normal
            resultado[str(p["title_id"])] = (normal, actual)
    return resultado


def precio_del_juego(juego, tabla):
    """El juego puede tener varios nsuid (juego, packs, mejoras de Switch 2): se usa el del juego base
    (empiezan por 7001) y, si no hay, el más barato de los demás."""
    base = [tabla[n] for n in juego["nsuids"] if n.startswith("7001") and n in tabla]
    if base:
        return base[0]
    otros = [tabla[n] for n in juego["nsuids"] if n in tabla and not n.startswith("7005")]
    return min(otros) if otros else None
