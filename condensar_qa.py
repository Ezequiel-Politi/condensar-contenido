"""
condensar_qa.py
QA mecánico de notas Obsidian — 100% local, 0 tokens LLM.

Verifica y corrige:
  1. Frontmatter YAML (campos obligatorios, slugs, tipo válido)
  2. Wikilinks rotos (los elimina y los reporta)
  3. Estructura (secciones obligatorias presentes)

Lo que NO hace (requiere LLM):
  - Completitud semántica de términos técnicos
  - Calidad del contenido

Uso:
    python condensar_qa.py "<vault_materia_dir>" "<slug_materia>" "<nombre_materia>" [archivo1.md archivo2.md ...]

    Si no se pasan archivos individuales, procesa TODOS los .md del vault_materia_dir.

Salida: JSON con reporte de correcciones.
"""
import sys
import os
import json
import re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

try:
    import yaml
except ImportError:
    os.system('pip install pyyaml -q')
    import yaml

# ─── Constantes ──────────────────────────────────────────────────────────────
TIPOS_VALIDOS = {'capsula', 'clase-en-vivo', 'capitulo-libro', 'paper', 'framework', 'integracion'}
CAMPOS_OBLIGATORIOS = {'tags', 'fecha', 'materia', 'tipo', 'fuente'}
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$')
WIKILINK_RE = re.compile(r'\[\[([^\]|#]+)(?:[|\#][^\]]*)?\]\]')
FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


# ─── Helpers ─────────────────────────────────────────────────────────────────
def slug(text: str) -> str:
    text = text.lower().strip()
    for src, dst in [('á','a'),('à','a'),('ä','a'),('é','e'),('è','e'),('ë','e'),
                     ('í','i'),('ì','i'),('ï','i'),('ó','o'),('ò','o'),('ö','o'),
                     ('ú','u'),('ù','u'),('ü','u'),('ñ','n')]:
        text = text.replace(src, dst)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def parse_frontmatter(content: str):
    m = FRONTMATTER_RE.match(content)
    if not m:
        return None, content
    try:
        fm = yaml.safe_load(m.group(1))
        body = content[m.end():]
        return fm, body
    except yaml.YAMLError:
        return None, content


def render_frontmatter(fm: dict, body: str) -> str:
    fm_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False,
                       sort_keys=False).rstrip()
    return f'---\n{fm_str}\n---\n{body}'


def fix_tags_to_slugs(tags) -> list:
    if not isinstance(tags, list):
        tags = [str(tags)]
    return [slug(str(t)) for t in tags]


# ─── QA por archivo ──────────────────────────────────────────────────────────
def qa_archivo(path: Path, slug_materia: str, nombre_materia: str,
               notas_existentes: set) -> dict:
    correcciones = {
        'archivo': path.name,
        'frontmatter': [],
        'wikilinks_eliminados': [],
        'estructura': [],
        'modificado': False
    }

    content = path.read_text(encoding='utf-8', errors='replace')
    fm, body = parse_frontmatter(content)

    # ── 1. FRONTMATTER ────────────────────────────────────────────────────────
    if fm is None:
        correcciones['frontmatter'].append('SIN FRONTMATTER — no se puede corregir automáticamente')
        return correcciones

    changed_fm = False

    # Campos obligatorios
    for campo in CAMPOS_OBLIGATORIOS:
        if campo not in fm or fm[campo] is None:
            if campo == 'tags':
                fm['tags'] = [slug_materia]
            elif campo == 'fecha':
                from datetime import date
                fm['fecha'] = date.today().isoformat()
            elif campo == 'materia':
                fm['materia'] = nombre_materia
            elif campo == 'tipo':
                fm['tipo'] = 'paper'  # fallback
            elif campo == 'fuente':
                fm['fuente'] = path.stem
            correcciones['frontmatter'].append(f'Campo faltante agregado: {campo}')
            changed_fm = True

    # materia consistente
    if fm.get('materia') != nombre_materia:
        correcciones['frontmatter'].append(f'materia corregida: "{fm.get("materia")}" → "{nombre_materia}"')
        fm['materia'] = nombre_materia
        changed_fm = True

    # tipo válido
    tipo_actual = str(fm.get('tipo', '')).lower().strip()
    if tipo_actual not in TIPOS_VALIDOS:
        correcciones['frontmatter'].append(f'tipo inválido "{tipo_actual}" — no se corrige automáticamente')
    else:
        if fm['tipo'] != tipo_actual:
            fm['tipo'] = tipo_actual
            changed_fm = True

    # tags: asegurar slug_materia y que sean slugs
    tags = fm.get('tags', [])
    if isinstance(tags, str):
        tags = [tags]
    tags_slug = fix_tags_to_slugs(tags)
    if slug_materia not in tags_slug:
        tags_slug.insert(0, slug_materia)
        correcciones['frontmatter'].append(f'slug_materia "{slug_materia}" agregado a tags')
    if tags_slug != tags:
        fm['tags'] = tags_slug
        changed_fm = True

    # ── 2. WIKILINKS ROTOS ───────────────────────────────────────────────────
    def replace_wikilink(m):
        target = m.group(1).strip()
        if target in notas_existentes or slug(target) in {slug(n) for n in notas_existentes}:
            return m.group(0)  # existe, mantener
        else:
            correcciones['wikilinks_eliminados'].append(target)
            return target  # eliminar corchetes, dejar texto plano

    new_body = WIKILINK_RE.sub(replace_wikilink, body)
    body_changed = new_body != body
    if body_changed:
        body = new_body

    # ── 3. ESTRUCTURA ────────────────────────────────────────────────────────
    tipo = str(fm.get('tipo', ''))
    headers = set(re.findall(r'^##\s+(.+)', body, re.MULTILINE))

    # ## Para estudiar — requerido en todos excepto integración
    if tipo != 'integracion' and 'Para estudiar' not in headers:
        body += '\n\n## Para estudiar\n\n> ⚠️ Pendiente de revisión\n'
        correcciones['estructura'].append('Sección ## Para estudiar agregada (vacía)')
        body_changed = True

    # ## Preguntas de la clase — requerido en Tipo B
    if tipo == 'clase-en-vivo' and 'Preguntas de la clase' not in headers:
        # Insertar antes de ## Para estudiar si existe
        if '## Para estudiar' in body:
            body = body.replace('## Para estudiar',
                                '## Preguntas de la clase\n\n> ⚠️ Pendiente de revisión\n\n## Para estudiar')
        else:
            body += '\n\n## Preguntas de la clase\n\n> ⚠️ Pendiente de revisión\n'
        correcciones['estructura'].append('Sección ## Preguntas de la clase agregada (vacía)')
        body_changed = True

    # ## Relacionado — requerido en todos
    if 'Relacionado' not in headers:
        body += '\n\n## Relacionado\n\n'
        correcciones['estructura'].append('Sección ## Relacionado agregada (vacía)')
        body_changed = True

    # ── Escribir si hubo cambios ──────────────────────────────────────────────
    if changed_fm or body_changed:
        new_content = render_frontmatter(fm, body)
        path.write_text(new_content, encoding='utf-8')
        correcciones['modificado'] = True

    return correcciones


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 4:
        print(json.dumps({'error': 'Uso: condensar_qa.py <vault_dir> <slug_materia> <nombre_materia> [archivo1.md ...]'}))
        sys.exit(1)

    vault_dir = Path(sys.argv[1])
    slug_materia = sys.argv[2]
    nombre_materia = sys.argv[3]
    archivos_arg = sys.argv[4:]

    # Notas existentes en el vault (para validar wikilinks)
    notas_existentes = {p.stem for p in vault_dir.rglob('*.md')}

    # Archivos a revisar
    if archivos_arg:
        archivos = [Path(a) for a in archivos_arg if Path(a).exists()]
    else:
        archivos = list(vault_dir.rglob('*.md'))

    if not archivos:
        print(json.dumps({'error': 'No se encontraron archivos .md para revisar'}))
        sys.exit(1)

    resultados = []
    total_fm = 0
    total_wl = 0
    total_struct = 0
    wikilinks_pendientes = {}  # target → [notas que lo mencionan]

    for archivo in archivos:
        r = qa_archivo(archivo, slug_materia, nombre_materia, notas_existentes)
        resultados.append(r)
        total_fm += len(r['frontmatter'])
        total_wl += len(r['wikilinks_eliminados'])
        total_struct += len(r['estructura'])
        for wl in r['wikilinks_eliminados']:
            wikilinks_pendientes.setdefault(wl, []).append(archivo.name)

    resumen = {
        'archivos_revisados': len(archivos),
        'archivos_modificados': sum(1 for r in resultados if r['modificado']),
        'correcciones': {
            'frontmatter': total_fm,
            'wikilinks_eliminados': total_wl,
            'estructura': total_struct
        },
        'wikilinks_pendientes_de_crear': wikilinks_pendientes,
        'detalle': resultados
    }

    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
