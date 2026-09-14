---
name: Opendatafeed Reisadviezen Validatie
last_updated: 2026-09-14
---

# Opendatafeed Reisadviezen Validatie — Strategie

## Doelprobleem

Als een reisadvies niet goed toont in een afnemend systeem (Reisapp, website, informatieservice), ontstaat er discussie waar het misgaat — in het CMS, de opendatafeed, of bij het afnemende systeem zelf — omdat niemand een overzicht heeft of alle landen en alle datavelden daadwerkelijk correct door de opendatafeed heen komen.

## Onze aanpak

We winnen door de opendatafeed zelf structureel te toetsen aan een vaste set volledigheids- en kwaliteitsregels (226 landen met geldige ISO-codes, kaarten aanwezig, wijzigingsdatum, geldigheid, ambassade-/consulaatgegevens gevuld) — in plaats van te vergelijken met de brondata in het CMS, omdat het te bouwen systeem niet aan die brondata gekoppeld kan worden.

## Voor wie

**Primair:** Product owner CMS reisadviezen & opendatafeed — huurt het product in om te kunnen aantonen of een gemeld probleem in een afnemend systeem (Reisapp, website, informatieservice) zijn oorzaak heeft in de opendatafeed zelf of elders ligt, zonder directe koppeling met de brondata in het CMS.

## Sporen

### Validatieregels

Bepalen en toetsen wat de opendatafeed per land aan gegevens moet bevatten (landen, ISO-codes, kaarten, wijzigingsdatum, geldigheid, ambassade-/consulaatgegevens).

_Waarom het de aanpak dient:_ dit is de kern van "toetsen aan een vaste set regels" zelf.

### Vergelijking met de website

De feed-inhoud afzetten tegen wat nederlandwereldwijd.nl per land daadwerkelijk toont.

_Waarom het de aanpak dient:_ praktische manier om afwijkingen te signaleren zonder koppeling met de brondata.

### Rapportage & inzicht

De resultaten van de checks overzichtelijk maken voor de product owner.

_Waarom het de aanpak dient:_ maakt het mogelijk om snel te tonen waar het probleem zit in de discussie CMS-vs-feed-vs-afnemer.

### Automatisering

Bepalen hoe vaak en op welke manier de checks draaien (handmatig, gepland, getriggerd).

_Waarom het de aanpak dient:_ maakt de toetsing structureel in plaats van incidenteel.

## Positionering

**Kernboodschap:** Als een reisadvies niet goed toont in de Reisapp, website of informatieservice, weten we voortaan binnen enkele klikken of het probleem in de opendatafeed zit of elders — in plaats van een welles-nietes-discussie zonder bewijs.
