import math

def calculate_squeeze_metrics(btc_price, gex_profile, net_gamma, gamma_flip):
    """
    Calculates Gamma Squeeze risk metrics based on Deribit GEX profile.
    
    Args:
        btc_price (float): Current BTC spot price
        gex_profile (list of dict): List of {"strike": S, "gex": GEX_in_BTC} sorted by strike
        net_gamma (float): Total Net Market Gamma
        gamma_flip (float): Price where gamma flips from negative to positive
        
    Returns:
        dict: Squeeze risk metrics
    """
    
    # 1. Spot-to-Flip Distance (%)
    if gamma_flip > 0:
        spot_to_flip_pct = ((btc_price - gamma_flip) / gamma_flip) * 100
    else:
        spot_to_flip_pct = 0.0

    # 2. Short Gamma Density (concentration of negative gamma immediately above spot)
    # Look at strikes up to 10% above spot price
    upper_bound = btc_price * 1.10
    short_gamma_density = 0.0
    for item in gex_profile:
        strike = item["strike"]
        gex = item["gex"]
        
        # We only care about negative gamma above the spot price
        if btc_price <= strike <= upper_bound and gex < 0:
            short_gamma_density += abs(gex)
            
    # 3. Squeeze Risk Score (0 - 100)
    # The score is high when:
    # - Net Gamma is deeply negative
    # - We are far above the Gamma Flip point
    # - There is a huge wall of short gamma immediately above us
    
    score = 0.0
    
    # Base risk from Net Gamma
    if net_gamma < 0:
        score += min(30, abs(net_gamma) / 50.0) # Up to 30 points for raw negative gamma
        
    # Risk from being above flip
    if spot_to_flip_pct > 0:
        score += min(30, spot_to_flip_pct * 3) # e.g. 10% above flip = 30 points
        
    # Risk from immediate short gamma density above us
    if short_gamma_density > 0:
        score += min(40, short_gamma_density / 20.0) # e.g. 800 BTC of short gamma nearby = 40 points
        
    # Cap at 100
    risk_score = max(0, min(100, score))
    
    # Define Squeeze Threat Level
    if risk_score >= 80:
        threat_level = "CRITICAL (Imminent Squeeze Risk)"
    elif risk_score >= 60:
        threat_level = "HIGH (Elevated Squeeze Potential)"
    elif risk_score >= 40:
        threat_level = "MODERATE (Some Short Gamma Walls)"
    else:
        threat_level = "LOW (Dealers Long Gamma)"

    return {
        "spotToFlipPct": round(spot_to_flip_pct, 2),
        "shortGammaDensityBtc": round(short_gamma_density, 2),
        "squeezeRiskScore": round(risk_score, 1),
        "threatLevel": threat_level
    }
