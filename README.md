# webodm2QGIS-tools

**Plugin per QGIS 4** (Qt6 / PyQt6, Python 3.12). Non è un plugin di WebODM.

È il "gemello" di `..\webodm-model-tools\` (che gira **dentro WebODM**): questo gira **dentro QGIS**, si collega a un
server WebODM e carica in QGIS i prodotti dei task (ortofoto, DSM/DTM, nuvola di punti, punti di scatto delle foto,
scatti/prospetti del plugin WebODM) senza passare da scarica → decomprimi → importa, con avvisi su EPSG/georiferimento.

| Cartella | Cosa è | Dove gira |
|---|---|---|
| `..\webodm-model-tools\` | plugin **WebODM** (scala/orienta il modello, esporta, scatta prospetti) | WebODM (Django + browser) |
| `webodm2QGIS-tools\` (questa) | plugin **QGIS 4** (elenca, scarica, importa, avvisa su EPSG, visualizza) | QGIS 4 |

Stato: **v0.1.0, sperimentale** (installato nel profilo QGIS 4). Progetto: [PROGETTO.md](PROGETTO.md) · guida con immagini:
[italiano](webodm2qgis_tools/docs/guide_it.html) · [English](webodm2qgis_tools/docs/guide_en.html) (si apre anche dal pulsante *Guida* del plugin) ·
note per chi sviluppa: [docs/GUIDA.md](docs/GUIDA.md).

> ⚠️ **Software sperimentale, per QGIS 4. Può fare danni.** Realizzato da **Luca Mandolesi** di [Flyoveracademy.it](https://flyoveracademy.it),
> scritto interamente con **Claude Code** (modelli Claude Sonnet e Opus di Anthropic). Nessuna garanzia, uso a proprio rischio: scrive file nella
> cartella che scegli (può sovrascrivere file con lo stesso nome), può cambiare il CRS del progetto QGIS, salva la password del server nel gestore di
> autenticazione di QGIS. Lavora su una copia del progetto, fai un backup, usa una cartella dedicata. Non scrive nulla sul server WebODM.
>
> ⚠️ **Experimental software, for QGIS 4. It can cause damage.** By **Luca Mandolesi** of [Flyoveracademy.it](https://flyoveracademy.it),
> written entirely with **Claude Code** (Anthropic Claude Sonnet and Opus models). No warranty, use at your own risk. It writes files into the folder
> you choose (it may overwrite same-named files), can change the QGIS project CRS and stores the server password in the QGIS authentication manager.
> Work on a copy of the project, make a backup, use a dedicated folder. It writes nothing to the WebODM server.

Lingue dell'interfaccia: italiano, English, français, Deutsch, español, português. Guida: italiano e inglese.

**Licenza**: [GNU GPL versione 2 o successiva](LICENSE) (la stessa di QGIS) · GNU GPL version 2 or later. Copyright © 2026 Luca Mandolesi.

```
webodm2qgis_tools/     il pacchetto QGIS (core/ puro Python, net/, loaders/, ui/, controller.py, plugin.py)
qgis_dev.py            controlli -> versione -> zip -> installa nel profilo QGIS 4 -> backup   (python qgis_dev.py)
run_qgis.py            esegue script col Python di QGIS 4 in ambiente pulito (vedi sotto)
probe_webodm.py        prova le rotte REST contro un WebODM vero
tests/                 test_core / test_i18n (Python puro), test_integration (dentro QGIS), smoke_gui (QGIS vero)
docs/build_docs.py     costruisce le guide it/en (HTML con immagini) dalle schermate di `qgis_dev.py shots`
```

**Trappola**: il Python di QGIS 4 non parte con il `PYTHONPATH` utente né con le variabili di PostGIS
(`PROJ_LIB`, `GDAL_DATA`): "DLL load failed while importing _core". Usa sempre `run_qgis.py`.
