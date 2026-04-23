"""
procesar.py — Orquestador principal de /condensar-contenido
============================================================
100% programático. 0 tokens LLM. Sin intervención de agentes IA.

Escanea una carpeta, transcribe audio/video y extrae texto de documentos,
generando archivos .md con el contenido ÍNTEGRO (sin resúmenes ni reinterpretaciones).

Uso:
    python procesar.py "<ruta_carpeta>"
    python procesar.py "<ruta_carpeta>" --lang es --model small
"""
import sys
import io
import os
import time
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Forzar UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

SKILL_DIR = Path(__file__).parent.resolve()

# ─── Extensiones ─────────────────────────────────────────────────────────────
AUDIO_EXT = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma', '.aac',
             '.mp2', '.opus', '.aiff', '.au'}
VIDEO_EXT = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.webm', '.flv',
             '.ts', '.mts', '.m4v', '.3gp'}
AV_EXT = AUDIO_EXT | VIDEO_EXT

DOC_EXT = {'.pdf', '.docx', '.pptx', '.xlsx', '.xls'}

# Extensiones que se ignoran (no son procesables)
IGNORAR_EXT = {'.md', '.txt', '.jpg', '.jpeg', '.png', '.gif', '.bmp',
               '.svg', '.ico', '.zip', '.rar', '.7z', '.tar', '.gz',
               '.exe', '.dll', '.bat', '.sh', '.py', '.json', '.xml',
               '.csv', '.log', '.ini', '.cfg', '.yaml', '.yml'}


def separador(char='═', ancho=56):
    return char * ancho


def descubrir_archivos(carpeta: Path):
    """Escanea la carpeta y clasifica archivos en pendientes/omitidos."""
    todos = sorted(p for p in carpeta.rglob('*') if p.is_file())

    av_pendientes = []
    av_omitidos = []
    doc_pendientes = []
    doc_omitidos = []
    ignorados = []

    for archivo in todos:
        ext = archivo.suffix.lower()

        if ext in AV_EXT:
            # Audio/video → verificar si ya existe _transcripcion.md
            transcripcion = archivo.parent / f"{archivo.stem}_transcripcion.md"
            if transcripcion.exists():
                av_omitidos.append(archivo)
            else:
                av_pendientes.append(archivo)

        elif ext in DOC_EXT:
            # Documento → verificar si ya existe _extraido.md
            extraido = archivo.parent / f"{archivo.stem}_extraido.md"
            if extraido.exists():
                doc_omitidos.append(archivo)
            else:
                doc_pendientes.append(archivo)

        else:
            ignorados.append(archivo)

    return av_pendientes, av_omitidos, doc_pendientes, doc_omitidos, ignorados


def transcribir_carpeta(archivos_av: list, modelo: str, idioma: str):
    """Transcribe archivos de audio/video usando transcribir.py.

    Agrupa por carpeta para llamar al transcriptor una vez por carpeta.
    """
    if not archivos_av:
        return 0, []

    transcribir_py = SKILL_DIR / "transcribir.py"
    if not transcribir_py.exists():
        print(f"  ERROR: No se encontró {transcribir_py}", file=sys.stderr)
        return 0, [("transcribir.py", "Script no encontrado")]

    # Agrupar por carpeta padre
    por_carpeta: dict[Path, list[Path]] = {}
    for archivo in archivos_av:
        carpeta = archivo.parent
        por_carpeta.setdefault(carpeta, []).append(archivo)

    exitosos = 0
    errores = []

    for carpeta, archivos in por_carpeta.items():
        print(f"\n  Transcribiendo {len(archivos)} archivo(s) en: {carpeta.name}/")

        cmd = [sys.executable, str(transcribir_py), str(carpeta),
               '--model', modelo]
        if idioma:
            cmd.extend(['--lang', idioma])

        try:
            resultado = subprocess.run(
                cmd,
                capture_output=False,
                text=True,
                timeout=7200  # 2 horas máximo por carpeta
            )
            if resultado.returncode == 0:
                exitosos += len(archivos)
            else:
                errores.append((carpeta.name, f"Exit code {resultado.returncode}"))
        except subprocess.TimeoutExpired:
            errores.append((carpeta.name, "Timeout (2h)"))
        except Exception as e:
            errores.append((carpeta.name, str(e)))

    return exitosos, errores


def extraer_y_guardar(archivo: Path) -> tuple[bool, str]:
    """Extrae texto de un documento y lo guarda como _extraido.md.

    Retorna (éxito, mensaje).
    El contenido se preserva ÍNTEGRO — sin resúmenes ni modificaciones.
    """
    extraer_py = SKILL_DIR / "condensar_extraer.py"

    try:
        resultado = subprocess.run(
            [sys.executable, str(extraer_py), str(archivo)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300  # 5 minutos máximo por archivo
        )

        if resultado.returncode != 0:
            error_msg = resultado.stderr.strip() or f"Exit code {resultado.returncode}"
            return False, error_msg

        texto = resultado.stdout

        # Quitar la línea de metadatos (PAGINAS:N o HOJAS:N) si existe
        lineas = texto.split('\n', 1)
        if lineas[0].startswith('PAGINAS:') or lineas[0].startswith('HOJAS:'):
            texto = lineas[1] if len(lineas) > 1 else ''

        if not texto.strip():
            return False, "No se extrajo texto"

        # Guardar como _extraido.md en la misma carpeta
        salida = archivo.parent / f"{archivo.stem}_extraido.md"
        contenido = f"# {archivo.name}\n\n{texto}"
        salida.write_text(contenido, encoding='utf-8')

        return True, str(salida.name)

    except subprocess.TimeoutExpired:
        return False, "Timeout (5min)"
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(
        description='Procesa una carpeta: transcribe audio/video y extrae texto de documentos a .md',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python procesar.py "D:/Facultad/Materia"
  python procesar.py "D:/Facultad/Materia" --lang es
  python procesar.py "D:/Facultad/Materia" --model medium --lang es

Todo el procesamiento es 100%% local. No se consumen tokens LLM.
Los archivos .md generados contienen el texto ÍNTEGRO del original.
        """
    )
    parser.add_argument('carpeta', help='Ruta a la carpeta con los archivos')
    parser.add_argument('--model', '-m', default='small',
                        choices=['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3'],
                        help='Modelo Whisper para transcripción (default: small)')
    parser.add_argument('--lang', '-l', default='es',
                        help='Idioma para transcripción (default: es)')

    args = parser.parse_args()
    carpeta = Path(args.carpeta)

    if not carpeta.exists():
        print(f"ERROR: Carpeta no encontrada: {carpeta}", file=sys.stderr)
        sys.exit(1)

    if not carpeta.is_dir():
        print(f"ERROR: No es un directorio: {carpeta}", file=sys.stderr)
        sys.exit(1)

    t_inicio = time.time()

    # ═══ FASE 0: DESCUBRIMIENTO ═══
    print(f"\n{separador()}")
    print(f"PROCESANDO: {carpeta}")
    print(separador())

    av_pend, av_omit, doc_pend, doc_omit, ignorados = descubrir_archivos(carpeta)

    total_pendientes = len(av_pend) + len(doc_pend)
    total_omitidos = len(av_omit) + len(doc_omit)

    print(f"Archivos encontrados: {total_pendientes + total_omitidos + len(ignorados)}")
    print(f"  ↳ PENDIENTES:   {total_pendientes}")
    print(f"     Audio/Video: {len(av_pend)}")
    print(f"     Documentos:  {len(doc_pend)}")
    print(f"  ↳ OMITIDOS:     {total_omitidos} (ya tienen .md)")
    print(f"  ↳ IGNORADOS:    {len(ignorados)} (extensiones no procesables)")

    if total_pendientes == 0:
        print(f"\n✓ No hay archivos pendientes de procesar.")
        print(separador())
        sys.exit(0)

    if av_pend:
        print(f"\nAudio/Video pendientes:")
        for a in av_pend:
            print(f"  [{'AUDIO' if a.suffix.lower() in AUDIO_EXT else 'VIDEO'}] {a.relative_to(carpeta)}")

    if doc_pend:
        print(f"\nDocumentos pendientes:")
        for a in doc_pend:
            print(f"  [{a.suffix.upper().strip('.')}]  {a.relative_to(carpeta)}")

    print(separador())

    # ═══ FASE 1: TRANSCRIPCIÓN ═══
    av_exitosos = 0
    av_errores = []
    if av_pend:
        print(f"\n{'─'*56}")
        print(f"FASE 1: TRANSCRIPCIÓN DE AUDIO/VIDEO ({len(av_pend)} archivos)")
        print(f"{'─'*56}")
        av_exitosos, av_errores = transcribir_carpeta(av_pend, args.model, args.lang)

    # ═══ FASE 2: EXTRACCIÓN DE DOCUMENTOS ═══
    doc_exitosos = 0
    doc_errores = []
    detalle_docs = []
    if doc_pend:
        print(f"\n{'─'*56}")
        print(f"FASE 2: EXTRACCIÓN DE TEXTO ({len(doc_pend)} archivos)")
        print(f"{'─'*56}")

        for i, archivo in enumerate(doc_pend, 1):
            nombre_rel = archivo.relative_to(carpeta)
            print(f"\n  [{i}/{len(doc_pend)}] {nombre_rel}")

            ok, msg = extraer_y_guardar(archivo)
            if ok:
                doc_exitosos += 1
                detalle_docs.append((archivo.name, msg))
                print(f"         → {msg}")
            else:
                doc_errores.append((archivo.name, msg))
                print(f"         ✗ ERROR: {msg}")

    # ═══ REPORTE FINAL ═══
    t_total = time.time() - t_inicio
    minutos = int(t_total // 60)
    segundos = int(t_total % 60)

    todos_errores = av_errores + doc_errores

    print(f"\n{separador()}")
    print(f"RESUMEN")
    print(f"Tiempo total: {minutos}m {segundos}s")
    print(separador())
    print(f"Transcripciones (audio/video):  {av_exitosos}")
    print(f"Extracciones (documentos):      {doc_exitosos}")
    print(f"Omitidos (ya procesados):       {total_omitidos}")
    print(f"Errores:                        {len(todos_errores)}")

    if todos_errores:
        print(f"\nErrores:")
        for nombre, error in todos_errores:
            print(f"  ✗ {nombre}: {error}")

    if detalle_docs:
        print(f"\nDocumentos extraídos:")
        for original, salida in detalle_docs:
            print(f"  {original} → {salida}")

    print(separador())


if __name__ == '__main__':
    main()
