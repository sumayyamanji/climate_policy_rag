# Information_Retrieval_Report.md

## `climate_tracker/scripts/05_information_retrieval.py`

This document outlines the process for generating country-specific climate action reports based on predefined questions. The system scrapes information from climateactiontracker.org, processes the text by generating embeddings, and then creates markdown reports with relevant answers and source URLs.

## Key Features & Recent Modifications

The report generation process, primarily handled by the `climate_tracker/climate_tracker/scripts/05_information_retrieval.py` script, has been significantly updated:

*   **Utilizes Text Chunking for Answers**: Instead of using entire scraped sections as answers, the system now breaks down section text into smaller, more focused chunks (typically a few sentences).
*   **Chunk-Based Similarity Matching**: Answers to predefined questions are identified by finding the text chunk with the highest semantic similarity to the question's embedding. This results in more concise and contextually relevant answers in the final reports.
*   **Accurate Source URLS**: Each answer is accompanied by a source URL that points directly to the web page from which the specific answer chunk was derived, ensuring traceability.
*   **Improved Robustness**: Enhanced error handling has been implemented in the `05_information_retrieval.py` script to manage potential issues during data processing and embedding generation more gracefully, including detailed error messages in logs and output files if problems occur.

## Prerequisites

Before running the scripts, ensure the following are set up:

1.  **Python Environment**: Python 3.x is recommended.
2.  **Dependencies**: Install required Python packages. If a `requirements.txt` file is available for the project, use it. Key dependencies for these scripts include:
    *   `psycopg2-binary` (for PostgreSQL connection)
    *   `SQLAlchemy` (for ORM and database interaction)
    *   `python-dotenv` (for managing environment variables)
    *   `nltk` (for text tokenization/chunking)
    *   `scikit-learn` (for `cosine_similarity`)
    *   `numpy` (for numerical operations, especially with embeddings)
    *   `tqdm` (for progress bars)
    *   `click` (used in `02_create-table.py`)
    *   `sentence-transformers` or `transformers` and `torch` (these are common dependencies for embedding models like BAAI/bge-m3, used by `BAAIEmbedder`)
    *   `requests`, `beautifulsoup4` (or similar, for the data scraping part of the project)

3.  **PostgreSQL Database**:
    *   A running PostgreSQL instance.
    *   The database connection string must be configured (see `.env` file section).
    *   The `vector` extension should be available in PostgreSQL (the `04_generate_embeddings.py` script attempts to create it using `CREATE EXTENSION IF NOT EXISTS vector`).

4.  **.env File**: Create a `.env` file in the project root directory (e.g., `DS205-final-project-team-CPR-1/.env`) with the following variables:
    ```env
    DATABASE_URL="postgresql://your_user:your_password@your_host:your_port/your_database_name"
    BGE_MODEL_PATH="BAAI/bge-m3" # Optional: Path to a local BGE model or a Hugging Face model ID. Defaults to "BAAI/bge-m3" if not set.
    ```
    Replace the placeholder values in `DATABASE_URL` with your actual database credentials.

5.  **NLTK Data**: The `nltk.punkt` tokenizer is required for text chunking. The `05_information_retrieval.py` script attempts to download this automatically if it's not found.

## Process for Generating Reports

Execute the scripts from the project root directory (e.g., `DS205-final-project-team-CPR-1/`). The scripts are designed to handle relative paths internally.

1.  **Initialize Database Tables**:
    *   If the necessary tables (`countries_v2`, `country_page_sections_v2`) do not exist in your database, run the table creation script:
        ```bash
        python climate_tracker/climate_tracker/scripts/02_create-table.py
        ```
    *   This script creates the tables as defined in `climate_tracker/climate_tracker/models.py`.

2.  **Scrape Country Data**:
    *   Run the project's scraping script(s) to populate the `countries_v2` (for country metadata) and `country_page_sections_v2` (for detailed text content from country pages) tables in your database with data from climateactiontracker.org.
    *   *(Note: The specific scraping script(s) were not part of these recent modifications but are a necessary precursor to have data for processing. Ensure this step has been completed successfully.)*

3.  **Generate Section Embeddings**:
    *   Once the `country_page_sections_v2` table is populated with text content, generate embeddings for these larger sections:
        ```bash
        python climate_tracker/climate_tracker/scripts/04_generate_embeddings.py
        ```
    *   This script uses the embedding model specified by `BGE_MODEL_PATH` (or its default) and stores the resulting embeddings in the `embedding` column of the `country_page_sections_v2` table.

4.  **Retrieve Information and Generate Reports (Modified Process)**:
    *   With the database populated and section embeddings generated, run the main information retrieval script that incorporates the chunking logic:
        ```bash
        python climate_tracker/climate_tracker/scripts/05_information_retrieval.py
        ```
    *   This script will:
        *   Fetch country data and their associated text sections (from `country_page_sections_v2`).
        *   Chunk the `text_content` from each section.
        *   Generate embeddings for these text chunks *on-the-fly*.
        *   For each predefined question, compare its embedding against all chunk embeddings for a country to find the most semantically similar chunk.
        *   Compile and save markdown reports using these chunks as answers.

## Output

*   The generated markdown reports will be saved in the `retrieved_country_reports_v2_chunked/` directory, located within your project root.
*   Each report file (e.g., `nigeria_report.md`, `south-korea_report.md`) contains the answers to the predefined questions for a specific country, the similarity score of the answer chunk to the question, and the source URL for that chunk.

## Scripts Involved

*   `climate_tracker/climate_tracker/scripts/02_create-table.py`: Sets up the required database tables.
*   **Scraping script(s)** (e.g., potentially `03_scrape_country_pages.py` or similar - name depends on your project): Responsible for data acquisition from the web.
*   `climate_tracker/climate_tracker/scripts/04_generate_embeddings.py`: Pre-computes and stores embeddings for larger text sections scraped from country pages.
*   `climate_tracker/climate_tracker/scripts/05_information_retrieval.py`: The core script for the updated process. It performs text chunking of sections, on-the-fly embedding generation for these chunks, similarity-based question-answering using chunks, and generation of the final markdown reports. 