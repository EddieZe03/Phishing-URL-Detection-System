"""Output Handler Module for phishing detection inference results.

Responsibilities:
- Format prediction output for presentation
- Assign risk level based on label/confidence
- Generate actionable recommendations
"""

from __future__ import annotations


def _risk_level(label: str, confidence_percent: float) -> str:
    if label == "Uncertain":
        return "Needs Manual Review"

    if label == "Phishing":
        if confidence_percent >= 90:
            return "Critical"
        if confidence_percent >= 75:
            return "High"
        return "Medium"

    if confidence_percent >= 90:
        return "Low"
    return "Medium-Low"


def _create_user_friendly_rule_summary(technical_reason: str) -> str:
    """Convert technical override explanation to user-friendly warning."""
    reason_lower = technical_reason.lower()
    
    # Map technical descriptions to user-friendly summaries
    if "wp-admin" in reason_lower or "wp-includes" in reason_lower or "wordpress" in reason_lower:
        return "⚠️ Suspicious WordPress admin/login pattern detected. This domain is being abused to host fake login pages."
    
    if "brand-impersonation" in reason_lower or "brand token" in reason_lower:
        return "⚠️ Brand impersonation detected. This URL contains a legitimate brand name in the path but uses a different domain - classic phishing tactic."
    
    if "php" in reason_lower and "endpoint" in reason_lower:
        return "⚠️ Suspicious PHP script detected on a new/unknown domain. This is a common hosting method for phishing payloads."
    
    if "embedded-domain" in reason_lower or "domain pattern" in reason_lower:
        return "⚠️ Embedded domain pattern detected. This URL masks another domain name in its path - likely credential harvesting attempt."
    
    if "high-risk structural" in reason_lower:
        return "⚠️ High-risk URL structure detected. This domain shows suspicious characteristics combined with phishing-like path patterns."
    
    if "ip-host" in reason_lower or "ip address" in reason_lower:
        return "⚠️ IP-based domain with suspicious content detected. Phishers use IP addresses to bypass domain reputation checks."
    
    if "mail-stack" in reason_lower or "zimbra" in reason_lower or "owa" in reason_lower:
        return "⚠️ Mail server phishing pattern detected. This URL mimics corporate email system paths (Zimbra/Outlook/Exchange)."
    
    if "hosted-form" in reason_lower:
        return "⚠️ Hosted phishing form detected. This uses a legitimate service (Google Forms) to harvest credentials."
    
    if "suspicious-tld" in reason_lower:
        return "⚠️ Suspicious domain extension (.tk, .ml, etc.) combined with phishing keywords - common in low-cost phishing campaigns."
    
    # Fallback for any other override
    if "override" in reason_lower:
        return "⚠️ Security rule triggered: Multiple phishing indicators detected. Treat this URL as unsafe."
    
    return ""


def _recommendations(label: str, risk_level: str) -> list[str]:
    if label == "Uncertain":
        return [
            "Result is borderline. Treat with caution and verify manually.",
            "Open the destination only through official channels or trusted bookmarks.",
            "Do not submit credentials or payment details until verified.",
        ]

    if label == "Phishing":
        return [
            "Do not click or open the URL.",
            "Do not enter credentials or payment details.",
            "Verify the sender/domain through official channels.",
            "Report the URL to your security/admin team.",
        ]

    if risk_level == "Medium-Low":
        return [
            "Likely safe, but still verify the domain carefully.",
            "Prefer typing the official website directly.",
        ]

    return [
        "URL appears legitimate.",
        "Continue normal browsing with standard precautions.",
    ]


def format_output(label: str, phishing_probability: float, explanation: str) -> dict[str, object]:
    """Create a UI-ready output payload from raw model output."""
    if label == "Phishing":
        confidence = phishing_probability
    elif label == "Legitimate":
        confidence = 1.0 - phishing_probability
    else:
        # For uncertain outcomes, confidence reflects uncertainty distance from 50%.
        confidence = 1.0 - (abs(phishing_probability - 0.5) * 2.0)

    confidence_percent = max(0.0, min(confidence * 100.0, 100.0))
    risk_level = _risk_level(label, confidence_percent)
    explanation_text = explanation or ""
    explanation_lower = explanation_text.lower()

    # Threshold is fixed in production, so suppress this internal detail from UI.
    if explanation_lower.startswith("threshold decision"):
        explanation_text = ""

    # Create user-friendly rule summary for UI display
    rule_trigger = ""
    if "override applied" in explanation_lower:
        rule_trigger = _create_user_friendly_rule_summary(explanation)

    return {
        "result_badge": (
            "PHISHING"
            if label == "Phishing"
            else ("LEGITIMATE" if label == "Legitimate" else "UNCERTAIN")
        ),
        "result_label": label,
        "result_confidence": f"{confidence_percent:.2f}%",
        "risk_level": risk_level,
        "explanation_text": explanation_text,
        "rule_trigger": rule_trigger,
        "recommendations": _recommendations(label, risk_level),
    }
