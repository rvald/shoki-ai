import hashlib
from typing import Dict, List, Optional

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerResult
from presidio_anonymizer import AnonymizerEngine

from .exceptions import RetryableError, PermanentError
from .logging import jlog
from .schemas import RedactRequest, RedactResponse, RedactionSummary
from .storage import download_blob, save_artifact

# Global engines (load once per instance)
_ANALYZER: Optional[AnalyzerEngine] = None
_ANONYMIZER: Optional[AnonymizerEngine] = None

# Salt for deterministic masking (configure via env)
import os
REDACTION_SALT = os.getenv("REDACTION_SALT", "dev-salt-change-in-prod")

def _init_engines():
    global _ANALYZER, _ANONYMIZER
    if _ANALYZER is None:
        _ANALYZER = AnalyzerEngine()
        # Custom US address recognizer to improve detection
        address_pattern = Pattern(
            name="us_address_pattern",
            regex=r"\b\d{1,6}\s+[A-Z][a-zA-Z]+\s(?:[A-Z][a-zA-Z]+\s)?(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Trail|Trl|Parkway|Pkwy)\b(?:,)?\s+[A-Za-z .'-]+,\s*[A-Za-z]{2}\s+\d{5}\b",
            score=0.5,
        )
        custom_address = PatternRecognizer(
            supported_entity="ADDRESS", patterns=[address_pattern], supported_language="en"
        )
        _ANALYZER.registry.add_recognizer(custom_address)
    if _ANONYMIZER is None:
        _ANONYMIZER = AnonymizerEngine()

def _deterministic_token(entity_type: str, raw_text: str) -> str:
    digest = hashlib.sha256((REDACTION_SALT + raw_text).encode("utf-8")).hexdigest()[:8]
    return f"[{entity_type}_{digest}]"

def _apply_deterministic_mask(text: str, results: List[RecognizerResult]) -> str:
    ordered = sorted(results, key=lambda r: (r.start, r.end))
    out = []
    cursor = 0
    for r in ordered:
        if r.start is None or r.end is None:
            continue
        start, end = int(r.start), int(r.end)
        if start < cursor:  # overlap; skip inner
            continue
        out.append(text[cursor:start])
        span = text[start:end]
        out.append(_deterministic_token(r.entity_type, span))
        cursor = end
    out.append(text[cursor:])
    return "".join(out)

def _entity_counts(results: List[RecognizerResult]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in results:
        counts[r.entity_type] = counts.get(r.entity_type, 0) + 1
    return counts

def redact_with_idempotency(
    req: RedactRequest, correlation_id: Optional[str], idempotency_key: Optional[str]
) -> RedactResponse:
    jlog(event="redact_start", correlation_id=correlation_id, idempotency_key=req.idem_key, bucket=req.bucket)

    if not req.idem_key or not req.bucket:
        raise PermanentError("Empty idempotency key or bucket")

    try:
        # Load prior step artifact (transcription) from artifact bucket keyed by idem_key
        transcript_obj = download_blob(req.bucket, req.idem_key)
        # Expect TranscriptionResponse-like structure
        transcription = transcript_obj.get("transcription", {})
        text = transcription.get("text", "")
        if not text:
            raise PermanentError("Empty transcript text")

        _init_engines()

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
            "CREDIT_CARD",
        ]
        results = _ANALYZER.analyze(text=text, entities=entities_to_detect, language=req.language or "en")  # type: ignore

        if req.stable_masking:
            redacted_text = _apply_deterministic_mask(text, results)
        else:
            redacted_text = _ANONYMIZER.anonymize(text=text, analyzer_results=results).text  # type: ignore

        summary = RedactionSummary(entities=_entity_counts(results), total=len(results), policy=req.policy)
        resp = RedactResponse(text=redacted_text, summary=summary)

        # Persist artifact keyed by idem_key for downstream reuse
        save_artifact(idempotency_key, resp)

        jlog(
            event="redact_ok",
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            text_len=len(text),
            entities=summary.entities,
            total=summary.total,
        )
        return resp

    except RetryableError:
        # Keep pathway if you later depend on external services
        raise
    except Exception as e:
        # Default to permanent; refine if you add retryable dependencies
        raise PermanentError(f"redaction failure: {e}") from e