import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text
from tqdm import tqdm

# --- Path setup: START ---
# Current file is DS205-final-project-team-CPR-1/climate_tracker/climate_tracker/scripts/04_generate_embeddings.py
# We want DS205-final-project-team-CPR-1/ to be in sys.path
_project_root = Path(__file__).resolve().parents[3] # Go up 3 levels: scripts -> climate_tracker -> climate_tracker -> project_root
sys.path.insert(0, str(_project_root)) # Insert at beginning to take precedence
# --- Path setup: END ---

load_dotenv(dotenv_path=_project_root / ".env") # Load .env from explicit project root

# Now use absolute imports from the 'climate_tracker.climate_tracker' sub-package
from climate_tracker.climate_tracker.my_logging import get_logger
logger = get_logger(__name__)
# Note: The original script had 'from models import ...' which implies models.py is in the same directory 
# or in a directory already in sys.path. The path adjustment above makes 'climate_tracker.climate_tracker' accessible.
from climate_tracker.climate_tracker.models import Base, get_db_session, CountryModel
from climate_tracker.climate_tracker.embedding_utils import BAAIEmbedder

def generate_embeddings(batch_size=5, max_chars=3000):
    # Get model path from environment variable, fallback to Hugging Face ID
    default_model_path = "BAAI/bge-m3"
    model_path = os.getenv("BGE_MODEL_PATH", default_model_path)
    logger.info(f"Using embedding model path: {model_path}")

    session = get_db_session(os.getenv("DATABASE_URL"))
    session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    session.commit()

    embedder = BAAIEmbedder(model_path)

    logger.info("Fetching documents without embeddings...")
    total_to_process = session.query(CountryModel).filter(CountryModel.embedding == None).count()
    logger.info(f"Total documents to embed: {total_to_process}")

    processed = 0

    while True:
        countries = session.query(CountryModel).filter(CountryModel.embedding == None).limit(batch_size).all()
        if not countries:
            break

        texts, valid_countries = [], []

        for c in countries:
            if not c.text:
                continue
            trimmed = c.text.strip()[:max_chars]  # truncate to avoid huge memory
            if len(trimmed) < 20:
                continue
            texts.append(trimmed)
            valid_countries.append(c)

        if not texts:
            logger.warning("No valid texts to embed in this batch.")
            break

        try:
            embeddings = embedder.encode_batch(texts)
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}")
            break

        for i, country in enumerate(valid_countries):
            country.embedding = embeddings[i].tolist()

        session.commit()
        processed += len(valid_countries)
        logger.info(f"Processed {processed}/{total_to_process} countries")

    logger.info("✅ Embedding generation complete")
    session.close()

if __name__ == "__main__":
    generate_embeddings()
