"""WI-015: Human-readable HL7 field descriptions for hover tooltips.

Maps (segment_name, field_index) → description string.
Covers the most common segments from HL7 v2.x.
"""

FIELD_DESCRIPTIONS: dict[tuple[str, int], str] = {
    # MSH — Message Header
    ("MSH", 1): "Field Separator",
    ("MSH", 2): "Encoding Characters",
    ("MSH", 3): "Sending Application",
    ("MSH", 4): "Sending Facility",
    ("MSH", 5): "Receiving Application",
    ("MSH", 6): "Receiving Facility",
    ("MSH", 7): "Date/Time of Message",
    ("MSH", 8): "Security",
    ("MSH", 9): "Message Type",
    ("MSH", 10): "Message Control ID",
    ("MSH", 11): "Processing ID",
    ("MSH", 12): "Version ID",

    # PID — Patient Identification
    ("PID", 1): "Set ID",
    ("PID", 2): "Patient ID (External)",
    ("PID", 3): "Patient Identifier List",
    ("PID", 4): "Alternate Patient ID",
    ("PID", 5): "Patient Name",
    ("PID", 6): "Mother's Maiden Name",
    ("PID", 7): "Date/Time of Birth",
    ("PID", 8): "Administrative Sex",
    ("PID", 9): "Patient Alias",
    ("PID", 10): "Race",
    ("PID", 11): "Patient Address",
    ("PID", 12): "County Code",
    ("PID", 13): "Phone Number — Home",
    ("PID", 14): "Phone Number — Business",
    ("PID", 15): "Primary Language",
    ("PID", 16): "Marital Status",
    ("PID", 17): "Religion",
    ("PID", 18): "Patient Account Number",
    ("PID", 19): "SSN / AHV Number",
    ("PID", 20): "Driver's License Number",
    ("PID", 21): "Mother's Identifier",
    ("PID", 22): "Ethnic Group",
    ("PID", 23): "Birth Place",
    ("PID", 24): "Multiple Birth Indicator",
    ("PID", 25): "Birth Order",
    ("PID", 26): "Citizenship",
    ("PID", 27): "Veterans Military Status",
    ("PID", 28): "Nationality",
    ("PID", 29): "Patient Death Date/Time",
    ("PID", 30): "Patient Death Indicator",

    # NK1 — Next of Kin
    ("NK1", 1): "Set ID",
    ("NK1", 2): "Name",
    ("NK1", 3): "Relationship",
    ("NK1", 4): "Address",
    ("NK1", 5): "Phone Number",
    ("NK1", 6): "Business Phone Number",
    ("NK1", 7): "Contact Role",
    ("NK1", 30): "Contact Person's Name",
    ("NK1", 31): "Contact Person's Phone",
    ("NK1", 32): "Contact Person's Address",

    # PV1 — Patient Visit
    ("PV1", 1): "Set ID",
    ("PV1", 2): "Patient Class",
    ("PV1", 3): "Assigned Patient Location",
    ("PV1", 4): "Admission Type",
    ("PV1", 7): "Attending Doctor",
    ("PV1", 8): "Referring Doctor",
    ("PV1", 9): "Consulting Doctor",
    ("PV1", 10): "Hospital Service",
    ("PV1", 14): "Admit Source",
    ("PV1", 17): "Admitting Doctor",
    ("PV1", 19): "Visit Number",
    ("PV1", 44): "Admit Date/Time",
    ("PV1", 45): "Discharge Date/Time",
    ("PV1", 50): "Alternate Visit ID",
    ("PV1", 52): "Other Healthcare Provider",

    # PV2 — Patient Visit (Additional)
    ("PV2", 13): "Referral Source Code",

    # IN1 — Insurance
    ("IN1", 1): "Set ID",
    ("IN1", 2): "Insurance Plan ID",
    ("IN1", 3): "Insurance Company ID",
    ("IN1", 4): "Insurance Company Name",
    ("IN1", 5): "Insurance Company Address",
    ("IN1", 16): "Name of Insured",
    ("IN1", 19): "Insured's Address",
    ("IN1", 36): "Policy Number",
    ("IN1", 49): "Insured's ID Number",

    # GT1 — Guarantor
    ("GT1", 1): "Set ID",
    ("GT1", 3): "Guarantor Name",
    ("GT1", 5): "Guarantor Address",
    ("GT1", 6): "Guarantor Phone — Home",
    ("GT1", 7): "Guarantor Phone — Business",
    ("GT1", 16): "Guarantor Employer Name",
    ("GT1", 17): "Guarantor Employer Address",
    ("GT1", 18): "Guarantor Employer Phone",

    # OBR — Observation Request
    ("OBR", 2): "Placer Order Number",
    ("OBR", 3): "Filler Order Number",
    ("OBR", 4): "Universal Service Identifier",
    ("OBR", 7): "Observation Date/Time",
    ("OBR", 10): "Collector Identifier",
    ("OBR", 16): "Ordering Provider",
    ("OBR", 28): "Result Copies To",

    # OBX — Observation/Result
    ("OBX", 2): "Value Type",
    ("OBX", 3): "Observation Identifier",
    ("OBX", 5): "Observation Value",
    ("OBX", 11): "Observation Result Status",
    ("OBX", 14): "Date/Time of Observation",
    ("OBX", 16): "Responsible Observer",

    # ORC — Common Order
    ("ORC", 1): "Order Control",
    ("ORC", 2): "Placer Order Number",
    ("ORC", 3): "Filler Order Number",
    ("ORC", 12): "Ordering Provider",
    ("ORC", 19): "Action By",

    # NTE — Notes and Comments
    ("NTE", 1): "Set ID",
    ("NTE", 2): "Source of Comment",
    ("NTE", 3): "Comment",

    # DG1 — Diagnosis
    ("DG1", 3): "Diagnosis Code",
    ("DG1", 4): "Diagnosis Description",
    ("DG1", 16): "Diagnosing Clinician",

    # AL1 — Allergy
    ("AL1", 2): "Allergen Type Code",
    ("AL1", 3): "Allergen Code",
    ("AL1", 5): "Allergy Reaction Code",
    ("AL1", 6): "Identification Date",
}


def get_field_tooltip(segment_name: str, field_index: int) -> str:
    """Build tooltip string for a field: 'SEG.N — Description' or just 'SEG.N'."""
    path = f"{segment_name}.{field_index}"
    desc = FIELD_DESCRIPTIONS.get((segment_name, field_index))
    if desc:
        return f"{path} — {desc}"
    return path
