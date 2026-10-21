"""Lanzamientos notables de un año según "List of video games released in AAAA" (Wikipedia en inglés).

Se lee el wikitexto: cada fila de las tablas es "fecha | título | plataformas | ...". Si la fecha
ocupa varias filas (rowspan), las siguientes empiezan directamente por el título.
"""
import datetime as dt
import re

from .comun import descargar

MESES = ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"]
RE_FECHA = re.compile(r"\b(" + "|".join(MESES) + r")\b\.?\s*(\d{1,2})?", re.I)
RE_ATRIBUTOS = re.compile(r'^\s*(?:(?:rowspan|colspan|style|class|id|align|data-sort-value)\s*=\s*"?[^|"]*"?\s*)+\|(?!\|)', re.I)
# Lanzamientos solo para un país de Asia: no llegan a la tienda española.
RE_SOLO_ASIA = re.compile(r"\((?:JP|KOR|KR|CHN|CN|TW|AS|JP/AS)\)")
RE_REGION = re.compile(r"\((?:[A-Z]{2,3}(?:/[A-Z]{2,3})*)\)")


def _limpiar(celda):
    celda = re.sub(r"<ref[^>]*/>", "", celda)
    celda = re.sub(r"<ref[^>]*>.*?</ref>", "", celda, flags=re.S)
    celda = re.sub(r"\{\{efn[^{}]*\}\}", "", celda)
    celda = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", celda)        # [[enlace|texto]] -> texto
    celda = re.sub(r"\{\{(?:sort|nowrap|small|vgy)\|(?:[^{}|]*\|)?([^{}|]*)\}\}", r"\1", celda, flags=re.I)
    celda = re.sub(r"\{\{dts\|([^{}]*)\}\}", lambda m: m.group(1).replace("|", " "), celda, flags=re.I)
    celda = re.sub(r"<br\s*/?>", " ", celda)
    return celda.strip()


def _celdas(bloque):
    celdas = []
    for linea in bloque.split("\n"):
        if not linea.startswith("|") or linea.startswith(("|}", "|-", "|+")):
            continue
        for parte in linea[1:].split("||"):
            celdas.append(_limpiar(RE_ATRIBUTOS.sub("", parte)))
    return celdas


def _fecha(texto, anio):
    """'October 1' -> date(anio, 10, 1). Sin día -> None (fecha sin concretar)."""
    m = re.fullmatch(r"\s*(\d{4})\s+(\d{1,2})\s+(\d{1,2})\s*", texto)  # {{dts|2023|10|5}}
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = RE_FECHA.search(texto)
    if not m or not m.group(2) or len(texto) > 40:
        return None
    try:
        return dt.date(anio, MESES.index(m.group(1).lower()) + 1, int(m.group(2)))
    except ValueError:
        return None


def lanzamientos(anio):
    """Lista de {titulo, fecha (date), plataformas (set)} del año, en el orden de Wikipedia."""
    texto = descargar(f"https://en.wikipedia.org/w/index.php?title=List_of_video_games_released_in_{anio}&action=raw")
    # Desde la sección "List" hasta la de juegos sin fecha (encabezados, no los enlaces del índice).
    inicio = re.search(r"^==\s*List\s*==\s*$", texto, re.M)
    fin = re.search(r"^=+\s*Unscheduled releases\s*=+\s*$", texto, re.M)
    texto = texto[inicio.start() if inicio else 0: fin.start() if fin else None]

    juegos, fecha = [], None
    for bloque in texto.split("\n|-"):
        celdas = _celdas(bloque)
        if len(celdas) < 3:
            continue
        i_titulo = next((i for i, c in enumerate(celdas[:3]) if c.startswith("''")), None)
        if i_titulo is None:
            continue
        if i_titulo > 0:
            fecha = _fecha(celdas[i_titulo - 1], anio)
        if fecha is None or i_titulo + 1 >= len(celdas):
            continue
        celda_titulo = celdas[i_titulo]
        if RE_SOLO_ASIA.search(celda_titulo):
            continue
        titulo = re.sub(r"'{2,}", "", celda_titulo)
        titulo = " ".join(RE_REGION.sub("", titulo).split())
        plataformas = {p.strip() for p in celdas[i_titulo + 1].split(",") if p.strip()}
        if titulo:
            juegos.append({"titulo": titulo, "fecha": fecha, "plataformas": plataformas})
    return juegos
