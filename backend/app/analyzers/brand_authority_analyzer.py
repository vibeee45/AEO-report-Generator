

from bs4 import BeautifulSoup
import re


def analyze_brand_authority(soup: BeautifulSoup) -> dict:

    html = str(soup).lower()

    # ── Raw signal detection (unchanged from v1) ────────────────────────────
    about_page = bool(soup.find("a", href=lambda x: x and "about" in x.lower()))
    contact_page = bool(soup.find("a", href=lambda x: x and "contact" in x.lower()))

    email_present = bool(re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        html
    ))

    phone_present = bool(re.search(
        r"(\+?\d[\d\s\-\(\)]{8,})",
        html
    ))

    linkedin = "linkedin.com" in html
    facebook = "facebook.com" in html
    instagram = "instagram.com" in html
    twitter = "twitter.com" in html or "x.com" in html
    youtube = "youtube.com" in html

    social_count = sum([linkedin, facebook, instagram, twitter, youtube])
    # ── Organization Schema Detection ─────────────────────────────

    organization_schema = (
    '"@type":"organization"' in html
    or '"@type": "organization"' in html
    or '"@type":"localbusiness"' in html
    or '"@type": "localbusiness"' in html
)
    # ── Privacy Policy Detection ─────────────────────────────

    privacy_policy = bool(
    soup.find(
        "a",
        href=lambda x: x and "privacy" in x.lower()
    )
)
    # ── Terms & Conditions Detection ─────────────────────────────

    terms_page = bool(
    soup.find(
        "a",
        href=lambda x: x and (
            "terms" in x.lower()
            or "conditions" in x.lower()
        )
    )
)
    # ── Author Information Detection ─────────────────────────────

    author_info = False
    
# Meta author
    if soup.find("meta", attrs={"name": "author"}):
        author_info = True

# Common author patterns
    author_patterns = [
    "author",
    "written by",
    "published by",
    "byline"
]

    if any(pattern in html for pattern in author_patterns):
        author_info = True

# itemprop author
    if soup.find(attrs={"itemprop": "author"}):
        author_info = True
    # ── Score (unchanged formula: 10 pts per signal, 9 signals = 90 max) ───
    score = 0
    score += 10 if about_page else 0
    score += 10 if contact_page else 0
    score += 10 if email_present else 0
    score += 10 if phone_present else 0
    score += 10 if linkedin else 0
    score += 10 if facebook else 0
    score += 10 if instagram else 0
    score += 10 if twitter else 0
    score += 10 if youtube else 0
    score += 10 if organization_schema else 0
    score += 10 if privacy_policy else 0
    score += 10 if terms_page else 0
    score += 10 if author_info else 0
    # ── Contact signals ──────────────────────────────────────────────────────
    contact_signals = [
        {"signal": "Email Address",  "status": "Present" if email_present else "Missing",
         "notes": "Found in page content" if email_present else "No email address detected"},
        {"signal": "Phone Number",   "status": "Present" if phone_present else "Missing",
         "notes": "Found in page content" if phone_present else "No phone number detected"},
        {"signal": "Contact Page",   "status": "Present" if contact_page else "Missing",
         "notes": "Link to a contact page found" if contact_page else "No contact page link found"},
    ]

    # ── Trust signals ────────────────────────────────────────────────────────
    trust_signals = [
        {"signal": "About Page", "status": "Present" if about_page else "Missing",
         "notes": "Link to an about page found" if about_page else "No about page link found"},
        {"signal": "Social Media Presence", "status": "Present" if social_count > 0 else "Missing",
         "notes": f"{social_count} social platform(s) linked" if social_count > 0
                  else "No social media links detected"},
    ]

    # ── Authority signals (off-page; not derivable from a single page) ──────
    authority_signals = [
        {"signal": "Domain Authority",  "status": "Not Available",
         "notes": "Requires third-party SEO data (e.g. Moz, Ahrefs)"},
        {"signal": "Referring Domains", "status": "Not Available",
         "notes": "Requires backlink index data"},
        {"signal": "Knowledge Panel",   "status": "Not Available",
         "notes": "Requires Google Knowledge Graph lookup"},
    ]

    # ── Brand metrics table ───────────────────────────────────────────────────
    social_platforms = [
        name for name, present in [
            ("LinkedIn", linkedin),
            ("Facebook", facebook),
            ("Instagram", instagram),
            ("Twitter/X", twitter),
            ("YouTube", youtube),
        ] if present
    ]

    domain_authority = "Not Available (requires external SEO data)"
    referring_domains = "Not Available (requires external SEO data)"
    brand_mentions = "Not Available (requires external SEO data)"
    social_signals = f"{social_count} platform(s) linked: {', '.join(social_platforms)}" if social_count else "None detected"
    knowledge_panel = "Not Available (requires Google Knowledge Graph lookup)"

    # ── Strengths / Weaknesses ────────────────────────────────────────────────
    strengths = []
    weaknesses = []

    if about_page:
        strengths.append("About page link found — supports brand transparency")
    else:
        weaknesses.append("No about page found — add one to build brand trust")

    if contact_page:
        strengths.append("Contact page link found")
    else:
        weaknesses.append("No contact page found — add one for trust and accessibility")

    if email_present:
        strengths.append("Email address detected on page")
    else:
        weaknesses.append("No email address found on page")

    if phone_present:
        strengths.append("Phone number detected on page")
    else:
        weaknesses.append("No phone number found on page")

    if social_count > 0:
        strengths.append(f"Social media presence detected ({social_count} platform(s): {', '.join(social_platforms)})")
    else:
        weaknesses.append("No social media profiles linked — add links to build brand authority")
    if organization_schema:
        strengths.append(
        "Organization schema detected — strengthens brand entity recognition"
    )
    else:
        weaknesses.append(
        "No Organization/LocalBusiness schema found — add schema markup to improve brand authority"
    )
    if privacy_policy:
        strengths.append(
        "Privacy Policy detected — improves trust and compliance signals"
    )
    else:
        weaknesses.append(
        "No Privacy Policy found — add one to strengthen trust and transparency"
    )
    if terms_page:
        strengths.append(
        "Terms & Conditions page detected — strengthens legal and trust signals"
    )
    else:
        weaknesses.append(
        "No Terms & Conditions page found — add one to improve credibility and compliance"
    )
    if author_info:
        strengths.append(
        "Author information detected — strengthens E-E-A-T and content credibility"
    )
    else:
        weaknesses.append(
        "No author information detected — add author attribution to improve trust signals"
    )
    # Convert score to 100-point scale
    score = round((score / 130) * 100)
    # ── Verdict ────────────────────────────────────────────────────────────

    if score >= 90:
        grade, status = "A+", "EXCELLENT"

    elif score >= 80:
        grade, status = "A", "EXCELLENT"

    elif score >= 70:
        grade, status = "B", "GOOD"

    elif score >= 60:
        grade, status = "C", "AVERAGE"

    elif score >= 40:
        grade, status = "D", "POOR"
    else:
        grade, status = "F", "CRITICAL"

    verdict = (
        f"{status} — Grade {grade}. Brand authority scored {score}/100 based on "
        f"on-page trust signals (about/contact pages, contact info, social profiles). "
        f"Off-page metrics (domain authority, referring domains, knowledge panel) "
        f"require external SEO/Knowledge Graph data and are not assessed here."
    )

    return {
        # Raw flags (kept for backward compatibility / debugging)
        "about_page": about_page,
        "contact_page": contact_page,
        "email_present": email_present,
        "phone_present": phone_present,
        "linkedin": linkedin,
        "facebook": facebook,
        "instagram": instagram,
        "twitter": twitter,
        "youtube": youtube,
        "organization_schema": organization_schema,
        "privacy_policy": privacy_policy,
        "terms_page": terms_page,
        "author_info": author_info,
        # Schema expected by report.py / build_pdf_report_data()
        "brand_score": score,
        "domain_authority": domain_authority,
        "referring_domains": referring_domains,
        "brand_mentions": brand_mentions,
        "social_signals": social_signals,
        "knowledge_panel": knowledge_panel,
        "contact_signals": contact_signals,
        "trust_signals": trust_signals,
        "authority_signals": authority_signals,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "verdict": verdict,
        
    }