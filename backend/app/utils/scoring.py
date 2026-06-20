def calculate_aeo_score(
    content_score: int,
    technical_score: int,
    brand_score: int
) -> float:

    score = (
        content_score * 0.3 +
        technical_score * 0.4 +
        brand_score * 0.3
    )

    return round(score, 2)