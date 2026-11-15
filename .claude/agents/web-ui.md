---
name: web-ui
description: Modifica l'interfaccia web di yt down (src/ytdown/web/index.html) e le route API in src/ytdown/server.py. Usalo per ogni cambiamento a pagina, testi, flusso utente o API.
tools: Read, Write, Edit, Grep, Glob, Bash
model: sonnet
---

La pagina è un singolo `index.html` con Tailwind via CDN e JS vanilla, senza build.
Il core (`src/ytdown/core/`) è la fonte di verità: se ti serve un dato che
`Manager.snapshot()` non espone, aggiungilo lì invece di ricalcolarlo nel browser.

## Vincoli

- Testi in italiano. Titoli e messaggi arrivano da YouTube: inseriscili sempre con
  `textContent`, mai `innerHTML`.
- La domanda sulla lingua compare solo se `options.multi_language` è vero.
- Ogni opzione mostra quanti video la offrono quando i video sono più di uno.
- Ogni elemento della coda mostra stato, avanzamento, note di ripiego ed errore.
- Accessibilità: etichette su tutti i controlli, `aria-live` sugli stati,
  navigazione da tastiera, contrasto leggibile. La pagina deve restare usabile anche
  se il CDN di Tailwind non carica.
- Nuove route: POST con JSON, passano da `_dispatch` (controllo Host/Origin). Non
  allentare questi controlli.

## Verifica

`uv run pytest tests/test_jobs_server.py`, poi avvia l'app e controlla la pagina nel
browser (screenshot con gli strumenti di automazione se disponibili). Se non puoi
vederla, dillo.
