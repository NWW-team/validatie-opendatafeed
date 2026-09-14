import json

import pytest
import requests

from feedvalidator.client import FeedClient, FeedError, _as_list, _as_single
from feedvalidator.config import MAX_ROWS_PER_PAGE, Settings


class NepAntwoord:
    def __init__(self, payload, status_code=200, url="https://feed/test"):
        self._payload = payload
        self.status_code = status_code
        self.url = url
        self.headers = {}

    def json(self):
        if isinstance(self._payload, str):
            return json.loads(self._payload)
        return self._payload


class NepSessie:
    """Legt vast welke verzoeken gedaan worden en speelt antwoorden af."""

    def __init__(self, antwoorden):
        self.antwoorden = list(antwoorden)
        self.verzoeken = []
        self.headers = {}

    def get(self, url, params=None, timeout=None, **kwargs):
        self.verzoeken.append((url, dict(params or {})))
        if not self.antwoorden:
            raise AssertionError(f"onverwacht verzoek naar {url}")
        antwoord = self.antwoorden.pop(0)
        if isinstance(antwoord, Exception):
            raise antwoord
        return antwoord


@pytest.fixture
def settings():
    return Settings(retries=2, timeout=1)


def test_vraagt_altijd_json_op(settings):
    sessie = NepSessie([NepAntwoord([{"id": "ESP"}])])
    client = FeedClient(settings, session=sessie)

    client.get_json("infotypes/countries")

    _, params = sessie.verzoeken[0]
    assert params["output"] == "json"


def test_stuurt_een_eigen_user_agent_mee(settings):
    sessie = NepSessie([])
    FeedClient(settings, session=sessie)
    assert "nww-feedvalidator" in sessie.headers["User-Agent"]


def test_bladert_door_tot_een_onvolledige_pagina(settings):
    volle_pagina = [{"id": f"L{i}"} for i in range(MAX_ROWS_PER_PAGE)]
    sessie = NepSessie([NepAntwoord(volle_pagina), NepAntwoord([{"id": "rest"}])])
    client = FeedClient(settings, session=sessie)

    items = list(client.paginate("infotypes/countries"))

    assert len(items) == MAX_ROWS_PER_PAGE + 1
    assert [p["offset"] for _, p in sessie.verzoeken] == [0, MAX_ROWS_PER_PAGE]


def test_probeert_opnieuw_na_een_netwerkfout(settings):
    sessie = NepSessie([requests.ConnectionError("reset"), NepAntwoord([{"id": "ESP"}])])
    client = FeedClient(settings, session=sessie)

    assert client.get_json("infotypes/countries") == [{"id": "ESP"}]
    assert len(sessie.verzoeken) == 2


def test_geeft_op_na_het_maximum_aantal_pogingen(settings):
    sessie = NepSessie([NepAntwoord(None, status_code=503) for _ in range(2)])
    client = FeedClient(settings, session=sessie)

    with pytest.raises(FeedError, match="bleef falen"):
        client.get_json("infotypes/countries")


def test_niet_herhaalbare_status_wordt_een_feederror(settings):
    sessie = NepSessie([NepAntwoord(None, status_code=404)])
    client = FeedClient(settings, session=sessie)

    with pytest.raises(FeedError, match="HTTP 404"):
        client.get_json("infotypes/countries/nergens")
    assert len(sessie.verzoeken) == 1


def test_detailantwoord_mag_een_dict_of_een_lijst_zijn():
    assert _as_single({"id": "ESP"}, "test")["id"] == "ESP"
    assert _as_single([{"id": "ESP"}], "test")["id"] == "ESP"
    with pytest.raises(FeedError):
        _as_single([], "test")


def test_xml_achtig_omhulsel_wordt_uitgepakt():
    assert _as_list({"documents": [{"id": "ESP"}]}) == [{"id": "ESP"}]
    assert _as_list(None) == []
