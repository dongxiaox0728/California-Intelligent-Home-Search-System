from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass(frozen=True)
class CompliancePattern:
    category: str
    label: str
    regex: str
    severity: str
    message: str


class ComplianceChecker:
    """
    Rule-based Fair Housing advertising compliance checker.

    Screening design:
    - "error": explicit discriminatory preference/exclusion language
    - "warning": context-sensitive language that should be reviewed
    - "info": reserved for future informational checks

    Notes:
    - This is a screening/educational component, not legal advice.
    - HUD Part 109 treats listed words/phrases as contextual indicators
      of possible discriminatory advertising, not a complete automatic blacklist.
    """

    SEVERITY_ORDER = {"info": 1, "warning": 2, "error": 3}

    def __init__(self) -> None:
        self.patterns = self._build_patterns()

    @staticmethod
    def _build_patterns() -> List[CompliancePattern]:
        P = CompliancePattern
        return [
            # Familial status
            P("familial_status", "no children", r"\bno\s+children\b", "error",
              "Potential familial-status discrimination."),
            P("familial_status", "adults only", r"\badults?\s+only\b", "error",
              "Potential familial-status discrimination."),
            P("familial_status", "adult only", r"\badult[-\s]+only\b", "error",
              "Potential familial-status discrimination."),
            P("familial_status", "adult building", r"\badult\s+building\b", "warning",
              "HUD-style indicator that may imply a familial-status limitation."),
            P("familial_status", "no families", r"\bno\s+famil(?:y|ies)\b", "error",
              "Potential familial-status discrimination."),
            P("familial_status", "families not allowed",
              r"\bfamil(?:y|ies)\s+(?:are\s+)?not\s+allowed\b", "error",
              "Potential familial-status discrimination."),
            P("familial_status", "singles only", r"\bsingles?\s+only\b", "error",
              "Potential preference based on familial status."),
            P("familial_status", "perfect for singles", r"\bperfect\s+for\s+singles?\b", "warning",
              "Potential familial-status preference; review context."),
            P("familial_status", "one or two adults", r"\bone\s+or\s+two\s+adults?\b", "warning",
              "Potential limitation affecting families with children; review context."),
            P("familial_status", "children not permitted",
              r"\bchildren\s+(?:are\s+)?not\s+(?:permitted|allowed)\b", "error",
              "Potential familial-status discrimination."),

            # Disability
            P("disability", "no wheelchairs", r"\bno\s+wheelchairs?\b", "error",
              "Potential disability discrimination."),
            P("disability", "must be able-bodied", r"\bmust\s+be\s+able[-\s]?bodied\b", "error",
              "Potential disability discrimination."),
            P("disability", "able-bodied only", r"\bable[-\s]?bodied\s+only\b", "error",
              "Potential disability discrimination."),
            P("disability", "no disabled persons",
              r"\bno\s+(?:disabled|handicapped)\s+(?:persons?|people|tenants?|renters?)\b", "error",
              "Potential disability discrimination."),
            P("disability", "disabled not allowed",
              r"\b(?:disabled|handicapped)\s+(?:persons?\s+)?(?:are\s+)?not\s+allowed\b", "error",
              "Potential disability discrimination."),
            P("disability", "no service animals", r"\bno\s+service\s+animals?\b", "warning",
              "May conflict with disability accommodation requirements; review context."),
            P("disability", "no assistance animals", r"\bno\s+assistance\s+animals?\b", "warning",
              "May conflict with disability accommodation requirements; review context."),

            # Religion
            P("religion", "Jewish home", r"\bjewish\s+home\b", "warning",
              "HUD-style religious descriptor that should be reviewed in context."),
            P("religion", "Christians only", r"\bchristians?\s+only\b", "error",
              "Potential religious preference."),
            P("religion", "Christian preferred", r"\bchristians?\s+(?:preferred|preference)\b", "error",
              "Potential religious preference."),
            P("religion", "Catholics only", r"\bcatholics?\s+only\b", "error",
              "Potential religious preference."),
            P("religion", "Jewish only", r"\bjewish\s+(?:persons?\s+)?only\b", "error",
              "Potential religious preference."),
            P("religion", "Muslims only", r"\bmuslims?\s+only\b", "error",
              "Potential religious preference."),
            P("religion", "no Muslims", r"\bno\s+muslims?\b", "error",
              "Potential religious exclusion."),
            P("religion", "no Christians", r"\bno\s+christians?\b", "error",
              "Potential religious exclusion."),

            # Race / color
            P("race_color", "white private home", r"\bwhite\s+private\s+home\b", "warning",
              "HUD lists this type of wording as a possible discriminatory indicator."),
            P("race_color", "colored home", r"\bcolored\s+home\b", "warning",
              "HUD lists this type of wording as a possible discriminatory indicator."),
            P("race_color", "white only", r"\bwhite\s+(?:persons?\s+)?only\b", "error",
              "Potential race/color discrimination."),
            P("race_color", "Black only", r"\bblack\s+(?:persons?\s+)?only\b", "error",
              "Potential race/color discrimination."),
            P("race_color", "no Black people",
              r"\bno\s+black\s+(?:persons?|people|tenants?|renters?|families)\b", "error",
              "Potential race/color discrimination."),
            P("race_color", "Caucasian only", r"\bcaucasians?\s+only\b", "error",
              "Potential race discrimination."),
            P("race_color", "Asian only", r"\basians?\s+only\b", "error",
              "Potential race/national-origin discrimination."),
            P("race_color", "no Asians", r"\bno\s+asians?\b", "error",
              "Potential race/national-origin discrimination."),
            P("race_color", "American Indian only", r"\bamerican\s+indians?\s+only\b", "error",
              "Potential race discrimination."),
            P("race_color", "Native American only", r"\bnative\s+americans?\s+only\b", "error",
              "Potential race discrimination."),

            # National origin / ethnicity
            P("national_origin", "Hispanic residence", r"\bhispanic\s+residence\b", "warning",
              "HUD-style national-origin descriptor that should be reviewed in context."),
            P("national_origin", "Hispanics only", r"\bhispanics?\s+only\b", "error",
              "Potential national-origin discrimination."),
            P("national_origin", "no Hispanics", r"\bno\s+hispanics?\b", "error",
              "Potential national-origin discrimination."),
            P("national_origin", "Latinos only", r"\blatinos?\s+only\b", "error",
              "Potential national-origin discrimination."),
            P("national_origin", "Mexican American only",
              r"\bmexican[-\s]+americans?\s+only\b", "error",
              "Potential national-origin discrimination."),
            P("national_origin", "Puerto Rican only", r"\bpuerto\s+ricans?\s+only\b", "error",
              "Potential national-origin discrimination."),
            P("national_origin", "Chinese only", r"\bchinese\s+(?:persons?\s+)?only\b", "error",
              "Potential national-origin discrimination."),
            P("national_origin", "Irish only", r"\birish\s+(?:persons?\s+)?only\b", "error",
              "Potential national-origin discrimination."),
            P("national_origin", "Italian only", r"\bitalians?\s+only\b", "error",
              "Potential national-origin discrimination."),
            P("national_origin", "Polish only", r"\bpolish\s+(?:persons?\s+)?only\b", "error",
              "Potential national-origin discrimination."),

            # Sex — context-sensitive because limited exceptions can apply
            P("sex", "men only", r"\bmen\s+only\b", "warning",
              "Possible sex-based preference; review context and any applicable exception."),
            P("sex", "women only", r"\bwomen\s+only\b", "warning",
              "Possible sex-based preference; review context and any applicable exception."),
            P("sex", "males only", r"\bmales?\s+only\b", "warning",
              "Possible sex-based preference; review context and any applicable exception."),
            P("sex", "females only", r"\bfemales?\s+only\b", "warning",
              "Possible sex-based preference; review context and any applicable exception."),
            P("sex", "male preferred", r"\bmales?\s+(?:preferred|preference)\b", "warning",
              "Possible sex-based preference; review context."),
            P("sex", "female preferred", r"\bfemales?\s+(?:preferred|preference)\b", "warning",
              "Possible sex-based preference; review context."),
        ]

    def check_listing(self, text: str) -> Dict:
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        if not text.strip():
            return {
                "compliant": True,
                "needs_review": False,
                "highest_severity": None,
                "violations": [],
                "counts": {"error": 0, "warning": 0, "info": 0},
            }

        violations = []

        for rule in self.patterns:
            for match in re.finditer(rule.regex, text, flags=re.IGNORECASE):
                violations.append({
                    **asdict(rule),
                    "matched_text": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                })

        counts = {"error": 0, "warning": 0, "info": 0}
        for violation in violations:
            counts[violation["severity"]] += 1

        highest_severity = None
        if violations:
            highest_severity = max(
                (v["severity"] for v in violations),
                key=lambda level: self.SEVERITY_ORDER[level],
            )

        return {
            "compliant": counts["error"] == 0,
            "needs_review": len(violations) > 0,
            "highest_severity": highest_severity,
            "violations": violations,
            "counts": counts,
        }

    def pattern_count(self) -> int:
        return len(self.patterns)


if __name__ == "__main__":
    checker = ComplianceChecker()

    examples = [
        "Beautiful 3-bedroom home with a renovated kitchen and large backyard.",
        "Spacious apartment. No children allowed.",
        "Updated unit. Christians preferred.",
        "Wheelchair accessible entrance and first-floor bedroom.",
        "Women only.",
        "No service animals.",
    ]

    print(f"Loaded {checker.pattern_count()} compliance patterns.\n")

    for text in examples:
        result = checker.check_listing(text)

        print("TEXT:", text)
        print("COMPLIANT:", result["compliant"])
        print("NEEDS REVIEW:", result["needs_review"])
        print("HIGHEST SEVERITY:", result["highest_severity"])
        print("COUNTS:", result["counts"])

        for violation in result["violations"]:
            print(
                f'  - [{violation["severity"]}] '
                f'{violation["category"]}: '
                f'{violation["matched_text"]}'
            )

        print()
