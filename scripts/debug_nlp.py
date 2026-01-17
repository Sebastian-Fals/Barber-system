import datetime

import dateparser

from app.utils.nlp import correct_typos

test_phrases = ["hoy a las 3pm", "hoy a las 2pm", "mañana a las 10am", "el viernes por la tarde", "2026-01-20"]

print("--- Testing correct_typos ---")
for phrase in test_phrases:
    corrected = correct_typos(phrase)
    print(f"Original: '{phrase}' -> Corrected: '{corrected}'")

    settings = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": datetime.datetime.now(),
        "DATE_ORDER": "DMY",
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    parsed = dateparser.parse(corrected, languages=["es"], settings=settings)
    print(f"Parsed: {parsed}\n")
