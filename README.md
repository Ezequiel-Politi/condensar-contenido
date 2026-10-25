# transcribir

Transcribe audio/video a `.md` (local, sin APIs). Detalle de uso en `SKILL.md`.

```bash
python transcribir.py "D:/Clases/Mod1" "E:/Otros/video.mp4" --dry-run
python transcribir.py "D:/Clases/Mod1" "E:/Otros/video.mp4"
```

Archivos: `transcribir.py` (todo el código), `SKILL.md` (instrucciones del skill). La configuración (umbral de duración, modelos, nombre a resaltar) son constantes al inicio de `transcribir.py`.

Instalación:

```bash
pip install faster-whisper resemblyzer librosa scipy webrtcvad-wheels
```
