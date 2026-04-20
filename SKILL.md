---
name: condensar-contenido
description: Transcribe audio/video localmente y condensa todo el material de una carpeta de materia al vault Obsidian Hana. Usar cuando se quiere procesar los archivos de una materia (PDFs, transcripciones, cápsulas, clases en vivo) para condensarlos como notas en Obsidian.
argument-hint: "<ruta absoluta a la carpeta de la materia>"
---

# /condensar-contenido

Condensa todos los archivos de una carpeta de materia y los guarda como notas estructuradas en el vault Obsidian Hana.

## CONFIGURACIÓN

```
CARPETA_MATERIA = $ARGUMENTS
```

**Paso obligatorio al iniciar**: leer la configuración del usuario ejecutando:

```bash
# Windows
python "%USERPROFILE%\.claude\skills\condensar-contenido\config.py"

# Linux / Mac
python ~/.claude/skills/condensar-contenido/config.py
```

Esto devuelve JSON con `vault_raiz`, `transcribir_py` y `skill_dir`. Usar esos valores para todo lo que sigue. **Nunca usar paths hardcodeados.**

Asignar:
- `SKILL_DIR` = valor de `skill_dir` del JSON
- `VAULT_RAIZ` = valor de `vault_raiz` del JSON
- `TRANSCRIBIR_PY` = valor de `transcribir_py` del JSON

---

## REGLA CRÍTICA — NO ENTRAR EN PLAN MODE

**Nunca activar plan mode durante la ejecución de este skill.** Si el harness lo sugiere, ignorarlo y continuar ejecutando directamente. Este skill es autónomo por diseño.

---

## FASE 0 — INVENTARIO Y DESCUBRIMIENTO (Python local)

Ejecutar el script de inventario. Hace todo: descubrir vault, clasificar archivos, detectar omitidos. Cero tokens LLM.

```bash
python "<SKILL_DIR>/condensar_inventario.py" "<CARPETA_MATERIA>" "<VAULT_RAIZ>"
```

Parsear el JSON resultante y extraer:
- `nombre_materia`, `slug_materia`, `ruta_vault`
- Lista `pendientes` (cada item tiene: `archivo`, `tipo`, `output`, `output_path`, `clase_n`, `extension`)
- Lista `omitidos`
- `stats`

Mostrar el plan con esos datos:

```
════════════════════════════════════════════════════
MATERIA: <nombre_materia>
Vault: <ruta_vault>
════════════════════════════════════════════════════
Archivos fuente: N
  ↳ PENDIENTES: N
  ↳ OMITIDOS:   N

PENDIENTES:
  [TIPO] archivo.ext  →  output.md
  ...
════════════════════════════════════════════════════
```

Registrar T_INICIO: `date +%s`

---

## FASE 1 — TRANSCRIPCIÓN

Solo archivos PENDIENTES con extensión de audio/video que no tengan ya `<stem>_transcripcion.md` en la misma carpeta fuente.

```
Audio: .mp3 .wav .m4a .flac .ogg .wma .aac .mp2 .opus .aiff .au
Video: .mp4 .mkv .avi .mov .wmv .webm .flv .ts .mts .m4v .3gp
```

Por cada carpeta con pendientes de transcripción:
```bash
python "<TRANSCRIBIR_PY>" "<ruta_carpeta>" --lang es
```

Esperar que termine antes de lanzar la siguiente. Si falla → loggear ERROR, continuar.

Actualizar PENDIENTES: reemplazar cada entrada de audio/video por su `_transcripcion.md`. Los originales pasan a IGNORAR.

---

## FASE 2 — CONDENSACIÓN

### Estrategia según volumen

- **≤ 2 archivos PENDIENTES**: procesar en el contexto principal (no lanzar subagentes — el overhead fijo no vale la pena).
- **≥ 3 archivos PENDIENTES**: lanzar un subagente por archivo. Archivos independientes se lanzan en paralelo (múltiples Agent tool calls en el mismo mensaje).

### Procedimiento por archivo (en contexto principal o en subagente)

1. **Verificar idempotencia**: si el output ya existe en disco → OMITIR.
2. **Extraer texto** usando Python con encoding UTF-8 explícito (ver EXTRACCIÓN DE TEXTO).
3. **Condensar** según tipo (ver CRITERIOS DE CONDENSACIÓN).
4. **Aplicar formato Obsidian** (ver FORMATO OBSIDIAN).
5. **Escribir** en `RUTA_MATERIA_VAULT/<Clase N>/<nombre>.md`.

### Prompt para subagente de condensación

Cuando se usan subagentes, enviar este prompt (adaptar los valores en `<>`):

```
Sos un agente de condensación académica. Procesá un único archivo y escribí una nota Obsidian.

ARCHIVO FUENTE: <ruta absoluta>
ARCHIVO OUTPUT: <ruta absoluta del .md de destino>
TIPO: <A | B | C | D | E>
NOMBRE_MATERIA: <NOMBRE_MATERIA>
SLUG_MATERIA: <slug-materia>
CLASE_N: <N>

PASO 1 — Verificar idempotencia: si OUTPUT ya existe en disco, terminar y reportar "OMITIDO".

PASO 2 — Extraer texto del archivo fuente ejecutando:
  python "<SKILL_DIR>/condensar_extraer.py" "<ARCHIVO FUENTE>"
  Capturar stdout como texto. Si la primera línea empieza con "PAGINAS:", ignorarla al procesar.
  Si exit code != 0 → reportar ERROR y terminar.

PASO 3 — Condensar según TIPO (ver CRITERIOS DE CONDENSACIÓN más abajo).

PASO 4 — Aplicar formato Obsidian (ver FORMATO OBSIDIAN más abajo).

PASO 5 — Crear carpeta Clase N/ si no existe. Escribir OUTPUT.

PASO 6 — Reportar: "DONE: <nombre-output.md>"

[Incluir aquí las secciones EXTRACCIÓN DE TEXTO, CRITERIOS DE CONDENSACIÓN y FORMATO OBSIDIAN completas]
```

### Barra de progreso (en contexto principal, al recibir resultados de subagentes)

```
[████████████░░░░░░░░░░░░░░░░░░] 12/25 (48%) — nombre-archivo.pdf
⏱  Transcurrido: 4m 32s | ETA: ~4m 55s
```

ETA = ELAPSED × (TOTAL - DONE) / DONE. Formatear segundos como `Xm Ys`.

---

## EXTRACCIÓN DE TEXTO (Python local)

Usar el script de extracción. Maneja todos los formatos, encoding UTF-8, e instalación de dependencias automáticamente. Cero tokens LLM.

```bash
python "<SKILL_DIR>/condensar_extraer.py" "<ruta_archivo>"
```

- Para PDFs: la primera línea del output es `PAGINAS:<N>` (ignorar al pasar el texto al LLM).
- Si devuelve error (exit code != 0) → loggear y saltar el archivo.
- El texto resultante es lo que se pasa al subagente de condensación.

---

## CLASIFICACIÓN DE ARCHIVOS

**Solo por nombre de archivo y ruta — nunca leer el archivo para clasificar.**

Aplicar en orden. La primera regla que coincida gana.

| Regla | Tipo |
|---|---|
| Extensión de audio o video | IGNORAR (Fase 1) |
| .pptx y hay .pdf con mismo nombre base en la carpeta | IGNORAR |
| Nombre contiene: cronograma, programa, guía de actividades, glosario | IGNORAR |
| Ruta contiene `/Capsulas/` o `/Cápsulas/` y ext es .docx o .md | A — CÁPSULA |
| Ruta contiene `/Clase en vivo/` o `/Clase En Vivo/` y ext es .docx o .md | B — CLASE EN VIVO |
| .pdf Y nombre contiene: Cap, Capítulo, Chapter, Kotler, Keller | C — CAPÍTULO DE LIBRO |
| .pdf Y nombre contiene: PESTEL, FODA, Porter, BCG, Ansoff, Canvas, SWOT | E — FRAMEWORK |
| .pdf Y nombre contiene: Case, HBR, S-, -S, código alfanumérico | D — PAPER / CASO |
| .pdf (sin regla anterior) y tamaño de archivo > 2MB | C — CAPÍTULO DE LIBRO |
| .pdf (sin regla anterior) | D — PAPER / CASO |
| .pptx sin .pdf equivalente | D — PAPER / CASO |

Si hay ambigüedad entre C y D → asignar C.
Los `_transcripcion.md` caen en la regla de su carpeta: `/Capsulas/` → A, `/Clase en vivo/` → B.

---

## CRITERIOS DE CONDENSACIÓN POR TIPO

### A — CÁPSULA

No resumir: versión estructurada que preserva TODO el contenido conceptual.

```
# [Tema del video]
## [Sección lógica 1]
## [Sección lógica 2]
## Idea central
[2-3 oraciones con el núcleo]
```

Reglas:
- Todo término técnico mencionado debe aparecer con su definición. Si no hay definición explícita, inferirla del contexto e indicar con `> 📖 Inferida del contexto`.
- Si un concepto tiene múltiples nombres, incluir todos en el encabezado o primera línea.
- `>` para definiciones formales o afirmaciones clave. Listas ordenadas para pasos/procesos. LaTeX para fórmulas.

---

### B — CLASE EN VIVO

**Principio rector: preservar todo el contenido conceptual. Filtrar SOLO ruido conversacional puro.**

INCLUIR: definiciones, términos técnicos (aunque sean de pasada), ejemplos, analogías, respuestas del docente a alumnos con contenido, referencias a autores/teorías, datos numéricos, comparaciones.

OMITIR: saludos, cierres, comentarios administrativos, interrupciones técnicas, anécdotas sin valor conceptual, respuestas incorrectas de alumnos sin corrección.

> ⚠️ Ante la duda, INCLUIR. Una nota larga con todo supera una nota corta que no puede responder preguntas de examen.

Reglas adicionales:
- Completitud: verificar que estén definidos todos los términos técnicos del dominio. Si aparecen sin definición, inferirla e indicar que es inferida.
- Sinónimos: si el docente usa varios nombres para el mismo concepto, incluir todos vinculados.
- Si la transcripción menciona lecturas obligatorias cuyos conceptos no están desarrollados → agregar `## Conceptos de la lectura complementaria` con los términos que deberían estar cubiertos.

```
# [Tema general de la clase]
## [Bloque temático 1]
### [Subtema]
## [Bloque temático 2]
## Preguntas de la clase
[preguntas respondidas por el docente con contenido — pregunta → respuesta condensada]
## Para estudiar
[5-8 preguntas de examen posibles]
```

---

### C — CAPÍTULO DE LIBRO

No resumir: versión densa que preserva todo lo que importa.

```
# [Título del capítulo]
## [Sección original 1]
## [Sección original 2]
## Conceptos clave
| Término | Definición |
|---------|------------|
## Para estudiar
[5-10 preguntas conceptuales]
```

Reglas: respetar estructura original · todas las definiciones, modelos, teorías y ejemplos · `>` para citas y definiciones formales · tablas para comparaciones · LaTeX para fórmulas · describir textualmente figuras importantes.

---

### D — PAPER / CASO / ARTÍCULO

Contenido completo estructurado. No un abstract.

```
# [Título]
## Introducción / Contexto
## Marco teórico
## Metodología  ← omitir si paper puramente teórico
## Resultados / Desarrollo
## Discusión e interpretación
## Conclusiones
## Limitaciones  ← omitir si no aplica
## Conceptos y términos clave
| Término | Definición |
|---------|------------|
## Para estudiar
[4-6 preguntas de examen]
```

Reglas: incluir datos numéricos y tablas · no incluir referencias bibliográficas · si hay contribución teórica, explicarla en detalle.

---

### E — FRAMEWORK

```
# [Nombre del framework]
## Definición
## Componentes
## Cómo se aplica
## Para estudiar
[3-5 preguntas]
```

---

## FORMATO OBSIDIAN

### Frontmatter

```yaml
---
tags: [<slug-materia>, <tipo>, clase-<N>, <concepto-1>, <concepto-2>]
fecha: <YYYY-MM-DD>
materia: <NOMBRE_MATERIA exacto>
tipo: <capsula | clase-en-vivo | capitulo-libro | paper | framework>
fuente: <nombre del archivo original>
---
```

Slug de materia: palabras en minúscula con guiones. Ej: `gestion-estrategica-marketing`. Idéntico en todas las notas de la materia.
Conceptos: 2-3 temas principales en slug.

### Wikilinks

**Solo crear wikilinks a notas que YA EXISTEN en el vault.** No crear wikilinks rotos.

Procedimiento:
1. Obtener lista de nombres de archivo existentes en el vault (ya disponible como YA_EN_VAULT + los generados en esta ejecución).
2. Para cada concepto principal del texto, buscar si hay una nota con ese nombre en la lista.
3. Si existe → usar `[[Nombre exacto del archivo sin .md]]`.
4. Si no existe → no crear wikilink. Agregar el concepto a la lista de `Wikilinks pendientes de crear` en el reporte final.

### Sección de relaciones

```
## Relacionado
[[Nota A]] — motivo de relación
[[Nota B]] — motivo de relación
```

Solo enlazar notas que existen. Siempre enlazar entre sí las notas de la misma clase.

---

## FASE 3 — QA

### 3.1 QA mecánico (Python local — cero tokens LLM)

Ejecutar primero el script. Corrige frontmatter, elimina wikilinks rotos y verifica secciones automáticamente:

```bash
python "<SKILL_DIR>/condensar_qa.py" \
  "<ruta_vault>" "<slug_materia>" "<nombre_materia>" \
  <paths absolutos de los .md generados separados por espacios>
```

Parsear el JSON resultante y registrar:
- `correcciones.frontmatter`, `correcciones.wikilinks_eliminados`, `correcciones.estructura`
- `wikilinks_pendientes_de_crear` → incluir en el reporte final

### 3.2 QA semántico (subagente LLM — solo completitud de términos)

Lanzar un subagente con este prompt:

```
Sos un agente de QA semántico. El QA mecánico (frontmatter, wikilinks, estructura) ya fue ejecutado
por un script Python. Tu única tarea es verificar COMPLETITUD DE TÉRMINOS TÉCNICOS.

ARCHIVOS A REVISAR: <lista de paths>
SLUG_MATERIA: <slug-materia>

Para cada archivo:
  1. Leer el contenido.
  2. Identificar todos los términos técnicos del dominio presentes en el texto.
  3. Verificar que cada término tenga al menos una oración de definición o descripción.
  4. Si falta definición → agregarla. Si es inferida → marcar con:
     > 📖 Definición inferida del contexto — no explicitada en la fuente.
  5. Guardar si hubo cambios.

Reportar: "QA semántico OK. Términos completados: N en X archivos."
```

---

## FASE FINAL — INTEGRACIÓN (VÍA SUBAGENTE)

### Estrategia: patch quirúrgico, no reescritura completa

Si ya existe `00_<slug-materia>_completa.md`:
- Leer el doc integrado existente.
- Leer SOLO las notas nuevas (generadas en esta ejecución).
- Hacer un patch: agregar sección(es) `## Clase N` nuevas, actualizar `## Hilo conceptual` y `## Preguntas de integración`.
- No releer todas las notas de clases anteriores.

Si NO existe el doc integrado:
- Leer todas las notas del vault de la materia (única vez que se lee todo).
- Generar el documento completo desde cero.

### Prompt para subagente de integración

```
Sos un agente de integración académica.

RUTA_MATERIA_VAULT: <ruta>
NOMBRE_MATERIA: <NOMBRE_MATERIA>
SLUG_MATERIA: <slug-materia>
ARCHIVO_OUTPUT: <RUTA_MATERIA_VAULT>/00_<slug-materia>_completa.md
NOTAS_NUEVAS: <lista de paths de .md generados en esta ejecución>

PASO 1 — Verificar si ARCHIVO_OUTPUT ya existe.

Si YA EXISTE (patch quirúrgico):
  a. Leer ARCHIVO_OUTPUT.
  b. Leer SOLO las NOTAS_NUEVAS.
  c. Para cada clase nueva: agregar sección ## Clase N con su contenido.
  d. Actualizar ## Hilo conceptual: incorporar los nuevos conceptos al hilo existente (no reescribir desde cero, extender).
  e. Agregar nuevas preguntas a ## Preguntas de integración que crucen las clases nuevas con las anteriores.
  f. Sobreescribir ARCHIVO_OUTPUT con el documento actualizado.

Si NO EXISTE (generación completa):
  a. Leer todas las notas .md del vault de la materia, en orden de clase.
  b. Generar documento con:
     - # <NOMBRE_MATERIA>
     - ## Índice temático con anclas internas
     - ## Clase N por cada unidad
     - ## Hilo conceptual (300-500 palabras: conexión entre unidades, 3-5 conceptos vertebradores)
     - ## Preguntas de integración (10 preguntas que crucen distintas unidades)
  c. Frontmatter:
     ---
     tags: [<slug-materia>, integracion]
     fecha: <YYYY-MM-DD>
     materia: <NOMBRE_MATERIA>
     tipo: integracion
     fuente: generado automáticamente
     ---
  d. Escribir ARCHIVO_OUTPUT.

Reportar: "Integración completada: 00_<slug-materia>_completa.md [patch | generación completa]"
```

---

## CONVENCIÓN DE NOMBRES Y DESTINO

Ruta output: `RUTA_MATERIA_VAULT/<Clase N>/<nombre>.md`

El número `N` se deriva de la subcarpeta de CARPETA_MATERIA. Si la subcarpeta dice `Clase 1`, usar ese número. Si no hay estructura explícita, inferirla del nombre del archivo o usar `Clase 1`.

| Tipo | Nombre |
|---|---|
| A | `capsula_<tema-en-slug>.md` |
| B | `clase-en-vivo_clase-<N>_<tema>.md` |
| C | `<autor>_cap<N>_<tema>.md` |
| D | `<apellido-o-codigo>_<tema>.md` |
| E | `framework_<nombre>.md` |

---

## REPORTE FINAL

```
════════════════════════════════════════════════════
RESUMEN — <NOMBRE_MATERIA>
Tiempo total: Xm Ys
════════════════════════════════════════════════════
Transcriptos (Fase 1):  N
Condensados (Fase 2):   N archivos
Omitidos (ya en vault): N archivos
QA correcciones:        N (N frontmatter, N wikilinks, N estructura)
Errores:                N — [lista con nombre y motivo]

Wikilinks pendientes de crear:
  [[Concepto A]] — mencionado en: nota1.md, nota2.md
  [[Concepto B]] — mencionado en: nota3.md
════════════════════════════════════════════════════
```
