# sunnyportal2ha

**Die PV-Historie aus dem SMA Sunny Portal holen, aufbereiten und nach Home Assistant übernehmen.**

Wer eine Photovoltaikanlage von SMA betreibt, hat jahrelange Messdaten — aber sie
liegen in der Cloud des Herstellers und nicht im eigenen Haus. Wer auf Home
Assistant umsteigt, fängt dort bei null an: Das Energie-Dashboard kennt nur, was
seit der Installation aufgezeichnet wurde. Dieses Projekt schließt die Lücke.

Es holt den kompletten Bestand seit Inbetriebnahme in voller
Viertelstundenauflösung, rechnet ihn in ein importierbares Format um und spielt
ihn in die Langzeitstatistik von Home Assistant ein.

---

## Stand

```
  ┌────────────┐   ┌────────────┐   ┌──────────────────┐   ┌────────────┐
  │ 1 Export   │──▶│ 2 Analyse  │──▶│ 3 Transformation │──▶│ 4 Import   │
  │            │   │            │   │                  │   │            │
  │ Portal →   │   │ Was ist da?│   │ Einheiten        │   │ HA         │
  │ Dateien    │   │ Welcher WR │   │ Zeitstempel      │   │ aufräumen  │
  │            │   │ wann?      │   │ Lücken           │   │ → Statistik│
  └────────────┘   └────────────┘   └──────────────────┘   └────────────┘
    ✔ hier          in Arbeit          in Arbeit             geplant
```

**In diesem Repository liegt bislang nur Schritt 1.** Er ist für sich
brauchbar: Am Ende hat man die vollständige Historie der eigenen Anlage als
CSV- und JSON-Dateien auf der eigenen Platte, unabhängig davon, was man damit
weiter vorhat.

Die Schritte 2 bis 4 werden gerade entwickelt und kommen dazu, sobald sie an
mehr als einer Anlage geprüft sind. Ihre Aufgaben sind unten beschrieben —
teils, weil sie erklären, warum Schritt 1 bestimmte Dinge so macht, wie er sie
macht.

---

## Schritt 1 — Export

`1_export.py` holt drei verschiedene Datenarten, wahlweise einzeln oder mit
`alles` nacheinander — mit mehreren gleichzeitigen Verbindungen:

| Aufruf | Was es liefert | Zuschnitt |
|---|---|---|
| `1_export.py bilanz` | PV-Erzeugung, Gesamtverbrauch, Direktverbrauch, Netzbezug, **Netzeinspeisung**, Batterie | ein Monat je Abfrage |
| `1_export.py wechselrichter` | Ertrag **je Gerät** plus Anlagensumme | ein Monat je Abfrage |
| `1_export.py verbraucher` | die Kurven **je Verbraucher** — Wärmepumpe, Wallbox, Heizstab | ein Tag je Abfrage |

Für die Anlagensummen ist die Energiebilanz der beste Weg: ein ganzer Monat in
einer Anfrage, und sie ist die einzige Quelle mit der Netzeinspeisung.
Dreieinhalb Jahre sind damit in gut einer Viertelstunde exportiert. Die
Verbraucher gehen nur tageweise und dauern deshalb am längsten.

### Schnellstart

```bash
pip install requests
python 1_export.py
```

Ohne Argument wird alles geholt. Beim ersten Start wird `zugangsdaten.ini` als
Vorlage angelegt; dort trägst du die Zugangsdaten deines Sunny-Portal-Kontos
ein:

```ini
[sunnyportal]
benutzer = deine@mailadresse.de
passwort = deinPasswort

[export]
parallel = 4
timeout  = 300
```

Diese Datei steht in `.gitignore` und darf niemals ins Repository. Danach genügt
ein erneuter Aufruf; das Skript arbeitet sich Monat für Monat durch und legt die
Ergebnisse in `bilanz/`, `wechselrichter/` und `rohdaten/` ab.

Ein Abbruch mit `Strg+C` ist jederzeit gefahrlos — laufende Abfragen werden zu
Ende gebracht, fertige Zeiträume beim nächsten Start übersprungen.

**Tipp für große Zeiträume:** Das Portal erlaubt mehrere gleichzeitige
Anmeldungen und parallele Downloads. Wer nicht warten will, startet dasselbe
Skript mehrfach mit verschiedenen Zeiträumen — die Läufe kommen sich nicht in
die Quere, weil jeder Monat in seine eigene Datei geht und fertige Monate
übersprungen werden:

```bash
python 1_export.py verbraucher --von 2023-04 --bis 2024-06
python 1_export.py verbraucher --von 2024-07 --bis 2025-08   # zweites Fenster
python 1_export.py verbraucher --von 2025-09                 # drittes Fenster
```

Einfacher geht es aber über die Einstellung `parallel` in `zugangsdaten.ini`:
Dann erledigt ein einziger Aufruf das mit mehreren gleichzeitigen Verbindungen.
Bitte mit Augenmaß — es ist der Server eines Herstellers, nicht der eigene.
Vier bis sechs sind ein vernünftiger Bereich.

**Voraussetzungen:** Python 3.9 oder neuer, ein Sunny-Portal-Konto, und eine
Anlage mit Sunny Home Manager (nur dann gibt es die Energiebilanz-Seite).

---

## Wie der Zugriff funktioniert

Es gibt keine offene API. Der Weg führt über dieselben Aufrufe, die auch die
Weboberfläche benutzt — nur ohne Browser.

**Anmeldung.** Das Portal meldet über SMA ID an, einen Keycloak-Server. Das
Skript holt die Anmeldeseite, sendet Benutzername und Passwort an das
Formularziel und folgt der Weiterleitung zurück ins Portal. Kein Selenium, kein
Chromedriver.

**Energiebilanz.** Ihre Diagramme werden nachgeladen. Der Export macht dasselbe,
in drei Schritten:

```
1. GET /PortalCharts/Core/PortalChartsAPI.aspx?id=mainChart&presetting=day
      einmal je Sitzung; wählt das Zeitraster (day / month / year / total)

2. GET /PortalCharts/Core/PortalChartsAPI.aspx?id=mainChart&xf=<von>&xt=<bis>
      setzt den Zeitraum in der Sitzung; die Antwort ist ein Bild

3. GET /Templates/DownloadDiagram.aspx?down=homanEnergyRedesign&chartId=mainChart
      liefert die Daten des zuletzt gesetzten Diagramms als CSV
```

`xf` und `xt` sind Unix-Zeiten in Sekunden.

**Verbraucherbilanz.** Hier gibt es einen JSON-Endpunkt:

```
GET /Homan/ConsumerBalance/GetMeasuredValues
    ?IntervalId=<n>&PlantOid=<guid>&StartTime=JJJJ-MM-TT&EndTime=JJJJ-MM-TT
```

mit `IntervalId` 0=5min, 1=10min, 2=15min, 3=Stunde, 4=Tag, 5=Monat, 6=Jahr.
`EndTime` ist ausschließend. Mehrtägige Zeiträume nimmt der Endpunkt nur bei
Tageswerten an.

Anlagenkennung und Betriebszeitraum liest das Skript beim Start aus dem Portal.
Es ist an keine bestimmte Anlage gebunden.

---

## Fallstricke, die Zeit gekostet haben

Diese Punkte stehen hier, weil sie **stille Fehler** erzeugen — Läufe, die
erfolgreich aussehen und falsche Daten liefern. Jeder einzelne davon hat in der
Entwicklung mindestens einen halben Tag gekostet.

**Der Punkt ist der Tausendertrenner, nicht das Dezimalzeichen.** In der CSV
steht `1.008` für 1008 Watt und `"14,04"` für 14,04 Kilowattstunden. Wer den
Punkt als Dezimalzeichen liest, teilt jeden Wert ab tausend durch tausend — und
weil das nur die großen Werte trifft, sehen die Dateien danach immer noch
plausibel aus. Ein Monat kam so mit 2 kWh statt 536 kWh heraus. Gegenprobe: Die
Tagestabelle desselben Monats holen und die rekonstruierten Tagessummen damit
vergleichen; sie müssen auf unter ein Prozent übereinstimmen.

**Das Zeitraster muss man ansagen.** Die Diagrammanfrage kennt einen Parameter
`presetting` mit den Werten `day`, `month`, `year`, `total` — genau den schickt
der Browser, wenn man oben auf einen Reiter klickt. Ohne ihn entscheidet die
Vorgabe des Servers, und die ist nicht verlässlich: Steht sie auf `month`,
kommen kommentarlos Tagessummen statt Viertelstundenwerten. Die Datei sieht dann
tadellos aus, nur eben mit 31 Zeilen. Das versteckte Formularfeld
`DateTimeTabs$CurrentTab` ist übrigens nur Anzeige — es lässt sich setzen und
ändert nichts.

**Der Zeitschritt ist nicht immer eine Viertelstunde.** Für den ersten,
angebrochenen Monat einer Anlage liefert das Portal Stundenwerte. Wer fest mit
96 Zeilen je Tag rechnet, staucht diesen Monat auf ein Viertel des Tages und
viertelt zusätzlich jeden Wert. Der Schritt gehört aus den Uhrzeiten der Datei
abgelesen, nicht angenommen.

**Der Download gibt immer das zuletzt angezeigte Diagramm aus.** Schlägt die
Diagrammanfrage fehl, bleibt das vorherige stehen, und der Download liefert den
Vormonat ein zweites Mal, ohne Fehlermeldung. Das Skript prüft deshalb jede
Datei gegen die Prüfsummen aller anderen Monate und die Tageszahl gegen den
Kalender.

**Fünf-Minuten-Auflösung liefert nur die Verbraucher.** Die anlagenweiten Reihen
kommen dann als leere Listen. Wer eine Antwort schon deshalb als gültig ansieht,
weil irgendetwas darin steht, exportiert jahrelang Hüllen.

**Die Einheit wechselt zwischen `[W]` und `[kW]`,** abhängig davon, wie das
Portal die Achse skaliert — und zwar von Monat zu Monat. Sie steht in der
Kopfzeile und muss dort gelesen werden.

**Die CSV enthält kein Datum, nur die Uhrzeit** — und zwar das *Ende* des
Intervalls. Ein Tag läuft von 00:15 bis 00:00.

**Es gibt echte Lücken.** Zeiträume ohne Werte sind nicht immer
Übertragungsfehler; das Portal hat sie manchmal wirklich nicht. Solche Tage
werden benannt und müssen beim Import als *fehlend* gelten, nicht als Null —
sonst verfälschen sie jede Bilanz.

**Die Aufteilung auf einzelne Wechselrichter kann falsch sein.** In der zuerst
untersuchten Anlage lieferte die Analyse-Seite über zwanzig Monate hinweg exakt
ein Viertel der Anlagensumme als Ertrag des einen Wechselrichters — ein Faktor
vier, kein Messrauschen. Die Anlagensumme selbst stimmte dagegen auf die Stelle
mit der Energiebilanz überein. Deshalb wird die Geräteaufteilung in Schritt 2
nicht geraten, sondern aus den Daten abgeleitet und dem Anlagenbetreiber zur
Bestätigung vorgelegt.

---

## Was noch kommt

### Schritt 2 — Analyse

Prüft beide Seiten, ohne etwas zu verändern. Auf der Portalseite: welcher
Wechselrichter wann Werte lieferte und ob die Gerätereihen zusammen die
Anlagensumme ergeben. In Home Assistant: welche Statistiken es schon gibt, wie
weit sie zurückreichen und welche das Energie-Dashboard verwendet. Ergebnis ist
eine Datei mit Abschnitten, Rückfragen und einem `"bestaetigt": false`, das der
Anlagenbetreiber setzen muss — nur er weiß, ob im März wirklich ein Gerät
dazukam oder ob bloß anders verkabelt wurde.

### Schritt 3 — Transformation

Macht aus den Monatsdateien stündliche Energiereihen: Einheit und Zeitschritt
aus der Datei lesen, Leistung mal Dauer zu Energie, Datum aus dem Tageswechsel
ergänzen, zu Stunden addieren, fortlaufende Summen bilden. Tage ohne Werte
werden **übersprungen statt genullt** — „wir wissen es nicht" ist etwas anderes
als „es war nichts".

### Schritt 4 — Import

Vorhandene, möglicherweise unvollständige Statistiken in Home Assistant
bereinigen und die Historie als externe Statistik einspielen. Mit Probelauf als
Vorgabe: Ein Import, der sich nicht vorher ansehen lässt, wird nicht gebaut.

---

## Aufbau des Projekts

```
1_export.py                Daten aus dem Portal holen, parallel
portal.py                  Modul: Anmeldung am Portal, Anlagendaten, Abfragen

zugangsdaten.ini.beispiel  Vorlage für die Zugangsdaten
```

`portal.py` ist kein Schritt — es wird importiert, nicht gestartet.

Beim Lauf entstehen `bilanz/`, `wechselrichter/` und `rohdaten/` mit den
Messdaten sowie je Ordner ein `_protokoll.json` mit den Prüfwerten und ein
`_verdaechtig/` mit aussortierten Dateien. Sie stehen alle in der `.gitignore`:
**In dieses Repository gehört Code, keine Messdaten.**

---

## Mitmachen

Beiträge sind willkommen — **am liebsten als Pull Request.**

Besonders wertvoll sind Rückmeldungen von *anderen* Anlagen. Entwickelt wurde
das Projekt an genau einer: zwei Wechselrichtern, Sunny Home Manager 2.0, ohne
Batteriespeicher. Ob es mit Speicher, mit nur einem Wechselrichter, mit einer
Anlage im ennexOS-Portal oder mit einem Konto voller mehrerer Anlagen ebenso
läuft, weiß niemand. Wenn du es ausprobierst, sag Bescheid — auch und gerade
dann, wenn es nicht funktioniert hat.

Ebenso hilfreich: eine Meldung, sobald SMA etwas ändert und der Export bricht.

### Bevor du einen Pull Request stellst

Ein paar Dinge, die Ärger ersparen:

* **Keine Zugangsdaten und keine Messdaten** im Commit. `zugangsdaten.ini` und
  die Datenordner stehen in der `.gitignore` — bitte prüfe mit `git status`,
  bevor du committest.
* **Den Kopf des Skripts pflegen.** Jede produktive Datei trägt Version, Datum
  der letzten Änderung, Beschreibung und Aufruf. Wenn du etwas am Verhalten
  änderst, gehört eine Zeile in den Änderungsblock und die Version eine Stufe
  hoch.
* **Nichts fest verdrahten.** Anlagenkennung und Zeitraum werden zur Laufzeit
  aus dem Portal gelesen. Wer eigene Werte einträgt, macht das Projekt für
  alle anderen unbrauchbar.
* **Stille Fehler sind der Feind.** Wenn du eine neue Abfrage einbaust, baue
  auch die Prüfung dazu: Ist die Antwort wirklich das, was sie sein soll? Der
  Abschnitt oben erklärt, warum — jeder Punkt dort war einmal ein Lauf, der
  erfolgreich aussah.
* Ein Issue vorab ist nie verkehrt, besonders bei größeren Änderungen — dann
  arbeitet niemand doppelt.

Fehlerberichte gern mit der Ausgabe des Laufs und, falls vorhanden, dem
zugehörigen Eintrag aus `bilanz/_protokoll.json`. **Bitte ohne echte Messwerte
und ohne Anlagenkennung.**

---

## Hinweise

Dieses Projekt nutzt **nicht dokumentierte Schnittstellen** der Weboberfläche.
Sie können sich jederzeit ändern; dann bricht der Export. Ob automatisierte
Abrufe von den Nutzungsbedingungen des Portals gedeckt sind, wurde nicht
geprüft — jeder nutzt das auf eigene Verantwortung und ausschließlich für die
eigenen Anlagendaten.

Die Skripte lesen ausschließlich. Sie verändern nichts im Portal und in keiner
Anlagenkonfiguration.

---

## Lizenz

MIT — siehe [LICENSE](LICENSE).

---

*Dieses Projekt steht in keiner Verbindung zur SMA Solar Technology AG. SMA,
Sunny Portal und Sunny Home Manager sind eingetragene Marken der SMA Solar
Technology AG und werden hier ausschließlich zur Beschreibung der
Kompatibilität genannt. Home Assistant ist eine Marke der Open Home Foundation.*
