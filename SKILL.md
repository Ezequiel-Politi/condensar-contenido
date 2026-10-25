---
name: transcribir
description: Transcribe videos y audios (una o varias carpetas, o archivos sueltos) a .md junto al original. Ordena la cola de menor a mayor duración, elige el modelo Whisper según la duración, marca al docente y resalta las menciones a Ezequiel. 100% local, 0 tokens LLM.
argument-hint: "<ruta1> [ruta2 ...]  (carpetas y/o archivos)"
---

# /transcribir

Un solo script hace todo: arma la cola, copia a disco local, transcribe, deja el `.md` junto al original y limpia.

## EJECUCIÓN

1. Armar la lista de rutas que pasó el usuario (carpetas y/o archivos, pueden estar en lugares distintos).
2. Mostrar el plan primero:

```bash
python "C:\Users\pc\.claude\skills\transcribir\transcribir.py" "<ruta1>" "<ruta2>" --dry-run
```

3. Lanzar la corrida real con el Bash tool, **`run_in_background: true` obligatorio** (tarda más que el timeout de 2 min):

```bash
python "C:\Users\pc\.claude\skills\transcribir\transcribir.py" "<ruta1>" "<ruta2>"
```

Decirle al usuario: *"Procesando en background. Te aviso cuando termine."* No usar el Monitor tool (falla en Windows); el harness notifica solo. Si el usuario pide ver el avance, leer el archivo de salida del background (imprime porcentaje cada 5%).

4. Al terminar, mostrar el resumen por carpeta que imprime el script. **No leer ni resumir los `.md` generados.**

## QUÉ HACE

- **Cola única**: junta todos los archivos de todas las rutas (recursivo), sin repetir, y los ordena de menor a mayor duración.
- **Saltea** los que ya tienen `<nombre>_transcripcion.md` (para re-transcribir, borrar ese `.md`).
- **Modelo según duración**: menos de 20 min → `small`; 20 min o más → `medium`. Se fuerza con `--model`.
- **Disco local**: copia cada archivo a `C:\Temp\transcripcion_temp\`, transcribe desde ahí y limpia al terminar (evita cuelgues con Drive/red).
- **Docente**: el hablante con más tiempo de habla va con la etiqueta `**Docente:**`. Los demás párrafos van sin etiqueta. Si hay un solo hablante o ninguno domina, no etiqueta y avisa en el resumen. Se desactiva con `--no-docente`.
- **Menciones**: cada "Ezequiel" sale en **negrita**.
- **Glosario**: si la carpeta (o una carpeta superior dentro de la ruta pasada) tiene `glosario.txt`, sus términos se pasan a Whisper como pista. Un término por línea; `#` comenta.
- **Progreso**: porcentaje por archivo cada 5% y contador `[n/total]`.

## OPCIONES

| Opción | Efecto |
|---|---|
| `--dry-run` | Solo muestra el plan |
| `--model small\|medium\|large-v3...` | Fuerza el modelo |
| `--lang es` | Idioma (default `es`) |
| `--no-docente` | Sin identificación de hablantes |

## SALIDA

`<nombre>_transcripcion.md` junto a cada original: cabecera con nombre, fecha, duración y modelo; luego párrafos sin marcas de tiempo.

## DEPENDENCIAS

`faster-whisper`, `resemblyzer`, `librosa`, `scipy`, `webrtcvad-wheels` y `ffmpeg` en el PATH. La primera vez que se usa cada modelo se descarga (small ~460 MB, medium ~1.5 GB).
