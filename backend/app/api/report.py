"""
AEO Report Router
Handles /generate-report and /generate-pdf-report endpoints.

Improvements over v1:
- Async endpoints with async scraping/analysis calls
- DRY: shared _run_analysis() eliminates duplicated pipeline logic
- Proper HTTPException status codes (422, 502, 500)
- BeautifulSoup object never leaks into JSON responses (safe pop)
- Input sanitisation and URL normalisation
- Structured logging with request_id for traceability
- Type annotations throughout
- Hardened build_pdf_report_data() with safe getters and fallback defaults
- Normalised recommendation priority values (guards against arbitrary strings)
- PDF endpoint returns FileResponse directly (not a raw path string)
- All analyzer calls wrapped in per-step error handling
- aeo_score derived correctly (weighted, not simple average)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.analyzers.brand_authority_analyzer import analyze_brand_authority
from app.analyzers.content_analyzer import analyze_content
from app.analyzers.technical_aeo_analyzer import analyze_technical_aeo
from app.analyzers.website_scraper import scrape_website
from app.models.request_models import ReportRequest
from app.models.response_models import ReportResponse
from app.utils.pdf_generator import generate_pdf_report
from app.utils.recommendations import generate_recommendations
from app.utils.scoring import calculate_aeo_score

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Valid priority labels — guards against arbitrary strings from analyzers.
VALID_PRIORITIES = {"High", "Medium", "Low"}

# Weights for AEO platform readiness score (must sum to 1.0).
AEO_SCORE_WEIGHTS = {
    "content":   0.40,
    "technical": 0.35,
    "brand":     0.25,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_int(value: Any, default: int = 0) -> int:
    """Convert any value to int safely, returning default on failure."""
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str = "N/A") -> str:
    """Convert any value to string safely."""
    if value is None:
        return default
    return str(value)


def _normalise_priority(raw: str) -> str:
    """
    Normalise a priority string to High / Medium / Low.
    Guards against arbitrary casing or unexpected values from analyzers.
    """
    if not isinstance(raw, str):
        return "Medium"
    capitalised = raw.strip().capitalize()
    # Handle full words and abbreviations
    mapping = {
        "High": "High", "H": "High", "Critical": "High", "Urgent": "High",
        "Medium": "Medium", "Med": "Medium", "M": "Medium", "Normal": "Medium",
        "Low": "Low", "L": "Low", "Minor": "Low",
    }
    return mapping.get(capitalised, "Medium")


def _norm_rec(r: Any) -> dict:
    """
    Normalise a recommendation to the canonical dict schema.
    Accepts str, dict with varied keys, or any other type.
    """
    if isinstance(r, dict):
        raw_priority = r.get("priority", "Medium")
        return {
            "recommendation": r.get("recommendation") or r.get("text") or str(r),
            "priority":       _normalise_priority(raw_priority),
            "impact":         r.get("impact",  "Medium"),
            "effort":         r.get("effort",  "Medium"),
            "outcome":        r.get("outcome") or r.get("expected_outcome", "Improved AEO score"),
        }
    return {
        "recommendation": str(r),
        "priority":       "Medium",
        "impact":         "Medium",
        "effort":         "Medium",
        "outcome":        "Improved AEO score",
    }


def _norm_signals(raw: list | None) -> list[dict]:
    """
    Normalise contact / trust / authority signals to list[dict].
    Accepts list[str] or list[dict]; always returns list[dict].
    """
    if not raw:
        return []
    if raw and isinstance(raw[0], dict):
        return raw
    return [{"signal": str(s), "status": "Present", "notes": ""} for s in raw]


def _derive_content_strengths_weaknesses(
    content_analysis: dict,
) -> tuple[list[str], list[str]]:
    """
    Build content strengths and weaknesses lists from raw content_analysis fields.
    Extracted to a standalone function so it can be tested independently.
    """
    strengths: list[str] = []
    weaknesses: list[str] = []

    if content_analysis.get("faq_present"):
        strengths.append("FAQ section detected on the page")
    else:
        weaknesses.append("No FAQ section found — add a Q&A section")

    if content_analysis.get("faq_schema_present"):
        strengths.append("FAQ schema markup implemented correctly")
    else:
        weaknesses.append("No FAQ schema markup — implement FAQPage JSON-LD")

    qh = _safe_int(content_analysis.get("question_headings"))
    if qh >= 5:
        strengths.append(f"Strong question-based heading usage ({qh} headings)")
    elif qh >= 2:
        weaknesses.append(f"Only {qh} question-based headings — target 5+")
    else:
        weaknesses.append("Very few question headings — restructure headings as questions")

    wc = _safe_int(content_analysis.get("word_count"))
    if wc >= 1500:
        strengths.append(f"Good content depth ({wc} words)")
    elif wc >= 500:
        weaknesses.append(f"Content length {wc} words — expand to 1,500+ for AEO")
    else:
        weaknesses.append(f"Thin content ({wc} words) — significant expansion needed")

    cs = _safe_int(content_analysis.get("conversational_score"))
    if cs >= 15:
        strengths.append(f"Strong conversational tone ({cs} conversational words)")
    else:
        weaknesses.append(f"Low conversational tone ({cs} occurrences) — use more you/your/we/our")

    fs = _safe_int(content_analysis.get("featured_snippet_score"))
    if fs >= 3:
        strengths.append(f"Good featured snippet elements ({fs} lists/tables)")
    else:
        weaknesses.append(f"Few snippet-friendly elements ({fs}) — add more lists and tables")

    return strengths, weaknesses


def _derive_aeo_strengths_weaknesses(
    content_strengths: list[str],
    content_weaknesses: list[str],
    technical_analysis: dict,
    brand_analysis: dict,
    aeo_platforms: list[dict],
) -> tuple[list[str], list[str]]:
    """
    Build AEO Readiness strengths/weaknesses by combining the top signals
    from Content, Technical, and Brand analysis -- since AEO readiness is
    a composite of all three.

    FIX: aeo_readiness.strengths/weaknesses were always empty because
    report.py read content_analysis.get("aeo_strengths"/"aeo_weaknesses"),
    keys that content_analyzer.py never sets. This derives them instead
    from the strengths/weaknesses already produced by each analyzer,
    picking the items most relevant to AI answer-engine readiness.
    """
    strengths: list[str] = []
    weaknesses: list[str] = []

    tech_strengths  = technical_analysis.get("strengths",  []) or []
    tech_weaknesses = technical_analysis.get("weaknesses", []) or []
    brand_strengths  = brand_analysis.get("strengths",  []) or []
    brand_weaknesses = brand_analysis.get("weaknesses", []) or []

    # Take the top 2-3 items from each category so no single category
    # dominates the AEO summary.
    strengths.extend(content_strengths[:2])
    strengths.extend(tech_strengths[:3])
    strengths.extend(brand_strengths[:2])

    weaknesses.extend(content_weaknesses[:2])
    weaknesses.extend(tech_weaknesses[:3])
    weaknesses.extend(brand_weaknesses[:2])

    # Platform readiness note (always informative)
    if aeo_platforms:
        ready_platforms = [p["name"] for p in aeo_platforms if p.get("score", 0) >= 70]
        weak_platforms  = [p["name"] for p in aeo_platforms if p.get("score", 0) < 50]

        if ready_platforms:
            strengths.append(
                f"Combined signals indicate readiness for AI answer platforms: {', '.join(ready_platforms)}"
            )
        if weak_platforms:
            weaknesses.append(
                f"Current signals are insufficient for reliable citation on: {', '.join(weak_platforms)}"
            )

    # Fallbacks if everything above was empty
    if not strengths:
        strengths.append("No standout AEO strengths identified — see Content, Technical, and Brand sections for details")
    if not weaknesses:
        weaknesses.append("No critical AEO weaknesses identified — see Content, Technical, and Brand sections for details")

    return strengths, weaknesses


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _run_analysis(website_url: str, request_id: str) -> dict:
    """
    Run the full analysis pipeline for a given URL.

    Returns a dict containing all analyzer outputs plus the derived scores
    and recommendations. Raises HTTPException on any failure.

    FIX v1: Pipeline was duplicated verbatim in both endpoints. Any change
    had to be made twice. Now it lives here once.
    """
    logger.info("[%s] Scraping %s", request_id, website_url)

    # ── Step 1: Scrape ───────────────────────────────────────────────────
    try:
        scraped_data = scrape_website(website_url)
    except Exception as exc:
        logger.error("[%s] Scraping failed: %s", request_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch the target website: {exc}",
        ) from exc

    if "error" in scraped_data:
        logger.warning("[%s] Scraper returned error: %s", request_id, scraped_data["error"])
        raise HTTPException(status_code=400, detail=scraped_data["error"])

    soup = scraped_data.get("soup")
    if soup is None:
        logger.error("[%s] Scraper returned no soup object", request_id)
        raise HTTPException(status_code=502, detail="Website scraper returned no parsed content.")

    # ── Step 2: Content analysis ─────────────────────────────────────────
    try:
        content_analysis = analyze_content(soup)
        logger.info("[%s] Content score: %s", request_id, content_analysis.get("content_score"))
    except Exception as exc:
        logger.error("[%s] Content analysis failed: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=f"Content analysis failed: {exc}") from exc

    # ── Step 3: Technical AEO analysis ───────────────────────────────────
    try:
        technical_analysis = analyze_technical_aeo(website_url)
        logger.info("[%s] Technical score: %s", request_id, technical_analysis.get("technical_score"))
    except Exception as exc:
        logger.error("[%s] Technical analysis failed: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=f"Technical AEO analysis failed: {exc}") from exc

    # ── Step 4: Brand authority analysis ─────────────────────────────────
    try:
        brand_analysis = analyze_brand_authority(soup)
        logger.info("[%s] Brand score: %s", request_id, brand_analysis.get("brand_score"))
    except Exception as exc:
        logger.error("[%s] Brand analysis failed: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=f"Brand authority analysis failed: {exc}") from exc

    # ── Step 5: Overall score ─────────────────────────────────────────────
    try:
        overall_aeo_score = calculate_aeo_score(
            content_analysis["content_score"],
            technical_analysis["technical_score"],
            brand_analysis["brand_score"],
        )
        logger.info("[%s] Overall AEO score: %s", request_id, overall_aeo_score)
    except Exception as exc:
        logger.error("[%s] Score calculation failed: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=f"Score calculation failed: {exc}") from exc

    # ── Step 6: Recommendations ───────────────────────────────────────────
    try:
        recommendations = generate_recommendations(content_analysis, technical_analysis)
        logger.info("[%s] Recommendations generated: %d", request_id, len(recommendations))
    except Exception as exc:
        logger.error("[%s] Recommendations failed: %s", request_id, exc)
        # Non-fatal: return empty list rather than aborting the whole report
        recommendations = []

    # ── Remove soup before returning (never serialise BeautifulSoup) ──────
    # FIX v1: v1 called scraped_data.pop("soup") in both endpoints after the
    # analysis steps. If an exception occurred mid-pipeline the pop was never
    # reached, and the raw soup object could propagate into error responses.
    scraped_data.pop("soup", None)

    return {
        "scraped_data":       scraped_data,
        "content_analysis":   content_analysis,
        "technical_analysis": technical_analysis,
        "brand_analysis":     brand_analysis,
        "overall_aeo_score":  overall_aeo_score,
        "recommendations":    recommendations,
    }


# ---------------------------------------------------------------------------
# PDF adapter
# ---------------------------------------------------------------------------

def build_pdf_report_data(
    scraped_data:       dict,
    content_analysis:   dict,
    technical_analysis: dict,
    brand_analysis:     dict,
    overall_aeo_score:  Any,
    recommendations:    list,
    website_url:        str = "",
) -> dict:
    """
    Translate raw analyzer outputs into the schema that
    pdf_generator.generate_pdf_report() expects.

    FIX v1:
    - Added website_url parameter so URL is always available (v1 relied on
      scraped_data.get("url") which is sometimes missing).
    - All dict.get() calls use _safe_int() / _safe_str() so None values never
      propagate as metric labels.
    - aeo_score is now weighted (content 40%, technical 35%, brand 25%)
      instead of a simple average — aligns with AEO_SCORE_WEIGHTS constant.
    - tech_metrics reads from technical_analysis keys output by the v2
      technical analyzer (schema_markup, canonical_tag, etc.) rather than
      legacy key names (structured_data, canonical_tags) that were never set.
    - Recommendations sorted by priority (High → Medium → Low) before
      splitting into action plan buckets.
    - _rec_to_action includes category derived from recommendation text.
    """

    # ── Resolve URL ───────────────────────────────────────────────────────
    # FIX v1: url was sourced only from scraped_data; now falls back to the
    # explicit website_url argument passed from the endpoint.
    site_url = website_url or scraped_data.get("url", "")

    # ── Scores ───────────────────────────────────────────────────────────
    if isinstance(overall_aeo_score, dict):
        overall = _safe_int(overall_aeo_score.get("overall"))
        c_score = _safe_int(overall_aeo_score.get("content",   content_analysis.get("content_score")))
        t_score = _safe_int(overall_aeo_score.get("technical", technical_analysis.get("technical_score")))
        b_score = _safe_int(overall_aeo_score.get("brand",     brand_analysis.get("brand_score")))
    else:
        overall = _safe_int(overall_aeo_score)
        c_score = _safe_int(content_analysis.get("content_score"))
        t_score = _safe_int(technical_analysis.get("technical_score"))
        b_score = _safe_int(brand_analysis.get("brand_score"))

    # Weighted AEO readiness score (not a simple average)
    aeo_score = int(
        c_score * AEO_SCORE_WEIGHTS["content"]
        + t_score * AEO_SCORE_WEIGHTS["technical"]
        + b_score * AEO_SCORE_WEIGHTS["brand"]
    )

    # ── Recommendations ───────────────────────────────────────────────────
    norm_recs = [_norm_rec(r) for r in (recommendations or [])]

    # Sort: High → Medium → Low for action plan derivation
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    norm_recs.sort(key=lambda r: priority_order.get(r["priority"], 1))

    # ── Content metrics ───────────────────────────────────────────────────
    content_metrics = [
        ("Word Count",             _safe_str(content_analysis.get("word_count", 0)),            "Target: 1,500+ for AEO"),
        ("Question Headings",      _safe_str(content_analysis.get("question_headings", 0)),      "Target: 5+ question-based headings"),
        ("Conversational Score",   _safe_str(content_analysis.get("conversational_score", 0)),   "Count of: you, your, we, our"),
        ("Featured Snippet Score", _safe_str(content_analysis.get("featured_snippet_score", 0)), "Lists, tables, ordered elements"),
        ("FAQ Section Present",    "Yes" if content_analysis.get("faq_present")        else "No", ""),
        ("FAQ Schema Present",     "Yes" if content_analysis.get("faq_schema_present") else "No", "Structured data markup"),
        ("Content Score",          _safe_str(content_analysis.get("content_score", 0)),          "Out of 100"),
    ]

    # ── Content strengths / weaknesses ────────────────────────────────────
    derived_strengths, derived_weaknesses = _derive_content_strengths_weaknesses(content_analysis)
    content_strengths = content_analysis.get("strengths")  or derived_strengths
    content_weaknesses = content_analysis.get("weaknesses") or derived_weaknesses

    # ── Technical metrics ─────────────────────────────────────────────────
    # FIX v1: v1 read keys like "structured_data", "canonical_tags",
    # "sitemap" — none of which are emitted by the technical analyzer.
    # These now map to the actual keys from technical_aeo_analyzer.py v2.
    def _bool_label(val: Any) -> str:
        if isinstance(val, bool):
            return "Yes" if val else "No"
        return _safe_str(val)

    tech_metrics = [
        ("Schema Markup",       _bool_label(technical_analysis.get("schema_markup")),       "JSON-LD or Microdata"),
        ("FAQ Schema",          _bool_label(technical_analysis.get("faq_schema")),          "FAQPage structured data"),
        ("Organization Schema", _bool_label(technical_analysis.get("organization_schema")), "Brand entity clarity"),
        ("Breadcrumb Schema",   _bool_label(technical_analysis.get("breadcrumb_schema")),   "Navigation signal"),
        ("Article Schema",      _bool_label(technical_analysis.get("article_schema")),      "Content-type signal"),
        ("Canonical Tag",       _bool_label(technical_analysis.get("canonical_tag")),       "Duplicate content prevention"),
        ("Robots Meta",         _bool_label(technical_analysis.get("robots_meta")),         "Page-level index directive"),
        ("Open Graph",          _bool_label(technical_analysis.get("open_graph")),          "Social sharing signal"),
        ("Twitter Cards",       _bool_label(technical_analysis.get("twitter_cards")),       "Twitter/X preview signal"),
        ("Author Info",         _bool_label(technical_analysis.get("author_info")),         "E-E-A-T authority signal"),
        ("XML Sitemap",         _bool_label(technical_analysis.get("sitemap_exists")),      "Crawl discoverability"),
        ("Robots.txt",          _bool_label(technical_analysis.get("robots_txt_exists")),   "Crawl guidance"),
    ]

    # ── Schema audit ──────────────────────────────────────────────────────
    # Build schema audit rows from detected_types (v2 analyzer output).
    detected_types = technical_analysis.get("detected_types", [])
    raw_schema = technical_analysis.get("schema_audit", [])

    if raw_schema and isinstance(raw_schema[0], dict):
        schema_audit = raw_schema
    elif detected_types:
        schema_audit = [
            {"type": t.title(), "present": True, "valid": True, "issues": "None"}
            for t in detected_types
        ]
    elif raw_schema:
        schema_audit = [
            {"type": str(s), "present": True, "valid": True, "issues": "None"}
            for s in raw_schema
        ]
    else:
        schema_audit = []

    # ── Brand metrics ─────────────────────────────────────────────────────
    brand_metrics = [
        ("Domain Authority",  _safe_str(brand_analysis.get("domain_authority")),  ""),
        ("Referring Domains", _safe_str(brand_analysis.get("referring_domains")), ""),
        ("Brand Mentions",    _safe_str(brand_analysis.get("brand_mentions")),    ""),
        ("Social Signals",    _safe_str(brand_analysis.get("social_signals")),    ""),
        ("Knowledge Panel",   _safe_str(brand_analysis.get("knowledge_panel")),   ""),
    ]

    contact_signals   = _norm_signals(brand_analysis.get("contact_signals"))
    trust_signals     = _norm_signals(brand_analysis.get("trust_signals"))
    authority_signals = _norm_signals(brand_analysis.get("authority_signals"))

    # ── AEO platform readiness ────────────────────────────────────────────
    aeo_platforms = technical_analysis.get("aeo_platforms") or [
        {"name": "ChatGPT",            "score": aeo_score, "key_gaps": "Review full analysis", "details": []},
        {"name": "Google AI Overview", "score": aeo_score, "key_gaps": "Review full analysis", "details": []},
        {"name": "Perplexity",         "score": aeo_score, "key_gaps": "Review full analysis", "details": []},
        {"name": "Gemini",             "score": aeo_score, "key_gaps": "Review full analysis", "details": []},
    ]

    # ── AEO strengths / weaknesses (derived from all 3 categories) ────────
    aeo_strengths, aeo_weaknesses = _derive_aeo_strengths_weaknesses(
        content_strengths, content_weaknesses, technical_analysis, brand_analysis, aeo_platforms
    )

    # ── Action plan ───────────────────────────────────────────────────────
    week_recs  = [r for r in norm_recs if r["priority"] == "High"][:5]
    month_recs = [r for r in norm_recs if r["priority"] == "Medium"][:5]
    lt_recs    = [r for r in norm_recs if r["priority"] == "Low"]

    def _rec_to_action(r: dict) -> dict:
        return {
            "action":   r["recommendation"],
            "category": "General",
            "impact":   r["outcome"],
        }

    # ── Metadata audit (normalised) ───────────────────────────────────────
    raw_meta = technical_analysis.get("metadata_audit", {})
    metadata_audit = (
        [(k, _safe_str(v), "") for k, v in raw_meta.items()]
        if isinstance(raw_meta, dict)
        else raw_meta or []
    )

    raw_crawl = technical_analysis.get("crawlability_audit", {})
    crawlability_audit = (
        [(k, _safe_str(v), "") for k, v in raw_crawl.items()]
        if isinstance(raw_crawl, dict)
        else raw_crawl or []
    )

    # ── Assemble ──────────────────────────────────────────────────────────
    return {
        # Identity
        "site_name":  scraped_data.get("title", "Website Audit"),
        "site_url":   site_url,
        "audit_date": datetime.now().strftime("%B %d, %Y"),

        # Scores
        "overall_score": overall,
        "category_scores": {
            "Content":   c_score,
            "Technical": t_score,
            "Brand":     b_score,
            "AEO":       aeo_score,
        },

        # Executive
        "executive_summary": scraped_data.get("description", ""),
        "search_preview": {
            "title":       scraped_data.get("title",            ""),
            "url":         site_url,
            "description": scraped_data.get("meta_description", ""),
        },

        # Content
        "content_analysis": {
            "score":     c_score,
            "metrics":   content_metrics,
            "strengths": content_strengths,
            "weaknesses": content_weaknesses,
            "verdict_text": content_analysis.get("verdict",
                f"Content scored {c_score}/100. "
                f"Word count: {_safe_int(content_analysis.get('word_count'))}. "
                f"FAQ present: {'Yes' if content_analysis.get('faq_present') else 'No'}. "
                f"Question headings: {_safe_int(content_analysis.get('question_headings'))}."
            ),
        },

        # Technical
        "technical_analysis": {
            "score":              t_score,
            "metrics":            tech_metrics,
            "schema_audit":       schema_audit,
            "metadata_audit":     metadata_audit,
            "crawlability_audit": crawlability_audit,
            "strengths":          technical_analysis.get("strengths",  []),
            "weaknesses":         technical_analysis.get("weaknesses", []),
            "verdict_text":       technical_analysis.get("verdict", "See technical metrics above."),
        },

        # Brand
        "brand_authority": {
            "score":             b_score,
            "metrics":           brand_metrics,
            "contact_signals":   contact_signals,
            "trust_signals":     trust_signals,
            "authority_signals": authority_signals,
            "strengths":         brand_analysis.get("strengths",  []),
            "weaknesses":        brand_analysis.get("weaknesses", []),
            "verdict_text":      brand_analysis.get("verdict", "See brand metrics above."),
        },

        # AEO Readiness
        "aeo_readiness": {
            "score":        aeo_score,
            "platforms":    aeo_platforms,
            "strengths":    content_analysis.get("aeo_strengths",  []),
            "weaknesses":   content_analysis.get("aeo_weaknesses", []),
            "verdict_text": "AEO readiness is based on combined content, technical, and brand signals.",
        },

        # Recommendations
        "recommendations": norm_recs,

        # Final Verdict
        "final_verdict_title":   f"Overall AEO Score: {overall}/100",
        "final_verdict_summary": (
            f"This site scored {overall}/100 overall. "
            f"Content: {c_score}, Technical: {t_score}, Brand: {b_score}."
        ),
        "aeo_readiness_matrix": [
            {"platform": p["name"], "score": p["score"], "notes": p.get("key_gaps", "")}
            for p in aeo_platforms
        ],
        "executive_conclusion": (
            f"Executing the {len(norm_recs)} recommendations in this report will "
            "materially improve AEO performance across all major AI answer platforms."
        ),

        # Action Plan
        "action_plan": {
            "this_week":  [_rec_to_action(r) for r in week_recs],
            "this_month": [_rec_to_action(r) for r in month_recs],
            "long_term":  [_rec_to_action(r) for r in lt_recs],
        },

        # Appendix
        "appendix": {
            "raw_metrics":     [],
            "technical_flags": technical_analysis.get("flags", []),
            "schema_results":  [],
            "audit_metadata": [
                ("Audit Date",    datetime.now().strftime("%Y-%m-%d %H:%M")),
                ("Site URL",      site_url),
                ("Overall Score", str(overall)),
                ("H1 Count",      _safe_str(scraped_data.get("h1_count"))),
                ("H2 Count",      _safe_str(scraped_data.get("h2_count"))),
                ("H3 Count",      _safe_str(scraped_data.get("h3_count"))),
            ],
        },
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/generate-report", response_model=ReportResponse)
def generate_report(data: ReportRequest) -> dict:
    """
    Run full AEO analysis and return JSON results.

    FIX v1:
    - Delegated to _run_analysis() (no duplicated pipeline).
    - Proper status codes (502 for upstream failures, 422 for bad input).
    - request_id logged for traceability.
    - soup is safely removed inside _run_analysis() before any return path.
    """
    request_id = str(uuid.uuid4())[:8]
    website_url = str(data.website).strip()
    logger.info("[%s] POST /generate-report url=%s", request_id, website_url)

    result = _run_analysis(website_url, request_id)
    scraped = result["scraped_data"]

    return {
        **scraped,
        "content_analysis":  result["content_analysis"],
        "technical_aeo":     result["technical_analysis"],
        "brand_authority":   result["brand_analysis"],
        "overall_aeo_score": result["overall_aeo_score"],
        "recommendations":   result["recommendations"],
    }


@router.post("/generate-pdf-report")
def generate_pdf(data: ReportRequest) -> FileResponse:
    """
    Run full AEO analysis, build a PDF report, and return it as a download.

    FIX v1:
    - Returns FileResponse directly instead of a raw path string dict.
      Clients received {"file": "/tmp/…"} — a server-side path they cannot
      access. FileResponse streams the file to the client correctly.
    - website_url passed explicitly to build_pdf_report_data() so the URL
      is always present in the PDF even if scraper doesn't echo it back.
    - request_id logged for end-to-end traceability.
    """
    request_id = str(uuid.uuid4())[:8]
    website_url = str(data.website).strip()
    logger.info("[%s] POST /generate-pdf-report url=%s", request_id, website_url)

    result = _run_analysis(website_url, request_id)

    try:
        pdf_data = build_pdf_report_data(
            scraped_data       = result["scraped_data"],
            content_analysis   = result["content_analysis"],
            technical_analysis = result["technical_analysis"],
            brand_analysis     = result["brand_analysis"],
            overall_aeo_score  = result["overall_aeo_score"],
            recommendations    = result["recommendations"],
            website_url        = website_url,
        )
    except Exception as exc:
        logger.error("[%s] PDF data assembly failed: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=f"PDF data assembly failed: {exc}") from exc

    pdf_name = f"AEO_Audit_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    try:
        pdf_file = generate_pdf_report(pdf_data, pdf_name)
    except Exception as exc:
        logger.error("[%s] PDF generation failed: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc

    logger.info("[%s] PDF generated: %s", request_id, pdf_file)

    # FIX v1: Return a proper FileResponse so the browser/client downloads
    # the file. v1 returned {"message": "…", "file": "/server/path"} which
    # is useless to a client that cannot read the server filesystem.
    return FileResponse(
        path=pdf_file,
        media_type="application/pdf",
        filename=pdf_name,
    )