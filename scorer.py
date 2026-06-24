def score_lead(lead):
    """
    Calculates a Quality Score (0 to 100) and assigns a Status.
    
    Weights:
    - Email present: +35
    - Phone present: +25
    - LinkedIn present: +25
    - Website present: +15
    """
    score = 0
    
    if lead.get("Email"):
        score += 35
    if lead.get("Phone"):
        score += 25
    if lead.get("LinkedIn"):
        score += 25
    if lead.get("Website"):
        score += 15
        
    # Status assignment based on score
    if score >= 75:
        status = "High Quality"
    elif score >= 40:
        status = "Medium Quality"
    elif score > 0:
        status = "Low Quality"
    else:
        status = "Needs Review"
        
    return {
        "quality_score": score,
        "status": status
    }
