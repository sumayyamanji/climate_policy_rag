import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModel
import torch
import torch.nn.functional as F

# Load env and project root
load_dotenv()
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from my_logging import get_logger
logger = get_logger(__name__)
from models import Base, get_db_session, CountryModel  # No import of NDCDocumentModel
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Text
from pgvector.sqlalchemy import Vector

class BAAIEmbedder:
    def __init__(self, model_path):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)
        self.model.eval()

    def encode_batch(self, sentences):
        inputs = self.tokenizer(sentences, padding=True, truncation=True, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
        embeddings = self.mean_pooling(outputs.last_hidden_state, inputs['attention_mask'])
        return F.normalize(embeddings, p=2, dim=1).cpu().numpy()

    def mean_pooling(self, token_embeddings, attention_mask):
        mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * mask_expanded, dim=1) / torch.clamp(mask_expanded.sum(dim=1), min=1e-9)

def generate_embeddings(batch_size=5, model_path="/space_mounts/ps2-drive/local_models/BAAI/bge-m3", max_chars=3000):
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

        torch.cuda.empty_cache()  # just in case (won't error if using CPU)

    logger.info("✅ Embedding generation complete")
    session.close()

if __name__ == "__main__":
    generate_embeddings()
