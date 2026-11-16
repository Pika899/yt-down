# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Progetto

**yt down**: web app locale (server Python su `127.0.0.1` + pagina nel browser) che
scarica video e playlist YouTube chiedendo prima risoluzione e lingua audio. Uso
privato del proprietario e dei soci, su macOS e Windows. Architettura, motivazioni e
decisioni aperte: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Guida utente:
[README.md](README.md).

## Comandi

```bash
uv sync                                   # dipendenze (yt-dlp, deno, ffmpeg inclusi)
uv run python -m ytdown                   # finestra dell'app (pywebview); se manca, browser
uv run python -m ytdown --browser         # pagina nel browser, Ctrl+C per chiudere
uv run python -m ytdown --no-browser --port 8791   # solo server (test, CI)
uv run pytest                             # test (offline, su fixture reali)
uv run pytest tests/test_links.py -k playlist      # singolo test
uvx ruff check --fix . && uvx ruff format .
uv run python -m ytdown.capture <url> <nome> [--flat]   # nuova fixture in tests/fixtures/
```

Gli utenti finali avviano `start-windows.bat` / `start-mac.command`, che usano
`uv sync --frozen`: dopo aver cambiato dipendenze va committato `uv.lock`.

Installer: `.github/workflows/installers.yml` costruisce, testa e pubblica in un'unica
Release, a ogni tag `v*` (`git tag v1.1.1 && git push origin v1.1.1`):
- Windows `yt-down-setup.exe` (`installer/ytdown.iss`, Inno Setup): sorgenti + `uv.exe`,
  `start-windows.bat --setup` prepara il venv durante l'installazione; i collegamenti
  avviano `.venv\Scripts\pythonw.exe -m ytdown` (niente console).
- Mac `yt-down-mac.dmg` (`macos/build-app.sh`, provabile in locale): `yt down.app` con
  sorgenti + uv arm64 (solo Apple Silicon, niente Rosetta); `macos/launcher.sh` (eseguibile del bundle) prepara il venv in
  `~/Library/Application Support/yt down/venv`, usa `PYTHONPATH=src` (il bundle può essere
  di sola lettura o traslocato) e fa `exec` di Python, che diventa il processo "yt down". Firma ad-hoc, non
  notarizzata.

Entrambi lasciano yt-dlp aggiornabile a ogni avvio: non congelare l'app con PyInstaller.

## Regole architetturali

- yt-dlp si lancia solo da `core/runner.py`, come sottoprocesso (`python -m yt_dlp`),
  mai `import yt_dlp` nel processo del server.
- Ogni chiamata a yt-dlp passa da `tools.base_argv()`: contiene
  `player_client=default,web_embedded`, senza il quale **le tracce audio doppiate
  spariscono** (vedi ARCHITECTURE §5.1).
- `core/selection.py` resta una funzione pura con format ID espliciti; ogni deviazione
  dalla scelta dell'utente diventa una nota in `ResolvedFormat.notes`.
- `core/` non dipende da `server.py`. Lo stato vive in `core/jobs.py` (`Manager`),
  protetto da un unico lock; la pagina fa polling di `/api/state`.
- Nei test niente rete: si usano fixture reali in `tests/fixtures/` e fake di
  probe/download iniettati nel `Manager`. Mai scrivere a mano JSON che imiti yt-dlp.
- Testi dell'interfaccia e messaggi all'utente in italiano; codice in inglese.
- Il server accetta solo Host `127.0.0.1`/`localhost` e POST JSON: non allentare.
- L'interfaccia è una sola (`web/index.html`): `desktop.py` la mostra in una finestra
  pywebview (WebKit su Mac, WebView2 su Windows); il browser è solo il ripiego.
- yt-dlp si aggiorna in background all'avvio (`tools.start_ytdlp_update`, via uv); ogni
  chiamata a yt-dlp aspetta la fine dell'aggiornamento (`tools.wait_until_ready`).

## Orchestrazione

Il modello predefinito del progetto (orchestratore) è Opus 5.5, impostato in
`.claude/settings.json`. Delega così:

| Agente | Quando |
|---|---|
| `ytdlp-integrator` (progetto) | `core/`: link, probe, selezione, avanzamento, coda |
| `web-ui` (progetto) | `src/ytdown/web/index.html` e API in `server.py` |
| `codex-delegate` (progetto) | task ben specificati da far scrivere a Codex, o revisione indipendente |
| `researcher` / `reviewer` / `qa` (globali) | novità di yt-dlp/YouTube; revisione; verifica reale |

Una modifica al download si considera finita solo dopo una prova reale dall'app in
esecuzione (non solo i test): YouTube cambia senza preavviso.

Skill di progetto: `ytdlp-format-selection`.

## Hook (`.claude/settings.json`)

- Dopo Edit/Write su `.py` del progetto: `ruff format` + `ruff check --fix`.
- Prima di Bash/Read: blocca lettura di `.env`/file cookie e `git add` di media
  scaricati o `git add -A`/`git add .` (aggiungere i file esplicitamente).
