# WebODM2QGIS-tools — guida rapida

Plugin per **QGIS 4**. Elenca i prodotti di un server WebODM e li importa in QGIS, con avvisi su EPSG e georiferimento.
È in **sola lettura**: non scrive nulla sul server.

## Installare
```
python qgis_dev.py            # controlli, zip, copia nel profilo QGIS 4, backup
```
Poi in QGIS: *Plugin ▸ Gestisci e installa plugin ▸ Installati ▸ WebODM2QGIS-tools* (spunta). Compaiono il menu
**WebODM**, la barra **WebODM** e il pannello a sinistra. In alternativa installa `webodm2qgis_tools.zip` da
*Installa da ZIP*.

## Primo uso
1. **Collega**: pulsante «...» ▸ *WebODM locale* (compila `http://localhost:29800`) ▸ utente e password ▸ *Salva e
   collega*. La password va nel gestore di autenticazione di QGIS (ti chiede la password principale), mai nel progetto.
2. **Progetto e task**: elenchi nel pannello, oppure *Scegli…* (ricerca, stato, anteprima, georiferito sì/no).
   Si possono scegliere solo task *completati*.
3. **Sessione di import**: al primo caricamento chiede un **nome** e una **cartella**. I file vanno in
   `<cartella>\<nome>\<task>_<id>\…`; nel pannello Livelli nasce un gruppo con il nome della sessione. Si cambia con
   *Sessione…*. Nome e cartella restano salvati nel progetto QGIS (`.qgz`). `sessione.json` elenca cosa è stato importato.
4. **Prodotti**: seleziona uno o più prodotti ▸ *Carica nel progetto* (o doppio clic). Il pallino dice se ci sono avvisi
   (verde / giallo / rosso); il tooltip spiega perché.

## Avvisi su CRS ed EPSG
Prima di caricare compare una finestra se c'è qualcosa da decidere:

| Codice | Quando | Cosa puoi fare |
|---|---|---|
| C01 | task **non georiferito** (zona UTM fittizia) | caricare sapendo che la posizione non ha significato |
| C02 | CRS del prodotto ≠ CRS del progetto | riproiettare al volo / adottare il CRS del prodotto |
| C03 | file **senza CRS** | assegnare tu l'EPSG (non si assegna mai a caso) |
| C04 | EPSG del task ≠ CRS del file | si usa quello del file |
| C05 | CRS in gradi dove servono metri | usare un CRS proiettato |
| C06/C10/C11 | trasformazione non disponibile / prodotto lontano / file grande o poco spazio | conferma |
| C07 | quote senza datum verticale | informazione |
| C08 | esiste la versione scalata dal plugin WebODM | scegli il prodotto giusto |
| C12 | punti di scatto = posizione stimata dalla ricostruzione | informazione |
| P01–P04 | scatti/prospetti (vedi sotto) | — |

Menu *WebODM ▸ Verifica CRS del progetto*: elenca i layer fuori dal CRS del progetto, in gradi, senza CRS o in CRS locale.

## Punti di scatto delle foto
Prodotto **Foto ▸ Punti di scatto delle foto** → layer puntuale `Foto - <task>` nel gruppo della sessione, con freccia
orientata, quota, orientamento, camera, data e il campo `originale` (`?` / `si` / `no`).

**Aprire l'originale** (tutti e tre i modi):
- **Strumento Foto** (barra): un clic sul punto mostra la foto nel pannello *WebODM – Foto* (miniatura e metadati);
  **doppio clic** apre l'originale.
- Strumento QGIS «Esegui azione sull'elemento»: l'azione predefinita è *Apri foto originale*.
- Pulsante *Apri originale* nel pannello Foto.

Ordine di ricerca: **cartella locale delle foto** (se indicata) ▸ copia già scaricata nella sessione ▸ **server**. Se
l'originale non c'è sul server il campo diventa `no` e lo dice, senza errori. *Verifica tutti gli originali* riempie il
campo per tutto il task. I file sopra 30 MB chiedono conferma.

## Scatti e prospetti (plugin webodm-model-tools)
Scheda *Scatti e prospetti*: miniature e dati (vista, dimensione, scala 1:N, dpi, EPSG).
- **Pianta georiferita** → si carica nell'EPSG reale e si sovrappone al resto (P02).
- **Prospetto/sezione o pianta non georiferita** → il GeoTIFF ha coordinate del *piano dell'immagine in metri*, non una
  posizione sulla Terra. Si carica con un **CRS locale** nel sottogruppo *Prospetti (CRS locale)*, **spento**, e si apre
  in una **mappa a parte**. Il file `.points` arriva accanto, per il Georeferenziatore di QGIS.

## Visualizzatore WebODM
Menu *WebODM ▸ Visualizzatore WebODM*: vista 3D (Potree), mappa 2D o dashboard del task dentro QGIS (QtWebEngine); il
login è automatico con le credenziali del server. Se QtWebEngine manca si apre il browser di sistema.

## Salvato dove
- Server: impostazioni di QGIS. Password: gestore di autenticazione di QGIS.
- Scelta (server, progetto, task, sessione, cartella foto): dentro il progetto `.qgz`.
- File scaricati: `<cartella della sessione>`.

## Limiti noti
- Una sessione può contenere più task: si scelgono uno dopo l'altro (non in blocco).
- Lo streaming dell'ortofoto richiede la password salvata nel gestore di autenticazione di QGIS.
- Le mesh OBJ texturizzate si scaricano e si decomprimono, ma QGIS non le mostra: usa il visualizzatore 3D di WebODM.
- La nuvola di punti si apre col provider *pdal* di QGIS, che indicizza il file in background.

## Per chi sviluppa
```
python qgis_dev.py check      # sintassi + test (core, traduzioni, integrazione dentro QGIS 4)
python qgis_dev.py gui        # prova nel QGIS 4 vero senza finestra, con schermate in tests\_gui_out
python qgis_dev.py status     # versione sorgente / zip / installata
python probe_webodm.py http://localhost:29800 admin    # prova le rotte contro il WebODM vero
```
**Attenzione**: il Python di QGIS 4 non parte con il tuo `PYTHONPATH` utente né con `PROJ_LIB`/`GDAL_DATA` di PostGIS
("DLL load failed while importing _core"). `run_qgis.py` li toglie; usalo sempre per lanciare script con QGIS.
