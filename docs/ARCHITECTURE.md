# Architettura — yt down

Stato: **v1 funzionante** (2026-11-15). Per 2–3 utenti privati, macOS e Windows.

## 1. Obiettivo

L'utente incolla link singoli, liste di link o playlist YouTube. L'app espande le
playlist, analizza i video, chiede **prima del download** risoluzione e — solo se
serve — lingua audio, poi scarica tutto in coda in automatico.

## 2. Forma: web app locale

| Opzione | Esito |
|---|---|
| Sito su Netlify | Non fattibile da solo: funzioni serverless con timeout di secondi, niente ffmpeg, e YouTube blocca gli IP dei datacenter. |
| Estensione browser | Non può eseguire ffmpeg (serve per unire audio e video separati sopra i 720p). |
| **Web app locale** | Server Python su `127.0.0.1`, interfaccia nel browser, download con l'IP dell'utente. Si avvia con doppio clic, nessun installer da firmare. |

## 3. Stack

| Componente | Scelta | Motivo |
|---|---|---|
| Ambiente | `uv` + `uv.lock` | Installa anche Python; stesso ambiente su mac e Windows. |
| yt-dlp | pacchetto PyPI `yt-dlp[default]` (include `yt-dlp-ejs`), **eseguito come sottoprocesso** (`python -m yt_dlp`) | Isolamento e cancellazione del processo; aggiornabile a ogni avvio con `uv pip install -U`. |
| Runtime JS | pacchetto PyPI `deno` | Richiesto da yt-dlp per YouTube dalla 2025.11. Deno e non QuickJS: è l'unico abilitato di default in yt-dlp e, senza installer, il peso non conta. |
| ffmpeg | pacchetto PyPI `imageio-ffmpeg` (binario statico per OS) | Nessuna installazione di sistema. |
| Server | `http.server` della libreria standard | Zero dipendenze; API JSON minima. |
| UI | un `index.html` con Tailwind via CDN e JS vanilla | Nessun build step. |

Verificato: `uv.lock` contiene wheel `win_amd64` per `deno` e `imageio-ffmpeg`.

## 4. Moduli

```
src/ytdown/
├── __main__.py      # avvio: porta libera, apre il browser, chiusura pulita
├── server.py        # API JSON + pagina; solo 127.0.0.1, controllo Host/Origin
├── capture.py       # cattura fixture reali per i test
├── web/index.html   # interfaccia
└── core/            # nessuna dipendenza dal server
    ├── models.py    # dataclass condivise
    ├── links.py     # parsing URL, video vs playlist, dedup
    ├── tools.py     # trova deno/ffmpeg, comando base di yt-dlp
    ├── runner.py    # unico punto che lancia yt-dlp
    ├── probe.py     # JSON di yt-dlp → VideoInfo / Playlist
    ├── selection.py # funzione pura (VideoInfo, Choice) → ResolvedFormat
    ├── options.py   # aggrega risoluzioni e lingue su tutti i video in attesa
    ├── progress.py  # argomenti di download e parsing delle righe di avanzamento
    ├── jobs.py      # coda: analisi, scelta, download, annulla/riprova
    └── settings.py  # cartella di destinazione (~/.ytdown/settings.json)
```

## 5. Flusso

```
incolla → links.parse → playlist: yt-dlp --flat-playlist → un Item per occorrenza
        → analisi per video (3 in parallelo, cache per ID) → stato READY
        → la pagina mostra options.aggregate dei READY → l'utente sceglie
        → selection.resolve per ogni video → download (2 in parallelo)
        → <cartella>/[<playlist>/NN - ]<titolo> [<id>].<mp4|mkv>
```

Scelta e analisi si sovrappongono: si può avviare chi è pronto mentre il resto è
ancora in analisi; la scelta successiva vale per i nuovi pronti.

### 5.1 Lingue audio — scoperta importante

Con i client predefiniti yt-dlp restituisce **solo la traccia originale**. Il client
`web_embedded` restituisce anche le tracce doppiate (25 lingue sul video di test).
Per questo ogni chiamata usa `--extractor-args youtube:player_client=default,web_embedded`
(`core/tools.py`). La traccia originale ha `language_preference == 10` e
`format_note` contenente "original"; le doppiate hanno `-1`.

### 5.2 Regole di selezione

1. **Risoluzione** = tetto: la massima ≤ scelta; se nessuna, la minima disponibile.
   Si usa l'etichetta YouTube (`1080p60` → 1080), non l'altezza in pixel, così i
   video verticali/non 16:9 si comportano come ci si aspetta.
2. **Stream**: si escludono gli HDR se c'è un SDR; H.264 → **mp4**, altrimenti
   (VP9/AV1, tipico sopra 1080p) → **mkv**. A parità: download diretto HTTPS
   (più veloce, dimensione nota) prima di HLS, poi fps e bitrate.
3. **Audio**: lingua scelta (confronto sul codice principale, `it` ≡ `it-IT`),
   altrimenti originale; in mp4 si preferisce AAC.
4. Ogni deviazione dalla scelta diventa una nota visibile in coda.

## 6. Errori

| Caso | Comportamento |
|---|---|
| Link non YouTube / non riconosciuto | Elencato in "Link non elaborati". |
| Playlist inesistente o vuota | Idem, con il messaggio di yt-dlp. |
| Video non disponibile / privato | Item in errore con il messaggio di yt-dlp; gli altri proseguono. |
| Format ID cambiati tra analisi e download | Nuova analisi + nuova scelta automatica, una volta; nota in coda. |
| Download fallito | Errore visibile, pulsante **Riprova**. |
| yt-dlp obsoleto | Aggiornato a ogni avvio dagli script `start-*`. |
| File già scaricato | yt-dlp lo salta; l'item risulta completato con il percorso. |
| Richieste da altri siti (CSRF, DNS rebinding) | Rifiutate: controllo Host/Origin e `Content-Type: application/json` obbligatorio. |

## 7. Decisioni aperte

1. **Playlist molto lunghe**: l'analisi costa ~2–4 s per video (3 in parallelo).
   Con centinaia di video sono minuti; si può avviare il download dei pronti prima.
2. **Sottotitoli**: non inclusi in v1.
3. **Versione installabile** (PyInstaller + firma): rimandata; gli script `start-*`
   coprono l'uso privato.
