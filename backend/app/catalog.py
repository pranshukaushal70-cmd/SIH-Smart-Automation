"""Static vocabularies shared by the pipeline, rules and API."""

DOCUMENT_CATEGORIES = {
    "affiliation_letter": "University Affiliation Letter",
    "fire_safety_certificate": "Fire Safety NOC / Certificate",
    "occupancy_certificate": "Building Occupancy / Completion Certificate",
    "trust_registration_certificate": "Society / Trust Registration Certificate",
    "other": "Other Supporting Document",
}

# Keyword evidence used by the deterministic document classifier (weight per hit).
CLASSIFIER_KEYWORDS = {
    "affiliation_letter": {
        "affiliation": 2, "affiliated": 2, "university": 1, "academic session": 2,
        "grant of affiliation": 3, "affiliation no": 3, "registrar": 0.5, "intake": 1,
    },
    "fire_safety_certificate": {
        "fire safety": 3, "fire": 1, "no objection": 2, "fire and emergency": 3,
        "fire extinguish": 2, "fire service": 2, "evacuation": 1, "noc": 1,
    },
    "occupancy_certificate": {
        "occupancy certificate": 4, "occupancy": 2, "building completion": 3, "completion certificate": 3,
        "fit for occupation": 3, "structural": 1, "built-up area": 2, "municipal": 1,
    },
    "trust_registration_certificate": {
        "registration of societies": 4, "societies registration": 4, "society": 1.5, "trust": 1.5,
        "registered under": 2, "trust deed": 3, "registrar of societies": 3, "memorandum of association": 2,
    },
}

FIELD_LABELS = {
    "institution_name": "Institution name",
    "institution_id": "Institution identifier",
    "issue_date": "Issue date",
    "expiry_date": "Expiry / valid until",
    "issuer_name": "Issuing authority",
    "reference_number": "Certificate / reference no.",
    "approval_reference": "Approval / affiliation reference",
}

APPLICATION_TYPES = [
    "Extension of Approval (EoA)",
    "Approval for New Institution",
    "Increase in Intake",
    "Change of Site / Location",
    "Introduction of New Course",
]

REVIEW_ACTIONS = {
    "request_clarification": ("Clarification Requested", "Request clarification from institution"),
    "request_issuer_verification": ("Issuer Verification Pending", "Request issuer verification (simulated)"),
    "return_for_missing_info": ("Returned for Missing Information", "Return application for missing information"),
    "provisional_recommendation": ("Provisional Approval Recommended", "Record provisional approval recommendation"),
    "recommend_further_scrutiny": ("Further Scrutiny Recommended", "Recommend further scrutiny / site inspection"),
    "add_note": (None, "Add review note (no status change)"),
}

SEVERITIES = ["critical", "high", "medium", "low", "info"]
OUTCOMES = ["Missing", "Expired", "Flagged", "Review Required", "Screening Signal"]
