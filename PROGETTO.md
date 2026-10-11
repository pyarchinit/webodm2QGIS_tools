# Progetto — webodm2QGIS-tools (plugin QGIS 4)

> **STATO 2026-10-11: realizzato v0.1.0** (fasi 0–3 in forma funzionante). Vedi README.md e docs/GUIDA.md.
> Scelte fatte per le decisioni aperte di §12 (default proposti): ortofoto **scaricata** (streaming opzionale);
> prospetti in **CRS locale**, sottogruppo spento + mappa dedicata; server locali e remoti (avviso su HTTP in chiaro);
> lingue **it + en**; **nessuna modifica** al plugin WebODM (la rotta `products` di §5.3 non serve: il catalogo si
> ricostruisce dalle rotte esistenti); **solo QGIS 4**; foto originali aperte col programma del sistema, con
> cartella locale di ripiego. Aggiunta richiesta in corso d'opera: **sessione di import** (nome + cartella scelti
> dall'utente: file, GeoPackage delle foto e gruppo dei layer). Non fatto / da fare: scelta di più task in blocco,
> provider nel Browser di QGIS, impronta 3D della camera, Processing provider, ripresa dei download già fatta.
> Dettagli rimasti da provare dal vivo: visualizzatore web con GPU (in "offscreen" si verifica solo l'import di
> QtWebEngine), streaming XYZ, rotte contro il WebODM vero (`probe_webodm.py`).

Versione del documento: bozza 2 · 2026-10-11 · lingua UI: italiano (chiave) + inglese
(bozza 2: aggiunti i **punti di scatto delle foto** con apertura dell'originale, e la **scelta esplicita di progetto e task**)

## 1. Obiettivo

Da QGIS, senza aprire WebODM nel browser:

1. collegarsi a un server WebODM (locale `http://localhost:29800` o remoto);
2. vedere progetti → task → **elenco dei prodotti scaricabili**;
3. scaricarli e caricarli come layer nel progetto QGIS, con il CRS giusto;
4. **avvisare** quando CRS/EPSG, georiferimento o scala rendono l'import ingannevole;
5. includere i prodotti del plugin `webodm-model-tools`: modelli scalati/georiferiti, **scatti e prospetti** (ortofoto da camera virtuale);
6. avere un **visualizzatore WebODM dentro QGIS** (3D, mappa 2D, galleria scatti);
7. **scegliere esplicitamente progetto e task** di WebODM (selettore nel pannello e finestra di scelta), con la scelta ricordata nel progetto QGIS;
8. **importare i punti di scatto delle foto** (posizione della camera di ogni foto) e, **con un clic su un punto, aprire la foto originale se è presente** sul server (o in una cartella locale indicata).

Non-obiettivi (v1): lanciare nuove elaborazioni ODM, caricare foto, editare il modello 3D, scattare nuovi prospetti (resta nel plugin WebODM).

## 2. Fatti verificati sull'ambiente (2026-10-11)

| Fatto | Conseguenza |
|---|---|
| `C:\Program Files\QGIS 4.2.2` presente (accanto a 3.44.3), profilo `%APPDATA%\QGIS\QGIS4` | si sviluppa e si prova qui; i plugin di QGIS4 stanno in `...\QGIS4\profiles\default\python\plugins` |
| Python 3.12 (`apps\Python312`), **PyQt6** | niente `PyQt5`; importare sempre da `qgis.PyQt`; enum scoped (`Qt.AlignmentFlag.AlignLeft`) |
| `QtWebEngineWidgets.pyd` e `Qt6WebEngine*.dll` presenti | il visualizzatore web integrato è fattibile su questa installazione |
| `pdal.exe` in `bin` | si può convertire LAZ → COPC per la vista 3D nativa di QGIS |
| `plugin_reloader` già installato nel profilo QGIS4 | ciclo di sviluppo veloce senza riavviare QGIS |
| Altri plugin QGIS4 usano `supportsQt6=True` + `qgisMinimumVersion=4.0` | convenzione da copiare in `metadata.txt` |
| WebODM desktop = Electron 9, servito a `localhost:29800`, auto-login admin | in locale il token si ottiene senza interazione (vedi §5.1) |

Da **verificare nello spike (fase 0)**, perché non toccati in questa sessione: le rotte REST di WebODM sotto elencate contro la versione installata in `C:\WebODM`, e il nome esatto del modulo WebEngine esposto da `qgis.PyQt` in QGIS 4.

## 3. Dove vive, come si chiama

```
webodm-model-tools\                  <- cartella di lavoro
├── webodm-model-tools\              plugin WebODM (esistente, NON si tocca se non in fase 2)
├── dev.py, tests\, docs\ ...        tooling del plugin WebODM
└── webodm2QGIS-tools\               <- questo progetto (cartella-madre, trattino ok)
    ├── README.md                    cos'è, in 10 righe
    ├── PROGETTO.md                  questo documento
    ├── qgis_dev.py                  (fase 0) check -> bump -> zip -> installa nel profilo QGIS4 + backup
    ├── tests\                       test puri (senza QGIS) + test d'integrazione (python-qgis)
    ├── docs\                        guida utente
    └── webodm2qgis_tools\           <- il pacchetto QGIS vero (nome Python valido)
```

Nome in QGIS: **"WebODM2QGIS-tools"**; cartella plugin `webodm2qgis_tools`; menu e barra si chiamano **WebODM**.
`qgis_dev.py` replica lo schema di `dev.py` (check prima del bump, zip, copia nel profilo, backup in `Documents\copia_backup\`), così le abitudini sono le stesse.

## 4. Architettura

Principio: **tutto ciò che non serve Qt è Python puro**, così si prova senza avviare QGIS (come `transform_math.py` nel plugin WebODM).

```
webodm2qgis_tools/
├── metadata.txt            qgisMinimumVersion=4.0, supportsQt6=True, qgisMaximumVersion=4.99
├── __init__.py             classFactory(iface)
├── plugin.py               crea menu, barra, dock, azioni; unico punto che conosce iface
├── core/                   PURO, testabile senza QGIS
│   ├── models.py           Server, Project, Task, Product (dataclass)
│   ├── catalog.py          da risposta API -> lista Product tipizzata (kind, size, crs, alert)
│   ├── selection.py        scelta corrente (server, progetto, task), filtri, ordinamento, (de)serializzazione nel .qgz
│   ├── photos.py           da shots.geojson -> PhotoShot (nome file, posizione, quota, rotazione) e stato "originale presente"
│   ├── crs_guard.py        regole di avviso EPSG (§7) -> lista di Alert(level, code, testo)
│   └── urls.py             costruzione/validazione URL e nomi (stessa disciplina di ORTHO_NAME)
├── net/
│   ├── client.py           WebODMClient: login JWT, GET JSON, download; usa QgsNetworkAccessManager
│   ├── auth.py             credenziali nel gestore autenticazione di QGIS (QgsAuthManager), mai in chiaro
│   └── downloader.py       QgsTask: download a blocchi con avanzamento, ripresa, cache, annullo
├── loaders/                un loader per tipo di prodotto: carica il file come layer
│   ├── raster.py           GeoTIFF/COG (ortofoto, DSM, DTM, scatti), world file
│   ├── pointcloud.py       LAZ/COPC -> QgsPointCloudLayer; indicizzazione/COPC con PDAL se serve
│   ├── vector.py           cameras.json, impronte degli scatti
│   ├── shots_points.py     punti di scatto delle foto -> layer puntuale con campi e azioni (§6.1)
│   ├── xyz.py              tile in streaming (XYZ) senza scaricare nulla
│   └── model3d.py          OBJ/PLY: apre nel visualizzatore web / cartella (QGIS non mostra OBJ texturizzati)
├── ui/
│   ├── dock.py             pannello ancorabile: albero Server > Progetto > Task > Prodotti
│   ├── connect_dialog.py   server, utente, prova connessione
│   ├── selector.py         scelta progetto e task (finestra + combo del pannello, §8.1)
│   ├── photo_panel.py      pannello "Foto": miniatura, metadati, [Apri originale], [Mostra sulla mappa]
│   ├── photo_tool.py       strumento mappa: clic su un punto di scatto -> pannello Foto / apertura originale
│   ├── products_dialog.py  scelta multipla, dimensione, destinazione, opzioni di import
│   ├── crs_dialog.py       avvisi EPSG con scelta guidata (§7)
│   ├── shots_panel.py      galleria scatti/prospetti (miniature + metadati)
│   └── viewer.py           visualizzatore web integrato (QtWebEngine)
├── i18n/                   it (chiave), en
└── resources/              icone svg, stili
```

Dipendenze esterne: **nessuna** da installare (né `requests` né `laspy`): rete con `QgsNetworkAccessManager` (rispetta proxy e certificati di QGIS), raster/nuvole con le API di QGIS/GDAL/PDAL già incluse. Niente `requirements.txt`.

## 5. Collegamento a WebODM

### 5.1 Autenticazione
- `POST /api/token-auth/` `{username, password}` → JWT; poi header `Authorization: JWT <token>`; rinnovo al 401.
- Le credenziali stanno nel **gestore di autenticazione di QGIS** (configurazione `authcfg`, protetta da password principale), non in `QgsSettings` né nel progetto `.qgz`.
- I layer in streaming (XYZ/COG remoti) usano `authcfg` con header API, **mai** `?token=` nell'URL: finirebbe scritto nel `.qgz`.
- Server locale: pulsante "Collega a WebODM locale" (`localhost:29800`, utente admin) per il caso d'uso del desktop app.
- Più server salvati; uno attivo alla volta nel dock.

### 5.2 Rotte WebODM usate (da confermare nello spike)
| Scopo | Rotta |
|---|---|
| progetti, task | `GET /api/projects/`, `/api/projects/{pid}/tasks/` |
| dettaglio task: `available_assets`, `epsg`, estensioni, stato, dimensioni | `GET /api/projects/{pid}/tasks/{tid}/` |
| prodotti standard | `GET /api/projects/{pid}/tasks/{tid}/download/{asset}` (orthophoto.tif, dsm.tif, dtm.tif, georeferenced_model.laz, textured_model.zip, all.zip…) |
| tile ortofoto per streaming | `/api/projects/{pid}/tasks/{tid}/orthophoto/tiles.json` e `.../tiles/{z}/{x}/{y}` |
| file nel task (prodotti del plugin) | `/api/projects/{pid}/tasks/{tid}/assets/scaling_tool/...` (stesso percorso che usa già il plugin WebODM) |
| punti di scatto | `GET .../tasks/{tid}/download/shots.geojson` (una feature per foto, con `filename`) |
| foto originale / miniatura | `GET .../tasks/{tid}/images/download/{filename}` e `.../images/thumbnail/{filename}` (da confermare: dipendono dalla versione di WebODM) |
| prodotti del plugin WebODM | `GET /api/plugins/webodm-model-tools/task/{tid}/export` e `.../ortho`, `.../transform`, `.../georef`, `.../map-ortho` |

Il plugin WebODM già restituisce, per ogni scatto, un JSON con `view`, `source`, `epsg`, `crs_offset`, `upper_left_m`, `lower_right_m`, `size_m`, `scale`, `dpi`, `georef`, `files[{name,url}]` — è tutto ciò che serve per catalogo e avvisi. Se `/api/plugins/webodm-model-tools/` risponde 404, il plugin non c'è: QGIS mostra solo i prodotti standard, senza errori.

### 5.3 Ritocco opzionale lato WebODM (fase 2)
Aggiungere a `webodm-model-tools` una rotta `task/{pk}/products` che restituisce **un solo manifesto**: elenco prodotti con tipo, dimensione, EPSG *reale* di ciascuno, `georeferenced: true/false`, `scaled: true/false`, `api_version`. Evita che QGIS indovini e permette un controllo di compatibilità tra le due versioni. Il client QGIS funziona anche senza (ricostruisce dalle rotte sopra).

## 6. Catalogo prodotti

Raggruppati per task nel dock, con icona, dimensione, e **semaforo CRS** (verde / giallo / rosso, §7).

| Gruppo | Prodotto | Come entra in QGIS |
|---|---|---|
| Ortofoto | `orthophoto.tif` | raster (scarica) **oppure** XYZ in streaming |
| Quote | `dsm.tif`, `dtm.tif` | raster con rampa pseudocolore + ombreggiatura suggerita |
| Nuvola | `georeferenced_model.laz`, `scaled_model.laz` | `QgsPointCloudLayer`; se manca l'indice, conversione COPC con PDAL (in background) |
| Mesh | `textured_model.zip`, `scaled_textured_model/` | scarica e decomprime; **non** diventa layer (QGIS non mostra OBJ texturizzati): si apre nel visualizzatore 3D integrato |
| **Punti di scatto** | `shots.geojson` | layer puntuale "Foto – <task>" con azione **Apri foto originale** (§6.1) |
| Vettori | `cameras.json` | vettore (parametri camera) |
| Plugin WebODM | export (`out/`) | come sopra, marcati "scalato / georiferito dal plugin" |
| **Scatti e prospetti** | `ortho_*.tif` (+ `.png/.jpg/.pdf`, `.points`, `_preview.jpg`, `.json`) | raster **con CRS locale** (vedi §7.4) + galleria |
| Rapporto | `report.pdf` | apre con il sistema |
| Tutto | `all.zip` | solo download |

Cartella cache: `%LOCALAPPDATA%\webodm2qgis\<server>\<task>\` (configurabile); i file scaricati sono riusati se dimensione e data coincidono; i progetti `.qgz` puntano al file locale, così restano apribili offline.

### 6.1 Punti di scatto delle foto e apertura dell'originale

**Cosa si importa.** `shots.geojson` di ODM contiene una feature per foto orientata dalla ricostruzione. Il layer **"Foto – <task>"** ha un punto per foto, nel CRS del task (stessi avvisi C01–C06), con i campi:
`nome_file`, `quota` (Z), rotazione/orientamento (se presente), `camera`, `originale` (sì / no / ?), `url_originale`, `percorso_locale`, `miniatura`.
La Z resta come attributo e, dove il formato lo consente, come Z della geometria (serve alla vista 3D di QGIS).

**Cosa succede al clic** (tre modi equivalenti, per non dipendere da uno solo):
1. **Azione del layer** `QgsAction` "Apri foto originale" — è nel menu del tasto destro di *Identifica* e dalla tabella attributi;
2. **Strumento "Foto"** della barra: clic su un punto → si apre il pannello Foto (miniatura, nome, quota, metadati EXIF principali) con il pulsante **Apri originale**;
3. **Map tip** (HTML) con la miniatura quando si passa sopra al punto.

**Cosa significa "originale presente".** La foto può non esserci più: task importato da `all.zip`, immagini cancellate dal server, task remoto con foto non scaricabili. Quindi:
- all'import il campo `originale` vale `?` (non si interrogano migliaia di foto in anticipo);
- al primo clic si chiede **una sola foto** al server (HEAD/GET) e il risultato si memorizza nel campo, **sì** o **no**;
- **no** → messaggio chiaro "L'originale non è sul server" e, se è impostata, si cerca per `nome_file` in una **cartella locale delle foto** (impostazione per task, ricordata nel progetto QGIS): un'unica ricerca indicizzata, non una scansione a ogni clic;
- comando "Verifica tutti gli originali" (QgsTask in background, annullabile) per riempire la colonna per l'intero task;
- se l'originale c'è: scaricato nella cache (`.part` → file) e aperto con il **visualizzatore di immagini predefinito del sistema** (`QDesktopServices.openUrl`); in alternativa dentro il pannello Foto. Le foto di drone sono pesanti (10–50 MB): chiedere conferma se il file supera una soglia e mostrare avanzamento.
- il nome file arriva dal server → validato (nessun `/`, `..`, solo estensioni immagini) prima di creare file.

**Stili e usi.** Simbolo con freccia di orientamento se la rotazione è nota; etichetta = nome file; filtro per quota/nome; "Seleziona le foto che vedono questa zona" (selezione per area → elenco foto, utile per il rilievo).

**Avvisi specifici** (vedi tabella §7):
- **C12** posizione = quella *stimata dalla ricostruzione*, non il GPS grezzo dell'EXIF; in task non georiferiti è in coordinate locali/fittizie;
- **C13** originale non presente (informativo, non blocca nulla).

## 7. Avvisi EPSG / georiferimento (cuore del progetto)

`core/crs_guard.py`, funzioni pure `check(product, project_crs, task_info) -> [Alert]`. Livelli: **info**, **attenzione** (si può proseguire), **blocco** (si propone un'alternativa). Ogni avviso ha un codice stabile (testabile) e una frase italiana.

| Cod. | Situazione | Livello | Cosa fa il plugin |
|---|---|---|---|
| C01 | Task **non georiferito** (niente GCP/EXIF): ODM usa una zona UTM fittizia | attenzione | dice "posizione senza significato, le distanze sono reali"; propone di caricare in un gruppo separato "non georiferiti"; **mai** sovrapposto in silenzio a dati reali |
| C02 | CRS del prodotto ≠ CRS del progetto QGIS | attenzione | scelta: *riproietta al volo* (default) / *imposta il CRS del progetto su quello del prodotto* / *annulla*. Se il progetto è vuoto propone di adottare il CRS del prodotto |
| C03 | File senza CRS leggibile (GeoTIFF/LAZ privo di SRS) | blocco | chiede l'EPSG, offrendo quello del task e quello del georef del plugin WebODM; non assegna a caso |
| C04 | EPSG del task (API) ≠ CRS letto dal file | attenzione | mostra entrambi; propone quello del file; evita il caso "ODM dichiara una zona, il file ne ha un'altra" |
| C05 | CRS **geografico** (gradi) dove servono metri (scale bar, misure) | attenzione | propone un CRS proiettato adatto |
| C06 | EPSG deprecato/non trovato nel database PROJ, o servono griglie mancanti | attenzione | elenca la griglia mancante, non cambia nulla |
| C07 | Quote: altezza ellissoidale vs ortometrica, nessun datum verticale dichiarato | info | segnala che DSM/DTM/LAZ non hanno geoide applicato |
| C08 | Modello **scalato/ruotato dal plugin WebODM** ma si sta caricando il prodotto originale (o viceversa) | attenzione | mostra quale versione è (`transform.json`); preferisce quella corretta |
| C09 | Georiferimento del plugin con coordinate assolute vs "offset di vista" (`crs_offset`) | info | spiega perché i valori nel viewer web sono piccoli e in QGIS grandi; il LAZ/GeoTIFF esportati sono in assoluto |
| C10 | Estensione del prodotto lontanissima dall'area del progetto QGIS (> 100 km) | attenzione | "forse CRS sbagliato": di solito segnala C01/C03 |
| C11 | Scarsa dimensione: file > soglia (es. 2 GB) o poco spazio disco | info | conferma prima del download |
| C12 | Punti di scatto: posizione stimata dalla ricostruzione (non l'EXIF); in task non georiferiti coordinate fittizie | info / attenzione | spiega la differenza; in task non georiferiti vale C01 |
| C13 | Foto originale non presente sul server | info | messaggio chiaro, ricerca nella cartella locale indicata |
| **P01** | **Scatto non-pianta (prospetto/sezione)** | **attenzione** | il raster è georiferito *solo nel suo piano immagine, in metri*: coordinate X = destra, Y = su dell'immagine, **non** una posizione sulla Terra (vedi sotto) |
| P02 | Scatto `top` georiferito (`epsg` valorizzato) | info | caricato in EPSG reale, sovrapponibile al resto |
| P03 | Scatto `top` non georiferito | attenzione | come C01 |
| P04 | Scatto in scala 1:N con DPI | info | mostra la dimensione di stampa; avverte che il progetto QGIS deve essere in metri |

### 7.4 Scatti e prospetti — la parte delicata
Dal codice di `ortho_worker.py`: uno scatto non-pianta ha un GeoTIFF con coordinate **del piano immagine** (metri, origine nell'angolo/posizione scelti), identico al `.wld/.tfw`. Se QGIS lo caricasse con un CRS "vero" finirebbe in un punto a caso del mondo. Regole:

1. Si crea un **CRS ingegneristico locale** (`LOCAL_CS`/CRS personalizzato "WebODM scatto <nome>", metri), mai un EPSG terrestre.
2. Lo scatto si carica in un **gruppo "Prospetti"** e si propone di aprirlo in una **mappa separata** (`QgsMapCanvas` dedicata / nuova vista di layout), non nel canvas principale del progetto.
3. `.points` (punti di controllo con coordinate tonde) si offrono al *Georeferenziatore* di QGIS se l'utente vuole poi posizionarlo davvero.
4. Idea fase 3: dai parametri `rotation` + `position` + `upper_left_m` ricostruire l'impronta 3D dello scatto e disegnarla come poligono nel CRS del modello (per vedere "dove" è stato scattato il prospetto), cioè l'impronta della camera, non il raster.

## 8. Interfaccia

### 8.1 Scelta di progetto e task

Il plugin non "indovina" mai il task: lo sceglie l'utente, in due modi che restano sincronizzati.

- **Nel pannello**, in alto: tre elenchi a cascata **Server ▸ Progetto ▸ Task**. Il progetto si cerca per nome; il task mostra nome, data, stato (solo i *completati* sono selezionabili per i prodotti; gli altri in grigio con lo stato), numero di foto, e un'icona se è georiferito.
- **Finestra "Scegli progetto e task…"** (menu e barra): tabella con ricerca e ordinamento, anteprima dell'ortofoto del task, dettagli (EPSG, estensione, dimensione dei prodotti, presenza del plugin WebODM). Multi-selezione di task per caricare più rilievi insieme: ognuno va in un **gruppo del Layers Panel con il nome del task** e un colore di etichetta.
- Elenchi paginati (WebODM pagina le risposte), caricati in background, con cache breve e pulsante Aggiorna.
- **Memoria**: ultima scelta per server; in più, la scelta viene scritta **nel progetto QGIS** (`QgsProject.writeEntry`: server, id progetto, id/uuid task, cartella foto locale), così riaprendo il `.qgz` il pannello ripropone lo stesso task e "Aggiorna prodotti" sa da dove venivano i layer. Nessuna credenziale nel progetto.
- Task cancellato o non più accessibile → avviso e il progetto QGIS continua a funzionare con i file in cache.
- Ogni azione (Carica ortofoto, Punti di scatto, Scatti…) opera sul **task scelto** ed è disabilitata, con tooltip esplicativo, se nulla è scelto.

**Menu** — voce di primo livello **WebODM** (e copia sotto *Plugin*): Collega…, **Scegli progetto e task…**, Aggiorna elenco, Prodotti del task…, **Punti di scatto delle foto**, **Strumento Foto**, Carica ortofoto (rapido), Scatti e prospetti…, Visualizzatore WebODM, Verifica CRS del progetto, Impostazioni, Guida, Informazioni.

**Barra** "WebODM": Collega · **Progetto/Task** · Aggiorna · Pannello · Ortofoto · Nuvola · **Punti foto** · **Strumento Foto** · Scatti · Visualizzatore · Verifica CRS. Icone SVG proprie, tutte con tooltip e abilitate solo se coerenti (es. "Ortofoto" attiva solo con un task selezionato che la possiede).

**Pannello (dock)** a sinistra, sotto il Browser:
- in alto: server attivo, stato connessione, **selettore Progetto ▸ Task** (§8.1);
- sotto: i prodotti del task scelto, a gruppi (Ortofoto, Quote, Nuvola, **Foto**, Scatti…), con semaforo CRS e dimensione;
- clic destro: *Carica in QGIS*, *Scarica solo*, *Apri nel visualizzatore*, *Mostra avvisi CRS*, *Copia URL*, *Apri cartella cache*;
- doppio clic = azione predefinita del tipo (ortofoto → carica; scatto → galleria);
- in basso: barra di avanzamento dei download (`QgsTask`, visibili anche nel gestore attività di QGIS).

**Integrazione Browser di QGIS** (fase 3): provider `QgsDataItemProvider` "WebODM", così i prodotti si trascinano sul canvas come un servizio WFS/XYZ.

**Visualizzatore WebODM** — tre livelli:
1. *Web*: `QWebEngineView` in un dock con profilo cookie dedicato (il login resta), mostra dashboard, **vista 3D Potree** (con il pannello del plugin WebODM) e **mappa 2D** del task. Barra con Indietro/Avanti/Ricarica e "Apri nel browser". Se QtWebEngine non è disponibile (Linux/macOS minimali) il pulsante apre il browser di sistema.
2. *Galleria scatti* nativa: miniature `_preview.jpg`, metadati (vista, scala 1:N, DPI, dimensione in m, sorgente mesh/nuvola, clip, EPSG), azioni *Carica*, *Apri PDF*, *Confronta due scatti* (cursore a tendina).
3. *Vista 3D nativa* della nuvola con la 3D View di QGIS (solo LAZ già indicizzato/COPC).

Lingue: italiano come chiave e inglese; stessa regola del plugin WebODM (il testo italiano nel codice è la chiave, `tr()`), ampliabile alle altre cinque lingue più avanti.

## 9. Sicurezza e robustezza
- Credenziali solo in `QgsAuthManager`; niente token in URL, log, `.qgz`.
- Nomi file e percorsi che arrivano dal server **validati** (niente `..`, niente percorsi assoluti, estensioni ammesse) prima di scrivere su disco; decompressione ZIP con controllo anti-"zip slip".
- HTTPS: si usa la gestione certificati di QGIS; per `http://localhost` nessun avviso. Avvertire se si invia la password su `http://` non locale.
- Download in `QgsTask`: interrompibile, non blocca la UI; file parziali con estensione `.part`, rinominati a fine download.
- Le foto originali scaricate vanno in cache con nome validato; mai eseguire file: si aprono solo estensioni immagine (jpg, jpeg, tif, tiff, png, dng) con il visualizzatore del sistema.
- Il plugin WebODM resta l'unico che *scrive* sul server; questo plugin è in **sola lettura** (nessun POST/PUT/DELETE in v1).
- Un server senza il plugin WebODM, o con versione diversa, non deve mai far fallire il resto (`api_version` + 404 gestiti).

## 10. Test
- `tests/test_crs_guard.py`, `test_catalog.py`, `test_urls.py`: Python puro, tabella di casi per ogni codice C/P.
- `tests/test_photos.py`: `shots.geojson` reale → `PhotoShot`; nomi file ostili (`../x`, percorsi assoluti) rifiutati; stato originale `?`/sì/no; ricerca nella cartella locale.
- `tests/test_selection.py`: serializzazione scelta server/progetto/task dentro il progetto QGIS; task non più esistente.
- `tests/test_client.py`: server WebODM finto (http.server) con risposte registrate dal vero.
- `tests/test_qgis_integration.py`: eseguiti con `python-qgis.bat` (QGIS 4.2.2) su file di esempio: carica raster, nuvola, scatto con CRS locale, verifica CRS e avvisi.
- `tests/test_loader_meta.py`: `metadata.txt` valido, nessun `PyQt5`, nessun import vietato.
- Prova dal vivo con il task 7 di WebODM **in sola lettura** (nessuna scrittura sul task: questo plugin non ne fa).

## 11. Fasi

| Fase | Contenuto | Esito atteso |
|---|---|---|
| **0 – Spike** (≈ mezza giornata) | rotte WebODM reali (**contenuto di `shots.geojson`; rotte `images/download` e `images/thumbnail`; paginazione di progetti/task**), `qgis.PyQt` + WebEngine in QGIS 4, plugin vuoto con menu/barra/dock che si installa | conferma delle ipotesi di §2 e §5.2 |
| **1 – Nucleo** | login, **selettore progetto/task** (pannello + finestra, memoria nel `.qgz`), catalogo standard, download in `QgsTask`, caricamento ortofoto/DSM/nuvola, **punti di scatto con azione "Apri foto originale"** (nome file, controllo presenza, cartella locale), `crs_guard` C01–C06, C12, C13 | usabile ogni giorno per i prodotti ODM e per le foto |
| **2 – Plugin WebODM** | prodotti del plugin (export, scatti), P01–P04, CRS locali, rotta `products` lato WebODM; **pannello Foto con miniatura e strumento Foto**, verifica massiva degli originali | gli scatti/prospetti arrivano in QGIS senza errori di posizione; foto consultabili dal clic |
| **3 – Visualizzatore** | WebEngine, galleria scatti, impronta camera, Browser provider | tutto senza uscire da QGIS |
| **4 – Rifinitura** | lingue, guida con immagini (come `docs/` dell'altro plugin), Processing provider (download in blocco), pubblicazione sul repository plugin | rilascio |

## 12. Decisioni aperte (servono a te)

1. **Streaming vs download dell'ortofoto**: default proposto = *scarica* (lavoro offline, progetto portabile), con "streaming" come opzione. Va bene?
2. **Prospetti in QGIS**: default proposto = CRS locale + gruppo separato + mappa dedicata (§7.4). Oppure vuoi che si sovrappongano comunque al modello 3D in qualche modo (impronta camera, fase 3)?
3. **Server**: solo WebODM locale (desktop) o anche server remoti con HTTPS? Cambia quanto curare il login e gli avvisi di sicurezza.
4. **Lingue** alla prima versione: solo italiano + inglese, o subito le sette del plugin WebODM?
5. **Ritocco al plugin WebODM** (rotta `products`, §5.3): lo autorizzi in fase 2, o il plugin QGIS deve restare compatibile con la versione attuale senza modificarla?
6. **Foto originali**: aprirle con il visualizzatore del sistema (proposto) o solo nel pannello Foto dentro QGIS? E la cartella locale delle foto come ripiego va bene?
7. **Compatibilità QGIS 3.44**: solo QGIS 4 (come chiesto), oppure doppia versione con uno strato `qgis.PyQt`? Costo stimato +20 % sul lavoro Qt.
