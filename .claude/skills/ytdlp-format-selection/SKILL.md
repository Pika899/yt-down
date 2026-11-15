---
name: ytdlp-format-selection
description: Regole verificate per leggere l'output di yt-dlp, scegliere stream video e traccia audio per lingua, interpretare l'avanzamento e catturare fixture reali in yt down. Usala quando lavori su probe.py, selection.py, options.py, progress.py o sui test che usano fixture yt-dlp.
---

# yt-dlp in yt down

Tutto ciò che segue è stato osservato su output reali il 2026-11-15 (yt-dlp
2026.10.26). Se YouTube cambia, ricattura le fixture e aggiorna qui.

## Invocazioni

Prefisso comune (`tools.base_argv()`):
`python -m yt_dlp --ignore-config --no-update --extractor-args youtube:player_client=default,web_embedded --js-runtimes deno:<path> --ffmpeg-location <ffmpeg>`

| Scopo | Argomenti aggiuntivi |
|---|---|
| Playlist | `-J --flat-playlist <url>` → `entries[].id/title/duration` |
| Video | `-J --no-playlist <url>` |
| Download | `progress.download_args()`: `-f <vid>+<aid> --merge-output-format <mp4\|mkv> --no-simulate --progress --newline --progress-template download:YTD-DL %(progress)j --progress-template postprocess:YTD-PP %(progress)j --print after_move:YTD-FILE %(filepath)s -o <template>` |

`--print` implica la simulazione: senza `--no-simulate` non scarica nulla.

## Lingue audio

- **Client**: con i client predefiniti c'è solo la traccia originale; `web_embedded`
  aggiunge le doppiate. Su `1WEAJ-DFkHE`: 1 lingua con `default`, 25 con
  `default,web_embedded`. I client `web`, `web_safari`, `tv`, `mweb` da soli
  falliscono o restituiscono solo storyboard.
- **Originale**: `language_preference == 10`, `format_note` es.
  `"English original (default), medium"`. Doppiate: `language_preference == -1`,
  `format_note` es. `"Italian, medium"`.
- Format ID delle tracce multilingua: `140-10`, `251-23`, ecc. Le varianti `-drc`
  (dynamic range compression) sono duplicati: scartate.
- Con una sola lingua tutte le tracce si considerano originali (spesso `language` è `null`).

## Video

- Solo-video: `acodec == "none"`. Qualità dall'etichetta in `format_note` (`1080p60`),
  fallback su `height`.
- `dynamic_range != "SDR"` → HDR: evitato se esiste SDR alla stessa qualità.
- Sopra 1080p di solito niente H.264 (solo VP9/AV1) → container mkv.
- `protocol == "https"` = file diretto con `filesize`; `m3u8_native` = HLS, spesso
  stessa qualità ma senza dimensione esatta → si preferisce https.
- Formati combinati (es. `18`) e `mhtml` (storyboard): ignorati.

## Avanzamento

- Due stream scaricati in sequenza: `filename` cambia (`…f137.mp4` → `…f140-10.m4a`)
  e i byte ripartono da zero. Il progresso totale = byte cumulati / `est_size`.
- Poi postprocess `Merger` (started/finished) e `MoveFiles`, infine la riga
  `YTD-FILE <percorso finale>`.
- File già presente: nessuna riga di download, ma `MoveFiles` e `YTD-FILE` arrivano.
- Errori: righe `ERROR: [youtube] <id>: <messaggio>` (stderr unito a stdout nel download).

## Fixture

```bash
uv run python -m ytdown.capture "<url>" <nome>          # video
uv run python -m ytdown.capture "<url>" <nome> --flat   # playlist
```

Usa le stesse opzioni dell'app e rimuove URL firmati e campi non usati. Se yt-dlp
fallisce salva `<nome>.error.txt`. Per l'output di un download reale, salva le righe
di `runner.Download(...).lines()` sostituendo la cartella con `/downloads` e
controlla che non resti nessun percorso personale.
