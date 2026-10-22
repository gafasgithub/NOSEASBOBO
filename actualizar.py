"""Actualiza los datos de la web: lanzamientos de los últimos meses (y de los mismos meses de años
anteriores) en Steam, Nintendo Switch y Xbox, con su precio de hoy en las tiendas españolas y, en
Xbox, si están hoy en Game Pass.

    py actualizar.py            # genera datos/juegos.js
    py actualizar.py --abrir    # y abre la web

Deja también datos/historial.json (precio visto la primera vez y mínimo de cada juego), que se sube
al repositorio: es la única forma de saber luego a qué precio salió cada juego.
"""
import datetime as dt
import json
import pathlib
import sys
import time
import traceback
import urllib.error
import webbrowser

from fuentes import eneba, nintendo, steam, wikipedia, xbox
from fuentes.comun import normalizar

MESES = 3            # mes actual y los dos anteriores
ANIOS_ATRAS = 3      # para comparar con los mismos meses de años anteriores
STEAM_POR_MES = 40   # de Steam, los 40 con más reseñas de cada mes
SWITCH_POPULARES = 10  # de Switch entran los de Wikipedia y, aunque no estén, los 10 más populares del mes
XBOX_POR_MES = 40    # de Xbox, los 40 con más valoraciones de cada mes y todos los de Game Pass

RAIZ = pathlib.Path(__file__).parent
DATOS = RAIZ / "datos"
SALIDA = DATOS / "juegos.js"
HISTORIAL = DATOS / "historial.json"
PRECIOS_ENEBA = DATOS / "eneba.json"
INDICE_ENEBA = RAIZ / ".cache" / "eneba_indice.json"
MINUTOS_ENEBA = 12   # tope para consultar precios de Eneba (~180 fichas); lo que falte, al día siguiente


def leer_json(ruta, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return defecto


def guardar_json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def periodos(hoy):
    """Meses (año, mes) a revisar: los MESES últimos de este año y los mismos de ANIOS_ATRAS años antes."""
    base = []
    anio, mes = hoy.year, hoy.month
    for _ in range(MESES):
        base.append((anio, mes))
        anio, mes = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    return [(a - atras, m) for atras in range(ANIOS_ATRAS + 1) for a, m in base]


def datos_anteriores():
    """Juegos de la última ejecución, por si una tienda falla hoy."""
    try:
        texto = SALIDA.read_text(encoding="utf-8")
        return json.loads(texto[texto.index("{"): texto.rindex("}") + 1])["juegos"]
    except (FileNotFoundError, ValueError, KeyError):
        return []


def lanzamientos_wikipedia(meses, hoy):
    """Lanzamientos de Wikipedia de esos meses que ya han salido."""
    juegos = []
    for anio in sorted({a for a, _ in meses}):
        juegos += [j for j in wikipedia.lanzamientos(anio) if (j["fecha"].year, j["fecha"].month) in meses and j["fecha"] <= hoy]
    return juegos


def juegos_steam(meses, hoy):
    juegos = steam.lanzamientos(meses, hoy, STEAM_POR_MES)
    print(f"Steam: {len(juegos)} juegos")
    return juegos


def juegos_switch(meses, hoy):
    wiki = lanzamientos_wikipedia(set(meses), hoy)
    juegos = []
    for anio, mes in meses:
        titulos = {normalizar(j["titulo"]) for j in wiki
                   if (j["fecha"].year, j["fecha"].month) == (anio, mes) and j["plataformas"] & {"NS", "NS2"}}
        juegos += nintendo.lanzamientos(anio, mes, titulos, SWITCH_POPULARES, hasta=hoy.isoformat())
    print(f"Switch: {len(juegos)} juegos; leyendo precios del eShop")
    tabla = nintendo.precios({n for j in juegos for n in j["nsuids"]})
    for j in juegos:
        precio = nintendo.precio_del_juego(j, tabla)
        j["pvp"], j["precio"] = precio if precio else (None, None)
        j["gratis"] = precio is not None and precio[0] == 0
        del j["nsuids"]
    return juegos


def juegos_xbox(meses, hoy):
    juegos = xbox.lanzamientos(meses, hoy, XBOX_POR_MES)
    print(f"Xbox: {len(juegos)} juegos, {sum(bool(j['gamepass']) for j in juegos)} en Game Pass")
    return juegos


def aplicar_eneba(juegos, hoy):
    """Precio de la clave en Eneba. Los juegos de los últimos meses se miran cada día y los de años
    anteriores cada semana. Si Eneba frena (429) o se acaba el tiempo, se deja para el día siguiente
    y se usan los últimos precios conocidos."""
    guardados = leer_json(PRECIOS_ENEBA, {})
    try:
        indice = eneba.cargar_indice(INDICE_ENEBA)
    except Exception:
        traceback.print_exc()
        print("Eneba: no se pudo leer el índice; se usan los precios guardados.")
        indice = None
    consultar = indice is not None
    consultados = 0
    fin = time.monotonic() + MINUTOS_ENEBA * 60
    # Primero los más recientes, que son los que cambian de precio a diario.
    for j in sorted(juegos, key=lambda j: j["fecha"], reverse=True):
        producto = eneba.producto(j, indice) if indice is not None else next(
            (p for p, g in guardados.items() if g.get("id") == j["id"]), None)
        if not producto:
            continue
        g = guardados.get(producto)
        dias = 1 if (hoy - dt.date.fromisoformat(j["fecha"])).days < 120 else 7
        caducado = not g or (hoy - dt.date.fromisoformat(g["fecha"])).days >= dias
        if consultar and caducado and time.monotonic() >= fin:
            print(f"Eneba: se acabaron los {MINUTOS_ENEBA} minutos; el resto, mañana.")
            consultar = False
        if consultar and caducado:
            try:
                g = guardados[producto] = {"id": j["id"], "precio": eneba.precio(producto), "fecha": hoy.isoformat()}
                consultados += 1
                if consultados % 25 == 0:
                    guardar_json(PRECIOS_ENEBA, guardados)
                    print(f"  Eneba: {consultados} precios consultados", flush=True)
            except urllib.error.HTTPError as error:
                if error.code == 429:
                    print("Eneba: pide que vayamos más despacio (429); el resto, mañana.")
                    consultar = False
                else:
                    print(f"  Eneba: {producto}: error {error.code}")
            except Exception as error:
                print(f"  Eneba: {producto}: {error}")
        if g and g.get("precio") is not None:
            j["eneba"] = {"precio": g["precio"], "url": eneba.WEB + producto, "fecha": g["fecha"]}
    guardar_json(PRECIOS_ENEBA, guardados)
    print(f"Eneba: {consultados} precios consultados, {sum('eneba' in j for j in juegos)} juegos con precio")


def aplicar_historial(juegos, hoy):
    """Guarda el primer precio visto y el mínimo. Si el juego se vio por primera vez en su primer mes
    a la venta, ese primer precio es su precio de salida real."""
    historial = leer_json(HISTORIAL, {})
    for j in juegos:
        if j["precio"] is None:
            continue
        h = historial.get(j["id"])
        if not h:
            h = historial[j["id"]] = {"visto": hoy.isoformat(), "pvp": j["pvp"], "minimo": j["precio"], "fecha_minimo": hoy.isoformat()}
        elif j["precio"] < h["minimo"]:
            h["minimo"], h["fecha_minimo"] = j["precio"], hoy.isoformat()
        cerca_de_salida = (dt.date.fromisoformat(h["visto"]) - dt.date.fromisoformat(j["fecha"])).days <= 31
        j["salida"] = h["pvp"] if cerca_de_salida else None
        j["minimo"] = h["minimo"]
        j["minimo_desde"] = h["visto"]
    guardar_json(HISTORIAL, historial)


def main():
    hoy = dt.date.today()
    meses = periodos(hoy)
    anteriores = datos_anteriores()
    juegos, avisos = [], []
    fuentes = (("steam", lambda: juegos_steam(set(meses), hoy)), ("switch", lambda: juegos_switch(meses, hoy)),
               ("xbox", lambda: juegos_xbox(set(meses), hoy)))
    for nombre, obtener in fuentes:
        try:
            juegos += obtener()
        except Exception:
            traceback.print_exc()
            viejos = [j for j in anteriores if j["plataforma"] == nombre]
            juegos += viejos
            avisos.append(nombre)
            print(f"¡{nombre} ha fallado! Se publican sus datos anteriores ({len(viejos)} juegos).")

    aplicar_historial([j for j in juegos if j["plataforma"] not in avisos], hoy)
    aplicar_eneba(juegos, hoy)
    for j in juegos:
        if j.get("pvp") and j.get("precio") is not None:
            j["descuento"] = round(100 * (1 - j["precio"] / j["pvp"]))
    juegos.sort(key=lambda j: (j["plataforma"], j["fecha"][:7], -(j.get("resenas", {}).get("total") or 0), j.get("popularidad") or 0))

    salida = {
        "generado": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "hoy": hoy.isoformat(),
        "meses": [f"{a}-{m:02d}" for a, m in meses[:MESES]],
        "anios_atras": ANIOS_ATRAS,
        "fallos": avisos,
        "juegos": juegos,
    }
    SALIDA.write_text("// Generado por actualizar.py; no editar a mano.\nwindow.DATOS = "
                      + json.dumps(salida, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Listo: {len(juegos)} juegos en {SALIDA.relative_to(RAIZ)}")
    if "--abrir" in sys.argv:
        webbrowser.open((RAIZ / "index.html").as_uri())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
