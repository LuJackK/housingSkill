"""Tests for housing_skill.scrapers.nepremicnine and bolha (HTML parsing)."""

from __future__ import annotations

import hashlib

import pytest
from bs4 import BeautifulSoup

from housing_skill.scrapers.nepremicnine import NepremicnineScraper
from housing_skill.scrapers.bolha import BolhaScraper
from housing_skill.models.listing import ListingCriteria


SAMPLE_NEPREMICNINE_ARTICLE = """
<article class="property-wrapper">
  <h2 class="title"><a href="/oglas/lepo-stanovanje-123/">Lepo stanovanje v centru</a></h2>
  <span class="cena">750 €</span>
  <span class="velikost">60 m²</span>
  <span class="sobe">2</span>
  <span class="lokacija">Ljubljana, Center</span>
  <p class="opis">Opremljeno stanovanje z balkonom.</p>
  <img src="https://img.nepremicnine.net/photo1.jpg" />
</article>
"""

SAMPLE_BOLHA_ARTICLE = """
<article class="entity-body">
  <h3 class="entity-title"><a href="/oglas/stanovanje-maribor-456/">Stanovanje v Mariboru</a></h3>
  <div class="price-box"><strong>500 €</strong></div>
  <p class="entity-description-body">Neopremljeno, 45 m2, 2 sobi, 2. nadstropje</p>
  <small class="city-name">Maribor</small>
</article>
"""


class TestNepremicnineScraper:
    def setup_method(self):
        self.scraper = NepremicnineScraper()

    def test_parse_article(self):
        soup = BeautifulSoup(SAMPLE_NEPREMICNINE_ARTICLE, "html.parser")
        article = soup.find("article")
        listing = self.scraper._parse_article(article)

        assert listing is not None
        assert "Lepo stanovanje" in listing.title
        assert listing.price_eur == 750.0
        assert listing.size_m2 == 60.0
        assert listing.rooms == 2.0
        assert "Ljubljana" in listing.location
        assert listing.furnished is True
        assert listing.source == "nepremicnine.net"
        assert listing.url == "https://www.nepremicnine.net/oglas/lepo-stanovanje-123/"

    def test_parse_article_no_title_returns_none(self):
        soup = BeautifulSoup("<article><p>nothing</p></article>", "html.parser")
        listing = self.scraper._parse_article(soup.find("article"))
        assert listing is None

    def test_detect_furnished(self):
        assert NepremicnineScraper._detect_furnished("opremljeno stanovanje") is True
        assert NepremicnineScraper._detect_furnished("neopremljeno") is False
        assert NepremicnineScraper._detect_furnished("brez podatkov") is None

    def test_parse_rooms(self):
        assert NepremicnineScraper._parse_rooms("2") == 2.0
        assert NepremicnineScraper._parse_rooms("2.5") == 2.5
        assert NepremicnineScraper._parse_rooms("ni podatka") is None

    def test_build_params(self):
        c = ListingCriteria(max_price_eur=900, min_size_m2=40, min_rooms=2)
        params = NepremicnineScraper._build_params(c)
        assert params["cena_do"] == 900
        assert params["velikost_od"] == 40
        assert params["sobe_od"] == 2


class TestBolhaScraper:
    def setup_method(self):
        self.scraper = BolhaScraper()

    def test_parse_article(self):
        soup = BeautifulSoup(SAMPLE_BOLHA_ARTICLE, "html.parser")
        article = soup.find("article")
        listing = self.scraper._parse_article(article)

        assert listing is not None
        assert "Maribor" in listing.title
        assert listing.price_eur == 500.0
        assert listing.size_m2 == 45.0
        assert listing.rooms == 2.0
        assert "Maribor" in listing.location
        assert listing.furnished is False
        assert listing.source == "bolha.com"

    def test_parse_article_no_title_returns_none(self):
        soup = BeautifulSoup("<article><p>nothing</p></article>", "html.parser")
        listing = self.scraper._parse_article(soup.find("article"))
        assert listing is None

    def test_extract_size_from_text(self):
        assert BolhaScraper._extract_size_from_text("45 m2 stanovanje") == 45.0
        assert BolhaScraper._extract_size_from_text("60m²") == 60.0
        assert BolhaScraper._extract_size_from_text("ni podatka") is None

    def test_extract_rooms_from_text(self):
        assert BolhaScraper._extract_rooms_from_text("2 sobi, lepo stanovanje") == 2.0
        assert BolhaScraper._extract_rooms_from_text("3 sobe na voljo") == 3.0
        assert BolhaScraper._extract_rooms_from_text("brez podatka") is None

    def test_detect_furnished(self):
        assert BolhaScraper._detect_furnished("opremljeno stanovanje") is True
        assert BolhaScraper._detect_furnished("neopremljeno prazno") is False
        assert BolhaScraper._detect_furnished("brez podatkov") is None

    def test_build_params(self):
        c = ListingCriteria(max_price_eur=700, min_price_eur=300, locations=["Ljubljana"])
        params = BolhaScraper._build_params(c, page=2)
        assert params["price_to"] == 700
        assert params["price_from"] == 300
        assert params["city"] == "Ljubljana"
        assert params["page"] == 2
