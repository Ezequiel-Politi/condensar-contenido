---
name: condensar-contenido
description: Transcribe audio/video y extrae texto de documentos (PDF, DOCX, PPTX, XLSX) a archivos .md. 100% programático, 0 tokens LLM. Preserva el contenido íntegro sin resúmenes ni reinterpretaciones.
argument-hint: "<ruta absoluta a la carpeta con los archivos>"
---

# /condensar-contenido

Procesa todos los archivos de una carpeta generando `.md` con el contenido íntegro.

## EJECUCIÓN

**Un solo comando. Sin pasos intermedios. Sin intervención de IA.**

```bash
python "<SKILL_DIR>/procesar.py" "<CARPETA>" --lang es
```

Donde `<SKILL_DIR>` se obtiene ejecutando:

```bash
# Windows
python "%USERPROFILE%\.claude\skills\condensar-contenido\config.py"

# Linux / Mac
python ~/.claude/skills/condensar-contenido/config.py
```

El JSON devuelto tiene `skill_dir`. Usar ese valor como `<SKILL_DIR>`.

## QUÉ HACE

El script `procesar.py` ejecuta todo automáticamente:

1. **Escanea** la carpeta recursivamente
2. **Transcribe** archivos de audio/video → `<nombre>_transcripcion.md` (vía Whisper local)
3. **Extrae texto** de PDF, DOCX, PPTX, XLSX → `<nombre>_extraido.md` (vía pdfplumber, python-docx, etc.)
4. **Omite** archivos que ya tienen su `.md` generado

Los `.md` generados contienen el **100% del contenido original**, sin resúmenes, sin reinterpretaciones, sin consumo de tokens LLM.

## REGLA CRÍTICA

**No analizar, resumir ni reinterpretar el contenido.** Este skill solo ejecuta el comando Python y muestra el reporte de salida. El agente NO debe leer los archivos generados ni procesarlos con LLM.

## OPCIONES

```bash
python "<SKILL_DIR>/procesar.py" "<CARPETA>"                    # Idioma: español (default)
python "<SKILL_DIR>/procesar.py" "<CARPETA>" --lang en          # Idioma: inglés
python "<SKILL_DIR>/procesar.py" "<CARPETA>" --model medium     # Modelo Whisper más preciso
```

## ARCHIVOS GENERADOS

| Archivo original | Archivo generado | Método |
|-----------------|-----------------|--------|
| `clase.mp4` | `clase_transcripcion.md` | Whisper (local) |
| `audio.mp3` | `audio_transcripcion.md` | Whisper (local) |
| `documento.pdf` | `documento_extraido.md` | pdfplumber |
| `archivo.docx` | `archivo_extraido.md` | python-docx |
| `slides.pptx` | `slides_extraido.md` | python-pptx |
| `datos.xlsx` | `datos_extraido.md` | openpyxl |

Todos los `.md` se generan en la **misma carpeta** que el archivo original.
