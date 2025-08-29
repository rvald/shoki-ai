import json, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transcribe")

def jlog(**kw):
    logger.info(json.dumps(kw, ensure_ascii=False))