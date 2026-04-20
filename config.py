"""
config.py — Configuración de /condensar-contenido
==================================================
ÚNICO archivo que hay que editar al instalar en una nueva máquina.
Ejecutar directamente para verificar la config: python config.py
"""
import json
import sys
from pathlib import Path

# ─── EDITAR ESTOS VALORES ────────────────────────────────────────────────────

# Carpeta raíz del vault Obsidian donde se guardan las notas por materia
VAULT_RAIZ = "C:/Users/pc/Mi unidad/Hana/Proyectos"

# Path completo al script de transcripción local
# Por defecto apunta al transcribir.py incluido en este mismo repo
TRANSCRIBIR_PY = str(Path(__file__).parent / "transcribir.py")

# ─── NO EDITAR DEBAJO DE ESTA LÍNEA ─────────────────────────────────────────

# Directorio donde viven los scripts del skill (mismo dir que este archivo)
SKILL_DIR = str(Path(__file__).parent.resolve())

CONFIG = {
    "vault_raiz":     VAULT_RAIZ,
    "transcribir_py": TRANSCRIBIR_PY,
    "skill_dir":      SKILL_DIR,
}

if __name__ == "__main__":
    # Verificación básica
    errores = []
    if not Path(VAULT_RAIZ).exists():
        errores.append(f"VAULT_RAIZ no existe: {VAULT_RAIZ}")
    if not Path(TRANSCRIBIR_PY).exists():
        errores.append(f"TRANSCRIBIR_PY no existe: {TRANSCRIBIR_PY}")

    if errores and "--json" not in sys.argv:
        print("⚠️  Advertencias de configuración:", file=sys.stderr)
        for e in errores:
            print(f"   {e}", file=sys.stderr)

    print(json.dumps(CONFIG, ensure_ascii=False))
