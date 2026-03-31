"""WI-004: PII field definitions from Requirements Section 4.

DEFAULT_PII_FIELDS: set of (segment_name, field_index) tuples that should be
auto-preselected (Amber) when valid HL7 is detected.

These are the "Kernfelder" from Section 4.1 of the requirements.
"""

# Section 4.1 — Kernfelder (Default vorselektiert bei erkanntem HL7)

# PID – Patient Identification
_PID_FIELDS = {
    2,   # Patient ID External
    3,   # Patient Identifier List
    4,   # Alternate Patient ID
    5,   # Patient Name
    6,   # Mother's Maiden Name
    7,   # Date/Time of Birth
    9,   # Patient Alias
    11,  # Patient Address
    12,  # County Code
    13,  # Phone Number Home
    14,  # Phone Number Business
    18,  # Patient Account Number
    19,  # SSN / AHV
    20,  # Driver's License
    21,  # Mother's Identifier
    23,  # Birth Place
    26,  # Citizenship
    28,  # Nationality
    29,  # Death Date/Time
}

# NK1 – Next of Kin
_NK1_FIELDS = {
    2,   # Name
    4,   # Address
    5,   # Phone
    6,   # Business Phone
    30,  # Contact Person Name
    31,  # Contact Person Phone
    32,  # Contact Person Address
}

# PV1 – Patient Visit
_PV1_FIELDS = {
    7,   # Attending Doctor
    8,   # Referring Doctor
    9,   # Consulting Doctor
    17,  # Admitting Doctor
    19,  # Visit Number
    50,  # Alternate Visit ID
    52,  # Other Healthcare Provider
}

# PV2
_PV2_FIELDS = {
    13,  # Referral Source
}

# IN1 – Insurance
_IN1_FIELDS = {
    2,   # Plan ID
    3,   # Company ID
    4,   # Company Name
    5,   # Company Address
    16,  # Name of Insured
    19,  # Insured's Address
    36,  # Policy Number
    49,  # Insured's ID
}

# GT1 – Guarantor
_GT1_FIELDS = {
    3,   # Name
    5,   # Address
    6,   # Phone Home
    7,   # Phone Business
    16,  # Employer Name
    17,  # Employer Address
    18,  # Employer Phone
}

# Combined: set of (segment_name, field_index)
DEFAULT_PII_FIELDS: set[tuple[str, int]] = set()

for _idx in _PID_FIELDS:
    DEFAULT_PII_FIELDS.add(("PID", _idx))
for _idx in _NK1_FIELDS:
    DEFAULT_PII_FIELDS.add(("NK1", _idx))
for _idx in _PV1_FIELDS:
    DEFAULT_PII_FIELDS.add(("PV1", _idx))
for _idx in _PV2_FIELDS:
    DEFAULT_PII_FIELDS.add(("PV2", _idx))
for _idx in _IN1_FIELDS:
    DEFAULT_PII_FIELDS.add(("IN1", _idx))
for _idx in _GT1_FIELDS:
    DEFAULT_PII_FIELDS.add(("GT1", _idx))
