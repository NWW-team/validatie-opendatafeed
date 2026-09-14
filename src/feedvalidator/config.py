"""Instellingen voor de feedvalidator."""

from __future__ import annotations

from dataclasses import dataclass, field

#: Basis-URL van de v2 opendatafeed. V1 is uitgefaseerd en geeft HTTP 410.
DEFAULT_BASE_URL = "https://opendata.nederlandwereldwijd.nl/v2/sources/nederlandwereldwijd"

#: Publiekssite waartegen de feed vergeleken kan worden.
DEFAULT_WEBSITE_BASE_URL = "https://www.nederlandwereldwijd.nl"

#: De Azure Application Gateway voor de feed blokkeert een aantal standaard
#: user agents (o.a. "python-requests/x.y") met HTTP 403. Altijd een eigen,
#: herkenbare user agent meesturen.
DEFAULT_USER_AGENT = (
    "nww-feedvalidator/0.1 (+https://github.com/NWW-team/validatie-opendatafeed)"
)

#: De feed levert maximaal 200 records per pagina, ongeacht de rows-parameter.
MAX_ROWS_PER_PAGE = 200


@dataclass(frozen=True)
class Thresholds:
    """Drempelwaarden waarop de kwaliteitsregels afgaan."""

    #: Boven deze leeftijd (dagen) van "Nog steeds geldig op" gaat de bel af.
    geldigheid_max_dagen: int = 180
    #: Boven deze leeftijd (dagen) sinds de laatste wijziging: waarschuwing.
    wijziging_max_dagen: int = 365
    #: Minimaal aantal reisadviezen dat de feed hoort te bevatten.
    min_aantal_reisadviezen: int = 220
    #: Minimale lengte (tekens) van een gevulde introductie.
    min_introductie_lengte: int = 40
    #: Hoe ver terug een wijziging "recent" heet bij het toetsen of er na die
    #: wijziging nog gepusht is (het veld issued).
    push_venster_dagen: int = 30


@dataclass(frozen=True)
class Settings:
    """Alle instellingen van één validatieronde."""

    base_url: str = DEFAULT_BASE_URL
    website_base_url: str = DEFAULT_WEBSITE_BASE_URL
    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = 30.0
    retries: int = 5
    #: De gateway van de feed knijpt af bij te veel verzoeken per seconde.
    #: Vier parallelle verzoeken op zes per seconde blijft er ruim onder.
    workers: int = 4
    requests_per_second: float = 6.0
    #: Kaartbestanden daadwerkelijk opvragen (extra request per kaart).
    check_files: bool = False
    #: Feed vergelijken met de publiekssite (extra request per land).
    check_website: bool = False
    #: Alleen de eerste N landen valideren (0 = alles). Handig bij testen.
    limit: int = 0
    #: Landcodes die afwijken van ISO 3166-1 maar die het team accepteert
    #: (bijvoorbeeld BQ-BO, BQ-SA en BQ-SE voor Caribisch Nederland).
    extra_isocodes: frozenset[str] = frozenset()
    #: Landsleutels die buiten beschouwing blijven, bijvoorbeeld omdat er
    #: bewust geen reisadvies (meer) van is. Ze worden niet getoetst, maar
    #: wel in het rapport genoemd, zodat niemand ze stilletjes kwijtraakt.
    excluded_countries: frozenset[str] = frozenset()
    #: Posten waarvan bekend is dat ze gesloten of opgeschort zijn en die geen
    #: adres hebben omdat er niets te bezoeken valt. Ze worden niet gemeld,
    #: maar wel in het rapport genoemd — en zodra er weer een adres of een
    #: waarnemende post opduikt, zegt de validator dat de vlag weg kan.
    closed_posts: frozenset[str] = frozenset()
    thresholds: Thresholds = field(default_factory=Thresholds)
