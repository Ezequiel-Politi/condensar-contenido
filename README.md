# condensar-contenido

Skill para Claude Code que transcribe audio/video y condensa material académico (PDFs, clases, cápsulas) en notas estructuradas para Obsidian.

## Archivos

```
condensar-contenido/
  SKILL.md                  # Instrucciones del skill (no editar)
  config.py                 # ← ÚNICO archivo que hay que editar al instalar
  condensar_inventario.py   # Fase 0: inventario y clasificación (0 tokens LLM)
  condensar_extraer.py      # Extracción de texto de PDF/DOCX/PPTX (0 tokens LLM)
  condensar_qa.py           # QA mecánico de notas Obsidian (0 tokens LLM)
```

## Instalación

### 1. Clonar en el directorio de skills de Claude Code

**Windows:**
```
git clone <repo-url> "%USERPROFILE%\.claude\skills\condensar-contenido"
```

**Linux / Mac:**
```
git clone <repo-url> ~/.claude/skills/condensar-contenido
```

### 2. Editar config.py

Abrir `config.py` y modificar las dos variables:

```python
VAULT_RAIZ     = "ruta/a/tu/vault/obsidian"
TRANSCRIBIR_PY = "ruta/a/tu/transcribir.py"
```

Verificar que la config es correcta:
```bash
python config.py
```

### 3. Instalar dependencias Python

```bash
pip install pdfplumber python-docx python-pptx pyyaml
```

### 4. Verificar instalación

En Claude Code, ejecutar:
```
/condensar-contenido
```

El skill debería arrancar y pedir el path de la carpeta de la materia.

## Dependencias externas

- **transcribir.py**: script local de transcripción de audio/video con Whisper. No incluido en este repo — cada usuario debe tener el suyo y apuntar `TRANSCRIBIR_PY` a él en `config.py`.
- **Python 3.8+**
- **pdfplumber**, **python-docx**, **python-pptx**, **pyyaml**

## Uso

```
/condensar-contenido "D:/Facultad/Gestión Estratégica de Marketing"
```

El skill procesa todos los archivos de la carpeta, transcribe audio/video si hay, condensa el contenido en notas Obsidian y ejecuta QA automático.
