def score_lead(lead):
    """
    Calculates Confidence Score (1-5) and assigns Status per client requirements.

    Status logic:
    - Verified: website + email + phone all present and clean (highest trust)
    - Enriched: most fields present (score >= 4) but not full triple match
    - Partial: some fields present (score == 3)
    - Needs Review: very little found, or data quality is uncertain (score <= 2)

    Weights:
    - Email present: +35
    - Phone present: +25
    - LinkedIn present: +25
    - Website present: +15
    """
    score = 0

    has_email = bool(lead.get("Email"))
    has_phone = bool(lead.get("Phone"))
    has_linkedin = bool(lead.get("LinkedIn Company Page"))
    has_website = bool(lead.get("Official Website"))

    if has_email:
        score += 35
    if has_phone:
        score += 25
    if has_linkedin:
        score += 25
    if has_website:
        score += 15

    # Convert 0-100 to 1-5
    if score >= 85:
        quality_score = 5
    elif score >= 65:
        quality_score = 4
    elif score >= 40:
        quality_score = 3
    elif score > 0:
        quality_score = 2
    else:
        quality_score = 1

    # Status labels per client requirements
    # "Verified" = website + email + phone all confirmed present (strongest signal)
    if has_website and has_email and has_phone:
        status = "Verified"
    elif quality_score >= 4:
        status = "Enriched"
    elif quality_score == 3:
        status = "Partial"
    elif quality_score == 2:
        status = "Needs Review"
    else:
        status = "Rejected"

    return {
        "quality_score": quality_score,
        "status": status
    }