# No seas bobo

¿Comprar un juego de salida o esperar? Web con lo que cuestan hoy los lanzamientos de los últimos
meses en **Steam** (PC) y **Nintendo Switch / Switch 2**, y cuánto han bajado los que salieron en esos
mismos meses uno, dos y tres años antes.

## Qué tiene

- Botones **STEAM / SWITCH** arriba para elegir plataforma (en Switch se puede filtrar Switch o Switch 2).
- **Novedades**: juegos salidos este mes y los dos anteriores, con su precio de hoy, la rebaja si la hay,
  las reseñas (Steam), el enlace a la tienda y, si existe, el precio de la clave en Eneba. Resumen del precio medio y de cuántos están ya rebajados.
- **Comparar**: los mismos meses de los tres años anteriores. Tabla por año con el precio medio de
  salida, el de hoy y cuánto más barato está (de media por juego), y la lista de juegos de cada año.

## De dónde salen los datos

Sin claves ni cuentas:

- **Steam**: el servicio de consultas de la propia tienda (España) da los primeros 15.000 juegos de
  sus clasificaciones de más vendidos y mejor valorados, con fecha, reseñas, precio e imágenes. De
  cada mes se quedan los 40 con más reseñas (en Steam, más reseñas = más ventas). Unas 30 peticiones.
- **Switch**: los juegos de Switch y Switch 2 de esas mismas listas de Wikipedia que están en el eShop
  español, más los 10 más populares de cada mes aunque no estén. Así se evita el relleno del eShop
  (packs a 0,99 € con un PVP inflado), que además falsearía las medias. Precio del eShop español.

- **Eneba**: si venden la clave del juego (Steam, o Switch/Switch 2 para Europa), su oferta más barata
  con existencias, sin la comisión de pago que suman al final. Eneba no tiene API pública: se leen
  despacio sus páginas públicas (sitemaps para saber qué claves hay, cada semana; y la ficha de cada
  producto para el precio: cada día los juegos recientes y cada semana los de años anteriores). Si
  algún día bloquean las descargas, la web sigue mostrando los últimos precios conocidos.

## Precio de salida

Ninguna tienda dice gratis a qué precio salió un juego, así que:

- Desde que existe la web, cada juego nuevo queda guardado en `datos/historial.json` con el precio del
  primer día que se ve (y el mínimo visto). Si se vio en su primer mes, ese es su **precio de salida**.
- Para juegos anteriores se usa el **PVP actual** de la tienda. Steam a veces baja el PVP para siempre;
  en ese caso la rebaja real es mayor de lo que se ve.

Con el tiempo, la comparación con años anteriores irá usando precios de salida reales.

## Uso local

```
py actualizar.py --abrir
```

Tarda un par de minutos (la primera vez, unos 10: índice de Eneba y precios de todas sus claves). Luego basta con abrir `index.html`.

## Publicación

`.github/workflows/actualizar-web.yml` se ejecuta cada día a las 8:00 (hora de España), en cada push a
`main` y a mano desde Actions: actualiza precios, sube `datos/` al repositorio y publica en GitHub Pages.
