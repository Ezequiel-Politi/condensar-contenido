---
name: condensar-contenido
description: Transcribe audio/video y extrae texto de documentos (PDF, DOCX, PPTX, XLSX) a archivos .md. 100% programático, 0 tokens LLM. Preserva el contenido íntegro sin resúmenes ni reinterpretaciones.
argument-hint: "<ruta absoluta a la carpeta con los archivos>"
---

# /condensar-contenido

Procesa todos los archivos de una carpeta generando `.md` con el contenido íntegro.

## EJECUCIÓN

**Un solo comando, sin pasos previos, sin intervención de IA.**

Ejecutar el Bash tool con **EXACTAMENTE** estos parámetros — no cambiar nada excepto `<CARPETA>`:

| Parámetro Bash tool | Valor |
|---|---|
| `command` | `python "C:\Users\pc\.claude\skills\condensar-contenido\procesar.py" "<CARPETA>" --lang es` |
| `run_in_background` | **`true`** ← OBLIGATORIO, nunca omitir |
| `description` | `Transcribir y extraer texto de <CARPETA>` |

⚠️ **`run_in_background: true` es OBLIGATORIO.** Sin él el Bash tool hace timeout en 2 minutos y el proceso falla. La transcripción de video tarda más que eso.

⚠️ **NO usar el Monitor tool.** El harness notifica automáticamente cuando el background termina. Usar Monitor provoca error exit 127 en Windows.

Después de lanzar, decirle al usuario: *"Procesando en background. Te notifico cuando termine."* No hacer nada más hasta recibir la notificación del harness.

## QUÉ HACE

El script `procesar.py` ejecuta todo automáticamente:

1. **Escanea** la carpeta recursivamente
2. **Transcribe** archivos de audio/video → `<nombre>_transcripcion.md` (vía Whisper local)
3. **Extrae texto** de PDF, DOCX, PPTX, XLSX → `<nombre>_extraido.md` (vía pdfplumber, python-docx, etc.)
4. **Omite** archivos que ya tienen su `.md` generado

Los `.md` generados contienen el **100% del contenido original**, sin resúmenes, sin reinterpretaciones, sin consumo de tokens LLM.

## REGLA CRÍTICA

**No analizar, resumir ni reinterpretar el contenido.** Este skill solo ejecuta el comando Python y muestra el reporte de salida. El agente NO debe leer los archivos generados ni procesarlos con LLM.

## OPCIONES (siempre con `run_in_background: true`)

```
python "C:\Users\pc\.claude\skills\condensar-contenido\procesar.py" "<CARPETA>"                  → español (default)
python "C:\Users\pc\.claude\skills\condensar-contenido\procesar.py" "<CARPETA>" --lang en        → inglés
python "C:\Users\pc\.claude\skills\condensar-contenido\procesar.py" "<CARPETA>" --model medium   → Whisper más preciso
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
