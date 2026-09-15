"""Commandoregel: valideer de opendatafeed en schrijf de rapporten weg."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .client import FeedClient
from .config import DEFAULT_BASE_URL, DEFAULT_USER_AGENT, Settings, Thresholds
from .report import (
    MANUAL_FILENAME,
    render_console,
    write_html,
    write_json,
    write_manual,
    write_markdown,
)
from .rules import COUNTRY_RULES, FEED_RULES
from .snapshot import load_snapshot, save_snapshot
from .theme import DEFAULT_THEME_CSS
from .validate import exit_code, run_rules, validate

logger = logging.getLogger("feedvalidator")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feedvalidator",
        description="Toets de opendatafeed met reisadviezen van Nederland Wereldwijd "
        "aan een vaste set volledigheids- en kwaliteitsregels.",
    )
    parser.add_argument("--version", action="version", version=f"feedvalidator {__version__}")
    sub = parser.add_subparsers(dest="commando")

    valideer = sub.add_parser("valideer", help="haal de feed op en toets hem (standaard)")
    _add_validate_arguments(valideer)

    sub.add_parser("regels", help="toon de catalogus met validatieregels")

    # Zonder subcommando gedraagt het programma zich als 'valideer'.
    _add_validate_arguments(parser)
    return parser


def _add_validate_arguments(parser: argparse.ArgumentParser) -> None:
    feed = parser.add_argument_group("feed")
    feed.add_argument("--base-url", default=DEFAULT_BASE_URL, help="basis-URL van de feed")
    feed.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="user agent voor verzoeken")
    feed.add_argument("--timeout", type=float, default=30.0, help="timeout per verzoek (seconden)")
    feed.add_argument("--retries", type=int, default=5, help="aantal pogingen per verzoek")
    feed.add_argument("--workers", type=int, default=4, help="aantal parallelle verzoeken")
    feed.add_argument(
        "--verzoeken-per-seconde",
        type=float,
        default=6.0,
        help="bovengrens aan het tempo van uitgaande verzoeken; de gateway van "
        "de feed knijpt af (HTTP 429) als het te snel gaat (standaard 6)",
    )
    feed.add_argument("--limit", type=int, default=0, help="alleen de eerste N landen toetsen")
    feed.add_argument(
        "--allow-isocode",
        action="append",
        default=[],
        metavar="CODE",
        help="landcode die van ISO 3166-1 afwijkt maar geaccepteerd wordt "
        "(herhaalbaar, bijvoorbeeld --allow-isocode BQ-BO)",
    )

    feed.add_argument(
        "--negeer-land",
        action="append",
        default=[],
        metavar="LANDSLEUTEL",
        help="land dat buiten beschouwing blijft, bijvoorbeeld omdat er bewust geen "
        "reisadvies van is (herhaalbaar, bijvoorbeeld --negeer-land vaticaanstad)",
    )

    feed.add_argument(
        "--gesloten-post",
        action="append",
        default=[],
        metavar="POST",
        help="post waarvan bekend is dat hij gesloten is en geen adres heeft "
        "(herhaalbaar, bijvoorbeeld --gesloten-post ambassade-kaboel)",
    )

    extra = parser.add_argument_group("extra controles")
    extra.add_argument(
        "--check-files", action="store_true", help="kaartbestanden daadwerkelijk ophalen"
    )
    extra.add_argument(
        "--check-website",
        action="store_true",
        help="wijzigingsdatum vergelijken met nederlandwereldwijd.nl",
    )

    drempels = parser.add_argument_group("drempelwaarden")
    drempels.add_argument("--geldigheid-max-dagen", type=int, default=180)
    drempels.add_argument("--wijziging-max-dagen", type=int, default=365)
    drempels.add_argument("--min-reisadviezen", type=int, default=220)
    drempels.add_argument(
        "--push-venster-dagen",
        type=int,
        default=30,
        help="hoe ver terug een wijziging 'recent' heet bij het toetsen of er "
        "na die wijziging nog gepusht is (standaard 30)",
    )

    uitvoer = parser.add_argument_group("uitvoer")
    uitvoer.add_argument(
        "--output-dir", type=Path, default=Path("rapport"), help="map voor de rapporten"
    )
    uitvoer.add_argument("--no-html", action="store_true", help="geen HTML-rapport schrijven")
    uitvoer.add_argument("--no-json", action="store_true", help="geen JSON-rapport schrijven")
    uitvoer.add_argument(
        "--no-markdown", action="store_true", help="geen Markdown-rapport schrijven"
    )
    uitvoer.add_argument(
        "--theme-css",
        default=DEFAULT_THEME_CSS,
        help="stylesheet van de Rijkshuisstijl Community voor het HTML-rapport",
    )
    uitvoer.add_argument(
        "--no-theme-css",
        action="store_true",
        help="geen extern stylesheet laden (rapport blijft volledig zelfstandig)",
    )
    uitvoer.add_argument(
        "--alleen-samenvatting",
        action="store_true",
        help="in het HTML-rapport de aantallen en de regelcatalogus tonen, maar de "
        "bevindingen zelf (welk land, welke melding) vervangen door een verwijzing "
        "naar de afgeschermde weergave — voor een pagina die zonder inloggen "
        "openbaar staat",
    )
    uitvoer.add_argument("--save-snapshot", type=Path, help="ruwe feed wegschrijven naar bestand")
    uitvoer.add_argument(
        "--from-snapshot", type=Path, help="regels draaien op een eerder bewaarde feed"
    )
    uitvoer.add_argument(
        "--fail-on",
        choices=["error", "warning", "never"],
        default="error",
        help="wanneer de exitcode 1 moet zijn (standaard: bij fouten)",
    )
    uitvoer.add_argument("--quiet", action="store_true", help="geen voortgang tonen")
    uitvoer.add_argument("--verbose", action="store_true", help="uitgebreide logging")


def _settings_from_args(args: argparse.Namespace) -> Settings:
    return Settings(
        base_url=args.base_url,
        user_agent=args.user_agent,
        timeout=args.timeout,
        retries=args.retries,
        workers=args.workers,
        requests_per_second=args.verzoeken_per_seconde,
        check_files=args.check_files,
        check_website=args.check_website,
        limit=args.limit,
        extra_isocodes=frozenset(args.allow_isocode),
        excluded_countries=frozenset(args.negeer_land),
        closed_posts=frozenset(args.gesloten_post),
        thresholds=Thresholds(
            geldigheid_max_dagen=args.geldigheid_max_dagen,
            wijziging_max_dagen=args.wijziging_max_dagen,
            min_aantal_reisadviezen=args.min_reisadviezen,
            push_venster_dagen=args.push_venster_dagen,
        ),
    )


def _print_rules() -> int:
    print("Validatieregels\n")
    for titel, regels in (("Feed als geheel", FEED_RULES), ("Per land", COUNTRY_RULES)):
        print(f"## {titel}\n")
        for regel in sorted(regels, key=lambda r: r.id):
            extra = f" (alleen met --{regel.requires.replace('_', '-')})" if regel.requires else ""
            print(f"{regel.id}  [{regel.severity.label}]{extra}\n    {regel.title}")
            print(f"    {regel.description}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.commando == "regels":
        return _print_rules()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    settings = _settings_from_args(args)

    def voortgang(fase: str, gedaan: int, totaal: int) -> None:
        if args.quiet:
            return
        eind = "\n" if gedaan == totaal else "\r"
        print(f"  {fase}: {gedaan}/{totaal}", end=eind, file=sys.stderr, flush=True)

    if args.from_snapshot:
        snapshot = load_snapshot(args.from_snapshot)
        report = run_rules(snapshot, settings)
    else:
        report, snapshot = validate(settings, FeedClient(settings), voortgang)
        if args.save_snapshot:
            save_snapshot(snapshot, args.save_snapshot)
            logger.info("snapshot bewaard in %s", args.save_snapshot)

    print(render_console(report))

    uitvoer: list[Path] = []
    if not args.no_json:
        uitvoer.append(write_json(report, args.output_dir / "rapport.json"))
    if not args.no_markdown:
        uitvoer.append(write_markdown(report, args.output_dir / "rapport.md"))
    if not args.no_html:
        thema = None if args.no_theme_css else args.theme_css
        uitvoer.append(
            write_html(
                report,
                args.output_dir / "index.html",
                theme_css=thema,
                summary_only=args.alleen_samenvatting,
            )
        )
        uitvoer.append(write_manual(args.output_dir / MANUAL_FILENAME))
    for pad in uitvoer:
        print(f"Geschreven: {pad}")

    return exit_code(report, args.fail_on)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
