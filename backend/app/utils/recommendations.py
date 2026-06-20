def generate_recommendations(
    content_analysis: dict,
    technical_analysis: dict
):

    recommendations = []

    if not content_analysis["faq_present"]:
        recommendations.append(
            "Add an FAQ section to improve AEO performance."
        )

    if content_analysis["question_headings"] < 5:
        recommendations.append(
            "Increase question-based headings."
        )

    if content_analysis["word_count"] < 1000:
        recommendations.append(
            "Increase content depth to at least 1000 words."
        )

    if not technical_analysis["breadcrumb_schema"]:
        recommendations.append(
            "Implement Breadcrumb schema."
        )

    if not technical_analysis["robots_meta"]:
        recommendations.append(
            "Add a robots meta tag."
        )

    if not technical_analysis["author_info"]:
        recommendations.append(
            "Add author information for E-E-A-T."
        )

    return recommendations