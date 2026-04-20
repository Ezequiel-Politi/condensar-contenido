"""
condensar_inventario.py
Fase 0 del skill /condensar-contenido — 100% local, 0 tokens LLM.

Uso:
    python condensar_inventario.py "<CARPETA_MATERIA>" "<VAULT_RAIZ>"

Salida: JSON con estructura del plan de trabajo.
"""
import sys
import os
import json
import re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ─── Extensiones ─────────────────────────────────────────────────────────────
AUDIO_EXT = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma', '.aac',
             '.mp2', '.opus', '.aiff', '.au'}
VIDEO_EXT = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.webm', '.flv',
             '.ts', '.mts', '.m4v', '.3gp'}
AV_EXT = AUDIO_EXT | VIDEO_EXT

IGNORAR_NOMBRES = {'cronograma', 'programa', 'guia de actividades',
                   'guía de actividades', 'glosario'}

LIBRO_NOMBRES = {'cap', 'capítulo', 'capitulo', 'chapter', 'kotler', 'keller'}
FRAMEWORK_NOMBRES = {'pestel', 'foda', 'porter', 'bcg', 'ansoff', 'canvas', 'swot'}
PAPER_NOMBRES = {'case', 'hbr'}
PAPER_REGEX = re.compile(r'(^s-\d|^[a-z]-\d|\bcase\b|hbr)', re.IGNORECASE)

# ─── Helpers ─────────────────────────────────────────────────────────────────
def slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[áàä]', 'a', text)
    text = re.sub(r'[éèë]', 'e', text)
    text = re.sub(r'[íìï]', 'i', text)
    text = re.sub(r'[óòö]', 'o', text)
    text = re.sub(r'[úùü]', 'u', text)
    text = re.sub(r'[ñ]', 'n', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def clasificar(path: Path, all_names_in_folder: set) -> str:
    """Clasifica un archivo por nombre/ruta/tamaño. Nunca lee su contenido."""
    ext = path.suffix.lower()
    name_lower = path.stem.lower()
    parts_lower = [p.lower() for p in path.parts]

    # IGNORAR: audio/video
    if ext in AV_EXT:
        return 'IGNORAR_AV'

    # IGNORAR: .pptx con .pdf equivalente
    if ext == '.pptx':
        pdf_equiv = path.with_suffix('.pdf').name
        if pdf_equiv in all_names_in_folder:
            return 'IGNORAR'

    # IGNORAR: por nombre
    for patron in IGNORAR_NOMBRES:
        if patron in name_lower:
            return 'IGNORAR'

    # Tipo A — Cápsula
    capsulas_path = any('capsulas' in p or 'cápsulas' in p for p in parts_lower)
    if capsulas_path and ext in {'.docx', '.md'}:
        return 'A'

    # Tipo B — Clase en vivo
    clase_vivo_path = any('clase en vivo' in p or 'clase en vivo' in p for p in parts_lower)
    if clase_vivo_path and ext in {'.docx', '.md'}:
        return 'B'

    # Transcripciones generadas
    if ext == '.md' and name_lower.endswith('_transcripcion'):
        if capsulas_path:
            return 'A'
        if clase_vivo_path:
            return 'B'

    # Tipos C / D / E para PDFs
    if ext == '.pdf':
        # Tipo E — Framework
        for kw in FRAMEWORK_NOMBRES:
            if kw in name_lower:
                return 'E'
        # Tipo C — Capítulo
        for kw in LIBRO_NOMBRES:
            if kw in name_lower:
                return 'C'
        # Tipo D — Paper
        if PAPER_REGEX.search(path.stem):
            return 'D'
        # Por tamaño: >2MB → C
        try:
            if path.stat().st_size > 2 * 1024 * 1024:
                return 'C'
        except OSError:
            pass
        return 'D'

    # .pptx sin PDF equivalente → D
    if ext == '.pptx':
        return 'D'

    return 'IGNORAR'


def nombre_output(path: Path, tipo: str, clase_n: int) -> str:
    stem = slug(path.stem.replace('_transcripcion', ''))
    if tipo == 'A':
        return f'capsula_{stem}.md'
    if tipo == 'B':
        return f'clase-en-vivo_clase-{clase_n}_{stem}.md'
    if tipo == 'C':
        # intentar extraer autor del nombre
        autor = path.stem.split('_')[0].lower() if '_' in path.stem else slug(path.stem[:10])
        return f'{slug(autor)}_{stem}.md'
    if tipo == 'D':
        return f'{stem}.md'
    if tipo == 'E':
        return f'framework_{stem}.md'
    return f'{stem}.md'


def extraer_clase_n(path: Path, carpeta_materia: Path) -> int:
    """Infiere el número de clase desde la subcarpeta."""
    try:
        rel = path.relative_to(carpeta_materia)
        for part in rel.parts:
            m = re.search(r'(\d+)', part)
            if m:
                return int(m.group(1))
    except ValueError:
        pass
    return 1


def descubrir_vault(carpeta_materia: Path, vault_raiz: Path):
    """Encuentra la subcarpeta del vault que corresponde a la materia."""
    nombre_materia_arg = carpeta_materia.name

    if not vault_raiz.exists():
        return nombre_materia_arg, vault_raiz / nombre_materia_arg

    # Buscar coincidencia exacta primero
    candidata_exacta = vault_raiz / nombre_materia_arg
    if candidata_exacta.exists():
        return nombre_materia_arg, candidata_exacta

    # Buscar por similitud (normalizar y comparar)
    slug_arg = slug(nombre_materia_arg)
    for d in vault_raiz.iterdir():
        if d.is_dir() and slug(d.name) == slug_arg:
            return d.name, d

    # Buscar subcarpetas un nivel más profundo (ej: MiM/01- Gestión...)
    slug_arg_words = set(slug_arg.split('-'))
    best_match = None
    best_score = 0
    for subdir in vault_raiz.rglob('*/'):
        if subdir.is_dir():
            slug_sub = slug(subdir.name)
            sub_words = set(slug_sub.split('-'))
            score = len(slug_arg_words & sub_words)
            if score > best_score and score >= max(2, len(slug_arg_words) // 2):
                best_score = score
                best_match = subdir

    if best_match:
        return best_match.name, best_match

    # Fallback: crear en vault_raiz / nombre original
    return nombre_materia_arg, vault_raiz / nombre_materia_arg


def build_ya_en_vault(ruta_vault: Path) -> set:
    """Lista nombres de archivo .md en el vault (sin extensión)."""
    if not ruta_vault.exists():
        return set()
    return {p.stem for p in ruta_vault.rglob('*.md')}


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Uso: condensar_inventario.py <CARPETA_MATERIA> <VAULT_RAIZ>'}))
        sys.exit(1)

    carpeta_materia = Path(sys.argv[1])
    vault_raiz = Path(sys.argv[2])

    if not carpeta_materia.exists():
        print(json.dumps({'error': f'Carpeta no encontrada: {carpeta_materia}'}))
        sys.exit(1)

    # Descubrir vault
    nombre_materia, ruta_vault = descubrir_vault(carpeta_materia, vault_raiz)
    slug_materia = slug(nombre_materia)

    # YA_EN_VAULT
    ya_en_vault = build_ya_en_vault(ruta_vault)

    # Escanear fuentes
    archivos_fuente = [p for p in carpeta_materia.rglob('*') if p.is_file()]

    pendientes = []
    omitidos = []
    ignorados = []

    for archivo in sorted(archivos_fuente):
        all_names_in_folder = {f.name for f in archivo.parent.iterdir() if f.is_file()}
        tipo = clasificar(archivo, all_names_in_folder)

        if tipo.startswith('IGNORAR'):
            ignorados.append(str(archivo))
            continue

        clase_n = extraer_clase_n(archivo, carpeta_materia)
        output_name = nombre_output(archivo, tipo, clase_n)
        output_stem = output_name.replace('.md', '')

        if output_stem in ya_en_vault:
            omitidos.append({
                'archivo': str(archivo),
                'tipo': tipo,
                'output': output_name,
                'clase_n': clase_n,
                'motivo': 'ya en vault'
            })
        else:
            pendientes.append({
                'archivo': str(archivo),
                'tipo': tipo,
                'output': output_name,
                'output_path': str(ruta_vault / f'Clase {clase_n}' / output_name),
                'clase_n': clase_n,
                'extension': archivo.suffix.lower()
            })

    resultado = {
        'nombre_materia': nombre_materia,
        'slug_materia': slug_materia,
        'ruta_vault': str(ruta_vault),
        'carpeta_materia': str(carpeta_materia),
        'ya_en_vault': sorted(list(ya_en_vault)),
        'pendientes': pendientes,
        'omitidos': omitidos,
        'ignorados_count': len(ignorados),
        'stats': {
            'total_fuente': len(archivos_fuente),
            'pendientes': len(pendientes),
            'omitidos': len(omitidos),
            'ignorados': len(ignorados)
        }
    }

    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
