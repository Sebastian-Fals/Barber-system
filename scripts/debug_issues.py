from datetime import datetime

import dateparser

from app.utils.nlp import correct_typos

print("--- Testing Time Parsing ---")
dates_to_test = ["12am", "12pm", "1pm", "2pm", "14:00", "Una de la tarde"]
base_date = "2026-01-14"

for t in dates_to_test:
    dummy = f"{base_date} {t}"
    print(f"Input: '{dummy}'")
    try:
        # Pyspellchecker might mess up "12am" if it thinks it's a typo?
        corrected = correct_typos(t)
        print(f"  Corrected: '{corrected}'")

        parsed = dateparser.parse(f"{base_date} {corrected}")
        print(f"  Parsed: {parsed}")
    except Exception as e:
        print(f"  Error: {e}")

print("\n--- Testing Barber Matching ---")
barbers_db = ["Alejandro", "Sebastian", "Roberto"]
user_inputs = ["alejandro", "Alejo", "quiero con sebastian", "el primero"]

from fuzzywuzzy import process  # If installed, otherwise we implement simple Match

for i in user_inputs:
    print(f"User Input: '{i}'")
    # Simple check
    match = None
    for b in barbers_db:
        if b.lower() in i.lower():
            match = b
    print(f"  Simple Match: {match}")
