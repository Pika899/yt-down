# yt down

Scarica video e playlist di YouTube sul tuo computer, scegliendo risoluzione e lingua
audio. Funziona nel browser ma gira tutto sul tuo PC: nessun sito esterno, nessun account.

## Installazione su Windows (consigliata)

1. Scarica **[yt-down-setup.exe](https://github.com/Pika899/yt-down/releases/latest/download/yt-down-setup.exe)**.
2. Aprilo. Se compare "Windows ha protetto il PC": **Ulteriori informazioni** →
   **Esegui comunque** (succede perché l'installer non è firmato).
3. Segui i passaggi: non servono permessi di amministratore. Alla fine trovi
   **yt down** sul Desktop e nel menu Start.

Al primo avvio yt down scarica da solo Python, yt-dlp, Deno e ffmpeg (qualche minuto,
serve internet). Per disinstallarlo: Impostazioni → App → yt down → Disinstalla.

## Installazione su Mac (consigliata)

1. Scarica **[yt-down-mac.dmg](https://github.com/Pika899/yt-down/releases/latest/download/yt-down-mac.dmg)**
   (solo Mac con chip Apple: M1 o successivi, macOS 11 o successivo).
2. Aprilo e trascina **yt down** nella cartella **Applicazioni**.
3. Il primo avvio: apri yt down da Applicazioni. macOS dice che non può verificarlo
   (l'app non è firmata da Apple): premi **Fine**, poi vai in **Impostazioni di Sistema →
   Privacy e sicurezza**, scorri in basso e premi **Apri comunque** accanto a "yt down".
   Dalla volta dopo si apre normalmente.

Al primo avvio yt down scarica da solo Python, yt-dlp, Deno e ffmpeg (circa un minuto,
serve internet). Per disinstallarlo: trascina yt down nel Cestino e, se vuoi, cancella
la cartella `~/Library/Application Support/yt down`.

## Installazione dallo ZIP (senza installer)

1. Su GitHub apri questa repository → pulsante verde **Code** → **Download ZIP**.
2. Estrai lo ZIP dove preferisci (es. `Documenti\yt-down`). **Non avviarlo dall'interno
   dello ZIP**: va estratto.

## Avvio

- **Windows con installer:** icona **yt down** sul Desktop o nel menu Start.
- **Mac con l'app:** **yt down** in Applicazioni (o dal Launchpad).
- **Windows dallo ZIP:** doppio clic su `start-windows.bat`.
  Se compare "Windows ha protetto il PC": **Ulteriori informazioni** → **Esegui comunque**.
- **Mac dallo ZIP:** clic destro su `start-mac.command` → **Apri** → **Apri** (solo la prima volta;
  poi basta il doppio clic).

Si apre una finestra nera (lasciala aperta: è il motore) e il browser su
`http://127.0.0.1:8765`. Per chiudere yt down chiudi la finestra nera.

## Uso

1. **Incolla i link**, uno per riga: video singoli e/o playlist. Premi **Analizza**.
2. **Scegli** la risoluzione massima e, se i video hanno più lingue audio, la lingua.
   Accanto a ogni opzione vedi quanti video la offrono (es. `1080p — 38/40 video`).
3. Premi **Scarica**. La coda mostra avanzamento, errori e i file salvati.

- I file vanno in `Download\yt down` (cambiabile in fondo alla pagina).
- Le playlist finiscono in una sottocartella col loro nome, video numerati `01 - …`.
- Se un video non ha la risoluzione o la lingua scelta, viene scaricato con la più
  vicina e la coda te lo segnala.
- Un link a un video *dentro* una playlist (`watch?v=…&list=…`) scarica solo quel video.
  Per l'intera playlist usa il link che contiene `/playlist?list=`.
- Fino a 1080p il file è `.mp4`; sopra (2K/4K) YouTube usa codec che vanno in `.mkv`
  (si apre con VLC).

## Aggiornare

YouTube cambia spesso. A ogni avvio lo script aggiorna yt-dlp da solo.
Per aggiornare yt down: riscarica e riapri `yt-down-setup.exe` su Windows, o riscarica il
`.dmg` e sostituisci l'app in Applicazioni su Mac (oppure, se usi lo ZIP,
scaricalo di nuovo e sostituisci la cartella). Le impostazioni sono salvate altrove e
non si perdono.

## Problemi

| Sintomo | Cosa fare |
|---|---|
| Molti video in errore all'improvviso (`HTTP Error 403`, "format not available") | Chiudi e riapri yt down: aggiorna yt-dlp. |
| "Installazione di uv non riuscita" | Installa uv a mano da <https://docs.astral.sh/uv/getting-started/installation/> e riavvia. |
| Il browser non si apre | Apri tu `http://127.0.0.1:8765` (il numero esatto è scritto nella finestra nera). |
| Video privato / rimosso / con limiti d'età | Non scaricabile: viene segnato in errore e gli altri proseguono. |

## Uso consentito

Usa yt down solo per contenuti tuoi o che hai il diritto di scaricare.

---

Note tecniche per chi sviluppa: [CLAUDE.md](CLAUDE.md) e [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
