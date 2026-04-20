# -*- coding: utf-8 -*-
"""
Transcriptor de audio/video en lote - usando OpenAI Whisper
Genera archivos .md con el mismo nombre del archivo original + "_transcripcion"

Acepta una carpeta (procesa todos los archivos) o un archivo individual.

Uso desde Claude Code:
    python transcribir.py "C:/ruta/a/carpeta"
    python transcribir.py "C:/ruta/a/video.mp4"
    python transcribir.py "C:/ruta/a/carpeta" --model medium --lang es
"""

import sys
import io
# Forzar UTF-8 en la salida de la terminal (Windows)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import os
import re
from pathlib import Path
from datetime import datetime
import time

# Extensiones soportadas
EXTENSIONES_AUDIO = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma', '.aac', '.mp2', '.opus', '.aiff', '.au'}
EXTENSIONES_VIDEO = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.webm', '.flv', '.ts', '.mts', '.m4v', '.3gp'}
EXTENSIONES_SOPORTADAS = EXTENSIONES_AUDIO | EXTENSIONES_VIDEO


def formatear_tiempo(segundos):
    """Convierte segundos a formato HH:MM:SS"""
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def obtener_duracion(ruta_archivo):
    """Obtiene la duración del archivo en segundos usando ffprobe"""
    import subprocess
    try:
        resultado = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(ruta_archivo)],
            capture_output=True, text=True, timeout=30
        )
        return float(resultado.stdout.strip())
    except Exception:
        return None


def limpiar_texto(texto):
    """Limpia y normaliza el texto de un segmento"""
    texto = texto.strip()
    # Colapsar espacios múltiples
    texto = re.sub(r'\s+', ' ', texto)
    return texto


def formar_parrafos(segmentos, palabras_por_parrafo=70, brecha_silencio=1.8):
    """
    Agrupa segmentos de Whisper en párrafos narrativamente coherentes.

    Criterios para iniciar un nuevo párrafo:
    1. Pausa larga entre segmentos (silencio > brecha_silencio segundos)
       → indica cambio de tema o respiración larga del locutor
    2. El párrafo acumuló suficientes palabras Y el segmento actual termina en
       puntuación de cierre (.  !  ?)
       → corte natural de idea, sin partir oraciones a la mitad

    Resultado: lista de strings, cada uno es un párrafo completo.
    """
    if not segmentos:
        return []

    parrafos = []
    grupo_actual = []      # segmentos del párrafo en curso
    palabras_actuales = 0

    for i, seg in enumerate(segmentos):
        texto = limpiar_texto(seg.get('text', ''))
        if not texto:
            continue

        # --- Detectar señales de corte ---

        # 1) Pausa/silencio largo antes de este segmento
        romper_por_pausa = False
        if grupo_actual and i > 0:
            fin_anterior = segmentos[i - 1].get('end', seg.get('start', 0))
            inicio_actual = seg.get('start', 0)
            if (inicio_actual - fin_anterior) > brecha_silencio:
                romper_por_pausa = True

        # 2) Párrafo ya largo y el segmento previo cerró una oración
        termina_oracion = grupo_actual and grupo_actual[-1][-1] in '.!?\u2026'
        romper_por_longitud = palabras_actuales >= palabras_por_parrafo and termina_oracion

        # --- Ejecutar corte si corresponde ---
        if (romper_por_pausa or romper_por_longitud) and grupo_actual:
            parrafos.append(' '.join(grupo_actual))
            grupo_actual = []
            palabras_actuales = 0

        grupo_actual.append(texto)
        palabras_actuales += len(texto.split())

    # Volcar el último grupo
    if grupo_actual:
        parrafos.append(' '.join(grupo_actual))

    return parrafos


def guardar_markdown(ruta_salida, nombre_archivo, segmentos, duracion_total):
    """Guarda la transcripción como .md con texto en párrafos, sin marcas de tiempo"""
    parrafos = formar_parrafos(segmentos)

    lineas = []

    # Título y metadatos
    lineas.append(f'# Transcripción')
    lineas.append(f'')
    lineas.append(f'**{nombre_archivo}**')
    lineas.append(f'')
    meta_linea = [f'Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}']
    if duracion_total:
        meta_linea.append(f'Duración: {formatear_tiempo(duracion_total)}')
    meta_linea.append(f'Segmentos: {len(segmentos)}')
    lineas.append(f'*{" | ".join(meta_linea)}*')
    lineas.append(f'')
    lineas.append(f'---')
    lineas.append(f'')

    # Párrafos
    for texto_parrafo in parrafos:
        if not texto_parrafo.strip():
            continue
        lineas.append(texto_parrafo)
        lineas.append(f'')

    with open(str(ruta_salida), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lineas))


def transcribir_archivo(ruta_archivo, modelo, idioma=None, verbose=False):
    """Transcribe un único archivo y retorna los segmentos"""
    print(f"\n  Cargando audio...")
    duracion = obtener_duracion(ruta_archivo)
    if duracion:
        print(f"  Duración: {formatear_tiempo(duracion)}")

    print(f"  Transcribiendo...")
    inicio = time.time()

    kwargs = {
        'language': idioma,
        'verbose': verbose,
        'word_timestamps': False,
    }

    resultado = modelo.transcribe(str(ruta_archivo), **kwargs)

    elapsed = time.time() - inicio
    print(f"  Completado en {formatear_tiempo(elapsed)}")

    if hasattr(resultado, 'segments_to_dicts'):
        segmentos = resultado.segments_to_dicts()
    else:
        segmentos = resultado['segments']

    return segmentos, duracion


def procesar(entrada, nombre_modelo='small', idioma=None, verbose=False):
    """Procesa un archivo individual o todos los archivos de una carpeta"""
    entrada = Path(entrada)

    if not entrada.exists():
        print(f"ERROR: La ruta no existe: {entrada}")
        sys.exit(1)

    # Determinar lista de archivos a procesar
    if entrada.is_file():
        if entrada.suffix.lower() not in EXTENSIONES_SOPORTADAS:
            print(f"ERROR: Formato no soportado: {entrada.suffix}")
            sys.exit(1)
        archivos = [entrada]
    else:
        archivos = []
        for ext in EXTENSIONES_SOPORTADAS:
            archivos.extend(entrada.glob(f'*{ext}'))
            archivos.extend(entrada.glob(f'*{ext.upper()}'))
        archivos = sorted(set(archivos))

    if not archivos:
        print(f"No se encontraron archivos de audio/video.")
        return

    print(f"\n{'='*60}")
    print(f"TRANSCRIPTOR DE AUDIO/VIDEO - Whisper ({nombre_modelo})")
    print(f"{'='*60}")
    print(f"Archivos a procesar: {len(archivos)}")
    if idioma:
        print(f"Idioma: {idioma}")
    else:
        print(f"Idioma: auto-detección")
    print(f"{'='*60}\n")

    # Cargar modelo (una sola vez para todos los archivos)
    print(f"Cargando modelo Whisper '{nombre_modelo}'...")
    import stable_whisper
    modelo = stable_whisper.load_model(nombre_modelo)
    print("Modelo cargado.\n")

    exitosos = 0
    fallidos = []

    for i, archivo in enumerate(archivos, 1):
        print(f"[{i}/{len(archivos)}] {archivo.name}")
        print(f"  Tamaño: {archivo.stat().st_size / (1024*1024):.1f} MB")

        ruta_salida = archivo.parent / f"{archivo.stem}_transcripcion.md"

        if ruta_salida.exists():
            print(f"  SALTANDO: ya existe {ruta_salida.name}")
            exitosos += 1
            continue

        try:
            segmentos, duracion = transcribir_archivo(archivo, modelo, idioma, verbose)

            print(f"  Formando párrafos y guardando markdown...")
            guardar_markdown(ruta_salida, archivo.name, segmentos, duracion)
            print(f"  Guardado: {ruta_salida.name}")
            exitosos += 1

        except KeyboardInterrupt:
            print("\n\nInterrumpido por el usuario.")
            break
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            fallidos.append((archivo.name, str(e)))

    # Resumen
    print(f"\n{'='*60}")
    print(f"RESUMEN")
    print(f"{'='*60}")
    print(f"Completados: {exitosos}/{len(archivos)}")
    if fallidos:
        print(f"Fallidos ({len(fallidos)}):")
        for nombre, error in fallidos:
            print(f"  - {nombre}: {error}")
    carpeta_salida = archivos[0].parent if archivos else entrada
    print(f"Archivos en: {carpeta_salida}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Transcribe archivos de audio/video a .md usando Whisper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python transcribir.py "C:/Videos"
  python transcribir.py "C:/Videos/clase.mp4"
  python transcribir.py "C:/Videos" --model medium --lang es
  python transcribir.py "C:/Videos" --verbose

Modelos (velocidad vs. precision):
  small  - RECOMENDADO (~462 MB)
  medium - mas preciso, mas lento (~1.5 GB)
  large  - maxima precision, muy lento (~3 GB)
        """
    )

    parser.add_argument(
        'entrada',
        help='Ruta a una carpeta o a un archivo de audio/video'
    )
    parser.add_argument(
        '--model', '-m',
        default='small',
        choices=['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3'],
        help='Modelo Whisper (default: small)'
    )
    parser.add_argument(
        '--lang', '-l',
        default=None,
        help='Idioma (ej: es, en, fr). Sin esto se auto-detecta.'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Mostrar texto mientras se transcribe'
    )

    args = parser.parse_args()
    procesar(args.entrada, args.model, args.lang, args.verbose)


if __name__ == '__main__':
    main()
