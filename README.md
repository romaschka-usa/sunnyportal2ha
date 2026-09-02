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
  │ Portal →   │   │ Was ist da?│   │ Einheiten        │   │ Vergleich  │
  │ Dateien    │   │ Welcher WR │   │ Zeitstempel      │   │ Schnitt    │
  │            │   │ wann?      │   │ Lücken           │   │ → Statistik│
  └────────────┘   └────────────┘   └──────────────────┘   └────────────┘
      ✔                ✔                    ✔                   ✔
```

Die Kette ist vollständig und einmal komplett durchgelaufen: dreieinhalb Jahre
Historie, vierzehn Reihen, lückenlos bis zu dem Tag, an dem die eigenen
Sensoren übernehmen.

**Erprobt ist sie an genau einer Anlage** — zwei Wechselrichtern, Sunny Home
Manager 2.0, ohne Speicher. Nichts darin ist auf diese Anlage zugeschnitten;
Anlagenkennung, Zeitraum und Geräteaufteilung werden zur Laufzeit ermittelt.
Aber „nicht zugeschnitten" ist etwas anderes als „geprüft". Rückmeldungen von
anderen Anlagen sind der nützlichste Beitrag, den dieses Projekt bekommen kann
— besonders die, bei denen es nicht funktioniert hat.

Jeder Schritt ist für sich brauchbar. Wer nur seine Daten sichern will, hört
nach Schritt 1 auf und hat die vollständige Historie als CSV und JSON auf der
eigenen Platte.

Die Änderungshistorie steht in [CHANGELOG.md](CHANGELOG.md).

---

## Schnellstart

```bash
pip install requests websocket-client

python 1_export.py                 # Portal → Dateien (dauert am längsten)
python 2_analyse.py --ha           # was ist da, auf beiden Seiten?
                                   # geraeteregeln.json prüfen und bestätigen
python 3_transform.py --leistung   # Dateien → stündliche Reihen
python 4_import.py --vergleich     # HA und Portal gegenüberstellen
python 4_import.py --bis JJJJ-MM-TT --los    # schreiben
```

Beim ersten Start von `1_export.py` wird `zugangsdaten.ini` als Vorlage
angelegt:

```ini
[sunnyportal]
benutzer = deine@mailadresse.de
passwort = deinPasswort

[homeassistant]
url   = http://192.168.x.y
token = langlebiges Zugriffstoken aus dem HA-Benutzerprofil

[export]
parallel = 4
timeout  = 300
```

Das Token erzeugst du in Home Assistant unter deinem Benutzernamen (unten
links) → Sicherheit → Langlebige Zugriffstoken. Diese Datei steht in
`.gitignore` und darf niemals ins Repository.

**Vor Schritt 4 eine Sicherung von Home Assistant anlegen.** Nicht wegen
dieses Skripts — es schreibt ausschließlich unter eigenen Kennungen und nimmt
sich mit `--entfernen` wieder zurück —, sondern weil man an der
Statistikdatenbank generell nicht ohne Rückweg arbeiten sollte. Die meisten
Leute haben keine Testinstanz.

**Voraussetzungen:** Python 3.9 oder neuer, ein Sunny-Portal-Konto, und eine
Anlage mit Sunny Home Manager (nur dann gibt es die Energiebilanz-Seite).

---

## Schritt 1 — Export

`1_export.py` holt drei verschiedene Datenarten, wahlweise einzeln oder mit
`alles` nacheinander — mit mehreren gleichzeitigen Verbindungen:

| Aufruf | Was es liefert | Zuschnitt |
|---|---|---|
| `1_export.py bilanz` | PV-Erzeugung, Gesamtverbrauch, Direktverbrauch, Netzbezug, **Netzeinspeisung**, Batterie — Viertelstundenwerte | ein Monat je Abfrage |
| `1_export.py wechselrichter` | Ertrag **je Gerät** plus Anlagensumme, Viertelstundenwerte | ein Monat je Abfrage |
| `…_tage` `…_monate` `…_jahre` | dieselben Reihen als **Zählerstandsänderung** je Tag, Monat und Jahr | ein Monat / ein Jahr / eine Abfrage |
| `…_luecken` | lädt **einzelne Tage** nach, an denen die Monatsabfrage keine Feinkurve hergab | ein Tag je Abfrage |
| `1_export.py verbraucher` | die Kurven **je Verbraucher** — Wärmepumpe, Wallbox, Heizstab | ein Tag je Abfrage |

Für die Anlagensummen ist die Energiebilanz der beste Weg: ein ganzer Monat in
einer Anfrage, und sie ist die einzige Quelle mit der Netzeinspeisung.
Dreieinhalb Jahre sind damit in gut einer Viertelstunde exportiert. Die
Verbraucher gehen nur tageweise und dauern deshalb am längsten.

Die groben Stufen sind keine Wiederholung. Feinkurve und Zählerstand entstehen
im Portal getrennt, und sie sind **nicht gleich vollständig** — siehe unten.
Zusammen ergeben sie eine Prüfsumme auf jeder Ebene und eine Liste der Tage,
die einzeln nachgeholt werden müssen. Die Reihenfolge ist wichtig und in
`alles` schon richtig: erst die Feinkurven, dann Tage und Monate, dann die
Lückensuche, die auf allen dreien aufbaut.

Ein **zweiter Aufruf danach** lohnt sich: Scheitert im ersten Lauf ein Monat,
so kennt die Lückensuche seine leeren Tage nicht und überspringt ihn. Der
zweite Lauf holt erst den Monat nach und sieht dann in derselben Runde dessen
Lücken. Alles Vorhandene wird dabei nur geprüft und übersprungen.

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

---

## Schritt 2 — Analyse

`2_analyse.py` prüft beide Seiten und **verändert nichts.**

```bash
python 2_analyse.py          # nur die Portaldaten
python 2_analyse.py --ha     # zusätzlich Home Assistant abfragen
```

Auf der Portalseite zweierlei. Erstens die **Geräteaufteilung**: Welcher
Wechselrichter hat wann Werte geliefert, und ergeben die Gerätereihen zusammen
die Anlagensumme? Daraus entsteht `geraeteregeln.json` mit Abschnitten,
Rückfragen und einem Vorschlag — und einem `"bestaetigt": false`, das du
setzen musst, bevor Schritt 3 überhaupt anläuft.

Warum diese Bremse? Anlagen wachsen. Wechselrichter kommen hinzu, fallen aus,
werden getauscht. Eine Reihe, die jahrelang leer ist und dann Werte liefert,
kann ein neues Gerät sein oder eine neue Verkabelung. Erkennen lässt sich das;
entscheiden muss es der Anlagenbetreiber. Nur er weiß, was im März wirklich
passiert ist.

Zweitens die **Plausibilitätsprüfung** über alle vier Auflösungen — der
eigentliche Abnahmetest des Exports. Steht in allen Zeilen
`fein ≈ Tage ≈ Monate ≈ Jahre`, ist die Historie vollständig; sonst nennt
`plausibilitaet.json` Monat, Reihe und Fehlbetrag in kWh.

Auf der HA-Seite: welche Langzeitstatistiken es schon gibt, wie weit sie
zurückreichen und welche das Energie-Dashboard verwendet. Das entscheidet, was
importiert werden muss und was nicht. Ergebnis in `ha/`.

---

## Schritt 3 — Transformation

`3_transform.py` macht aus den Monatsdateien stündliche Reihen.

```bash
python 3_transform.py               # nur Energie
python 3_transform.py --leistung    # zusätzlich Leistungsreihen
```

Was dabei passiert: Einheit aus der Kopfzeile lesen (`[W]` oder `[kW]`, das
wechselt von Monat zu Monat), Leistung mal Dauer zu Energie, Datum aus dem
Tageswechsel ergänzen, auf Stunden verdichten, fortlaufende Summen bilden.

**Tage ohne Werte werden übersprungen statt genullt.** „Wir wissen es nicht"
ist etwas anderes als „es war nichts", und eine Null verfälscht jede Bilanz,
die darauf aufbaut.

Heraus kommen externe Statistiken — Doppelpunkt statt Punkt:

```
sunnyportal2ha:pv_gesamt          PV-Erzeugung, ganze Anlage
sunnyportal2ha:netzbezug          aus dem Netz bezogen
sunnyportal2ha:einspeisung        ins Netz eingespeist
sunnyportal2ha:verbrauch_gesamt   Gesamtverbrauch des Hauses
sunnyportal2ha:direktverbrauch    direkt verbrauchte PV-Energie
sunnyportal2ha:wr_<name>          je Wechselrichter eine Reihe
```

Mit `--leistung` zu jeder dieser Reihen zusätzlich eine Leistungsreihe in Watt
— je Stunde Mittelwert, Minimum und Maximum — sowie `netz_leistung`, die
vorzeichenbehaftete Netzleistung (Bezug positiv, Einspeisung negativ). Das
braucht man, weil das Energie-Dashboard zu jeder Energiequelle auch eine
Leistung erwartet.

Der Umweg über die Energie und zurück ist übrigens keiner: Die Quelle **ist**
Leistung. Energie entsteht erst durch die Umrechnung.

---

## Schritt 4 — Import

`4_import.py` ist die einzige Stufe, die etwas verändert. Deshalb passiert
ohne `--los` nichts.

```bash
python 4_import.py --vergleich                 # erst ansehen
python 4_import.py                             # Probelauf
python 4_import.py --bis 2026-08-27 --los      # schreiben
python 4_import.py --pruefen                   # gegenrechnen
python 4_import.py --entfernen --los           # alles zurücknehmen
```

**Der Vergleich zuerst.** `--vergleich` stellt Home Assistant und Portal im
Überschneidungszeitraum Tag für Tag gegenüber und schlägt den Tag vor, ab dem
beide übereinstimmen und es auch bleiben. An diesem Tag wird geschnitten:
davor trägt das Portal die Geschichte, ab da die eigenen Sensoren. `--bis` ist
dabei **ausschließend** gemeint.

Danach beide Reihen im Energie-Dashboard derselben Rolle zuordnen — Home
Assistant addiert sie, und weil sie sich nicht überschneiden, entsteht ein
durchgehender Verlauf.

> **Achtung bei der Erzeugung:** entweder die Summenreihe `pv_gesamt` **oder**
> die Gerätereihen eintragen, niemals beides. Sonst zählt das Dashboard die
> Erzeugung doppelt.

**Warum externe Statistiken.** Home Assistant kennt zwei Namensräume:
Entitäten heißen `sensor.name` mit einem Punkt, externe Statistiken
`quelle:name` mit einem Doppelpunkt. Sie können sich deshalb nicht in die
Quere kommen. Alles, was dieses Skript schreibt, trägt die Kennung
`sunnyportal2ha:` und gehört ausschließlich diesem Projekt. Keine vorhandene
Statistik wird angefasst, keine Entität verändert, keine Automatisierung
berührt. Was nicht mit `sunnyportal2ha:` anfängt, schreibt das Skript nicht —
auch dann nicht, wenn es so in einer Datei steht.

Die Ausnahme ist `--ziel`, und sie ist bewusst umständlich: Damit lässt sich
**eine** Reihe unter eine fremde Kennung schreiben. Gebraucht wird das für die
Hilfsentitäten, die Home Assistant im Energie-Dashboard selbst anlegt — siehe
den Fallstrick weiter unten. Eigene Rückfrage, eigener Vermerk im Protokoll,
und `--entfernen` nimmt das **nicht** zurück.

`import/_import-protokoll.json` hält je Lauf fest, welche Kennung von welcher
bis zu welcher Stunde geschrieben wurde, mit Anzahl und Summenstand. Ohne das
lässt sich später nichts gezielt korrigieren.

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

**Home Assistant.** Statistiken sind über die REST-Schnittstelle **nicht**
erreichbar — dafür gibt es nur die WebSocket-Schnittstelle unter
`/api/websocket`. Verwendet werden `recorder/list_statistic_ids`,
`recorder/statistics_during_period`, `energy/get_prefs` sowie zum Schreiben
`recorder/import_statistics` und `recorder/clear_statistics`.

Anlagenkennung und Betriebszeitraum liest das Skript beim Start aus dem Portal.
Es ist an keine bestimmte Anlage gebunden.

---

## Fallstricke, die Zeit gekostet haben

Diese Punkte stehen hier, weil sie **stille Fehler** erzeugen — Läufe, die
erfolgreich aussehen und falsche Daten liefern. Jeder einzelne davon hat in der
Entwicklung mindestens einen halben Tag gekostet.

### Auf der Portalseite

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

**Der Zeitschritt ist nicht immer eine Viertelstunde — und nicht einmal in
einer Datei einheitlich.** Für den ersten, angebrochenen Monat einer Anlage
liefert das Portal Stundenwerte statt Viertelstundenwerte. Schlimmer: Innerhalb
*derselben* Datei können die Reihen unterschiedlich getaktet sein. In der hier
untersuchten Anlage hat die Anlagensumme bis Ende 2024 96 Werte am Tag, die
Reihe des Wechselrichters aber nur 24 — mit leeren Zellen dazwischen, in
denselben Zeilen.

Wer jeden Wert mit einer Viertelstunde multipliziert, macht aus jedem
Stundenwert ein Viertel und erhält für dieses Gerät exakt 25 % seiner
Erzeugung. Das sieht wie ein Fehler des Portals aus und ist keiner. Der Test,
der es entlarvt: **Die Spitzenleistung stimmt** — 12,60 gegen 12,63 kW — nur die
Energie nicht. Der Takt gehört deshalb je Spalte aus den tatsächlichen
Wertabständen bestimmt, nicht aus den Zeilenbeschriftungen.

**Die groben Auflösungen sind vollständiger als die feinen.** Das ist die
unangenehmste Eigenschaft dieser Quelle, weil sie sich nicht ansehen lässt:

```
März 2026, PV     Monat 1971 kWh    Tage 1971 kWh    Feinkurve 0 kWh
Juli 2023, PV     Monat  270 kWh    Tage   57 kWh    Feinkurve 57 kWh
```

Die Monatsabfrage gibt die Feinkurve für März 2026 nicht her — die
Tagesabfrage für denselben Zeitraum schon, vollständig und viertelstündlich.
Deshalb holt `…_luecken` solche Tage einzeln nach: gemessene Werte statt aus
Tagessummen verteilter. Welche Tage das sind, ergibt sich aus dem Vergleich der
Ebenen, nicht aus einer Liste im Code.

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

**Anlagen wachsen, und die Daten sagen es nicht dazu.** Wechselrichter kommen
hinzu, fallen aus, werden getauscht; eine Reihe, die jahrelang leer ist und
dann Werte liefert, kann ein neues Gerät sein oder eine neue Verkabelung.
Deshalb wird die Geräteaufteilung in Schritt 2 nicht geraten, sondern aus den
Daten abgeleitet und dem Anlagenbetreiber zur Bestätigung vorgelegt.

Wenn die Gerätereihen dabei ein glattes Verhältnis zur Anlagensumme ergeben —
genau ½, ⅓, ¼ —, ist das fast immer kein Anlagenereignis, sondern der
Taktfehler von weiter oben. Erst rechnen, dann fragen.

### Auf der Home-Assistant-Seite

**Eine Stunde ist die feinste Auflösung, die sich importieren lässt.** Home
Assistant führt zwei Statistiktabellen: `statistics` mit Stundenwerten,
dauerhaft, und `statistics_short_term` mit Fünfminutenwerten, nach etwa zehn
Tagen weggeräumt. `recorder/import_statistics` schreibt ausschließlich in die
erste, und die Stunde ist dort fest verdrahtet. Am Schnitt ist das sichtbar:
davor Stundentreppe, danach die feine Kurve der eigenen Sensoren. Daran lässt
sich nichts ändern — außer man verwürfe die feine Auflösung auch für die
Gegenwart.

**Energie steht in Wh, kWh und MWh nebeneinander** — je nach Gerät, im selben
Dashboard. Wer für einen Vergleich stumpf addiert, bekommt Abweichungen im
Faktor Hundert bis Tausend, die nach einem Datenfehler aussehen und keiner
sind. Die Einheit steht in den Metadaten jeder Statistik und muss von dort
kommen.

**Der Recorder schreibt im Hintergrund.** `import_statistics` quittiert sofort;
geschrieben wird danach. Wer gleich anschließend nachliest, sieht Reihen, die
noch nicht bis ans Ende reichen oder noch gar nicht in der Liste stehen — das
sieht nach einem misslungenen Import aus und ist keiner. Der Import wartet
deshalb, bis Home Assistant die Reihen auch zeigt.

**Große Blöcke reißen die Verbindung ab.** Bei jedem Block rechnet Home
Assistant die Statistik neu; bei 5000 Werten am Stück ist der Recorder so lange
beschäftigt, dass die WebSocket-Verbindung wegfällt. Tausenderblöcke mit
Verschnaufpause halten durch. Ein wiederholter Block ist harmlos: gleiche
Startzeitpunkte werden ersetzt, nicht verdoppelt.

**Die Leistungskurve im Energie-Dashboard nimmt keine externen Statistiken.**
Wird der Netzanschluss unter „Leistung" mit **„Zwei Sensoren"** konfiguriert,
legt Home Assistant daraus eine Hilfsentität an, deren Kennung aus den beiden
Quellkennungen zusammengesetzt wird. Bei Entitäten fällt dabei das `sensor.`
weg und nur der Objektteil bleibt übrig — der kann keinen Doppelpunkt
enthalten. Eine externe Statistik hat aber kein Präfix zum Abschneiden: Ihre
Kennung **ist** `quelle:name`, und der Doppelpunkt wandert mit in den
erzeugten Namen. Heraus kommt etwas wie

```
sensor.energy_grid_sunnyportal2ha:netzbezug_leistung_…_net_power
```

— eine Kennung, die es nie geben kann. Die Seite meldet dauerhaft
„Statistiken nicht definiert", und die Kurve bleibt leer. Die Auswahlliste
bietet externe Statistiken für diese Felder trotzdem an; gewarnt wird nicht.

Der Umweg: einen Vorlagensensor mit gültiger Kennung anlegen, die Historie mit
`4_import.py --ziel` dorthin schreiben und im Dashboard statt „Zwei Sensoren"
die einfache Einstellung **„Standard"** wählen.

```yaml
# configuration.yaml
template:
  - sensor:
      - name: "Sunnyportal Netzleistung"
        unique_id: sunnyportal_netzleistung
        unit_of_measurement: "W"
        device_class: power
        state_class: measurement
        state: "{{ 0 }}"
        availability: "{{ false }}"
```

```bash
python 4_import.py --nur netz_leistung --ziel sensor.sunnyportal_netzleistung --bis JJJJ-MM-TT --los
```

Bietet die Auswahlliste eine dauerhaft nicht verfügbare Entität nicht an, lässt
man die Zeile `availability` weg — dann meldet der Sensor konstant 0 W. Liegt
die Kurve spiegelverkehrt, ist „Invertiert" die richtige Einstellung.

Geprüft mit Home Assistant 2026.8.3 und 2026.9.0.

---

## Aufbau des Projekts

```
1_export.py                Daten aus dem Portal holen, parallel
2_analyse.py               Bestand prüfen, Geräteaufteilung klären
3_transform.py             CSV → stündliche Energie- und Leistungsreihen
4_import.py                nach Home Assistant schreiben

portal.py                  Modul: Anmeldung am Portal, Anlagendaten, Abfragen
daten.py                   Modul: Portal-CSV lesen, Geräteaufteilung beurteilen
ha.py                      Modul: lesender Zugriff auf Home Assistant

zugangsdaten.ini.beispiel  Vorlage für die Zugangsdaten
CHANGELOG.md               Änderungshistorie
```

Die drei Module sind keine Schritte — sie werden importiert, nicht gestartet.
`ha.py` enthält bewusst **keine** schreibende Funktion; das Schreiben steht
ausschließlich in `4_import.py`, dort mit Rückfrage und Probelauf als Vorgabe.

Beim Lauf entstehen die Datenordner — `bilanz/`, `bilanz_tage/`,
`bilanz_monate/`, `bilanz_jahre/`, `bilanz/luecken/`, dasselbe für
`wechselrichter` sowie `rohdaten/` — mit je einem `_protokoll.json` voller
Prüfwerte und einem `_verdaechtig/` für aussortierte Dateien. Dazu `ha/` mit
dem Inventar der Gegenseite und `import/` mit den fertigen Reihen. Sie stehen
alle in der `.gitignore`: **In dieses Repository gehört Code, keine Messdaten.**

Das `_protokoll.json` ist nicht nur Berichterstattung: Die Lückensuche liest
daraus, welche Tage in welcher Datei leer geblieben sind.

Daneben entsteht `export-log.txt`, das Laufprotokoll — die eine Datei, die
einem Fehlerbericht beiliegen darf, weil bewusst nichts Vertrauliches darin
steht. Auch sie bleibt außerhalb des Repositories.

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
  hoch. Was Anwender betrifft, gehört zusätzlich in `CHANGELOG.md`.
* **Nichts fest verdrahten.** Anlagenkennung, Zeitraum und Geräteaufteilung
  werden zur Laufzeit ermittelt. Wer eigene Werte einträgt, macht das Projekt
  für alle anderen unbrauchbar.
* **Stille Fehler sind der Feind.** Wenn du eine neue Abfrage einbaust, baue
  auch die Prüfung dazu: Ist die Antwort wirklich das, was sie sein soll? Der
  Abschnitt oben erklärt, warum — jeder Punkt dort war einmal ein Lauf, der
  erfolgreich aussah.
* **Was schreibt, fragt vorher.** Schritt 4 ist die einzige Stelle, die etwas
  verändert, und das soll so bleiben.
* Ein Issue vorab ist nie verkehrt, besonders bei größeren Änderungen — dann
  arbeitet niemand doppelt.

Für Fehlerberichte gibt es **`export-log.txt`**. Dort sammelt jeder Lauf
Version, Umgebung, Aufruf, je Quelle den Zeitraum und die Bilanz sowie jede
Aufgabe, die nicht glattging — mit Grund, Zeilenzahl, Größe der Antwort und
Versuchszahl. Die Datei enthält **keine Messwerte, keine Anlagenkennung und
keine Gerätenamen** und kann unbesehen mitgeschickt werden.

Nicht mitschicken, ohne hineinzusehen: die Rohantworten unter
`_verdaechtig/`. Das ist, was das Portal geschickt hat, und darin können sehr
wohl Messwerte stehen.

---

## Hinweise

Dieses Projekt nutzt **nicht dokumentierte Schnittstellen** der Weboberfläche.
Sie können sich jederzeit ändern; dann bricht der Export. Ob automatisierte
Abrufe von den Nutzungsbedingungen des Portals gedeckt sind, wurde nicht
geprüft — jeder nutzt das auf eigene Verantwortung und ausschließlich für die
eigenen Anlagendaten.

Gegenüber dem Portal lesen die Skripte ausschließlich. Sie verändern nichts im
Portal und in keiner Anlagenkonfiguration. Geschrieben wird nur in die eigene
Home-Assistant-Installation, und nur dort, wo es ausdrücklich verlangt wurde.

---

## Lizenz

MIT — siehe [LICENSE](LICENSE).

---

*Dieses Projekt steht in keiner Verbindung zur SMA Solar Technology AG. SMA,
Sunny Portal und Sunny Home Manager sind eingetragene Marken der SMA Solar
Technology AG und werden hier ausschließlich zur Beschreibung der
Kompatibilität genannt. Home Assistant ist eine Marke der Open Home Foundation.*
