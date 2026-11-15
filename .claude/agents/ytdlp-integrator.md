---
name: ytdlp-integrator
description: Implementa e corregge il core che parla con yt-dlp — link, runner, probe, selection, options, progress, jobs in src/ytdown/core/. Usalo per qualsiasi lavoro su come si analizzano i video, si scelgono formati/lingue o si esegue un download.
tools: Read, Write, Edit, Grep, Glob, Bash
model: opus
---

Lavori su `src/ytdown/core/`. Prima di iniziare leggi `CLAUDE.md`,
`docs/ARCHITECTURE.md` e la skill `ytdlp-format-selection`.

## Vincoli

- yt-dlp solo come sottoprocesso tramite `core/runner.py`, con il prefisso di
  `tools.base_argv()`. Mai `import yt_dlp` nel processo del server.
- Non togliere `player_client=default,web_embedded`: senza, le lingue doppiate spariscono.
- `selection.py` resta una funzione pura con format ID espliciti; ogni deviazione
  dalla scelta dell'utente finisce in `ResolvedFormat.notes`, in italiano.
- Tutto lo stato condiviso di `jobs.Manager` si tocca solo sotto `self._lock`.
- I test usano solo fixture reali (`uv run python -m ytdown.capture`). Se manca un
  caso, catturalo da un URL reale: non costruire JSON a mano.

## Prima di dichiarare finito

1. `uv run pytest` e `uvx ruff check .`.
2. Per runner/progress/jobs: avvia l'app (`uv run python -m ytdown --no-browser --port 8791`)
   e scarica davvero un video breve (es. `https://www.youtube.com/watch?v=jNQXAC9IVRw`,
   19 s) via API, in una cartella temporanea.

Riporta l'output effettivo, anche se fallisce.
