from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine

def anonymize_transcript(text: str):

    # Example: recognizes patterns like "892 Maple Avenue, Springfield, IL 62704"
    address_pattern = Pattern(
        name="us_address_pattern",
        regex=r"\b\d{1,6}\s+[A-Z][a-zA-Z]+\s(?:[A-Z][a-zA-Z]+\s)?(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Trail|Trl|Parkway|Pkwy)\b(?:,)?\s+[A-Za-z .'-]+,\s*[A-Za-z]{2}\s+\d{5}\b",
        score=0.5,  # Confidence between 0 (low) and 1 (high)
    )

    # Instantiate recognizer with entity type ADDRESS
    custom_address_recognizer = PatternRecognizer(
        supported_entity="ADDRESS",
        patterns=[address_pattern],
        supported_language="en"
    )

    text_to_analyze = text.strip()

    analyzer = AnalyzerEngine()

    # Add your custom recognizer to the registry
    analyzer.registry.add_recognizer(custom_address_recognizer)

    entities_to_detect = [
        "ADDRESS",
        "PERSON",
        "LOCATION",
        "DATE_TIME",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "US_SSN",
        "US_PASSPORT",
        "AGE",
        "MEDICAL_LICENSE",
        "CREDIT_CARD"
    ]
    
    analyzer_results = analyzer.analyze(
        text=text_to_analyze, 
        entities=entities_to_detect,
        language="en"
    )

    anonymizer = AnonymizerEngine()
    anonymized = anonymizer.anonymize(text=text_to_analyze, analyzer_results=analyzer_results)
    return anonymized.text

