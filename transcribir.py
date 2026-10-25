# -*- coding: utf-8 -*-
"""
Transcriptor de audio/video en lote (faster-whisper, local).

Acepta una o varias carpetas y/o archivos sueltos, arma una única cola
ordenada de menor a mayor duración y deja cada <nombre>_transcripcion.md
junto a su original.

Uso:
    python transcribir.py "D:/Clases/Mod1" "E:/Otros/video.mp4" "F:/Mod2"
    python transcribir.py "D:/Clases" --dry-run
    python transcribir.py "D:/Clases" --model medium --lang es --no-docente
"""

import sys
import io
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import re
import shutil
import subprocess
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

# ── Configuración ────────────────────────────────────────────────────────────
EXT_AUDIO = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma', '.aac', '.mp2', '.opus', '.aiff', '.au'}
EXT_VIDEO = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.webm', '.flv', '.ts', '.mts', '.m4v', '.3gp'}
EXTENSIONES = EXT_AUDIO | EXT_VIDEO

TEMP_DIR = Path(r'C:\Temp\transcripcion_temp')   # disco local: evita cuelgues con Drive/red
UMBRAL_MIN = 20                                  # < umbral: MODELO_CORTO, >= umbral: MODELO_LARGO
MODELO_CORTO = 'small'
MODELO_LARGO = 'medium'
NOMBRE_MENCION = 'Ezequiel'                      # se resalta en **negrita**
GLOSARIO = 'glosario.txt'                        # un término por línea; '#' comenta
ETIQUETA_DOCENTE = '**Docente:**'
UMBRAL_CLUSTER = 0.30                            # distancia coseno entre voces del mismo hablante
DOMINANCIA_MIN = 0.40                            # el docente debe tener >= 40% del habla


# ── Utilidades ───────────────────────────────────────────────────────────────
def fmt_tiempo(seg):
    seg = int(seg)
    return f"{seg // 3600:02d}:{(seg % 3600) // 60:02d}:{seg % 60:02d}"


def duracion(ruta):
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(ruta)],
            capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except Exception:
        return None


def salida_de(archivo):
    return archivo.parent / f"{archivo.stem}_transcripcion.md"


# ── Cola de trabajo ──────────────────────────────────────────────────────────
def juntar_archivos(rutas):
    """Devuelve (items, errores). item = dict(archivo, raiz, orden)."""
    items, vistos, errores = [], set(), []
    for orden, r in enumerate(rutas):
        p = Path(r)
        if not p.exists():
            errores.append(f"No existe: {p}")
            continue
        if p.is_file():
            if p.suffix.lower() not in EXTENSIONES:
                errores.append(f"Formato no soportado: {p}")
                continue
            candidatos, raiz = [p], p.parent
        else:
            candidatos = sorted(f for f in p.rglob('*') if f.is_file() and f.suffix.lower() in EXTENSIONES)
            raiz = p
        for f in candidatos:
            clave = str(f.resolve()).lower()
            if clave in vistos:
                continue
            vistos.add(clave)
            items.append({'archivo': f, 'raiz': raiz, 'orden': orden})
    return items, errores


def armar_plan(items):
    """Separa pendientes de salteados y ordena pendientes por duración (estable)."""
    pendientes, salteados = [], []
    for it in items:
        if salida_de(it['archivo']).exists():
            salteados.append(it)
        else:
            it['dur'] = duracion(it['archivo']) or 0
            pendientes.append(it)
    pendientes.sort(key=lambda x: (x['dur'], x['orden']))
    return pendientes, salteados


def mostrar_plan(pendientes, salteados, modelo_forzado):
    por_carpeta = OrderedDict()
    for it in pendientes + salteados:
        por_carpeta.setdefault(str(it['archivo'].parent), [0, 0])
    for it in pendientes:
        por_carpeta[str(it['archivo'].parent)][0] += 1
    for it in salteados:
        por_carpeta[str(it['archivo'].parent)][1] += 1

    print("\n" + "=" * 60)
    print("PLAN DE TRABAJO")
    print("=" * 60)
    print(f"Pendientes: {len(pendientes)} | Salteados (ya transcriptos): {len(salteados)}")
    for carpeta, (pend, salt) in por_carpeta.items():
        print(f"  {carpeta}: {pend} pendientes, {salt} salteados")
    if pendientes:
        total = sum(i['dur'] for i in pendientes)
        print(f"\nOrden (menor a mayor duración) — total {fmt_tiempo(total)} de audio:")
        for n, it in enumerate(pendientes, 1):
            print(f"  {n:>3}. [{fmt_tiempo(it['dur'])}] {modelo_para(it['dur'], modelo_forzado):<6} {it['archivo']}")
    print("=" * 60, flush=True)


def modelo_para(dur, forzado):
    if forzado:
        return forzado
    return MODELO_LARGO if dur >= UMBRAL_MIN * 60 else MODELO_CORTO


# ── Glosario ─────────────────────────────────────────────────────────────────
def leer_glosario(archivo, raiz):
    """Busca glosario.txt desde la carpeta del archivo hacia arriba hasta la raíz pasada."""
    carpeta = archivo.parent
    while True:
        g = carpeta / GLOSARIO
        if g.is_file():
            try:
                terminos = [l.strip() for l in g.read_text(encoding='utf-8').splitlines()
                            if l.strip() and not l.strip().startswith('#')]
                return terminos
            except Exception:
                return []
        if carpeta == raiz or carpeta.parent == carpeta:
            return []
        carpeta = carpeta.parent


def prompt_glosario(terminos):
    if not terminos:
        return None
    txt = "Glosario: " + ", ".join(terminos)
    return txt[:600]


# ── Docente (hablante dominante) ─────────────────────────────────────────────
def cargar_audio_16k(ruta):
    import numpy as np
    r = subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', str(ruta), '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
        capture_output=True, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace')[:200])
    return np.frombuffer(r.stdout, dtype=np.float32)


def marcar_docente(segmentos, ruta_audio):
    """
    Agrega seg['docente'] (bool) a cada segmento. Devuelve (ok, nota).
    El docente es el hablante con más tiempo de habla.
    """
    import numpy as np
    from resemblyzer import VoiceEncoder
    from scipy.cluster.hierarchy import linkage, fcluster

    wav = cargar_audio_16k(ruta_audio)
    sr = 16000
    enc = VoiceEncoder('cpu', verbose=False)

    idx, embs, durs = [], [], []
    for i, s in enumerate(segmentos):
        d = s['end'] - s['start']
        if d < 1.0:
            continue
        a, b = int(s['start'] * sr), int(s['end'] * sr)
        trozo = wav[a:b]
        if len(trozo) < sr:
            continue
        embs.append(enc.embed_utterance(trozo))
        idx.append(i)
        durs.append(d)

    if len(embs) < 3:
        return False, "muy poco habla para identificar hablantes"

    E = np.array(embs)
    durs = np.array(durs)
    if len(E) == 1:
        etiquetas = np.array([1])
    else:
        Z = linkage(E, method='average', metric='cosine')
        etiquetas = fcluster(Z, t=UMBRAL_CLUSTER, criterion='distance')

    tiempos = {c: durs[etiquetas == c].sum() for c in set(etiquetas)}
    if len(tiempos) == 1:
        return False, "se detectó un solo hablante: sin etiquetas"
    docente = max(tiempos, key=tiempos.get)
    share = tiempos[docente] / durs.sum()
    if share < DOMINANCIA_MIN:
        return False, f"sin hablante dominante claro ({share:.0%} del habla): sin etiquetas"

    centroide = E[etiquetas == docente].mean(axis=0)
    centroide /= np.linalg.norm(centroide)
    es_doc = {}
    for k, i in enumerate(idx):
        es_doc[i] = bool(etiquetas[k] == docente)

    # Segmentos cortos: heredan el hablante del segmento anterior
    previo = False
    for i, s in enumerate(segmentos):
        previo = es_doc.get(i, previo)
        s['docente'] = previo
    return True, f"docente = {share:.0%} del habla, {len(tiempos)} voces"


# ── Markdown ─────────────────────────────────────────────────────────────────
def limpiar(t):
    return re.sub(r'\s+', ' ', t.strip())


def formar_parrafos(segmentos, con_docente, palabras_por_parrafo=70, brecha_silencio=1.8):
    """Devuelve lista de (es_docente, texto). Corta por pausa, longitud o cambio de hablante."""
    parrafos, grupo, palabras, doc_actual = [], [], 0, False
    prev_end = None
    for seg in segmentos:
        texto = limpiar(seg['text'])
        if not texto:
            continue
        doc = bool(seg.get('docente')) if con_docente else False

        romper = False
        if grupo:
            if prev_end is not None and (seg['start'] - prev_end) > brecha_silencio:
                romper = True
            elif palabras >= palabras_por_parrafo and grupo[-1][-1] in '.!?\u2026':
                romper = True
            elif con_docente and doc != doc_actual:
                romper = True
        if romper:
            parrafos.append((doc_actual, ' '.join(grupo)))
            grupo, palabras = [], 0

        if not grupo:
            doc_actual = doc
        grupo.append(texto)
        palabras += len(texto.split())
        prev_end = seg['end']
    if grupo:
        parrafos.append((doc_actual, ' '.join(grupo)))
    return parrafos


def resaltar_mencion(texto):
    return re.sub(rf'\b({re.escape(NOMBRE_MENCION)})\b', r'**\1**', texto, flags=re.IGNORECASE)


def guardar_md(destino, nombre, segmentos, dur, modelo, con_docente):
    lineas = ['# Transcripción', '', f'**{nombre}**', '']
    meta = [f'Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}']
    if dur:
        meta.append(f'Duración: {fmt_tiempo(dur)}')
    meta.append(f'Modelo: {modelo}')
    lineas += [f'*{" | ".join(meta)}*', '', '---', '']
    for es_doc, texto in formar_parrafos(segmentos, con_docente):
        texto = resaltar_mencion(texto)
        lineas.append(f'{ETIQUETA_DOCENTE} {texto}' if es_doc else texto)
        lineas.append('')
    destino.write_text('\n'.join(lineas), encoding='utf-8')


# ── Transcripción ────────────────────────────────────────────────────────────
_modelos = {}


def cargar_modelo(nombre):
    if nombre not in _modelos:
        from faster_whisper import WhisperModel
        print(f"Cargando modelo '{nombre}' (la primera vez se descarga)...", flush=True)
        _modelos[nombre] = WhisperModel(nombre, device='cpu', compute_type='int8')
    return _modelos[nombre]


def transcribir(modelo, ruta, idioma, prompt, dur_total):
    gen, info = modelo.transcribe(
        str(ruta), language=idioma, initial_prompt=prompt,
        vad_filter=True, condition_on_previous_text=False, word_timestamps=False)
    total = dur_total or info.duration or 0
    segmentos, ultimo = [], -1
    for s in gen:
        segmentos.append({'start': s.start, 'end': s.end, 'text': s.text})
        if total:
            pct = min(100, int(s.end / total * 100))
            if pct >= ultimo + 5 or pct == 100:
                ultimo = pct
                print(f"    {pct:>3}%", flush=True)
    return segmentos


def procesar_item(it, n, total, args):
    archivo = it['archivo']
    dur = it['dur']
    nombre_modelo = modelo_para(dur, args.model)
    print(f"\n[{n}/{total}] {archivo.name}  ({fmt_tiempo(dur)}, modelo {nombre_modelo})", flush=True)

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    local = TEMP_DIR / f"{n}{archivo.suffix.lower()}"
    t0 = time.time()
    try:
        shutil.copy2(archivo, local)
        modelo = cargar_modelo(nombre_modelo)
        terminos = leer_glosario(archivo, it['raiz'])
        if terminos:
            print(f"  Glosario: {len(terminos)} términos", flush=True)
        segmentos = transcribir(modelo, local, args.lang, prompt_glosario(terminos), dur)

        con_docente, nota = False, None
        if not args.no_docente and segmentos:
            print("  Identificando docente...", flush=True)
            try:
                con_docente, nota = marcar_docente(segmentos, local)
            except Exception as e:
                nota = f"no se pudo identificar al docente ({e})"
            print(f"  {nota}", flush=True)

        guardar_md(salida_de(archivo), archivo.name, segmentos, dur, nombre_modelo, con_docente)
        print(f"  Listo en {fmt_tiempo(time.time() - t0)}: {salida_de(archivo).name}", flush=True)
        return None, nota if not con_docente and nota else None
    except Exception as e:
        print(f"  ERROR: {e}", flush=True)
        return str(e), None
    finally:
        try:
            local.unlink(missing_ok=True)
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description='Transcribe audio/video a .md (local, faster-whisper)')
    ap.add_argument('rutas', nargs='+', help='Carpetas y/o archivos de audio/video')
    ap.add_argument('--model', '-m', default=None,
                    choices=['tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3'],
                    help=f'Fuerza un modelo (default: {MODELO_CORTO} < {UMBRAL_MIN} min <= {MODELO_LARGO})')
    ap.add_argument('--lang', '-l', default='es', help='Idioma (default: es)')
    ap.add_argument('--no-docente', action='store_true', help='No identificar al docente')
    ap.add_argument('--dry-run', action='store_true', help='Solo mostrar el plan')
    args = ap.parse_args()

    items, errores = juntar_archivos(args.rutas)
    for e in errores:
        print(f"AVISO: {e}")
    if not items:
        print("No se encontraron archivos de audio/video.")
        return

    pendientes, salteados = armar_plan(items)
    mostrar_plan(pendientes, salteados, args.model)
    if args.dry_run or not pendientes:
        return

    hechos, fallidos, avisos = [], [], []
    try:
        for n, it in enumerate(pendientes, 1):
            err, aviso = procesar_item(it, n, len(pendientes), args)
            if err:
                fallidos.append((it, err))
            else:
                hechos.append(it)
                if aviso:
                    avisos.append((it, aviso))
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    print("\n" + "=" * 60)
    print("RESUMEN POR CARPETA")
    print("=" * 60)
    resumen = OrderedDict()
    for it in hechos:
        resumen.setdefault(str(it['archivo'].parent), {'ok': 0, 'salt': 0, 'fail': 0})['ok'] += 1
    for it in salteados:
        resumen.setdefault(str(it['archivo'].parent), {'ok': 0, 'salt': 0, 'fail': 0})['salt'] += 1
    for it, _ in fallidos:
        resumen.setdefault(str(it['archivo'].parent), {'ok': 0, 'salt': 0, 'fail': 0})['fail'] += 1
    for carpeta, r in resumen.items():
        print(f"{carpeta}\n  completados: {r['ok']} | salteados: {r['salt']} | fallidos: {r['fail']}")
    for it, e in fallidos:
        print(f"  FALLÓ {it['archivo'].name}: {e}")
    for it, a in avisos:
        print(f"  AVISO {it['archivo'].name}: {a}")
    print("=" * 60)


if __name__ == '__main__':
    main()
