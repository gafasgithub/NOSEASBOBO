# NOSEASBOBO

Web estática (HTML + CSS + JS sin compilación) con el precio de hoy de los lanzamientos de Steam,
Nintendo Switch y Xbox (marcando los que están en Game Pass) de los últimos meses, y comparación con los mismos meses de años anteriores. Ver README.md.

## Estructura

- `actualizar.py`: genera `datos/juegos.js` (`window.DATOS`, script clásico para que funcione con
  doble clic en `index.html`). `MESES` (3: el actual y dos anteriores) y `ANIOS_ATRAS` (3) fijan el
  alcance. Si una tienda falla, se publican sus juegos de la ejecución anterior (`fallos` en los datos).
- `fuentes/wikipedia.py` (solo para filtrar Switch): lee el wikitexto de "List of video games released in AAAA" (fila =
  fecha | título | plataformas; la fecha puede faltar por rowspan). Se quitan lanzamientos solo de Asia. Cortar
  en el encabezado "Unscheduled releases", no en el texto: el índice de arriba también lo nombra.
- `fuentes/steam.py`: `IStoreQueryService/Query` (sin clave, 1000 juegos por petición con fecha,
  reseñas, precio e imágenes). No filtra por fecha: se leen los 15.000 primeros de `sort` 10 (más
  vendidos) y 23 (mejor valorados) y de cada mes se quedan `STEAM_POR_MES` por número de reseñas.
  (`ISteamChartsService/GetTopReleasesPages` está abandonada: solo llega a feb. 2025.)
- `fuentes/nintendo.py`: buscador de nintendo.es (Solr) por fecha y `popularity asc` (250 por mes); se
  quedan los que están en Wikipedia (NS/NS2) y los `SWITCH_POPULARES` primeros; precio en
  `api.ec.nintendo.com/v1/price` (el del buscador está desfasado). Un juego tiene varios nsuid: 7001 =
  juego, 7007 = packs, 7005 = mejoras de Switch 2 (se ignoran). Consola: HAC = Switch, BEE = Switch 2.
- `fuentes/xbox.py`: POST a `emerald.xboxservices.com/xboxcomfd/browse` (pide las cabeceras `MS-CV` y
  `x-ms-api-version`), `ReleaseDate desc`, 25 por página, ~4 s cada una. El `EncodedCT` es base64 de
  `{SkipCount, TotalCount}`: se salta a cualquier posición. Hay que mandar el `TotalCount` real (con uno
  falso da 500). Se tantea dónde empieza cada tramo de meses y se lee en paralelo (`HILOS`; `comun.py`
  reparte las pausas con un cerrojo). Game Pass = `includedWithPassesProductIds` (coincide con
  `catalog.gamepass.com/sigls`): K6L8 consola, KGQ8 PC, P85B Premium, K5DJ Essential, K5DH EA Play,
  KHS0 Ultimate; QH5H es Ubisoft+ (no cuenta). Ediciones y lotes son productos aparte con las mismas
  valoraciones: `RE_REEDICION` los quita y se agrupan por `xboxTitleId` (o editor + valoraciones + nota).
  Fecha = `releaseDate` + 2 h (la tienda da la medianoche española en UTC). Xbox no tiene Eneba aún.
- `fuentes/eneba.py`: sin API. Índice de los sitemaps `es/sitemap/products*.xml` en
  `.cache/eneba_indice.json` (7 días; en Actions con actions/cache). URL de clave: `steam-<slug>-(pc-steam-key|
  steam-key-pc|steam-pc-key)-<región>` o `nintendo-<slug>-nintendo-switch[-2]-eshop-key-<región>`; regiones
  válidas en `REGIONES`. Precio: mínimo de los `Auction:` con existencias del `__APOLLO_STATE__` de la
  ficha. Precios en `datos/eneba.json` (recientes cada día, el resto cada 7). Cloudflare corta con 429
  si se va rápido: pausa de 4 s, sin reintentos y, al primer 429 o a los `MINUTOS_ENEBA`, se deja para
  el día siguiente (se usan los precios guardados). Las descargas tienen tope de tiempo total
  (`fuentes/comun.py`) y el job de Actions, `timeout-minutes: 30`. La línea de
  Eneba está dentro de la ficha `<a>`: abre con `data-eneba` + JS (no se pueden anidar enlaces).
- `datos/historial.json`: primer precio visto (`pvp`, `visto`) y mínimo de cada juego. Si `visto` está a
  ≤31 días de la salida, ese PVP es el precio de salida (`salida`); si no, la web usa el PVP actual.
- `js/app.js`: interfaz. Estado en `localStorage` (`noseasbobo.v1`, tema en `noseasbobo.tema`).
  El enlace lleva pestaña y plataforma (`#comparar/switch`).
- Estilo pixel art como TIPSTER y FUTBOL7. La letra pixelada no tiene tildes ni Ñ: textos sin tilde
  (ULTIMOS) y nada con Ñ en esa letra (las cabeceras de la tabla de años van en VT323).

## Probar cambios

- `py actualizar.py --abrir` (en Windows se usa `py`, no `python`; no hay Node).
- Capturas sin abrir ventanas: Edge headless con `--screenshot` desde PowerShell.
- El workflow sube `datos/` al repo con cada ejecución: hacer `git pull` antes de tocar nada.
