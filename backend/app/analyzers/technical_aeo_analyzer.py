"""
Technical AEO (Answer Engine Optimization) Analyzer
=====================================================

Evaluates the technical readiness of ANY website (blogs, ecommerce,
SaaS, enterprise, government, education, news, agency, personal) for:

  - Google Search
  - Google AI Overview
  - ChatGPT
  - Gemini
  - Perplexity
  - AI / Answer Engines generally

Stack: requests, BeautifulSoup4, json, re, urllib.parse, logging
No paid APIs / external SEO tools.

Main entry point:

    analyze_technical_aeo(url: str) -> dict

Returns a dict with all detection flags, a 0-100 technical_score,
a score_breakdown, strengths / weaknesses lists, and a verdict string.
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("aeo.technical")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 10

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# All schema @type / itemtype values we recognise and report on.
KNOWN_SCHEMA_TYPES: set[str] = {
    "faqpage",
    "organization",
    "localbusiness",
    "breadcrumblist",
    "website",
    "webpage",
    "article",
    "blogposting",
    "newsarticle",
    "person",
    "product",
    "review",
    "event",
    "howto",
    "recipe",
    "videoobject",
    "imageobject",
    "creativework",
    "sitelinksearchbox",
    "searchaction",
    "collectionpage",
    "itemlist",
    "service",
    "softwareapplication",
    "course",
    "jobposting",
}

# Sitemap paths to probe, in priority order. Covers common CMS conventions
# (WordPress, Shopify, custom static sites, etc.)
SITEMAP_PATHS: list[str] = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/post-sitemap.xml",
    "/page-sitemap.xml",
    "/news-sitemap.xml",
    "/product-sitemap.xml",
    "/category-sitemap.xml",
    "/sitemap/sitemap-index.xml",
    "/wp-sitemap.xml",
    "/sitemap1.xml",
]

# Common byline / author CSS class fragments.
BYLINE_CLASS_FRAGMENTS: list[str] = [
    "author",
    "byline",
    "post-author",
    "entry-author",
    "article-author",
    "writer",
    "contributor",
    "by-line",
]

# Fingerprints that indicate a bot-protection interstitial rather than real
# page HTML. If we detect one of these, the diagnostic flags it clearly so
# a low score isn't mistaken for a real audit finding.
BOT_WALL_SIGNALS: list[str] = [
    "cf-browser-verification",
    "cf_clearance",
    "challenge-platform",
    "datadome",
    "px-captcha",
    "recaptcha",
    "enable javascript",
    "checking your browser",
    "please wait",
    "ddos-guard",
    "under attack mode",
    "just a moment",
]


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[requests.Response | None, str | None]:
    """
    Fetch a URL with a browser-like User-Agent.

    Returns (response, error_message). error_message is None on success.
    """
    try:
        resp = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp, None
    except requests.exceptions.Timeout:
        return None, "Request timed out"
    except requests.exceptions.ConnectionError:
        return None, "Unable to connect to website"
    except requests.exceptions.HTTPError as exc:
        return None, f"HTTP error: {exc}"
    except requests.exceptions.RequestException as exc:
        return None, f"Request failed: {exc}"


def _probe_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Return True if *url* resolves to HTTP 200.

    Tries HEAD first; falls back to a streaming GET for servers that
    reject HEAD with 405 / 403 but serve the resource on GET.
    """
    try:
        response = requests.head(
            url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True
        )
        if response.status_code in (405, 403, 501):
            response = requests.get(
                url,
                headers=DEFAULT_HEADERS,
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
        return response.status_code == 200
    except requests.RequestException as exc:
        logger.debug("Probe failed for %s: %s", url, exc)
        return False


def _base_url(website_url: str) -> str:
    """Return scheme + netloc, e.g. https://example.com (no trailing slash)."""
    parsed = urlparse(website_url)
    if not parsed.scheme:
        parsed = urlparse(f"https://{website_url}")
    return f"{parsed.scheme}://{parsed.netloc}"


# ---------------------------------------------------------------------------
# JSON-LD helpers
# ---------------------------------------------------------------------------

def _flatten_ld_nodes(data: object) -> list[dict]:
    """
    Recursively flatten a JSON-LD blob into a list of individual schema nodes.

    Handles:
      - a single object   { "@type": "..." }
      - a top-level list  [ {...}, {...} ]
      - @graph wrappers    { "@graph": [ ... ] }
      - nested objects inside any value (e.g. WebPage containing
        a BreadcrumbList, or Organization nested inside Article.publisher)
    """
    nodes: list[dict] = []

    if isinstance(data, list):
        for item in data:
            nodes.extend(_flatten_ld_nodes(item))
    elif isinstance(data, dict):
        nodes.append(data)
        if "@graph" in data:
            nodes.extend(_flatten_ld_nodes(data["@graph"]))
        for value in data.values():
            if isinstance(value, (dict, list)):
                nodes.extend(_flatten_ld_nodes(value))

    return nodes


def _types_from_node(node: dict) -> list[str]:
    """Return a normalised (lowercase, stripped) list of @type values from a node."""
    raw = node.get("@type", "")
    types = raw if isinstance(raw, list) else [raw]
    return [t.strip().lower() for t in types if isinstance(t, str)]


# ---------------------------------------------------------------------------
# Schema detection: JSON-LD + Microdata + RDFa
# ---------------------------------------------------------------------------

def _check_schema_markup(soup: BeautifulSoup) -> dict:
    """
    Detect JSON-LD, Microdata, and RDFa schema markup on the page.

    Returns a dict with:
      schema_markup        - True if ANY structured data was found
      faq_schema           - FAQPage
      organization_schema  - Organization or LocalBusiness
      breadcrumb_schema    - BreadcrumbList
      website_schema       - WebSite
      webpage_schema       - WebPage
      article_schema       - Article / BlogPosting / NewsArticle
      person_schema        - Person
      detected_types       - sorted list of all recognised @type values
      json_ld_count        - number of JSON-LD <script> blocks found
      json_ld_errors       - number of JSON-LD blocks that failed to parse
      microdata_count      - number of elements with itemtype=
      rdfa_count           - number of elements with typeof= (RDFa)
    """
    result = {
        "schema_markup": False,
        "faq_schema": False,
        "organization_schema": False,
        "breadcrumb_schema": False,
        "website_schema": False,
        "webpage_schema": False,
        "article_schema": False,
        "person_schema": False,
        "detected_types": [],
        "json_ld_count": 0,
        "json_ld_errors": 0,
        "microdata_count": 0,
        "rdfa_count": 0,
    }

    found_types: set[str] = set()

    # ---- JSON-LD ----
    json_ld_scripts = soup.find_all("script", {"type": "application/ld+json"})
    result["json_ld_count"] = len(json_ld_scripts)
    logger.debug("JSON-LD blocks found: %d", len(json_ld_scripts))

    for script in json_ld_scripts:
        try:
            raw = script.string
            if raw is None:
                # Some pages put the JSON across multiple text nodes
                raw = script.get_text()
            raw = (raw or "").strip()
            if not raw:
                continue
            data = json.loads(raw)
        except (json.JSONDecodeError, AttributeError, ValueError, TypeError) as exc:
            result["json_ld_errors"] += 1
            logger.debug("JSON-LD parse error: %s", exc)
            continue

        nodes = _flatten_ld_nodes(data)
        for node in nodes:
            if not isinstance(node, dict):
                continue
            for t in _types_from_node(node):
                if t in KNOWN_SCHEMA_TYPES:
                    found_types.add(t)

    if json_ld_scripts:
        result["schema_markup"] = True

    # ---- Microdata (itemtype="https://schema.org/Xyz") ----
    microdata_items = soup.find_all(attrs={"itemtype": True})
    result["microdata_count"] = len(microdata_items)
    if microdata_items:
        result["schema_markup"] = True
        logger.debug("Microdata items found: %d", len(microdata_items))

    for item in microdata_items:
        raw_type = item.get("itemtype", "")
        if not isinstance(raw_type, str):
            continue
        # itemtype is a URL, e.g. https://schema.org/FAQPage — take the last
        # path segment as the type name.
        type_name = raw_type.rstrip("/").rsplit("/", 1)[-1].strip().lower()
        if type_name in KNOWN_SCHEMA_TYPES:
            found_types.add(type_name)
        else:
            # Fall back to substring matching for safety
            lowered = raw_type.lower()
            for known in KNOWN_SCHEMA_TYPES:
                if known in lowered:
                    found_types.add(known)

    # ---- RDFa (typeof="Xyz") ----
    rdfa_items = soup.find_all(attrs={"typeof": True})
    result["rdfa_count"] = len(rdfa_items)
    if rdfa_items:
        result["schema_markup"] = True
        logger.debug("RDFa items found: %d", len(rdfa_items))

    for item in rdfa_items:
        raw_type = item.get("typeof", "")
        if not isinstance(raw_type, str):
            continue
        for token in raw_type.split():
            type_name = token.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1].strip().lower()
            if type_name in KNOWN_SCHEMA_TYPES:
                found_types.add(type_name)

    # ---- Map found types -> result flags ----
    if "faqpage" in found_types:
        result["faq_schema"] = True
    if "organization" in found_types or "localbusiness" in found_types:
        result["organization_schema"] = True
    if "breadcrumblist" in found_types:
        result["breadcrumb_schema"] = True
    if "website" in found_types:
        result["website_schema"] = True
    if "webpage" in found_types or "collectionpage" in found_types:
        result["webpage_schema"] = True
    if any(t in found_types for t in ("article", "blogposting", "newsarticle")):
        result["article_schema"] = True
    if "person" in found_types:
        result["person_schema"] = True

    result["detected_types"] = sorted(found_types)
    logger.debug("Schema types detected: %s", result["detected_types"])
    return result


# ---------------------------------------------------------------------------
# Canonical / robots meta
# ---------------------------------------------------------------------------

def _check_canonical_tag(soup: BeautifulSoup) -> bool:
    """Return True if a non-empty <link rel="canonical"> tag is present."""
    try:
        canonical = soup.find("link", {"rel": "canonical"})
        if canonical and str(canonical.get("href", "")).strip():
            logger.debug("Canonical tag found: %s", canonical.get("href"))
            return True
    except Exception as exc:
        logger.debug("Canonical tag check error: %s", exc)
    logger.debug("Canonical tag: NOT found")
    return False


def _check_robots_meta(soup: BeautifulSoup) -> bool:
    """
    Return True if any robots-directive meta tag is present:
      - <meta name="robots" ...>
      - <meta http-equiv="robots" ...>
      - <meta name="googlebot" / "bingbot" ...>
    """
    try:
        tag = soup.find(
            "meta",
            attrs={"name": lambda n: isinstance(n, str) and n.strip().lower() == "robots"},
        )
        if tag:
            logger.debug("Robots meta (name=) found")
            return True

        tag_http = soup.find(
            "meta",
            attrs={"http-equiv": lambda h: isinstance(h, str) and h.strip().lower() == "robots"},
        )
        if tag_http:
            logger.debug("Robots meta (http-equiv=) found")
            return True

        for bot_name in ("googlebot", "bingbot"):
            bot_tag = soup.find(
                "meta",
                attrs={"name": lambda n, bn=bot_name: isinstance(n, str) and n.strip().lower() == bn},
            )
            if bot_tag:
                logger.debug("Robots meta (%s) found", bot_name)
                return True
    except Exception as exc:
        logger.debug("Robots meta check error: %s", exc)

    logger.debug("Robots meta: NOT found")
    return False


# ---------------------------------------------------------------------------
# Open Graph / Twitter Cards
# ---------------------------------------------------------------------------

def _check_open_graph(soup: BeautifulSoup) -> dict:
    """
    Detect Open Graph tags.

    Returns:
      open_graph    - True if at least one og: tag present
      og_title      - True if og:title present
      og_description- True if og:description present
      og_image      - True if og:image present
      og_url        - True if og:url present
    """
    result = {
        "open_graph": False,
        "og_title": False,
        "og_description": False,
        "og_image": False,
        "og_url": False,
    }

    targets = {
        "og:title": "og_title",
        "og:description": "og_description",
        "og:image": "og_image",
        "og:url": "og_url",
    }

    try:
        # Standard: <meta property="og:...">
        og_tags = soup.find_all(
            "meta",
            attrs={"property": lambda p: isinstance(p, str) and p.strip().lower().startswith("og:")},
        )
        # Non-standard but seen in the wild: <meta name="og:...">
        og_tags += soup.find_all(
            "meta",
            attrs={"name": lambda n: isinstance(n, str) and n.strip().lower().startswith("og:")},
        )

        if og_tags:
            result["open_graph"] = True

        for tag in og_tags:
            key = (tag.get("property") or tag.get("name") or "").strip().lower()
            if key in targets:
                result[targets[key]] = True

    except Exception as exc:
        logger.debug("Open Graph check error: %s", exc)

    logger.debug("Open Graph: %s", result)
    return result


def _check_twitter_cards(soup: BeautifulSoup) -> dict:
    """
    Detect Twitter Card tags. Supports both name= and property= variants.

    Returns:
      twitter_cards     - True if at least one twitter: tag present
      twitter_card      - True if twitter:card present
      twitter_title     - True if twitter:title present
      twitter_description - True if twitter:description present
    """
    result = {
        "twitter_cards": False,
        "twitter_card": False,
        "twitter_title": False,
        "twitter_description": False,
    }

    targets = {
        "twitter:card": "twitter_card",
        "twitter:title": "twitter_title",
        "twitter:description": "twitter_description",
    }

    try:
        tags = soup.find_all(
            "meta",
            attrs={"name": lambda n: isinstance(n, str) and n.strip().lower().startswith("twitter:")},
        )
        tags += soup.find_all(
            "meta",
            attrs={"property": lambda p: isinstance(p, str) and p.strip().lower().startswith("twitter:")},
        )

        if tags:
            result["twitter_cards"] = True

        for tag in tags:
            key = (tag.get("name") or tag.get("property") or "").strip().lower()
            if key in targets:
                result[targets[key]] = True

    except Exception as exc:
        logger.debug("Twitter Cards check error: %s", exc)

    logger.debug("Twitter Cards: %s", result)
    return result


# ---------------------------------------------------------------------------
# Author / E-E-A-T detection
# ---------------------------------------------------------------------------

def _check_author_info(soup: BeautifulSoup) -> bool:
    """
    Return True if author information is detectable via any of:
      1. <meta name="author">
      2. <link rel="author"> or <a rel="author">
      3. JSON-LD 'author' property (incl. nested in @graph)
      4. JSON-LD Person schema anywhere in the document
      5. Microdata itemprop="author"
      6. Common byline CSS classes (author, byline, post-author, ...)
      7. aria-label="author" / data-author attribute
      8. <address> element (common editorial/article pattern)
    """
    try:
        # 1. <meta name="author">
        if soup.find("meta", attrs={"name": lambda n: isinstance(n, str) and n.strip().lower() == "author"}):
            logger.debug("Author found: meta[name=author]")
            return True

        # 2. rel="author"
        if soup.find("link", attrs={"rel": "author"}):
            logger.debug("Author found: link[rel=author]")
            return True
        if soup.find("a", attrs={"rel": "author"}):
            logger.debug("Author found: a[rel=author]")
            return True

        # 3 & 4. JSON-LD — deep traversal including @graph
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                raw = script.string or script.get_text() or ""
                data = json.loads(raw.strip()) if raw.strip() else None
            except (json.JSONDecodeError, AttributeError, ValueError, TypeError):
                continue
            if data is None:
                continue
            for node in _flatten_ld_nodes(data):
                if not isinstance(node, dict):
                    continue
                if "author" in node:
                    logger.debug("Author found: JSON-LD 'author' property")
                    return True
                if "person" in _types_from_node(node):
                    logger.debug("Author found: JSON-LD Person schema")
                    return True

        # 5. Microdata itemprop="author"
        if soup.find(attrs={"itemprop": lambda v: isinstance(v, str) and "author" in v.strip().lower()}):
            logger.debug("Author found: itemprop=author")
            return True

        # 6. Common class-based byline patterns
        def _class_match(c, fragment):
            if c is None:
                return False
            if isinstance(c, list):
                return any(fragment in cls.lower() for cls in c)
            return fragment in str(c).lower()

        for cls_fragment in BYLINE_CLASS_FRAGMENTS:
            if soup.find(class_=lambda c, f=cls_fragment: _class_match(c, f)):
                logger.debug("Author found: class containing '%s'", cls_fragment)
                return True

        # 7. aria-label="author" / data-author
        if soup.find(attrs={"aria-label": lambda v: isinstance(v, str) and "author" in v.strip().lower()}):
            logger.debug("Author found: aria-label=author")
            return True
        if soup.find(attrs={"data-author": True}):
            logger.debug("Author found: data-author attribute")
            return True

        # 8. <address> element
        if soup.find("address"):
            logger.debug("Author found: <address> element")
            return True

    except Exception as exc:
        logger.debug("Author check error: %s", exc)

    logger.debug("Author info: NOT found")
    return False


# ---------------------------------------------------------------------------
# Sitemap / robots.txt
# ---------------------------------------------------------------------------

def _check_sitemap(base: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Return True if at least one sitemap is discoverable.

    1. Probes a prioritised list of common sitemap paths.
    2. Falls back to parsing /robots.txt for `Sitemap:` directives.
    """
    for path in SITEMAP_PATHS:
        url = urljoin(base, path)
        if _probe_url(url, timeout=timeout):
            logger.debug("Sitemap found at: %s", url)
            return True

    robots_url = urljoin(base, "/robots.txt")
    try:
        resp = requests.get(robots_url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    if sitemap_url and _probe_url(sitemap_url, timeout=timeout):
                        logger.debug("Sitemap found via robots.txt: %s", sitemap_url)
                        return True
    except requests.RequestException as exc:
        logger.debug("robots.txt read error during sitemap probe: %s", exc)

    logger.debug("Sitemap: NOT found")
    return False


def _check_robots_txt(base: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Return True if /robots.txt returns HTTP 200 with a body containing at
    least one recognised robots.txt directive (guards against CDNs that
    return a 200 HTML error page for any path).
    """
    url = urljoin(base, "/robots.txt")
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            logger.debug("robots.txt: status %d", resp.status_code)
            return False

        text = resp.text.strip()
        robots_directive = re.compile(
            r"^\s*(user-agent|disallow|allow|sitemap|crawl-delay)\s*:",
            re.IGNORECASE | re.MULTILINE,
        )
        if robots_directive.search(text):
            logger.debug("robots.txt: valid file found")
            return True

        logger.debug("robots.txt: 200 but no valid directives — likely a CDN error page")
    except requests.RequestException as exc:
        logger.debug("robots.txt probe failed: %s", exc)

    return False


# ---------------------------------------------------------------------------
# Bot-wall / empty-page diagnostic
# ---------------------------------------------------------------------------

def _diagnose_soup(soup: BeautifulSoup, url: str) -> dict:
    """
    Inspect the soup object and return a diagnostic dict that makes it
    immediately obvious whether the fetched HTML is real page content,
    or a bot-protection / JS-required interstitial.
    """
    raw_html = str(soup)
    html_len = len(raw_html)
    title_text = soup.title.get_text(strip=True) if soup.title else ""
    body = soup.body
    body_text = body.get_text(" ", strip=True)[:300] if body else ""
    body_text_len = len(body.get_text(strip=True)) if body else 0
    json_ld_count = len(soup.find_all("script", {"type": "application/ld+json"}))
    meta_count = len(soup.find_all("meta"))
    og_count = len(
        soup.find_all("meta", attrs={"property": lambda p: isinstance(p, str) and p.startswith("og:")})
    )
    canonical = soup.find("link", {"rel": "canonical"})
    canonical_href = canonical.get("href", "") if canonical else ""

    raw_lower = raw_html.lower()
    bot_signals_found = [sig for sig in BOT_WALL_SIGNALS if sig in raw_lower]
    is_bot_wall = bool(bot_signals_found) or (html_len < 3000 and body_text_len < 500)

    diag = {
        "url": url,
        "html_length": html_len,
        "body_text_length": body_text_len,
        "title": title_text,
        "body_preview": body_text,
        "json_ld_count": json_ld_count,
        "meta_count": meta_count,
        "og_tag_count": og_count,
        "canonical_href": canonical_href,
        "bot_wall_detected": is_bot_wall,
        "bot_signals_found": bot_signals_found,
    }

    logger.info("=== SOUP DIAGNOSTIC ===")
    logger.info("  URL              : %s", url)
    logger.info("  HTML length      : %d chars", html_len)
    logger.info("  Body text length : %d chars", body_text_len)
    logger.info("  Title            : %s", title_text)
    logger.info("  JSON-LD blocks   : %d", json_ld_count)
    logger.info("  <meta> tags      : %d", meta_count)
    logger.info("  OG tags          : %d", og_count)
    logger.info("  Canonical href   : %s", canonical_href or "NOT FOUND")
    if is_bot_wall:
        logger.warning(
            "  BOT WALL / EMPTY PAGE DETECTED -- signals: %s",
            bot_signals_found or ["page too small"],
        )
    else:
        logger.info("  Page appears to contain real HTML content")
    logger.info("=== END DIAGNOSTIC ===")

    return diag


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _calculate_technical_score(flags: dict) -> tuple[int, dict]:
    """
    Calculate a weighted technical AEO score (0-100).

    Category        | Max points | Rationale
    ----------------|------------|----------------------------------------
    Schema          |     40     | Core AEO signal (JSON-LD/Microdata/RDFa)
    Crawlability    |     25     | robots.txt, sitemap, canonical, robots meta
    Social / OG     |     20     | Drives AI answer-engine link previews
    Authority       |     15     | Author / E-E-A-T signal
    ----------------|------------|
    Total           |    100     |
    """
    schema_score = 0
    crawlability_score = 0
    social_score = 0
    authority_score = 0

    # ---- Schema (40 pts) ----
    if flags.get("schema_markup"):
        schema_score += 10   # base credit for any structured data
    if flags.get("faq_schema"):
        schema_score += 8    # FAQ rich-result eligibility
    if flags.get("organization_schema"):
        schema_score += 7    # entity clarity for AI / knowledge graph
    if flags.get("breadcrumb_schema"):
        schema_score += 4    # navigation signal
    if flags.get("article_schema"):
        schema_score += 5    # content-type signal
    if flags.get("website_schema"):
        schema_score += 3    # sitelinks search box eligibility
    if flags.get("webpage_schema"):
        schema_score += 2    # page-level type clarity
    if flags.get("person_schema"):
        schema_score += 1    # E-E-A-T (stacks with author_info)

    # ---- Crawlability (25 pts) ----
    if flags.get("canonical_tag"):
        crawlability_score += 8
    if flags.get("robots_txt_exists"):
        crawlability_score += 7
    if flags.get("sitemap_exists"):
        crawlability_score += 7
    if flags.get("robots_meta"):
        crawlability_score += 3

    # ---- Social / Open Graph (20 pts) ----
    if flags.get("open_graph"):
        social_score += 12
    if flags.get("twitter_cards"):
        social_score += 8

    # ---- Authority / E-E-A-T (15 pts) ----
    if flags.get("author_info"):
        authority_score += 15

    total_score = schema_score + crawlability_score + social_score + authority_score

    breakdown = {
        "schema_score": schema_score,
        "schema_max": 40,
        "crawlability_score": crawlability_score,
        "crawlability_max": 25,
        "social_score": social_score,
        "social_max": 20,
        "authority_score": authority_score,
        "authority_max": 15,
        "total": min(total_score, 100),
        "total_max": 100,
    }

    return min(total_score, 100), breakdown


# ---------------------------------------------------------------------------
# Strengths / Weaknesses / Verdict
# ---------------------------------------------------------------------------

def _build_strengths_weaknesses(flags: dict) -> tuple[list[str], list[str]]:
    """Derive human-readable strengths and weaknesses from detection flags."""
    strengths: list[str] = []
    weaknesses: list[str] = []

    # Schema markup
    if flags.get("schema_markup"):
        types = flags.get("detected_types") or []
        if types:
            strengths.append(
                f"Structured data detected ({', '.join(t.title() for t in types)})"
            )
        else:
            strengths.append("Structured data markup detected on the page")
    else:
        weaknesses.append("No structured data (JSON-LD/Microdata/RDFa) found — add schema.org markup")

    if flags.get("faq_schema"):
        strengths.append("FAQPage schema present — eligible for FAQ rich results / AI answer extraction")
    else:
        weaknesses.append("No FAQPage schema — add FAQPage JSON-LD to improve AI answer eligibility")

    if flags.get("organization_schema"):
        strengths.append("Organization/LocalBusiness schema present — clarifies brand entity for AI/Knowledge Graph")
    else:
        weaknesses.append("No Organization or LocalBusiness schema — add it for entity clarity")

    if flags.get("breadcrumb_schema"):
        strengths.append("BreadcrumbList schema present — improves navigation context for search engines")
    else:
        weaknesses.append("No BreadcrumbList schema — add breadcrumb markup for navigation signals")

    if flags.get("article_schema"):
        strengths.append("Article/BlogPosting schema present — improves content-type recognition")
    else:
        weaknesses.append("No Article/BlogPosting schema — add it if this page is editorial content")

    # Canonical
    if flags.get("canonical_tag"):
        strengths.append("Canonical tag present — helps prevent duplicate-content issues")
    else:
        weaknesses.append("No canonical tag found — add <link rel='canonical'> to prevent duplicate content issues")

    # Robots meta
    if flags.get("robots_meta"):
        strengths.append("Robots meta directive present — gives search engines explicit indexing guidance")
    else:
        weaknesses.append("No robots meta tag found — add one for explicit indexing guidance")

    # Open Graph
    if flags.get("open_graph"):
        og_parts = []
        if flags.get("og_title"):
            og_parts.append("og:title")
        if flags.get("og_description"):
            og_parts.append("og:description")
        if flags.get("og_image"):
            og_parts.append("og:image")
        if flags.get("og_url"):
            og_parts.append("og:url")
        if og_parts:
            strengths.append(f"Open Graph tags present ({', '.join(og_parts)}) — improves AI/social link previews")
        else:
            strengths.append("Open Graph tags present — improves AI/social link previews")
    else:
        weaknesses.append("No Open Graph tags found — add og:title, og:description, og:image, og:url")

    # Twitter Cards
    if flags.get("twitter_cards"):
        strengths.append("Twitter/X Card tags present — improves preview rendering on X")
    else:
        weaknesses.append("No Twitter/X Card tags found — add twitter:card, twitter:title, twitter:description")

    # Author info
    if flags.get("author_info"):
        strengths.append("Author information detected — strengthens E-E-A-T signals")
    else:
        weaknesses.append("No author information detected — add author bylines or Person schema for E-E-A-T")

    # Sitemap
    if flags.get("sitemap_exists"):
        strengths.append("XML sitemap discoverable — improves crawl discoverability")
    else:
        weaknesses.append("No XML sitemap discoverable — add a sitemap.xml and reference it in robots.txt")

    # Robots.txt
    if flags.get("robots_txt_exists"):
        strengths.append("robots.txt found with valid directives — provides crawl guidance")
    else:
        weaknesses.append("No valid robots.txt found — add one to provide crawl guidance")

    return strengths, weaknesses


def _build_verdict(score: int, flags: dict) -> str:
    """Build a human-readable verdict string from the score."""
    if score >= 85:
        grade, status = "A", "EXCELLENT"
    elif score >= 70:
        grade, status = "B", "GOOD"
    elif score >= 50:
        grade, status = "C", "NEEDS WORK"
    elif score >= 25:
        grade, status = "D", "POOR"
    else:
        grade, status = "F", "CRITICAL"

    detected = flags.get("detected_types") or []
    schema_note = (
        f"Detected schema types: {', '.join(t.title() for t in detected)}."
        if detected
        else "No recognised schema.org types were detected."
    )

    return (
        f"{status} — Grade {grade}. Technical AEO score: {score}/100. "
        f"{schema_note} "
        "This score reflects structured data, crawlability (robots.txt/sitemap/canonical), "
        "social preview tags (Open Graph/Twitter Cards), and author/E-E-A-T signals."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_technical_aeo(url: str) -> dict:
    """
    Analyze the technical AEO signals of *url*.

    This function performs its own HTTP fetch — it works for any public
    website (blogs, ecommerce, SaaS, enterprise, government, education,
    news, agency, or personal sites).

    Parameters
    ----------
    url : str
        The full URL of the page to analyze, e.g. "https://example.com".

    Returns
    -------
    dict
        {
          "technical_score": int,
          "schema_markup": bool,
          "faq_schema": bool,
          "organization_schema": bool,
          "breadcrumb_schema": bool,
          "website_schema": bool,
          "article_schema": bool,
          "person_schema": bool,
          "canonical_tag": bool,
          "robots_meta": bool,
          "open_graph": bool,
          "twitter_cards": bool,
          "author_info": bool,
          "sitemap_exists": bool,
          "robots_txt_exists": bool,
          "score_breakdown": {...},
          "strengths": [...],
          "weaknesses": [...],
          "verdict": "...",

          # Extra diagnostic / detail fields (not in the minimal spec but
          # useful for debugging and for richer reports):
          "detected_types": [...],
          "og_title": bool, "og_description": bool, "og_image": bool, "og_url": bool,
          "twitter_card": bool, "twitter_title": bool, "twitter_description": bool,
          "webpage_schema": bool,
          "soup_diagnostic": {...},
          "error": str | None,
        }
    """
    logger.info("Technical AEO analysis started | url=%s", url)

    # Normalise URL (add scheme if missing)
    if not urlparse(url).scheme:
        url = f"https://{url}"

    # ── Step 1: Fetch the page ───────────────────────────────────────────
    response, fetch_error = _fetch(url)

    if response is None:
        logger.error("Fetch failed for %s: %s", url, fetch_error)
        # Return a fully-populated, all-False/0 result so callers never
        # have to special-case a missing key.
        empty_flags = {
            "schema_markup": False,
            "faq_schema": False,
            "organization_schema": False,
            "breadcrumb_schema": False,
            "website_schema": False,
            "webpage_schema": False,
            "article_schema": False,
            "person_schema": False,
            "canonical_tag": False,
            "robots_meta": False,
            "open_graph": False,
            "og_title": False,
            "og_description": False,
            "og_image": False,
            "og_url": False,
            "twitter_cards": False,
            "twitter_card": False,
            "twitter_title": False,
            "twitter_description": False,
            "author_info": False,
            "sitemap_exists": False,
            "robots_txt_exists": False,
            "detected_types": [],
        }
        score, breakdown = _calculate_technical_score(empty_flags)
        strengths, weaknesses = _build_strengths_weaknesses(empty_flags)
        return {
            "technical_score": score,
            **empty_flags,
            "score_breakdown": breakdown,
            "strengths": strengths,
            "weaknesses": [f"Could not fetch the website: {fetch_error}"] + weaknesses,
            "verdict": (
                f"CRITICAL — Grade F. Technical AEO score: {score}/100. "
                f"The page could not be fetched ({fetch_error}). "
                "No technical signals could be evaluated."
            ),
            "soup_diagnostic": {},
            "error": fetch_error,
        }

    soup = BeautifulSoup(response.text, "html.parser")
    base = _base_url(url)

    # ── Step 2: Bot-wall / empty-page diagnostic (always runs) ───────────
    try:
        soup_diag = _diagnose_soup(soup, url)
    except Exception as exc:
        logger.error("Soup diagnostic failed: %s", exc)
        soup_diag = {}

    # ── Step 3: Run each detection independently ─────────────────────────
    try:
        schema_flags = _check_schema_markup(soup)
    except Exception as exc:
        logger.error("Schema check failed: %s", exc)
        schema_flags = {
            "schema_markup": False, "faq_schema": False, "organization_schema": False,
            "breadcrumb_schema": False, "website_schema": False, "webpage_schema": False,
            "article_schema": False, "person_schema": False, "detected_types": [],
            "json_ld_count": 0, "json_ld_errors": 0, "microdata_count": 0, "rdfa_count": 0,
        }

    try:
        canonical_tag = _check_canonical_tag(soup)
    except Exception as exc:
        logger.error("Canonical check failed: %s", exc)
        canonical_tag = False

    try:
        robots_meta = _check_robots_meta(soup)
    except Exception as exc:
        logger.error("Robots meta check failed: %s", exc)
        robots_meta = False

    try:
        og_flags = _check_open_graph(soup)
    except Exception as exc:
        logger.error("Open Graph check failed: %s", exc)
        og_flags = {"open_graph": False, "og_title": False, "og_description": False, "og_image": False, "og_url": False}

    try:
        twitter_flags = _check_twitter_cards(soup)
    except Exception as exc:
        logger.error("Twitter Cards check failed: %s", exc)
        twitter_flags = {"twitter_cards": False, "twitter_card": False, "twitter_title": False, "twitter_description": False}

    try:
        author_info = _check_author_info(soup)
    except Exception as exc:
        logger.error("Author info check failed: %s", exc)
        author_info = False

    try:
        sitemap_exists = _check_sitemap(base)
    except Exception as exc:
        logger.error("Sitemap check failed: %s", exc)
        sitemap_exists = False

    try:
        robots_txt_exists = _check_robots_txt(base)
    except Exception as exc:
        logger.error("Robots.txt check failed: %s", exc)
        robots_txt_exists = False

    # ── Step 4: Assemble flags ────────────────────────────────────────────
    all_flags = {
        **schema_flags,
        "canonical_tag": canonical_tag,
        "robots_meta": robots_meta,
        **og_flags,
        **twitter_flags,
        "author_info": author_info,
        "sitemap_exists": sitemap_exists,
        "robots_txt_exists": robots_txt_exists,
    }

    # ── Step 5: Score ──────────────────────────────────────────────────────
    try:
        technical_score, breakdown = _calculate_technical_score(all_flags)
    except Exception as exc:
        logger.error("Scoring failed: %s", exc)
        technical_score, breakdown = 0, {}

    # ── Step 6: Strengths / Weaknesses / Verdict ─────────────────────────
    try:
        strengths, weaknesses = _build_strengths_weaknesses(all_flags)
    except Exception as exc:
        logger.error("Strengths/weaknesses build failed: %s", exc)
        strengths, weaknesses = [], []

    try:
        verdict = _build_verdict(technical_score, all_flags)
    except Exception as exc:
        logger.error("Verdict build failed: %s", exc)
        verdict = f"Technical AEO score: {technical_score}/100."

    # ── Step 7: Final result ──────────────────────────────────────────────
    result = {
        "technical_score": technical_score,
        **all_flags,
        "score_breakdown": breakdown,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "verdict": verdict,
        "soup_diagnostic": soup_diag,
        "error": None,
    }

    logger.info(
        "Technical AEO complete | score=%d | schema=%s | og=%s | author=%s | "
        "sitemap=%s | robots_txt=%s | canonical=%s | types=%s",
        technical_score,
        all_flags.get("schema_markup"),
        all_flags.get("open_graph"),
        author_info,
        sitemap_exists,
        robots_txt_exists,
        canonical_tag,
        all_flags.get("detected_types"),
    )
    logger.info("Score breakdown: %s", breakdown)

    return result


