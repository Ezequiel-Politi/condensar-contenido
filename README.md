# condensar-contenido

Skill que transcribe audio/video y extrae texto de documentos, generando archivos `.md` con el contenido **íntegro** (sin resúmenes ni reinterpretaciones). 100% programático, 0 tokens LLM.

## Uso

```bash
python procesar.py "D:/Carpeta/Con/Archivos" --lang es
```

Eso es todo. Un solo comando procesa la carpeta entera.

## Archivos

```
condensar-contenido/
  SKILL.md              # Instrucciones del skill (no editar)
  config.py             # Configuración (editar si transcribir.py está en otro lado)
  procesar.py           # ← Orquestador principal (ejecutar este)
  condensar_extraer.py  # Extracción de texto de PDF/DOCX/PPTX/XLSX
  transcribir.py        # Transcripción de audio/video con Whisper
```

## Instalación

### 1. Dependencias

```bash
pip install pdfplumber python-docx python-pptx openpyxl
```

Para transcripción de audio/video:
```bash
pip install stable-whisper
```

### 2. Verificar

```bash
python config.py
```

## Formatos soportados

| Formato | Extensiones | Resultado |
|---------|------------|-----------|
| Audio | .mp3 .wav .m4a .flac .ogg .wma .aac .mp2 .opus .aiff .au | `_transcripcion.md` |
| Video | .mp4 .mkv .avi .mov .wmv .webm .flv .ts .mts .m4v .3gp | `_transcripcion.md` |
| PDF | .pdf | `_extraido.md` |
| Word | .docx | `_extraido.md` |
| PowerPoint | .pptx | `_extraido.md` |
| Excel | .xlsx .xls | `_extraido.md` |

## Comportamiento

- Los `.md` se generan en la **misma carpeta** que el original
- Si el `.md` ya existe, el archivo se **omite** (idempotente)
- El contenido se preserva **íntegro** — cero resúmenes, cero reinterpretaciones
- Todo corre **localmente** — cero tokens LLM, cero llamadas a APIs de IA
