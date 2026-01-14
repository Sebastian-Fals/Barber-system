from spellchecker import SpellChecker

# Initialize Spanish SpellChecker
spell = SpellChecker(language='es')

# Add our domain specific words to the dictionary so they aren't marked as wrong
DOMAIN_WORDS = [
    "hoy", "mañana", "manana", "proximo", "siguiente", "viene", 
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
    "enero", "febrero", "marzo", "abril", "mayo", "junio", 
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    "am", "pm", "a", "las", "la", "de", "del", "mediodia", "medianoche"
]
spell.word_frequency.load_words(DOMAIN_WORDS)

def correct_typos(text: str) -> str:
    """
    Uses pyspellchecker to correct typos in the text based on Spanish corpus
    plus our domain specific terms.
    Agrees to ignore words with digits (e.g. 3pm, 14:00).
    """
    words = text.lower().split()
    corrected_words = []
    
    # Pre-filter: Don't check words with digits
    words_to_check = [w for w in words if not any(c.isdigit() for c in w)]
    
    # Identify misspelled words (only from candidates)
    misspelled = spell.unknown(words_to_check)
    
    for word in words:
        # Skip if digit (e.g. 3pm) or punctuation only
        if any(c.isdigit() for c in word):
             corrected_words.append(word)
             continue

        if word in misspelled:
            # Get the one most likely correction
            correction = spell.correction(word)
            if correction:
                print(f"DEBUG: AI Correction '{word}' -> '{correction}'")
                corrected_words.append(correction)
            else:
                corrected_words.append(word)
        else:
            corrected_words.append(word)
            
    return " ".join(corrected_words)
