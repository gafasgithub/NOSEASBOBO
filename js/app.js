// Interfaz. Los datos los deja actualizar.py en datos/juegos.js (window.DATOS).
// Precio de referencia de un juego: el de salida si lo registramos al salir (j.salida) y, si no,
// el PVP actual de la tienda (j.pvp).
'use strict';

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const DATOS = window.DATOS || { juegos: [], meses: [], anios_atras: 0 };
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
  'septiembre', 'octubre', 'noviembre', 'diciembre'];
const POR_PAGINA = 24;

const estado = {
  pestana: 'novedades',
  plataforma: 'steam',
  consola: '',
  mes: '',            // novedades: '' = todos o 'AAAA-MM'
  orden: 'popular',
  busqueda: '',
  visibles: POR_PAGINA,
  mesComparar: '',    // comparar: '' = todos o 'MM'
  atras: 1,
  ordenComparar: 'ahorro',
  visiblesComparar: POR_PAGINA,
};
try {
  const guardado = JSON.parse(localStorage.getItem('noseasbobo.v1') || '{}');
  for (const k of ['plataforma', 'consola', 'orden', 'atras', 'ordenComparar']) if (k in guardado) estado[k] = guardado[k];
} catch (e) { /* sin almacenamiento */ }

function guardar() {
  try {
    const { plataforma, consola, orden, atras, ordenComparar } = estado;
    localStorage.setItem('noseasbobo.v1', JSON.stringify({ plataforma, consola, orden, atras, ordenComparar }));
  } catch (e) { /* sin almacenamiento */ }
}

// ---------- utilidades ----------

const formatoEuros = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' });
const euros = n => formatoEuros.format(n);
const pct = n => Math.round(n * 100) + '%';
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nombreMes = am => { const [a, m] = am.split('-'); return `${MESES[+m - 1]} ${a}`; };
const capital = s => s.charAt(0).toUpperCase() + s.slice(1);
const fechaCorta = f => { const [a, m, d] = f.split('-'); return `${+d} ${MESES[+m - 1].slice(0, 3)} ${a}`; };
const sinAcentos = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

const referencia = j => j.salida ?? j.pvp;
const dePago = j => j.precio != null && referencia(j) > 0;
const ahorro = j => dePago(j) ? 1 - j.precio / referencia(j) : null;
// Ahorro de la clave de Eneba frente al precio de hoy en la tienda oficial (negativo si es más cara).
const ahorroEneba = j => j.eneba && j.precio > 0 ? 1 - j.eneba.precio / j.precio : null;
const media = lista => lista.length ? lista.reduce((a, b) => a + b, 0) / lista.length : null;

function juegosDe(plataforma = estado.plataforma) {
  return DATOS.juegos.filter(j => j.plataforma === plataforma
    && (plataforma !== 'switch' || !estado.consola || j.consola === estado.consola));
}

function popularidad(j) {
  return j.plataforma === 'steam' ? -(j.resenas?.total || 0) : (j.popularidad ?? 1e9);
}

const ORDENES = {
  popular: ['Más populares', (a, b) => popularidad(a) - popularidad(b)],
  barato: ['Más baratos hoy', (a, b) => (a.precio ?? 1e9) - (b.precio ?? 1e9)],
  ahorro: ['Más rebajados', (a, b) => (ahorro(b) ?? -1) - (ahorro(a) ?? -1)],
  fecha: ['Más recientes', (a, b) => b.fecha.localeCompare(a.fecha)],
  caro: ['Más caros de salida', (a, b) => (referencia(b) ?? -1) - (referencia(a) ?? -1)],
  eneba: ['Más ahorro en Eneba', (a, b) => (ahorroEneba(b) ?? -2) - (ahorroEneba(a) ?? -2)],
};

function selectorOrden(id, valor) {
  return `<label class="etiqueta">Ordenar <select id="${id}">${Object.entries(ORDENES)
    .map(([k, [texto]]) => `<option value="${k}"${k === valor ? ' selected' : ''}>${texto}</option>`).join('')}</select></label>`;
}

function filtrosMes(opciones, valor, atributo) {
  return `<div class="filtros" role="group" aria-label="Mes">${opciones.map(([v, texto]) =>
    `<button type="button" data-${atributo}="${v}" aria-pressed="${v === valor}">${esc(texto)}</button>`).join('')}</div>`;
}

// ---------- ficha de un juego ----------

function lineaResenas(j) {
  const r = j.resenas;
  if (!r || !r.total) return '';
  const clase = r.pct >= 80 ? 'resena-buena' : r.pct < 50 ? 'resena-mala' : '';
  return `<div class="juego-dato"><span class="${clase}">${r.pct}% ${esc(r.desc || '')}</span> · ${r.total.toLocaleString('es-ES')} reseñas</div>`;
}

function bloquePrecios(j, comparando) {
  if (j.gratis || (j.precio === 0 && !j.pvp)) return '<div class="juego-precios"><span class="precio rebajado">GRATIS</span></div>';
  if (j.precio == null) return '<div class="juego-precios"><span class="nota">Sin precio en la tienda</span></div>';
  const ref = referencia(j);
  const rebajado = ref > j.precio;
  const etiquetaRef = j.salida != null ? 'Salida' : 'PVP';
  let html = '<div class="juego-precios">';
  if (comparando && ref) {
    html += `<span class="nota">${etiquetaRef} ${euros(ref)}</span><span class="flecha">→</span>`;
    html += `<span class="precio${rebajado ? ' rebajado' : ''}">${euros(j.precio)}</span>`;
  } else {
    html += `<span class="precio${rebajado ? ' rebajado' : ''}">${euros(j.precio)}</span>`;
    if (rebajado) html += `<span class="tachado">${euros(ref)}</span>`;
  }
  html += '</div>';
  html += lineaEneba(j);
  if (j.minimo != null && j.minimo < j.precio) {
    html += `<div class="nota">Mínimo visto: ${euros(j.minimo)} (desde ${fechaCorta(j.minimo_desde)})</div>`;
  }
  return html;
}

// Imágenes: cada juego trae varias (j.imagenes, de mejor a peor). Si una no carga se prueba la
// siguiente y, si no queda ninguna, se deja la portada de relleno con el título.
const IMAGENES = new Map(DATOS.juegos.map(j => [j.id, j.imagenes || (j.imagen ? [j.imagen] : [])]));

function siguienteImagen(img) {
  const lista = IMAGENES.get(img.dataset.id) || [];
  const i = +img.dataset.i + 1;
  if (i < lista.length) { img.dataset.i = i; img.src = lista[i]; }
  else img.remove();
}

function portada(j) {
  const lista = IMAGENES.get(j.id) || [];
  const relleno = `<div class="sin-portada ${j.plataforma}"><span>${esc(j.titulo)}</span></div>`;
  if (!lista.length) return relleno;
  return relleno + `<img src="${esc(lista[0])}" alt="" loading="lazy" data-id="${esc(j.id)}" data-i="0" onerror="siguienteImagen(this)">`;
}

// La ficha entera es un enlace a la tienda oficial; la línea de Eneba abre Eneba (ver el clic más abajo).
function lineaEneba(j) {
  if (!j.eneba) return '';
  const a = ahorroEneba(j);
  const comparacion = a == null ? '' : a >= 0.01 ? `<span class="eneba-ahorro">-${pct(a)} que la tienda</span>`
    : '<span class="nota">no sale más barato</span>';
  return `<div class="eneba" role="link" tabindex="0" data-eneba="${esc(j.eneba.url)}" title="Ver la clave en Eneba">
    <span class="eneba-marca">ENEBA</span><b>${euros(j.eneba.precio)}</b>${comparacion}</div>`;
}

function ficha(j, comparando = false) {
  const a = ahorro(j);
  const rebaja = a != null && a >= 0.01 ? `<span class="rebaja">-${pct(a)}</span>` : '';
  const chapa = j.plataforma === 'switch'
    ? `<span class="chapa${j.consola === 'Switch 2' ? ' s2' : ''}">${j.consola === 'Switch 2' ? 'SWITCH 2' : 'SWITCH'}</span>` : '';
  return `<a class="juego" href="${esc(j.url)}" target="_blank" rel="noopener">
    <div class="portada">${portada(j)}${chapa}${rebaja}</div>
    <div class="juego-cuerpo">
      <div class="juego-titulo">${esc(j.titulo)}</div>
      <div class="juego-dato">${fechaCorta(j.fecha)}${j.editor ? ' · ' + esc(j.editor) : ''}</div>
      ${lineaResenas(j)}
      ${bloquePrecios(j, comparando)}
    </div>
  </a>`;
}

function rejilla(lista, visibles, comparando, idMas) {
  if (!lista.length) return '<p class="vacio">No hay juegos con estos filtros.</p>';
  let html = `<div class="rejilla">${lista.slice(0, visibles).map(j => ficha(j, comparando)).join('')}</div>`;
  if (lista.length > visibles) {
    html += `<div class="mas"><button type="button" class="boton" id="${idMas}">Ver más (${lista.length - visibles})</button></div>`;
  }
  return html;
}

function buscar(lista) {
  const q = sinAcentos(estado.busqueda.trim());
  return q ? lista.filter(j => sinAcentos(j.titulo).includes(q)) : lista;
}

// ---------- novedades ----------

function pintarNovedades() {
  const todos = juegosDe().filter(j => DATOS.meses.includes(j.fecha.slice(0, 7)));
  const delMes = todos.filter(j => !estado.mes || j.fecha.startsWith(estado.mes));
  const lista = buscar(delMes).sort(ORDENES[estado.orden][1]);

  const pago = delMes.filter(dePago);
  const rebajados = pago.filter(j => ahorro(j) >= 0.01);
  const enEneba = delMes.filter(j => ahorroEneba(j) >= 0.01);
  const opciones = [['', `Todos (${todos.length})`],
    ...DATOS.meses.map(m => [m, `${capital(nombreMes(m))} (${todos.filter(j => j.fecha.startsWith(m)).length})`])];

  $('#novedades').innerHTML = `
    <h2>LANZAMIENTOS DE LOS ULTIMOS MESES</h2>
    <p class="explica">Juegos que han salido en ${estado.plataforma === 'steam' ? 'Steam' : 'Nintendo Switch'} y lo que cuestan hoy.
      ${estado.plataforma === 'steam' ? 'Los 40 con más reseñas de cada mes (en Steam, más reseñas = más ventas).' : 'Los que Wikipedia recoge como lanzamientos destacados y los 10 más populares de cada mes en el eShop.'}</p>
    ${filtrosMes(opciones, estado.mes, 'mes')}
    <div class="resumen" style="margin-top:16px">
      ${casilla(delMes.length, 'juegos')}
      ${casilla(pago.length ? euros(media(pago.map(referencia))) : '—', 'precio medio de salida')}
      ${casilla(pago.length ? pct(rebajados.length / pago.length) : '—', 'ya están rebajados', rebajados.length > 0)}
      ${casilla(rebajados.length ? '-' + pct(media(rebajados.map(ahorro))) : '—', 'rebaja media de los rebajados', rebajados.length > 0)}
      ${casilla(enEneba.length ? '-' + pct(media(enEneba.map(ahorroEneba))) : '—', `ahorro medio en Eneba (${enEneba.length} más baratos allí)`, enEneba.length > 0)}
    </div>
    <div class="herramientas">
      <input type="search" id="buscar" placeholder="Buscar juego…" value="${esc(estado.busqueda)}">
      ${selectorOrden('orden', estado.orden)}
    </div>
    <div id="lista-novedades">${rejilla(lista, estado.visibles, false, 'mas-novedades')}</div>`;
}

function casilla(valor, nombre, bien = false) {
  return `<div class="casilla"><div class="valor${bien ? ' bien' : ''}">${valor}</div><div class="nombre">${nombre}</div></div>`;
}

// ---------- comparar con años anteriores ----------

function mesesComparados(atras) {
  return DATOS.meses
    .filter(m => !estado.mesComparar || m.endsWith('-' + estado.mesComparar))
    .map(m => `${+m.slice(0, 4) - atras}${m.slice(4)}`);
}

function juegosHace(atras) {
  const meses = mesesComparados(atras);
  return juegosDe().filter(j => meses.includes(j.fecha.slice(0, 7)));
}

function pintarComparar() {
  const anioActual = +DATOS.hoy.slice(0, 4);
  const filas = [];
  for (let atras = 0; atras <= DATOS.anios_atras; atras++) {
    const juegos = juegosHace(atras);
    const pago = juegos.filter(dePago);
    const ahorros = pago.map(ahorro);
    filas.push({
      atras, juegos,
      anio: anioActual - atras,
      salida: pago.length ? media(pago.map(referencia)) : null,
      hoy: pago.length ? media(pago.map(j => j.precio)) : null,
      ahorro: pago.length ? media(ahorros) : null,
      rebajados: pago.length ? ahorros.filter(a => a >= 0.01).length / pago.length : null,
    });
  }
  const maxAhorro = Math.max(0.01, ...filas.map(f => f.ahorro || 0));
  const plataforma = estado.plataforma === 'steam' ? 'STEAM' : 'SWITCH';
  const elegida = filas.find(f => f.atras === estado.atras) || filas[1] || filas[0];
  const nombresMeses = mesesComparados(0).map(m => MESES[+m.slice(5) - 1]);
  const textoMeses = nombresMeses.length > 1 ? nombresMeses.slice(0, -1).join(', ') + ' y ' + nombresMeses.at(-1) : nombresMeses[0];

  const veredictos = filas.filter(f => f.atras > 0 && f.ahorro != null).map(f =>
    `<p class="veredicto">Los de hace ${f.atras} ${f.atras === 1 ? 'año' : 'años'} (${f.anio}) cuestan hoy de media
      un <b>${pct(f.ahorro)}</b> menos que de salida, y ${pct(f.rebajados)} están rebajados ahora mismo.</p>`).join('');

  const opciones = [['', 'Todos los meses'], ...DATOS.meses.map(m => [m.slice(5), capital(MESES[+m.slice(5) - 1])])];
  const lista = buscar(elegida.juegos).sort(ORDENES[estado.ordenComparar][1]);

  $('#comparar').innerHTML = `
    <div class="bloque">
      <h2>${plataforma}: HOY CONTRA AYER</h2>
      <p class="explica">Juegos que salieron en ${esc(textoMeses)} de cada año: cuánto costaban de salida y cuánto cuestan hoy.
        Pulsa un año para ver sus juegos.</p>
      ${filtrosMes(opciones, estado.mesComparar, 'mes-comparar')}
      <div class="desplazable" style="margin-top:14px">
        <table class="tabla-anios">
          <thead><tr><th>Año</th><th>Juegos</th><th class="ocultable">Precio medio de salida</th><th>Precio medio hoy</th><th>Más barato hoy</th><th class="ocultable">Rebajados</th></tr></thead>
          <tbody>${filas.map(f => `
            <tr class="${f.atras === elegida.atras ? 'elegido' : ''}" data-atras="${f.atras}" style="cursor:pointer">
              <td><button type="button" class="boton" data-atras="${f.atras}">${f.anio}</button></td>
              <td class="num">${f.juegos.length}</td>
              <td class="num ocultable">${f.salida != null ? euros(f.salida) : '—'}</td>
              <td class="num">${f.hoy != null ? euros(f.hoy) : '—'}</td>
              <td><div style="display:flex;gap:8px;align-items:center"><span class="num" style="font:12px var(--px);min-width:52px">${f.ahorro != null ? '-' + pct(f.ahorro) : '—'}</span>
                <div class="barra" style="flex:1"><span style="width:${f.ahorro ? 100 * f.ahorro / maxAhorro : 0}%"></span></div></div></td>
              <td class="num ocultable">${f.rebajados != null ? pct(f.rebajados) : '—'}</td>
            </tr>`).join('')}</tbody>
        </table>
      </div>
      ${veredictos || '<p class="veredicto">Aún no hay datos de años anteriores para estos filtros.</p>'}
      <p class="explica" style="margin-top:10px">"Salida" es el precio que registramos al salir el juego; si no lo tenemos
        (juegos anteriores a esta web), se usa el PVP actual de la tienda. Si la tienda bajó el PVP para siempre, la rebaja real es aún mayor.</p>
    </div>
    <h2>JUEGOS DE ${elegida.anio}</h2>
    <div class="herramientas">
      <input type="search" id="buscar" placeholder="Buscar juego…" value="${esc(estado.busqueda)}">
      ${selectorOrden('orden-comparar', estado.ordenComparar)}
    </div>
    ${rejilla(lista, estado.visiblesComparar, true, 'mas-comparar')}`;
}

// ---------- pintar y eventos ----------

function pintar() {
  history.replaceState(null, '', `#${estado.pestana}/${estado.plataforma}`);
  document.querySelectorAll('[data-pestana]').forEach(b => b.setAttribute('aria-selected', b.dataset.pestana === estado.pestana));
  document.querySelectorAll('.panel').forEach(p => { p.hidden = p.id !== estado.pestana; });
  document.querySelectorAll('[data-plataforma]').forEach(b => b.setAttribute('aria-pressed', b.dataset.plataforma === estado.plataforma));
  $('#consolas').hidden = estado.plataforma !== 'switch';
  document.querySelectorAll('[data-consola]').forEach(b => b.setAttribute('aria-pressed', b.dataset.consola === estado.consola));
  if (estado.pestana === 'novedades') pintarNovedades(); else pintarComparar();
}

function repintarConservandoBusqueda() {
  const enfocado = document.activeElement?.id === 'buscar';
  const pos = enfocado ? document.activeElement.selectionStart : 0;
  pintar();
  if (enfocado) { const c = $('#buscar'); c.focus(); c.setSelectionRange(pos, pos); }
}

function abrirEneba(e) {
  const linea = e.target.closest('[data-eneba]');
  if (!linea) return false;
  e.preventDefault();
  window.open(linea.dataset.eneba, '_blank', 'noopener');
  return true;
}

document.addEventListener('keydown', e => { if (e.key === 'Enter') abrirEneba(e); });

document.addEventListener('click', e => {
  if (abrirEneba(e)) return;
  const b = e.target.closest('button, tr[data-atras]');
  if (!b) return;
  const d = b.dataset;
  if (d.pestana) estado.pestana = d.pestana;
  else if (d.plataforma) { estado.plataforma = d.plataforma; estado.visibles = estado.visiblesComparar = POR_PAGINA; }
  else if ('consola' in d) estado.consola = d.consola;
  else if ('mes' in d) { estado.mes = d.mes; estado.visibles = POR_PAGINA; }
  else if ('mesComparar' in d) estado.mesComparar = d.mesComparar;
  else if ('atras' in d) { estado.atras = +d.atras; estado.visiblesComparar = POR_PAGINA; }
  else if (b.id === 'mas-novedades') estado.visibles += POR_PAGINA;
  else if (b.id === 'mas-comparar') estado.visiblesComparar += POR_PAGINA;
  else return;
  guardar();
  pintar();
});

document.addEventListener('input', e => {
  if (e.target.id !== 'buscar') return;
  estado.busqueda = e.target.value;
  estado.visibles = estado.visiblesComparar = POR_PAGINA;
  repintarConservandoBusqueda();
});

document.addEventListener('change', e => {
  if (e.target.id === 'orden') estado.orden = e.target.value;
  else if (e.target.id === 'orden-comparar') estado.ordenComparar = e.target.value;
  else return;
  guardar();
  pintar();
});

// ---------- tema claro / oscuro ----------

function rotularTema() {
  const oscuro = document.documentElement.dataset.tema === 'oscuro';
  const texto = oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
  $('#tema').setAttribute('aria-label', texto);
  $('#tema').title = texto;
}
$('#tema').addEventListener('click', () => {
  const oscuro = document.documentElement.dataset.tema !== 'oscuro';
  if (oscuro) document.documentElement.dataset.tema = 'oscuro';
  else delete document.documentElement.dataset.tema;
  try { localStorage.setItem('noseasbobo.tema', oscuro ? 'oscuro' : 'claro'); } catch (e) { /* sin almacenamiento */ }
  rotularTema();
});
rotularTema();

// ---------- arranque ----------

// El enlace dice pestaña y plataforma: #comparar/switch
for (const parte of location.hash.slice(1).split('/')) {
  if (parte === 'novedades' || parte === 'comparar') estado.pestana = parte;
  if (parte === 'steam' || parte === 'switch') estado.plataforma = parte;
}
if (!(estado.atras >= 1 && estado.atras <= DATOS.anios_atras)) estado.atras = 1;
if (!ORDENES[estado.orden]) estado.orden = 'popular';
if (!ORDENES[estado.ordenComparar]) estado.ordenComparar = 'ahorro';
$('#actualizado').textContent = DATOS.generado
  ? `Actualizado: ${fechaCorta(DATOS.hoy)}${DATOS.fallos?.length ? ' · hoy no respondió ' + DATOS.fallos.join(' ni ') + ' (datos del día anterior)' : ''}`
  : 'Sin datos: ejecuta py actualizar.py';
pintar();
