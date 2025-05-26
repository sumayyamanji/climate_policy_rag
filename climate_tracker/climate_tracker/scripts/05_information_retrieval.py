import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import nltk # Reinstated for chunking
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --- Path setup: START ---
_project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_project_root))
# --- Path setup: END ---

load_dotenv()

from climate_tracker.my_logging import get_logger
# Import both CountryModel (for countries_v2) and CountryPageSectionModel (for country_page_sections_v2)
from climate_tracker.models import get_db_session, CountryModel, CountryPageSectionModel 
from climate_tracker.embedding_utils import BAAIEmbedder

logger = get_logger(__name__)

PREDEFINED_QUESTIONS = [
    "Does the country have a net zero target, and if so, what year is the target set for?",
    "Does the country have a multi-sector climate strategy that sets quantified sector-specific emission targets or projections for key sectors like Electricity, Transport, Industry, LULUCF/Agriculture, and any other fifth sector with significant emissions?",
    "Does the country have an energy efficiency law or a strategic framework for national energy efficiency, AND has it set an energy efficiency target (economy-wide or sectoral)?",
    "Has the country set a net zero electricity target aligned with 1.5°C (e.g., by 2035 for high-income, 2040 for China, 2045 for rest of world), or an equivalent economy-wide net zero commitment?",
    "Does the country have a carbon pricing mechanism in place (e.g., carbon tax or emissions trading system)?"
]

# Reinstated chunk_text function
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
    step = max(1, chunk_size - overlap) # Ensure step is at least 1
    for i in range(0, len(sentences), step):
        chunk = " ".join(sentences[i:i + chunk_size])
        chunks.append(chunk)
    return [c for c in chunks if c.strip()]

def retrieve_and_format_answers(output_dir_name="retrieved_country_reports_v2_chunked"): # New output dir
    logger.info("Starting information retrieval process (chunking sections, on-the-fly chunk embeddings)...")
    
    output_path = _project_root / output_dir_name
    output_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output will be saved to directory: {output_path}")

    model_path = os.getenv("BGE_MODEL_PATH", "BAAI/bge-m3")
    embedder = BAAIEmbedder(model_path) 
    logger.info(f"Initialized embedder with model: {model_path}.")
    
    db_session = get_db_session(os.getenv("DATABASE_URL"))
    
    countries = db_session.query(CountryModel).all() # Fetches from countries_v2
    logger.info(f"Fetched {len(countries)} countries from 'countries_v2' table for processing.")

    for country_data in countries: 
        if country_data.doc_id != "gabon":
            continue
            
        country_doc_id = country_data.doc_id
        country_name = country_data.country_name
        logger.info(f"Processing country: {country_name} ({country_doc_id})")
        
        country_markdown_parts = [f"## Country: {country_name}\n\n---\n"]
        
        country_sections = db_session.query(CountryPageSectionModel).filter(
            CountryPageSectionModel.country_doc_id == country_doc_id
        ).all() # Fetches from country_page_sections_v2

        if not country_sections:
            logger.warning(f"No sections found for {country_name} ({country_doc_id}). Skipping questions.")
            country_markdown_parts.append(f"\n*No sections found in database for this country.*\n\n---\n")
            country_file_name = f"{country_doc_id.replace('.', '_')}_report.md"
            with open(output_path / country_file_name, "w", encoding="utf-8") as f: f.write("".join(country_markdown_parts))
            logger.info(f"Wrote minimal report for {country_name} to {output_path / country_file_name}")
            continue

        valid_chunk_texts = []
        valid_chunk_urls = []
        valid_chunk_titles = []

        for section in country_sections:
            if not section.text_content or not section.text_content.strip():
                logger.debug(f"Section '{section.section_title}' for {country_name} has no text. Skipping for chunking.")
                continue
            
            chunks_from_section = chunk_text(section.text_content)
            for chunk in chunks_from_section:
                valid_chunk_texts.append(chunk)
                valid_chunk_urls.append(section.section_url or country_data.country_url) # Fallback for URL
                valid_chunk_titles.append(section.section_title)
        
        if not valid_chunk_texts:
            logger.warning(f"No valid text chunks produced for {country_name} after processing all sections. Skipping questions for this country.")
            country_markdown_parts.append(f"\n*No text chunks could be generated from sections for this country.*\n\n---\n")
            country_file_name = f"{country_doc_id.replace('.', '_')}_report.md"
            with open(output_path / country_file_name, "w", encoding="utf-8") as f: f.write("".join(country_markdown_parts))
            logger.info(f"Wrote minimal report for {country_name} to {output_path / country_file_name}")
            continue

        logger.info(f"Embedding {len(valid_chunk_texts)} chunks for {country_name}...")

        raw_embeddings_for_debug = []
        valid_chunk_texts = []
        valid_chunk_urls = []
        valid_chunk_titles = []

        for i, chunk in enumerate(valid_chunk_texts):
            try:
                emb = embedder.encode_batch([chunk])[0]
                raw_embeddings_for_debug.append(emb)
                valid_chunk_texts.append(chunk)
                valid_chunk_urls.append(valid_chunk_urls[i])
                valid_chunk_titles.append(valid_chunk_titles[i])
            except Exception as e:
                logger.warning(f"⚠ Skipping chunk {i} due to embedding error: {e}")
                continue

        if not raw_embeddings_for_debug:
            logger.warning(f"No valid chunk embeddings generated for {country_name}. Skipping questions.")
            country_markdown_parts.append("\n*Failed to generate valid chunk embeddings.*\n\n---\n")
            country_file_path = output_path / f"{country_doc_id.replace('.', '_')}_report.md"
            with open(country_file_path, "w", encoding="utf-8") as f:
                f.write("".join(country_markdown_parts))
            continue

        try:
            # Check if raw_embeddings_for_debug is a non-empty numpy ndarray
            if isinstance(raw_embeddings_for_debug, np.ndarray) and raw_embeddings_for_debug.size > 0:
                country_chunk_embeddings_np = raw_embeddings_for_debug
                # Handle case of single chunk resulting in 1D array, ensure it's 2D
                if country_chunk_embeddings_np.ndim == 1: # .size > 0 is already confirmed
                    country_chunk_embeddings_np = country_chunk_embeddings_np.reshape(1, -1)
            # If not a valid numpy ndarray, country_chunk_embeddings_np remains None

            # Final check for validity (it should be a non-empty 2D numpy array here)
            if country_chunk_embeddings_np is None or country_chunk_embeddings_np.size == 0:
                actual_type_info = type(raw_embeddings_for_debug).__name__ if raw_embeddings_for_debug is not None else "None"
                logger.error(f"Failed to generate valid numpy embeddings for chunks for {country_name}. Initial object type from embedder: {actual_type_info}. Skipping questions for this country.")
                country_markdown_parts.append(f"\n*Failed to generate valid text embeddings from section chunks (embedder output type: {actual_type_info}).*\n\n---\n")
                country_file_name = f"{country_doc_id.replace('.', '_')}_report.md"
                country_file_path = output_path / country_file_name
                with open(country_file_path, "w", encoding="utf-8") as f:
                    f.write("".join(country_markdown_parts))
                logger.info(f"Wrote minimal report (chunk embedding failure/empty or wrong type) for {country_name} to {country_file_path}")
                continue
        except Exception as e:
            # This catches any error during the try block, including potential ValueErrors if logic is still flawed, or other issues.
            logger.error(f"Error during chunk embedding processing for {country_name}: {e} (Type: {type(e).__name__}). Skipping questions for this country.")
            country_markdown_parts.append(f"\n*Error during text embedding generation ({type(e).__name__}) for {country_name}: {e}*\n\n---\n")
            country_file_name = f"{country_doc_id.replace('.', '_')}_report.md"
            country_file_path = output_path / country_file_name
            with open(country_file_path, "w", encoding="utf-8") as f:
                f.write("".join(country_markdown_parts))
            logger.info(f"Wrote minimal report (chunk embedding exception) for {country_name} to {country_file_path}")
            continue

        for i, question in enumerate(PREDEFINED_QUESTIONS):
            country_markdown_parts.append(f"### Question {i+1}: {question}\n\n")
            
            try:
                question_embedding = embedder.encode_batch([question])[0] 
            except Exception as e:
                logger.error(f"Error embedding question '{{question[:50].replace('\n', ' ')}}...': {e}")
                country_markdown_parts.append(f"\n*Error embedding question: {e}*\n\n---\n")
                continue 

            # Calculate similarities between the question and all CHUNK embeddings for this country
            similarities = cosine_similarity(question_embedding.reshape(1, -1), country_chunk_embeddings_np)
            
            if similarities.size == 0:
                logger.warning(f"No similarities calculated for question {i+1} for country {country_name}. This might happen if chunk embeddings are empty.")
                country_markdown_parts.append(f"\n*Could not calculate similarities for this question (no chunk embeddings?).*\n\n---\n")
                continue

            best_chunk_index = np.argmax(similarities)
            best_score = similarities[0, best_chunk_index]
            best_matching_chunk_text = valid_chunk_texts[best_chunk_index]
            best_matching_chunk_source_url = valid_chunk_urls[best_chunk_index]
            source_section_title_for_log = valid_chunk_titles[best_chunk_index]

            # Format the strings before putting them in the f-string
            question_short = question[:50].replace('\n', ' ')
            chunk_short = best_matching_chunk_text[:100].replace('\n', ' ')
            logger.debug(f"Q: '{question_short}...' - Best chunk for {country_name} (from section '{source_section_title_for_log}'): '{chunk_short}...', Score: {best_score:.4f}")

            country_markdown_parts.append(f"**Answer/Evidence (Similarity: {best_score:.4f}):**\n")
            
            escaped_chunk_text = best_matching_chunk_text.replace('`', '\\`').replace('\n', ' ') # Escape backticks, replace newlines for blockquote
            country_markdown_parts.append(f"> {escaped_chunk_text}\n\n")
            
            final_url = best_matching_chunk_source_url 
            country_markdown_parts.append(f"**Source URL:** [{final_url}]({final_url})\n\n---\n")

        # Write the complete markdown for this country to its own file
        country_file_name = f"{country_doc_id.replace('.', '_')}_report.md"
        country_file_path = output_path / country_file_name
        with open(country_file_path, "w", encoding="utf-8") as f:
            f.write("".join(country_markdown_parts))
        logger.info(f"Wrote full report for {country_name} to {country_file_path}")

    logger.info(f"✅ Information retrieval process complete. Reports saved in {output_path}")
    if db_session:
        db_session.close()

if __name__ == "__main__":
    retrieve_and_format_answers() 