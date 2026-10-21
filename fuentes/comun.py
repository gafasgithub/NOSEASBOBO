"""Utilidades compartidas: descargas con reintentos y pausas, y normalización de títulos."""
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

AGENTE = "NOSEASBOBO/1.0 (https://github.com/gafasgithub/NOSEASBOBO)"

# Pausa mínima entre peticiones al mismo servidor (segundos), para no recibir bloqueos.
PAUSA = {
    "api.steampowered.com": 1.0,
    "en.wikipedia.org": 0.5,
    "searching.nintendo-europe.com": 0.3,
    "api.ec.nintendo.com": 0.5,
    "www.eneba.com": 4.0,   # con 1,5 s Cloudflare corta con 429 tras unas decenas de fichas
}
_ultima = {}


def _esperar(host):
    pausa = PAUSA.get(host, 0.3)
    falta = _ultima.get(host, 0) + pausa - time.monotonic()
    if falta > 0:
        time.sleep(falta)
    _ultima[host] = time.monotonic()


def _leer(peticion, limite):
    """Lee la respuesta entera, pero corta si tarda más de `limite` segundos en total: el timeout de
    urlopen solo vale para cada espera suelta y una descarga que llega a goteo no acabaría nunca."""
    inicio = time.monotonic()
    partes = []
    with urllib.request.urlopen(peticion, timeout=20) as respuesta:
        while True:
            parte = respuesta.read(1 << 16)
            if not parte:
                return b"".join(partes).decode("utf-8")
            partes.append(parte)
            if time.monotonic() - inicio > limite:
                raise TimeoutError(f"más de {limite} s descargando")


def descargar(url, params=None, intentos=4, limite=90):
    """Devuelve el texto de la URL. Reintenta con espera creciente si hay 429 o errores del servidor."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    host = urllib.parse.urlsplit(url).hostname
    for intento in range(intentos):
        _esperar(host)
        try:
            return _leer(urllib.request.Request(url, headers={"User-Agent": AGENTE}), limite)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or intento == intentos - 1:
                raise
            espera = 30 * (intento + 1) if error.code == 429 else 5 * (intento + 1)
            motivo = f"error {error.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if intento == intentos - 1:
                raise
            espera = 5 * (intento + 1)
            motivo = str(error)
        print(f"  {host}: {motivo}; reintento en {espera} s", flush=True)
        time.sleep(espera)


def descargar_json(url, params=None):
    return json.loads(descargar(url, params))


def normalizar(titulo):
    """Título reducido a letras y números en minúscula, para comparar nombres de tiendas distintas."""
    t = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    t = t.lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())
