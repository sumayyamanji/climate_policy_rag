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

load_dotenv() # Load .env from explicit project root

# Now use absolute imports from the 'climate_tracker.climate_tracker' sub-package
from climate_tracker.climate_tracker.my_logging import get_logger
logger = get_logger(__name__)
# Note: The original script had 'from models import ...' which implies models.py is in the same directory 
# or in a directory already in sys.path. The path adjustment above makes 'climate_tracker.climate_tracker' accessible.
from climate_tracker.climate_tracker.models import Base, get_db_session, CountryPageSectionModel
from climate_tracker.climate_tracker.embedding_utils import BAAIEmbedder

def generate_embeddings(batch_size=5, max_chars=30000):
    # Get model path from environment variable, fallback to Hugging Face ID
    default_model_path = "BAAI/bge-m3"
    model_path = os.getenv("BGE_MODEL_PATH", default_model_path)
    logger.info(f"Using embedding model path: {model_path}")

    session = get_db_session(os.getenv("DATABASE_URL"))
    session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    session.commit()

    embedder = BAAIEmbedder(model_path)

    logger.info("Fetching sections without embeddings...")
    # Query CountryPageSectionModel for sections to embed
    total_to_process = session.query(CountryPageSectionModel).filter(CountryPageSectionModel.embedding == None).count()
    logger.info(f"Total sections to embed: {total_to_process}")

    processed = 0

    while True:
        # Fetch a batch of sections from CountryPageSectionModel
        sections_to_embed = session.query(CountryPageSectionModel).filter(CountryPageSectionModel.embedding == None).limit(batch_size).all()
        if not sections_to_embed:
            break

        texts, valid_sections = [], []

        for section_obj in sections_to_embed:
            if not section_obj.text_content:
                logger.warning(f"Section ID {section_obj.id} (URL: {section_obj.section_url}) has no text_content. Skipping.")
                continue
            trimmed_text = section_obj.text_content.strip()[:max_chars]
            if len(trimmed_text) < 20: # Simple check for minimal content length
                logger.warning(f"Section ID {section_obj.id} (URL: {section_obj.section_url}) text_content too short after trimming. Skipping. Content: '{trimmed_text[:50]}...'")
                continue
            texts.append(trimmed_text)
            valid_sections.append(section_obj)

        if not texts:
            logger.info("No valid texts to embed in the current batch. Checking if more sections are pending...")
            # This condition might be hit if all remaining sections in the DB are empty or too short.
            # The outer while loop will break if sections_to_embed is empty on the next fetch.
            if not session.query(CountryPageSectionModel).filter(CountryPageSectionModel.embedding == None).first():
                 logger.info("No more sections found to process at all.")
                 break # Break if truly no more sections to process are found
            continue # Continue to fetch next batch if some might still exist beyond this one

        logger.info(f"Embedding batch of {len(texts)} sections...")
        try:
            embeddings = embedder.encode_batch(texts)
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}")
            # Potentially skip this batch or implement more granular error handling if needed
            break # For now, break on batch embedding error

        for i, section_obj in enumerate(valid_sections):
            section_obj.embedding = embeddings[i].tolist()
            logger.debug(f"Generated embedding for section ID {section_obj.id} (URL: {section_obj.section_url})")

        try:
            session.commit()
            processed += len(valid_sections)
            logger.info(f"Committed embeddings for {len(valid_sections)} sections. Total processed so far: {processed}/{total_to_process}")
        except Exception as e:
            logger.error(f"Failed to commit batch of embeddings: {e}")
            session.rollback()
            # Decide if to break or continue. For now, let's break to investigate commit issues.
            break 

    logger.info("✅ Embedding generation complete for all sections.")
    session.close()

if __name__ == "__main__":
    generate_embeddings()
