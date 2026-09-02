#!/usr/bin/env python3
"""
ha - Zugriff auf Home Assistant
================================

Version         : 1.0.0
Letzte Aenderung: 2026-09-01

Beschreibung
------------
Gemeinsames Modul fuer die Home-Assistant-Seite des Projekts. Wird importiert
und nicht direkt aufgerufen.

Statistiken sind ueber die REST-Schnittstelle NICHT erreichbar - dafuer gibt
es nur die WebSocket-Schnittstelle. Dieses Modul kapselt beides:

    version()                    HA-Version ueber REST
    statistik_kennungen()        alle bekannten Statistiken mit Einheit
    statistiken(ids, von, bis)   Werte je Zeitraum
    schreiben_erlaubt()          Schutzschalter, siehe unten

Schutz
------
Dieses Modul LIEST nur. Es enthaelt bewusst keine Funktion, die Statistiken
veraendert. Das Schreiben passiert ausschliesslich im Importskript, dort mit
ausdruecklicher Bestaetigung und Probelauf als Voreinstellung.

Zugangsdaten
------------
In zugangsdaten.ini neben den Skripten:

    [homeassistant]
    url = http://192.168.x.y
    token = langlebiges Zugriffstoken aus dem HA-Benutzerprofil

Das Token erzeugt man in Home Assistant unter
Benutzername (unten links) -> Sicherheit -> Langlebige Zugriffstoken.

Voraussetzungen
---------------
    pip install requests websocket-client

Aenderungen
-----------
1.0.0  2026-09-01  Erste Fassung, ausschliesslich lesend
"""

import configparser
import json
import os
import ssl
import sys
from datetime import datetime, timezone

__version__ = "1.0.0"
__stand__ = "2026-09-01"

try:
    import requests
except ImportError:
    sys.exit("Fehlt: das Paket 'requests'. Bitte 'pip install requests' ausfuehren.")

try:
    from websocket import create_connection
except ImportError:
    sys.exit("Fehlt: das Paket 'websocket-client'. "
             "Bitte 'pip install websocket-client' ausfuehren.")

HIER = os.path.dirname(os.path.abspath(__file__))
CONF_DATEI = os.path.join(HIER, "zugangsdaten.ini")


class HAFehler(RuntimeError):
    pass


# ------------------------------------------------------------- Zugangsdaten

def zugang():
    if not os.path.exists(CONF_DATEI):
        raise HAFehler(f"{CONF_DATEI} fehlt.")
    cp = configparser.ConfigParser()
    cp.read(CONF_DATEI, encoding="utf-8")
    if not cp.has_section("homeassistant"):
        raise HAFehler(
            "In zugangsdaten.ini fehlt der Abschnitt [homeassistant].\n"
            "        Bitte ergaenzen:\n\n"
            "        [homeassistant]\n"
            "        url = http://192.168.x.y\n"
            "        token = dein-langlebiges-token\n"
        )
    url = cp.get("homeassistant", "url", fallback="").strip().rstrip("/")
    token = cp.get("homeassistant", "token", fallback="").strip()
    if not url or not token or "dein-" in token:
        raise HAFehler("Bitte url und token im Abschnitt [homeassistant] ausfuellen.")
    return url, token


def ws_adresse(url):
    return url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"


# --------------------------------------------------------------------- REST

def version():
    """HA-Version und Zeitzone ueber die REST-Schnittstelle."""
    url, token = zugang()
    r = requests.get(f"{url}/api/config",
                     headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if r.status_code == 401:
        raise HAFehler("Token wurde abgelehnt (401). Ist es noch gueltig?")
    r.raise_for_status()
    d = r.json()
    return {"version": d.get("version"), "zeitzone": d.get("time_zone"),
            "name": d.get("location_name"), "waehrung": d.get("currency")}


# ---------------------------------------------------------------- WebSocket

class Verbindung:
    """Eine angemeldete WebSocket-Verbindung. Als Kontextmanager verwendbar."""

    def __init__(self, timeout=60):
        self.url, self.token = zugang()
        self.ws = None
        self.nr = 0
        self.timeout = timeout

    def __enter__(self):
        self.ws = create_connection(
            ws_adresse(self.url), timeout=self.timeout,
            sslopt={"cert_reqs": ssl.CERT_NONE} if self.url.startswith("https") else None,
        )
        gruss = json.loads(self.ws.recv())
        if gruss.get("type") != "auth_required":
            raise HAFehler(f"Unerwartete Begruessung: {gruss}")
        self.ws.send(json.dumps({"type": "auth", "access_token": self.token}))
        antwort = json.loads(self.ws.recv())
        if antwort.get("type") != "auth_ok":
            raise HAFehler(f"Anmeldung abgelehnt: {antwort.get('message', antwort)}")
        return self

    def __exit__(self, *_):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass

    def befehl(self, typ, **felder):
        self.nr += 1
        self.ws.send(json.dumps({"id": self.nr, "type": typ, **felder}))
        while True:
            antwort = json.loads(self.ws.recv())
            if antwort.get("id") != self.nr:
                continue
            if not antwort.get("success", False):
                fehler = antwort.get("error", {})
                raise HAFehler(f"{typ}: {fehler.get('code')} - {fehler.get('message')}")
            return antwort.get("result")


def statistik_kennungen(v, art=None):
    """
    Alle Statistiken, die HA kennt.
    art: None (alle), 'sum' (Zaehler) oder 'mean' (Messwerte)
    """
    felder = {"statistic_type": art} if art else {}
    return v.befehl("recorder/list_statistic_ids", **felder)


def statistiken(v, kennungen, von, bis, zeitraum="month", typen=None):
    """
    Werte je Zeitraum. von/bis sind date oder datetime.
    zeitraum: '5minute', 'hour', 'day', 'week', 'month'
    """
    def iso(d):
        if isinstance(d, datetime):
            dt = d
        else:
            dt = datetime(d.year, d.month, d.day)
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt.isoformat()

    felder = {
        "start_time": iso(von),
        "end_time": iso(bis),
        "statistic_ids": list(kennungen),
        "period": zeitraum,
    }
    if typen:
        felder["types"] = list(typen)
    return v.befehl("recorder/statistics_during_period", **felder)


def zeitstempel(eintrag):
    """Der Startzeitpunkt eines Statistikeintrags als datetime, egal in welchem Format."""
    wert = eintrag.get("start")
    if isinstance(wert, (int, float)):
        return datetime.fromtimestamp(wert / 1000 if wert > 1e11 else wert, tz=timezone.utc)
    if isinstance(wert, str):
        return datetime.fromisoformat(wert.replace("Z", "+00:00"))
    return None
