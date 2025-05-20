import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import nltk # For sentence tokenization (ensure it's installed and punkt is downloaded)
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --- Path setup: START ---
_project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_project_root))
# --- Path setup: END ---

load_dotenv(dotenv_path=_project_root / ".env")

from climate_tracker.climate_tracker.my_logging import get_logger
from climate_tracker.climate_tracker.models import get_db_session, CountryModel
from climate_tracker.climate_tracker.embedding_utils import BAAIEmbedder

logger = get_logger(__name__)

PREDEFINED_QUESTIONS = [
    "Does the country have a net zero target, and if so, what year is the target set for?",
    "Does the country have a multi-sector climate strategy that sets quantified sector-specific emission targets or projections for key sectors like Electricity, Transport, Industry, LULUCF/Agriculture, and any other fifth sector with significant emissions?",
    "Does the country have an energy efficiency law or a strategic framework for national energy efficiency, AND has it set an energy efficiency target (economy-wide or sectoral)?",
    "Has the country set a net zero electricity target aligned with 1.5°C (e.g., by 2035 for high-income, 2040 for China, 2045 for rest of world), or an equivalent economy-wide net zero commitment?",
    "Does the country have a carbon pricing mechanism in place (e.g., carbon tax or emissions trading system)?"
]

def chunk_text(text, chunk_size=3, overlap=1):
    """Splits text into sentences and then groups them into overlapping chunks."""
    if not text:
        return []
    try:
        nltk.data.find('tokenizers/punkt')
    except nltk.downloader.DownloadError:
        logger.info("NLTK 'punkt' tokenizer not found. Downloading...")
        nltk.download('punkt', quiet=True)
    
    sentences = nltk.sent_tokenize(text)
    if not sentences:
        return []

    chunks = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(sentences), step):
        chunk = " ".join(sentences[i:i + chunk_size])
        chunks.append(chunk)
    return [c for c in chunks if c.strip()]

def retrieve_and_format_answers(output_dir_name="retrieved_country_reports"):
    logger.info("Starting information retrieval process...")
    
    # Create the output directory if it doesn't exist
    output_path = _project_root / output_dir_name
    output_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output will be saved to directory: {output_path}")

    model_path = os.getenv("BGE_MODEL_PATH", "BAAI/bge-m3")
    embedder = BAAIEmbedder(model_path)
    logger.info(f"Initialized embedder with model: {model_path}")
    
    db_session = get_db_session(os.getenv("DATABASE_URL"))
    # To run on all countries with text:
    countries = db_session.query(CountryModel).filter(CountryModel.text != None, CountryModel.text != "").all()
    # For faster testing, use a doc_id that exists in your database (e.g., from the previous run):
    # countries = db_session.query(CountryModel).filter(CountryModel.doc_id == 'argentina.json').all()
    # Or process a small number of entries that have text:
    # countries = db_session.query(CountryModel).filter(CountryModel.text != None, CountryModel.text != "").limit(3).all()
    logger.info(f"Fetched {len(countries)} countries for processing.")

    all_markdown_outputs = [] # This will no longer be used to store all content

    for country_data in countries:
        logger.info(f"Processing country: {country_data.country} ({country_data.doc_id})")
        country_markdown_parts = [f"## Country: {country_data.country}\n\n---\n"]
        
        if not country_data.text or not country_data.text.strip():
            logger.warning(f"No text content for {country_data.country}, skipping questions.")
            country_markdown_parts.append("\n*No text content found in database for this country.*\n\n---\n")
            # Write this country's minimal report
            country_file_name = f"{country_data.doc_id.replace('.', '_')}_report.md"
            country_file_path = output_path / country_file_name
            with open(country_file_path, "w", encoding="utf-8") as f:
                f.write("".join(country_markdown_parts))
            logger.info(f"Wrote report for {country_data.country} to {country_file_path}")
            continue

        text_chunks = chunk_text(country_data.text)
        if not text_chunks:
            logger.warning(f"Could not chunk text for {country_data.country} (text was: '''{country_data.text[:100].replace('\n', ' ')}...'''), skipping questions.")
            country_markdown_parts.append("\n*Text content resulted in no valid chunks.*\n\n---\n")
            # Write this country's minimal report
            country_file_name = f"{country_data.doc_id.replace('.', '_')}_report.md"
            country_file_path = output_path / country_file_name
            with open(country_file_path, "w", encoding="utf-8") as f:
                f.write("".join(country_markdown_parts))
            logger.info(f"Wrote report for {country_data.country} to {country_file_path}")
            continue
        
        logger.info(f"Embedding {len(text_chunks)} text chunks for {country_data.country}...")
        try:
            chunk_embeddings = embedder.encode_batch(text_chunks)
        except Exception as e:
            logger.error(f"Error embedding chunks for {country_data.doc_id}: {e}")
            country_markdown_parts.append(f"\n*Error embedding text chunks for this country: {e}*\n\n---\n")
            # Write this country's error report
            country_file_name = f"{country_data.doc_id.replace('.', '_')}_report.md"
            country_file_path = output_path / country_file_name
            with open(country_file_path, "w", encoding="utf-8") as f:
                f.write("".join(country_markdown_parts))
            logger.info(f"Wrote error report for {country_data.country} to {country_file_path}")
            continue
        logger.info(f"Finished embedding text chunks for {country_data.country}.")

        for i, question in enumerate(PREDEFINED_QUESTIONS):
            country_markdown_parts.append(f"### Question {i+1}: {question}\n\n")
            
            try:
                question_embedding = embedder.encode_batch([question])[0]
            except Exception as e:
                logger.error(f"Error embedding question '''{question[:50].replace('\n', ' ')}...''': {e}")
                country_markdown_parts.append(f"\n*Error embedding question: {e}*\n\n---\n")
                continue # Continue to next question for this country

            similarities = cosine_similarity(question_embedding.reshape(1, -1), chunk_embeddings)
            best_chunk_index = np.argmax(similarities)
            best_score = similarities[0, best_chunk_index]
            best_chunk_text_original = text_chunks[best_chunk_index]
            
            logger.debug(f"Q: '{question[:50].replace('\\n', ' ')}...' - Best chunk score for {country_data.doc_id}: {best_score:.4f}")

            country_markdown_parts.append(f"**Answer/Evidence (Similarity: {best_score:.4f}):**\n")
            # Prepare text for Markdown blockquote: escape backticks and ensure single line for the blockquote marker
            escaped_chunk_text = best_chunk_text_original.replace('`', '\\`').replace('\n', ' ')
            country_markdown_parts.append(f"> {escaped_chunk_text}\n\n")
            country_markdown_parts.append(f"**Source URL:** [{country_data.url}]({country_data.url})\n\n---\n")

        # Write the complete markdown for this country to its own file
        country_file_name = f"{country_data.doc_id.replace('.', '_')}_report.md"
        country_file_path = output_path / country_file_name
        with open(country_file_path, "w", encoding="utf-8") as f:
            f.write("".join(country_markdown_parts))
        logger.info(f"Wrote report for {country_data.country} to {country_file_path}")

    logger.info(f"✅ Information retrieval process complete. Reports saved in {output_path}")
    db_session.close()

if __name__ == "__main__":
    retrieve_and_format_answers() 