#!/usr/bin/env python3
"""Costruisce la guida in italiano e in inglese (HTML in un solo file, immagini incorporate).

    python docs/build_docs.py

Le schermate vengono da `python qgis_dev.py shots` (docs/img_it e docs/img_en, fatte nel QGIS 4 vero).
Escono in webodm2qgis_tools/docs/guide_it.html e guide_en.html: il pulsante "Guida" del plugin le apre.
"""
import base64
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'webodm2qgis_tools', 'docs')
AUTHOR, SITE = 'Luca Mandolesi', 'https://flyoveracademy.it'
REPO = 'https://github.com/pyarchinit/webodm2QGIS_tools'


def version():
    for line in open(os.path.join(ROOT, 'webodm2qgis_tools', 'metadata.txt'), encoding='utf-8'):
        if line.startswith('version='):
            return line.split('=', 1)[1].strip()
    return '?'


def img(lang, name, alt, width=None):
    path = os.path.join(HERE, 'img_' + lang, name + '.png')
    if not os.path.isfile(path):
        return '<p class="missing">[%s]</p>' % html.escape(name)
    data = base64.b64encode(open(path, 'rb').read()).decode('ascii')
    w = ' style="max-width:%dpx"' % width if width else ''
    return ('<figure><img src="data:image/png;base64,%s" alt="%s"%s><figcaption>%s</figcaption></figure>'
            % (data, html.escape(alt), w, html.escape(alt)))


# ---------------------------------------------------------------------------------------------------------
# Testi. Blocchi: ('h2', titolo) ('p', html) ('ul', [html...]) ('img', nome, didascalia, larghezza) ('table', righe) ('warn', html)
# ---------------------------------------------------------------------------------------------------------
IT = {
    'lang': 'it', 'title': 'WebODM2QGIS-tools - Guida', 'toc': 'Indice',
    'subtitle': 'Plugin per QGIS 4 che elenca e importa i prodotti di WebODM',
    'blocks': [
        ('warn', "<b>Software sperimentale, per QGIS 4. Puo' fare danni.</b> Realizzato da <b>%(a)s</b> di "
                 "<a href='%(s)s'>Flyoveracademy.it</a>. Scritto interamente con <b>Claude Code</b> (modelli Claude Sonnet e "
                 "Opus di Anthropic). Fornito senza alcuna garanzia, uso a tuo rischio: scrive file nella cartella che "
                 "scegli e puo' sovrascrivere file con lo stesso nome; puo' cambiare il CRS del progetto QGIS e aggiungere "
                 "molti layer; salva la password del server nel gestore di autenticazione di QGIS. Lavora su una copia del "
                 "progetto, fai un backup e usa una cartella dedicata. Non scrive nulla sul server WebODM (sola lettura)."),
        ('h2', 'Che cos\'e\''),
        ('p', "WebODM2QGIS-tools si collega a un server <b>WebODM</b> (anche l'app per Windows aperta sul tuo PC) e porta "
              "in QGIS i prodotti dei task senza passare da scarica &rarr; decomprimi &rarr; importa: ortofoto, DSM/DTM, "
              "nuvole di punti, <b>punti di scatto delle foto</b> con apertura dell'originale, e i prodotti del plugin "
              "<i>webodm-model-tools</i> (nuvola scalata o georiferita, <b>scatti e prospetti</b>). Prima di caricare "
              "controlla EPSG, georiferimento e CRS e ti avvisa dei rischi."),
        ('img', 'finestra_qgis', 'QGIS 4 con il menu WebODM, la barra, il pannello a sinistra e il pannello Foto a destra', 900),
        ('h2', 'Installazione'),
        ('ul', ["Serve <b>QGIS 4</b> (Qt6). Non funziona con QGIS 3.",
                "Da ZIP: <i>Plugin &rarr; Gestisci e installa plugin &rarr; Installa da ZIP</i> e scegli <code>webodm2qgis_tools.zip</code>.",
                "Dal sorgente: copia la cartella <code>webodm2qgis_tools</code> in <code>%APPDATA%\\QGIS\\QGIS4\\profiles\\default\\python\\plugins</code> "
                "e attivala in <i>Gestisci e installa plugin &rarr; Installati</i>.",
                "Compaiono il menu <b>WebODM</b>, la barra <b>WebODM</b> e il pannello a sinistra. Il pulsante <b>Guida</b> (nel pannello e nel menu) apre questa guida."]),
        ('h2', '1. Collegarsi a WebODM'),
        ('p', "Pulsante <b>&laquo;...&raquo;</b> nel pannello (o menu <i>WebODM &rarr; Collega a WebODM</i>). Inserisci indirizzo, "
              "utente e password e premi <b>Salva e collega</b>. La password va nel <b>gestore di autenticazione di QGIS</b> "
              "(ti chiede la password principale), mai nel progetto. Per indirizzi remoti usa <code>https</code>: con "
              "<code>http</code> la password viaggerebbe in chiaro e il plugin ti avvisa."),
        ('img', 'dlg_server', 'Finestra dei server WebODM', 640),
        ('p', "<b>App WebODM per Windows aperta sul PC</b>: premi <b>WebODM locale</b>. Il plugin compila "
              "<code>http://127.0.0.1:29800</code> (il server dell'app ascolta solo su questo computer) e controlla che sia "
              "acceso. Poi inserisci utente e password con cui entri nell'app (quelli predefiniti dell'app sono <code>admin / admin</code>, "
              "da cambiare). Il login e' un accesso a parte (JWT): la finestra dell'app puo' restare aperta."),
        ('h2', '2. Scegliere progetto e task'),
        ('p', "Nel pannello trovi gli elenchi <b>Progetto</b> e <b>Task</b>, oppure <b>Scegli...</b> per una finestra con "
              "ricerca, stato, numero di foto, anteprima e se il task e' georiferito. Si caricano solo task <b>completati</b>."),
        ('img', 'dlg_picker', 'Scelta di progetto e task', 760),
        ('h2', '3. Sessione di import: nome e cartella'),
        ('p', "Al primo caricamento il plugin chiede un <b>nome</b> e una <b>cartella</b>. I file vanno in "
              "<code>cartella\\nome\\task_id\\...</code>, il gruppo nel pannello Livelli prende il nome della sessione e un "
              "file <code>sessione.json</code> elenca cosa e' stato importato. Nome e cartella sono salvati nel progetto QGIS "
              "e si cambiano con <b>Sessione...</b>."),
        ('img', 'dlg_sessione', 'Sessione di import', 640),
        ('h2', '4. Prodotti e semaforo CRS'),
        ('p', "Seleziona uno o piu' prodotti e premi <b>Carica nel progetto</b> (o doppio clic). Il pallino dice se ci sono "
              "avvisi: verde = nessuno, giallo = da leggere, rosso = serve una decisione. Il tooltip spiega perche'. "
              "I download sono in streaming su file, si possono annullare e riprendono se interrotti."),
        ('img', 'dock_prodotti', 'Pannello dei prodotti di un task', 420),
        ('h2', '5. Avvisi su EPSG e CRS'),
        ('p', "Se c'e' qualcosa da decidere compare una finestra con le scelte. Non viene mai assegnato un CRS a caso."),
        ('img', 'dlg_crs', 'Avviso CRS con le scelte possibili', 640),
        ('table', [("Codice", "Quando", "Cosa puoi fare"),
                   ("C01", "task non georiferito (zona UTM fittizia)", "caricare sapendo che la posizione non ha significato"),
                   ("C02", "CRS del prodotto diverso da quello del progetto", "riproiettare al volo o adottare il CRS del prodotto"),
                   ("C03", "file senza CRS", "assegnare tu l'EPSG"),
                   ("C04", "EPSG del task diverso dal CRS del file", "si usa quello del file"),
                   ("C05", "CRS in gradi dove servono metri", "usare un CRS proiettato"),
                   ("C06 / C10 / C11", "trasformazione non disponibile, prodotto lontano, file grande o poco spazio", "conferma"),
                   ("C07", "quote senza datum verticale", "informazione"),
                   ("C08", "esiste la versione scalata dal plugin WebODM", "scegliere il prodotto giusto"),
                   ("C12 / P10", "punti di scatto: posizione stimata dalla ricostruzione", "informazione"),
                   ("P01-P05", "prospetti, sezioni e modelli non georiferiti del plugin", "CRS locale, mappa separata"),
                   ("P07-P09", "il CRS del progetto non va bene per posizionare uno scatto", "impostare un CRS proiettato in metri")]),
        ('p', "Menu <i>WebODM &rarr; Verifica CRS del progetto</i>: elenca i layer fuori dal CRS del progetto, in gradi, senza CRS o in CRS locale."),
        ('h2', '6. Punti di scatto delle foto e originali'),
        ('p', "Il prodotto <b>Punti di scatto delle foto</b> crea un layer puntuale con una freccia orientata, quota, orientamento, "
              "camera, data e il campo <code>originale</code> (<code>?</code>, <code>si</code>, <code>no</code>). "
              "Per aprire la foto originale: <b>strumento Foto</b> (barra) &mdash; un clic mostra miniatura e dati, il doppio clic apre "
              "l'originale; oppure lo strumento QGIS &laquo;Esegui azione sull'elemento&raquo;; oppure il pulsante <b>Apri originale</b>."),
        ('img', 'pannello_foto', 'Pannello Foto con miniatura, dati e pulsanti', 420),
        ('ul', ["Ordine di ricerca: <b>cartella locale delle foto</b> (se indicata), copia gia' scaricata nella sessione, <b>server</b>.",
                "Se l'originale non e' piu' sul server il campo diventa <code>no</code> e lo dice, senza errori. <b>Verifica tutti gli originali</b> riempie il campo per tutto il task.",
                "I file sopra 30 MB chiedono conferma prima di scaricarsi."]),
        ('h2', '7. Foto che seguono il modello (scalato, ruotato, georiferito)'),
        ('p', "<code>shots.geojson</code> e' nel riferimento <b>originale</b> di ODM. Se hai scalato, ruotato o georiferito il modello "
              "con il plugin WebODM, per seguirlo le foto vanno trasformate con la stessa matrice. Nel gruppo <b>Foto</b> trovi tre prodotti:"),
        ('ul', ["<b>Punti di scatto delle foto</b>: riferimento originale (va con la nuvola originale). Nei task <b>non georiferiti</b> usa i metri locali del modello, non i gradi del file (che finirebbero a 0,0).",
                "<b>Punti di scatto &ndash; georiferiti con il plugin WebODM, EPSG:xxxx</b>: coordinate assolute (va con la nuvola georiferita).",
                "<b>Punti di scatto &ndash; scalati e orientati con il plugin WebODM</b>: coordinate locali, nel sottogruppo <i>CRS locale</i> (vanno con la nuvola scalata)."]),
        ('p', "Anche la direzione delle frecce ruota con il modello. Se cambi scala o georiferimento dopo l'export, esporta di nuovo, altrimenti nuvola e foto non coincidono."),
        ('h2', '8. Scatti e prospetti del plugin WebODM'),
        ('p', "La scheda <b>Scatti e prospetti</b> mostra le miniature e i dati (vista, dimensione, scala 1:N, dpi, EPSG) degli scatti creati con il plugin WebODM."),
        ('img', 'dock_scatti', 'Galleria degli scatti', 420),
        ('ul', ["<b>Pianta georiferita</b>: si carica nell'EPSG reale e si sovrappone al resto.",
                "<b>Prospetto, sezione o pianta non georiferita</b>: il GeoTIFF ha le coordinate del piano dell'immagine in metri, <b>non</b> una posizione sulla Terra. Si carica con un <b>CRS locale</b> in un sottogruppo spento e si apre in una <b>mappa a parte</b>. Il file <code>.points</code> arriva accanto, per il Georeferenziatore di QGIS."]),
        ('img', 'visualizzatore_scatto', 'Mappa dedicata di un prospetto (CRS locale)', 640),
        ('h3', 'Posizionare uno scatto sul canvas'),
        ('p', "Con lo scatto caricato, accendi la <b>modalita' posizionamento</b>, clicca un punto sul canvas di QGIS: le coordinate vengono catturate "
              "(correggibili a mano) e <b>Posiziona qui</b> crea una copia georiferita con l'<b>angolo in alto a sinistra</b> sul punto, nel CRS del progetto "
              "(un file VRT leggero: nessun dato copiato, l'originale resta com'e'). Il CRS del progetto deve essere proiettato in metri. "
              "Non ruota ne' cambia la scala dello scatto."),
        ('img', 'dock_posiziona', 'Posizionamento sul canvas con X, Y e CRS del progetto', 420),
        ('h2', '9. Export del plugin WebODM e nuvola georiferita'),
        ('p', "Il gruppo <b>Export del plugin WebODM</b> elenca i file salvati con <i>webodm-model-tools</i>. La <b>nuvola georiferita</b> riceve "
              "l'EPSG scelto nella sezione Georiferimento del plugin: se nel file il CRS manca viene assegnato quello, senza bloccarti. "
              "La <b>nuvola scalata</b> non georiferita ha coordinate locali: va in CRS locale, spenta, a parte dalla mappa."),
        ('h2', '10. Visualizzatore WebODM dentro QGIS'),
        ('p', "Menu <i>WebODM &rarr; Visualizzatore WebODM</i>: vista 3D, mappa 2D o dashboard del task dentro QGIS (QtWebEngine), con login automatico. "
              "Se QtWebEngine manca si apre il browser di sistema."),
        ('h2', '11. Lingua, informazioni e avvertenze'),
        ('p', "Lingue: italiano, inglese, francese, tedesco, spagnolo, portoghese. Si sceglie in <b>Informazioni &rarr; Lingua</b> "
              "(automatica = lingua di QGIS) e vale al prossimo avvio. Questa guida e' in italiano e in inglese."),
        ('img', 'dlg_about', 'Finestra Informazioni con crediti, avvertenze e lingua', 560),
        ('h2', 'Limiti noti'),
        ('ul', ["Una sessione puo' contenere piu' task, scelti uno dopo l'altro.",
                "Lo streaming dell'ortofoto richiede la password salvata nel gestore di autenticazione di QGIS (non scrive token nel progetto).",
                "Le mesh OBJ texturizzate si scaricano e si decomprimono ma QGIS non le mostra: usa il visualizzatore 3D di WebODM.",
                "La nuvola di punti si apre con il provider <i>pdal</i> di QGIS, che indicizza il file in background.",
                "Provato su QGIS 4.2 e su un finto server WebODM; il visualizzatore web con scheda grafica non e' stato verificato in automatico."]),
        ('h2', 'Licenza e crediti'),
        ('p', "Copyright &copy; 2026 %(a)s &mdash; <a href='%(s)s'>Flyoveracademy.it</a>. Licenza <b>GNU GPL versione 2 o successiva</b> "
              "(la stessa di QGIS). Codice: <a href='%(r)s'>%(r)s</a>. Scritto interamente con Claude Code (Claude Sonnet e Opus). "
              "Software sperimentale fornito &laquo;cosi' com'e'&raquo;, senza garanzie di alcun tipo: l'autore non risponde di danni o perdite di dati."),
    ],
}

EN = {
    'lang': 'en', 'title': 'WebODM2QGIS-tools - Guide', 'toc': 'Contents',
    'subtitle': 'QGIS 4 plugin that lists and imports WebODM products',
    'blocks': [
        ('warn', "<b>Experimental software, for QGIS 4. It can cause damage.</b> Created by <b>%(a)s</b> of "
                 "<a href='%(s)s'>Flyoveracademy.it</a>. Written entirely with <b>Claude Code</b> (Anthropic Claude Sonnet and "
                 "Opus models). Provided without any warranty, use at your own risk: it writes files into the folder you "
                 "choose and may overwrite files with the same name; it can change the CRS of the QGIS project and add many "
                 "layers; it saves the server password in the QGIS authentication manager. Work on a copy of the project, make a "
                 "backup and use a dedicated folder. It writes nothing to the WebODM server (read-only)."),
        ('h2', 'What it is'),
        ('p', "WebODM2QGIS-tools connects to a <b>WebODM</b> server (including the Windows app open on your PC) and brings task "
              "products into QGIS without the download &rarr; unzip &rarr; import routine: orthophotos, DSM/DTM, point clouds, "
              "<b>photo shot points</b> with one-click access to the original, and the products of the <i>webodm-model-tools</i> "
              "plugin (scaled or georeferenced cloud, <b>shots and elevations</b>). Before loading it checks EPSG, "
              "georeferencing and CRS and warns you about risks."),
        ('img', 'finestra_qgis', 'QGIS 4 with the WebODM menu, toolbar, the panel on the left and the Photos panel on the right', 900),
        ('h2', 'Installation'),
        ('ul', ["Requires <b>QGIS 4</b> (Qt6). It does not work with QGIS 3.",
                "From ZIP: <i>Plugins &rarr; Manage and Install Plugins &rarr; Install from ZIP</i> and choose <code>webodm2qgis_tools.zip</code>.",
                "From source: copy the <code>webodm2qgis_tools</code> folder into <code>%APPDATA%\\QGIS\\QGIS4\\profiles\\default\\python\\plugins</code> "
                "and enable it in <i>Manage and Install Plugins &rarr; Installed</i>.",
                "The <b>WebODM</b> menu, the <b>WebODM</b> toolbar and the panel on the left appear. The <b>Guide</b> button (in the panel and in the menu) opens this guide."]),
        ('h2', '1. Connect to WebODM'),
        ('p', "Button <b>&laquo;...&raquo;</b> in the panel (or menu <i>WebODM &rarr; Connect to WebODM</i>). Enter address, user and "
              "password and press <b>Save and connect</b>. The password goes into the <b>QGIS authentication manager</b> (it asks "
              "for the master password), never into the project. For remote addresses use <code>https</code>: with "
              "<code>http</code> the password would travel in clear text and the plugin warns you."),
        ('img', 'dlg_server', 'WebODM servers window', 640),
        ('p', "<b>WebODM Windows app open on your PC</b>: press <b>Local WebODM</b>. The plugin fills in "
              "<code>http://127.0.0.1:29800</code> (the app's server only listens on this computer) and checks that it is running. "
              "Then enter the user and password you use in the app (the app defaults are <code>admin / admin</code>, to be changed). "
              "The login is a separate access (JWT): the app window can stay open."),
        ('h2', '2. Choose project and task'),
        ('p', "The panel has the <b>Project</b> and <b>Task</b> lists, or <b>Choose...</b> for a window with search, status, photo count, "
              "preview and whether the task is georeferenced. Only <b>completed</b> tasks can be loaded."),
        ('img', 'dlg_picker', 'Choosing project and task', 760),
        ('h2', '3. Import session: name and folder'),
        ('p', "On the first load the plugin asks for a <b>name</b> and a <b>folder</b>. Files go to "
              "<code>folder\\name\\task_id\\...</code>, the group in the Layers panel takes the session name and a "
              "<code>sessione.json</code> file lists what was imported. Name and folder are saved in the QGIS project and "
              "changed with <b>Session...</b>."),
        ('img', 'dlg_sessione', 'Import session', 640),
        ('h2', '4. Products and CRS traffic light'),
        ('p', "Select one or more products and press <b>Load into project</b> (or double-click). The dot tells whether there are warnings: "
              "green = none, yellow = read them, red = a decision is needed. The tooltip explains why. "
              "Downloads stream to file, can be cancelled and resume if interrupted."),
        ('img', 'dock_prodotti', 'Products panel of a task', 420),
        ('h2', '5. EPSG and CRS warnings'),
        ('p', "When there is something to decide a window with the choices appears. A CRS is never assigned at random."),
        ('img', 'dlg_crs', 'CRS warning with the available choices', 640),
        ('table', [("Code", "When", "What you can do"),
                   ("C01", "task not georeferenced (fictitious UTM zone)", "load it knowing the position is meaningless"),
                   ("C02", "product CRS differs from the project CRS", "reproject on the fly or adopt the product CRS"),
                   ("C03", "file without CRS", "assign the EPSG yourself"),
                   ("C04", "task EPSG differs from the file CRS", "the file CRS is used"),
                   ("C05", "CRS in degrees where metres are needed", "use a projected CRS"),
                   ("C06 / C10 / C11", "transformation unavailable, product far away, big file or low disk space", "confirm"),
                   ("C07", "heights without a vertical datum", "information"),
                   ("C08", "a version scaled with the WebODM plugin exists", "pick the right product"),
                   ("C12 / P10", "shot points: position estimated by the reconstruction", "information"),
                   ("P01-P05", "elevations, sections and non-georeferenced models of the plugin", "local CRS, separate map"),
                   ("P07-P09", "the project CRS is not suitable to place a shot", "set a projected CRS in metres")]),
        ('p', "Menu <i>WebODM &rarr; Check project CRS</i>: lists layers outside the project CRS, in degrees, without CRS or in a local CRS."),
        ('h2', '6. Photo shot points and originals'),
        ('p', "The <b>Photo shot points</b> product creates a point layer with an oriented arrow, elevation, orientation, camera, date and the "
              "<code>originale</code> field (<code>?</code>, <code>si</code>, <code>no</code>). To open the original photo: <b>Photo tool</b> "
              "(toolbar) &mdash; one click shows thumbnail and data, a double-click opens the original; or the QGIS &laquo;Run feature action&raquo; tool; "
              "or the <b>Open original</b> button."),
        ('img', 'pannello_foto', 'Photo panel with thumbnail, data and buttons', 420),
        ('ul', ["Search order: <b>local photo folder</b> (if set), copy already downloaded in the session, <b>server</b>.",
                "If the original is no longer on the server the field becomes <code>no</code> and it tells you, without errors. <b>Verify all originals</b> fills the field for the whole task.",
                "Files over 30 MB ask for confirmation before downloading."]),
        ('h2', '7. Photos that follow the model (scaled, rotated, georeferenced)'),
        ('p', "<code>shots.geojson</code> is in the <b>original</b> ODM frame. If you scaled, rotated or georeferenced the model with the "
              "WebODM plugin, the photos must be transformed with the same matrix to follow it. The <b>Photos</b> group offers three products:"),
        ('ul', ["<b>Photo shot points</b>: original frame (goes with the original cloud). In <b>non-georeferenced</b> tasks it uses the model's local metres, not the file's degrees (which would land at 0,0).",
                "<b>Shot points &ndash; georeferenced with the WebODM plugin, EPSG:xxxx</b>: absolute coordinates (goes with the georeferenced cloud).",
                "<b>Shot points &ndash; scaled and oriented with the WebODM plugin</b>: local coordinates, in the <i>local CRS</i> subgroup (goes with the scaled cloud)."]),
        ('p', "The arrow directions also rotate with the model. If you change scale or georeferencing after the export, export again, otherwise cloud and photos will not match."),
        ('h2', '8. Shots and elevations from the WebODM plugin'),
        ('p', "The <b>Shots and elevations</b> tab shows thumbnails and data (view, size, scale 1:N, dpi, EPSG) of the shots made with the WebODM plugin."),
        ('img', 'dock_scatti', 'Shots gallery', 420),
        ('ul', ["<b>Georeferenced plan</b>: loaded in its real EPSG and overlays the rest.",
                "<b>Elevation, section or non-georeferenced plan</b>: the GeoTIFF has image-plane coordinates in metres, <b>not</b> a position on Earth. It is loaded with a <b>local CRS</b> in a switched-off subgroup and opened in a <b>separate map</b>. The <code>.points</code> file comes along, for the QGIS Georeferencer."]),
        ('img', 'visualizzatore_scatto', 'Dedicated map of an elevation (local CRS)', 640),
        ('h3', 'Placing a shot on the canvas'),
        ('p', "With the shot loaded, turn the <b>placement mode</b> on and click a point on the QGIS canvas: the coordinates are captured "
              "(editable by hand) and <b>Place here</b> creates a georeferenced copy with the <b>top-left corner</b> on that point, in the project CRS "
              "(a light VRT file: no data copied, the original is left as it is). The project CRS must be projected in metres. "
              "It does not rotate or rescale the shot."),
        ('img', 'dock_posiziona', 'Placement on the canvas with X, Y and the project CRS', 420),
        ('h2', '9. WebODM plugin exports and the georeferenced cloud'),
        ('p', "The <b>WebODM plugin exports</b> group lists the files saved with <i>webodm-model-tools</i>. The <b>georeferenced cloud</b> gets the EPSG chosen in the "
              "plugin's Georeferencing section: if the file has no CRS that one is assigned, without blocking you. The non-georeferenced "
              "<b>scaled cloud</b> has local coordinates: it goes in a local CRS, switched off, apart from the map."),
        ('h2', '10. WebODM viewer inside QGIS'),
        ('p', "Menu <i>WebODM &rarr; WebODM viewer</i>: 3D view, 2D map or dashboard of the task inside QGIS (QtWebEngine), with automatic login. "
              "If QtWebEngine is missing the system browser opens."),
        ('h2', '11. Language, About and warnings'),
        ('p', "Languages: Italian, English, French, German, Spanish, Portuguese. Choose in <b>About &rarr; Language</b> "
              "(automatic = QGIS language); it applies at the next start. This guide is in Italian and English."),
        ('img', 'dlg_about', 'About window with credits, warnings and language', 560),
        ('h2', 'Known limits'),
        ('ul', ["A session can hold several tasks, chosen one after the other.",
                "Orthophoto streaming needs the password saved in the QGIS authentication manager (no token is written into the project).",
                "Textured OBJ meshes are downloaded and unzipped but QGIS does not show them: use the WebODM 3D viewer.",
                "The point cloud opens with QGIS's <i>pdal</i> provider, which indexes the file in the background.",
                "Tested on QGIS 4.2 and on a fake WebODM server; the web viewer with a graphics card was not verified automatically."]),
        ('h2', 'License and credits'),
        ('p', "Copyright &copy; 2026 %(a)s &mdash; <a href='%(s)s'>Flyoveracademy.it</a>. License <b>GNU GPL version 2 or later</b> "
              "(the same as QGIS). Code: <a href='%(r)s'>%(r)s</a>. Written entirely with Claude Code (Claude Sonnet and Opus). "
              "Experimental software provided &laquo;as is&raquo;, without warranty of any kind: the author is not liable for damage or data loss."),
    ],
}

CSS = """
:root{--bg:#fff;--fg:#1c2330;--mut:#5a6577;--acc:#2b6cb0;--card:#f4f6f9;--line:#d8dee8;--warn-bg:#fff1f0;--warn-bd:#c92a2a}
@media (prefers-color-scheme:dark){:root{--bg:#14181f;--fg:#e6eaf0;--mut:#9aa6b8;--acc:#6aa9ec;--card:#1c222c;--line:#2e3644;--warn-bg:#2a1717;--warn-bd:#e86b6b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:24px 16px 80px}
header h1{margin:.2em 0 0;font-size:2rem}header p{color:var(--mut);margin:.2em 0 1em}
h2{margin:2em 0 .4em;padding-top:.6em;border-top:1px solid var(--line);font-size:1.35rem}h3{margin:1.4em 0 .3em}
a{color:var(--acc)}code{background:var(--card);padding:.1em .35em;border-radius:4px;font-size:.92em}
figure{margin:1em 0;text-align:center}figure img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:6px;box-shadow:0 2px 8px #0002}
figcaption{color:var(--mut);font-size:.88rem;margin-top:.4em}
.warn{background:var(--warn-bg);border:2px solid var(--warn-bd);border-radius:8px;padding:12px 16px;margin:1em 0}
table{border-collapse:collapse;width:100%;font-size:.94rem;display:block;overflow-x:auto}th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--card)}nav{background:var(--card);border-radius:8px;padding:10px 16px;margin:1em 0;font-size:.93rem}nav a{margin-right:.7em;white-space:nowrap}
.missing{color:var(--warn-bd)}footer{margin-top:3em;color:var(--mut);font-size:.88rem;border-top:1px solid var(--line);padding-top:1em}
@media (max-width:600px){body{font-size:15px}}
"""


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', re.sub(r'<[^>]+>', '', text).lower()).strip('-') or 'sec'


def render(cfg):
    lang = cfg['lang']
    sub = {'a': AUTHOR, 's': SITE, 'r': REPO}
    body, toc = [], []
    for blk in cfg['blocks']:
        k = blk[0]
        if k == 'h2':
            sid = slug(blk[1])
            toc.append('<a href="#%s">%s</a>' % (sid, blk[1]))
            body.append('<h2 id="%s">%s</h2>' % (sid, blk[1]))
        elif k == 'h3':
            body.append('<h3>%s</h3>' % blk[1])
        elif k == 'p':
            body.append('<p>%s</p>' % (blk[1] % sub if '%(' in blk[1] else blk[1]))
        elif k == 'warn':
            body.append('<div class="warn">%s</div>' % (blk[1] % sub))
        elif k == 'ul':
            body.append('<ul>%s</ul>' % ''.join('<li>%s</li>' % i for i in blk[1]))
        elif k == 'img':
            body.append(img(lang, blk[1], blk[2], blk[3] if len(blk) > 3 else None))
        elif k == 'table':
            rows = blk[1]
            body.append('<table><tr>%s</tr>%s</table>' % (''.join('<th>%s</th>' % c for c in rows[0]),
                        ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % c for c in r) for r in rows[1:])))
    other = 'guide_en.html' if lang == 'it' else 'guide_it.html'
    return ('<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><style>%s</style></head><body><div class="wrap"><header><h1>%s</h1><p>%s &middot; v%s &middot; '
            '<a href="%s">%s</a></p></header><nav><b>%s:</b> %s</nav>%s<footer>WebODM2QGIS-tools v%s &middot; %s &middot; GPL-2.0-or-later</footer>'
            '</div></body></html>') % (lang, html.escape(cfg['title']), CSS, html.escape(cfg['title']), cfg['subtitle'], version(),
                                       other, 'English' if lang == 'it' else 'Italiano', cfg['toc'], ' '.join(toc), ''.join(body),
                                       version(), AUTHOR)


def main():
    os.makedirs(OUT, exist_ok=True)
    for cfg in (IT, EN):
        path = os.path.join(OUT, 'guide_%s.html' % cfg['lang'])
        text = render(cfg)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print('%s  %.0f KB' % (path, len(text) / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
