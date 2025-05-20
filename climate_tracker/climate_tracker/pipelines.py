import json
import os
from itemadapter import ItemAdapter
import os
from datetime import datetime, date
from dotenv import load_dotenv
from itemadapter import ItemAdapter
import requests
import pdfplumber
from pathlib import Path

from scrapy.exceptions import DropItem

from .models import init_db, get_db_session, CountryModel
from .items import CountryTextItem
from .utils import now_london_time
from .utils import generate_word_embeddings, save_word2vec_model
from sentence_transformers import SentenceTransformer


class ClimateTrackerPipeline:
    def __init__(self):
        self.data_dir = os.path.abspath("climate_tracker/data/json")
        os.makedirs(self.data_dir, exist_ok=True)
        self.countries = set()
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        country_slug = adapter.get('country_slug')
        
        # Save JSON version of the item
        json_file = os.path.join(self.data_dir, f"{country_slug}_{adapter.get('section_title').lower().replace(' ', '_')}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(dict(item), f, ensure_ascii=False, indent=2)
        
        # Keep track of processed countries
        self.countries.add(country_slug)
        
        return item
    
    def close_spider(self, spider):
        # Create an index of all countries
        index_file = os.path.join(self.data_dir, "country_index.json")
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.countries), f, indent=2)
        
        spider.logger.info(f"Processed {len(self.countries)} countries in total")


def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file using pdfplumber."""
    try:
        if not pdf_path or not os.path.exists(pdf_path):
            print(f"PDF file not found: {pdf_path}")
            return None
            
        all_text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                try:
                    text = page.extract_text() or ''
                    all_text += text + "\n\n"
                except Exception as e:
                    print(f"Error extracting text from page: {e}")
                    continue
                    
        return all_text
    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {e}")
        return None

def generate_doc_id(item):
    """Generate a document ID from item metadata."""
    country = item.get('country', 'unknown').lower().replace(" ", "_")
    lang = item.get('language', 'unknown').lower().replace(" ", "_")
    try:
        # Ensure we're using just the date part for the ID
        submission_date = item.get('submission_date')
        if isinstance(submission_date, datetime):
            date_str = submission_date.date().strftime('%Y%m%d')
        elif isinstance(submission_date, date):
            date_str = submission_date.strftime('%Y%m%d')
        else:
            date_str = 'unknown_date'
    except:
        date_str = 'unknown_date'
    
    return f"{country}_{lang}_{date_str}"

class PostgreSQLPipeline:
    """Pipeline for storing NDC documents in PostgreSQL."""

    def __init__(self, db_url=None):
        # Load environment variables
        load_dotenv()
        self.db_url = db_url or os.getenv('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL not found in environment variables")
        print("PostgreSQLPipeline initialized")

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        """Initialize database connection when spider opens."""
        self.logger = spider.logger
        print("PostgreSQLPipeline: Opening spider")
        init_db(self.db_url)  # Create tables if they don't exist
        self.session = get_db_session(self.db_url)

    def close_spider(self, spider):
        """Close database connection when spider closes."""
        print("PostgreSQLPipeline: Closing spider")
        self.session.close()

    def process_item(self, item, spider):
        """Process scraped item and store in PostgreSQL."""
        print(f"PostgreSQLPipeline: Processing item for {item.get('country')}")
        adapter = ItemAdapter(item)
        
        # Convert submission_date to date if it's a datetime
        if 'submission_date' in item:
            submission_date = item['submission_date']
            if isinstance(submission_date, datetime):
                item['submission_date'] = submission_date.date()
        
        # Generate doc_id from metadata (same as future file name)
        doc_id = generate_doc_id(item)
        print(f"PostgreSQLPipeline: Generated doc_id: {doc_id}")

        # Create or update document record
        doc = self.session.query(NDCDocumentModel).filter_by(doc_id=doc_id).first()

        if doc:
            print(f"PostgreSQLPipeline: Document found in database: {doc_id}")
            retrieved_doc_as_dict = adapter.asdict()
            
            # Check if any data has changed
            has_changes = False
            changes = []
            
            for key, value in retrieved_doc_as_dict.items():
                if key in ['downloaded_at', 'processed_at', 'scraped_at']:
                    continue

                if hasattr(doc, key):
                    current_value = getattr(doc, key)
                    
                    if current_value != value:
                        changes.append(f"{key}: {current_value} -> {value}")
                        has_changes = True
                        setattr(doc, key, value)
            
            if has_changes:
                doc.scraped_at = now_london_time()
                print(f"PostgreSQLPipeline: Updating document {doc_id} with changes: {', '.join(changes)}")
            else:
                print(f"PostgreSQLPipeline: No changes detected for document {doc_id}")
                raise DropItem(f"No changes detected for document {doc_id}, skipping update")
        else:
            print(f"PostgreSQLPipeline: Creating new document: {doc_id}")
            doc = NDCDocumentModel(
                doc_id=doc_id,
                country=adapter.get('country'),
                title=adapter.get('title'),
                url=adapter.get('url'),
                language=adapter.get('language'),
                submission_date=adapter.get('submission_date'),
                file_path=None,
                file_size=None,
                extracted_text=None,
                chunks=None,
                downloaded_at=None,
                processed_at=None
            )
            try:
                self.session.add(doc)
                print(f"PostgreSQLPipeline: Added new document to session: {doc_id}")
            except Exception as e:
                print(f"PostgreSQLPipeline: Error adding document: {str(e)}")
                raise DropItem(f"Failed to add document to PostgreSQL: {str(e)}")
        
        try:
            self.session.commit()
            print(f"PostgreSQLPipeline: Committed document to database: {doc_id}")
            # Add doc_id back to the item for downstream processing
            item['doc_id'] = doc_id
        except Exception as e:
            self.session.rollback()
            print(f"PostgreSQLPipeline: Error committing document: {str(e)}")
            raise DropItem(f"Failed to store item in PostgreSQL: {e}")
        
        return item

class TextExtractionPipeline:
    """Pipeline to extract text from PDFs."""
    def __init__(self):
        # Import pdfplumber here to avoid dependency issues
        import pdfplumber
        self.pdfplumber = pdfplumber
        
    def process_item(self, item, spider):
        """Extract text from PDF and update the item."""
        file_path = item.get('file_path')
        if not file_path:
            print("TextExtractionPipeline: No file path provided, skipping text extraction")
            return item
            
        print(f"TextExtractionPipeline: Extracting text from {file_path}")
        text = extract_text_from_pdf(file_path)
        
        if text:
            item['extracted_text'] = text
            print(f"TextExtractionPipeline: Successfully extracted {len(text)} characters")
        else:
            print(f"TextExtractionPipeline: Failed to extract text from {file_path}")
            
        return item

class WordEmbeddingPipeline:
    """Pipeline to generate embeddings from extracted text."""
    def __init__(self, model_dir=None):
        # Load environment variables
        load_dotenv()
        self.model_dir = model_dir or os.path.join(os.getenv('DATA_DIR', 'data'), 'models')
        os.makedirs(self.model_dir, exist_ok=True)
        
    def process_item(self, item, spider):
        if not item.get('extracted_text'):
            print("WordEmbeddingPipeline: No extracted text, skipping embedding generation")
            return item
            
        try:
            print(f"WordEmbeddingPipeline: Generating embeddings for {item.get('doc_id')}")
            embeddings = generate_word_embeddings(item['extracted_text'])
            
            if embeddings:
                item['word_embeddings'] = embeddings.get('document_vector')
                
                # Save the model if needed
                if item.get('doc_id') and embeddings.get('model'):
                    model_path = save_word2vec_model(
                        embeddings['model'], 
                        item['doc_id'], 
                        self.model_dir
                    )
                    if model_path:
                        print(f"WordEmbeddingPipeline: Model saved to {model_path}")
            else:
                print(f"WordEmbeddingPipeline: No embeddings generated")
        except Exception as e:
            print(f"WordEmbeddingPipeline: Error generating embeddings: {str(e)}")
            
        return item


class ExtractionPipeline:
    """Pipeline to extract structured information from documents."""
    def process_item(self, item, spider):
        # Import here to avoid circular imports
        from .extraction_organised_2 import PolicyExtractor
        
        print(f"ExtractionPipeline: Extracting information for {item.get('doc_id')}")
        try:
            extractor = PolicyExtractor()
            results = extractor.extract_document(item.get('doc_id'))
            
            if results:
                item.update(results)
                print(f"ExtractionPipeline: Successfully extracted information")
            else:
                print(f"ExtractionPipeline: No information extracted")
                
        except Exception as e:
            print(f"ExtractionPipeline: Error extracting information: {str(e)}")
            
        return item
    




    

from sentence_transformers import SentenceTransformer
from datetime import datetime
from .utils import now_london_time


class TransformerPipeline:
    def __init__(self):
        self.model = SentenceTransformer('all-mpnet-base-v2')
        
    def process_item(self, item, spider):
        if item.get('content'):
            item['embedding'] = self.model.encode(item['content'])
            item['model_type'] = 'transformer'
            item['processed_at'] = now_london_time()
        return item

class CountryDataPostgreSQLPipeline:
    """Pipeline for storing CountryTextItem data in PostgreSQL using CountryModel."""

    def __init__(self, db_url=None):
        # Explicitly load .env from the project root
        # __file__ refers to pipelines.py
        # .parent.parent.parent should navigate to the project root directory
        dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
        
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path, override=True)
            # For debugging, let's see if it's loaded here
            print(f"DEBUG (pipelines.py): Loaded .env from {dotenv_path}. DATABASE_URL: {os.getenv('DATABASE_URL')}")
        else:
            # This print is for debugging
            print(f"DEBUG (pipelines.py): .env file not found at {dotenv_path}")

        self.db_url = db_url or os.getenv('DATABASE_URL')
        if not self.db_url:
            print(f"ERROR: DATABASE_URL not found in environment variables for CountryDataPostgreSQLPipeline after attempting to load from {dotenv_path}")
            raise ValueError("DATABASE_URL not found for CountryDataPostgreSQLPipeline")
        self.logger = None # Will be set in open_spider

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your pipeline instance
        return cls()

    def open_spider(self, spider):
        """Initialize database connection and session when spider opens."""
        self.logger = spider.logger
        self.logger.info("CountryDataPostgreSQLPipeline: Opening spider")
        try:
            init_db(self.db_url)  # Ensure tables are created (idempotent)
            self.session = get_db_session(self.db_url)
            self.logger.info("CountryDataPostgreSQLPipeline: Database session established.")
        except Exception as e:
            self.logger.error(f"CountryDataPostgreSQLPipeline: Failed to connect to DB: {e}")
            raise # Reraise to stop the spider if DB connection fails

    def close_spider(self, spider):
        """Close database connection when spider closes."""
        self.logger.info("CountryDataPostgreSQLPipeline: Closing spider")
        if hasattr(self, 'session') and self.session:
            self.session.close()
            self.logger.info("CountryDataPostgreSQLPipeline: Database session closed.")

    def process_item(self, item, spider):
        """Process CountryTextItem and store in PostgreSQL using CountryModel."""
        if not isinstance(item, CountryTextItem):
            return item # Only process CountryTextItem

        adapter = ItemAdapter(item)
        doc_id = adapter.get('doc_id')

        if not doc_id:
            self.logger.warning("CountryDataPostgreSQLPipeline: Item lacks doc_id, skipping.")
            raise DropItem("Item lacks doc_id")

        self.logger.info(f"CountryDataPostgreSQLPipeline: Processing item for doc_id: {doc_id}")

        try:
            country_entry = self.session.query(CountryModel).filter_by(doc_id=doc_id).first()

            if country_entry:
                # Update existing entry
                self.logger.info(f"CountryDataPostgreSQLPipeline: Updating existing entry for {doc_id}")
                country_entry.country = adapter.get('country')
                country_entry.language = adapter.get('language')
                country_entry.text = adapter.get('text')
                country_entry.url = adapter.get('url')
                # created_at is managed by model default, embedding is handled later
                country_entry.created_at = now_london_time() # Explicitly update timestamp on modification
            else:
                # Create new entry
                self.logger.info(f"CountryDataPostgreSQLPipeline: Creating new entry for {doc_id}")
                country_entry = CountryModel(
                    doc_id=doc_id,
                    country=adapter.get('country'),
                    language=adapter.get('language'),
                    text=adapter.get('text'),
                    url=adapter.get('url')
                    # embedding will be NULL initially
                    # created_at has a default in the model
                )
                self.session.add(country_entry)
            
            self.session.commit()
            self.logger.info(f"CountryDataPostgreSQLPipeline: Successfully committed {doc_id} to database.")
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"CountryDataPostgreSQLPipeline: Error processing/committing item {doc_id}: {e}")
            raise DropItem(f"Failed to process item {doc_id} for PostgreSQL: {e}")
        
        return item