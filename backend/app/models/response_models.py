from pydantic import BaseModel


class ContentBreakdown(BaseModel):
    faq: int
    questions: int
    word_count: int
    conversation: int
    snippets: int


class ContentAnalysis(BaseModel):
    faq_present: bool
    faq_schema_present: bool
    question_headings: int
    word_count: int
    conversational_score: int
    featured_snippet_score: int
    content_score: int
    content_breakdown: ContentBreakdown


class TechnicalBreakdown(BaseModel):
    schema_score: int
    crawlability: int
    social: int
    authority: int


class TechnicalAEO(BaseModel):
    schema_markup: bool
    faq_schema: bool
    organization_schema: bool
    breadcrumb_schema: bool
    canonical_tag: bool
    robots_meta: bool
    open_graph: bool
    twitter_cards: bool
    author_info: bool
    sitemap_exists: bool
    robots_txt_exists: bool

    technical_score: int
    score_breakdown: TechnicalBreakdown

class BrandAuthority(BaseModel):
    about_page: bool
    contact_page: bool
    email_present: bool
    phone_present: bool
    linkedin: bool
    facebook: bool
    instagram: bool
    twitter: bool
    youtube: bool
    brand_score: int

class ReportResponse(BaseModel):
    title: str
    meta_description: str
    h1_count: int
    h2_count: int
    h3_count: int

    content_analysis: ContentAnalysis
    technical_aeo: TechnicalAEO
    brand_authority: BrandAuthority

    overall_aeo_score: float
    recommendations: list[str]

