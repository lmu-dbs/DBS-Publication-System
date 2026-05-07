from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import sys
import os
import hashlib
from datetime import datetime
from pydantic import BaseModel, HttpUrl
import requests
from bs4 import BeautifulSoup
import time
import asyncio

from dotenv import load_dotenv
from huggingface_hub import login

from llama_cpp import Llama

from ..models.database import get_db
from ..models.models import User, CurrentEntry, Publication
from ..models.models import Author
from ..auth.auth import get_current_user
from ..schemas.schemas import ScrapingResponse, DeleteResponse, ScrapingRequest

from ..utils.bibtex_processor import parse_bibtex
from ..utils.bibtex_processor import get_existing_author, parse_author_name
from ..models.models import PublicationAuthor

# Load environment variables from .env file
load_dotenv()

# Get HF_TOKEN from environment
hf_token = os.getenv("HF_TOKEN")
print(f"HF_TOKEN: {hf_token is not None}", file=sys.stderr)

# Login to Hugging Face
if hf_token:
    login(token=hf_token)
    print('Logged in to Hugging Face')

# Model configuration for lazy loading
model_id = "hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF"
filename = "llama-3.2-3b-instruct-q4_k_m.gguf"

# Initialize LLM as None - will be loaded on first fallback use
llm = None

def get_llm():
    """Lazy load the Llama model only when needed (fallback scenario)"""
    global llm
    if llm is None:
        print('Loading local Llama model for fallback...')
        llm = Llama.from_pretrained(
            repo_id=model_id,
            filename=filename,
            verbose=False,
        )
        print('Finished loading local LLM')
    return llm


def text_to_bibtex(text):
    """Convert text to BibTeX format using NVIDIA NIM API (primary) or local Llama model (fallback)"""
    start_time = time.time()
    print(f'Convert the following text: {text}')

    instruction = (
        "Convert the text at INPUT to a complete, valid BibTeX entry and wrap it in triple quotes (\"\"\"). Follow these rules:\n"
        "1. Start with the correct entry type (@article, @inproceedings, etc.)\n"
        "2. Create a unique citation key using first author's surname and year\n"
        "3. Include all required fields: title, author, venue (journal/conference), year\n"
        "4. Format author names as 'Surname, Firstname' separated by 'and'\n"
        "5. Clean up venue names by removing years and edition numbers but keep workshop names\n"
        "6. Give back only the BibTeX entry wrapped in triple quotes, without any extra text\n"
        "7. Format the BibTeX with proper indentation and line breaks\n\n"
        "Example Input:\n"
        "'Deep Learning for Time Series Forecasting by John Smith and Mary Jones, published in IEEE Conference on Neural Networks 2023'\n\n"
        "Example Output:\n"
        "\"\"\"\n"
        "@inproceedings{smith2023deep,\n"
        "    title={Deep Learning for Time Series Forecasting},\n"
        "    author={Smith, John and Jones, Mary},\n"
        "    booktitle={IEEE Conference on Neural Networks},\n"
        "    year={2023}\n"
        "}\n"
        "\"\"\"\n\n"
        "Now convert the following to BibTeX (remember to wrap in triple quotes): "
    )

    # Try NVIDIA NIM API first
    try:
        from openai import OpenAI
        
        # Get NVIDIA API key from environment
        nvidia_api_key = os.getenv("NVIDIA_TOKEN")
        if not nvidia_api_key:
            raise ValueError("NVIDIA_TOKEN not found in environment variables")
        
        print("Attempting conversion using NVIDIA NIM API...")
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nvidia_api_key
        )
        
        formatted_prompt = f"{instruction}{text}\n"
        
        llama_nvidia = "meta/llama-3.3-70b-instruct"
        completion = client.chat.completions.create(
            model=llama_nvidia,
            messages=[{"role": "user", "content": formatted_prompt}],
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
            stream=False
        )
        
        converted_response = completion.choices[0].message.content
        
        # Extract content between triple quotes
        import re
        match = re.search(r'"""(.*?)"""', converted_response, re.DOTALL)
        generated_output = match.group(1).strip() if match else converted_response.strip()
        print(f"Generated output (NVIDIA NIM): {generated_output}")
        print(f"Generated output repr (NVIDIA NIM): {repr(generated_output)}")
        print(f"Conversion completed using NVIDIA NIM in {time.time() - start_time:.2f} seconds")
        
        return generated_output
        
    except Exception as e:
        print(f"NVIDIA NIM API failed: {str(e)}")
        print("Falling back to local Llama model...")
        
        # Fallback to local Llama model
        try:
            local_llm = get_llm()
            
            formatted_prompt = (
                "<|start_header_id|>user<|end_header_id|>\n"
                f"{instruction}{text}\n"
                "<|eot_id|>"
                "<|start_header_id|>assistant<|end_header_id|>\n"
            )

            output = local_llm(
                formatted_prompt,
                max_tokens=512,
                temperature=0.1,
                top_p=0.9,
                stop=["<|eot_id|>"],  # stop at end-of-turn
            )

            response_text = output["choices"][0]["text"]

            # Extract content between triple quotes
            import re
            match = re.search(r'"""(.*?)"""', response_text, re.DOTALL)
            generated_output = match.group(1).strip() if match else response_text.strip()
            print(f"Generated output (Local Llama): {generated_output}")
            print(f"Generated output repr (Local Llama): {repr(generated_output)}")
            print(f"Conversion completed using local Llama in {time.time() - start_time:.2f} seconds")
            
            return generated_output
            
        except Exception as fallback_error:
            print(f"Local Llama model also failed: {str(fallback_error)}")
            raise Exception(f"Both NVIDIA NIM API and local Llama model failed. Last error: {str(fallback_error)}")

router = APIRouter(
    prefix="/scraping",
    tags=["scraping"],
)

# Endpoint to list all scraped publications for the current user

from ..models.models import ScrapedPublication
import re
from fastapi import Body

def _build_main_title_index(db: Session):
    """Query title + key content fields from main publications and build lookup structures.
    Returns:
      exact_dict: {normalized_title: row}  — O(1) exact-match lookup with content data
      normalized_main: [(normalized_title, row), ...]  — for similarity scan
    """
    rows = db.query(
        Publication.title,
        Publication.abstract,
        Publication.doi,
        Publication.url,
        Publication.venue,
    ).filter(Publication.title.isnot(None)).all()
    normalized_main = []
    exact_dict = {}
    for r in rows:
        n = normalize_title(r.title)
        if n:
            exact_dict[n] = r
            normalized_main.append((n, r))
    return exact_dict, normalized_main


def _extra_content_fields(entry, main_row) -> list:
    """Return a list of field names present in the scraped entry but missing in the main publication."""
    extra = []
    for field in ('abstract', 'doi', 'url', 'venue'):
        entry_val = getattr(entry, field, None)
        main_val = getattr(main_row, field, None)
        if entry_val and not main_val:
            extra.append(field)
    return extra


def _check_against_main_db(entry, exact_dict: dict, normalized_main: list):
    """Check whether entry matches a main publication.
    Returns:
      match_type: 'exact' | 'similar' | None
      has_more_content: bool
      extra_fields: list
      matched_title: str | None  — original title of the matched main publication
    """
    if not entry.title:
        return None, False, [], None
    entry_normalized = normalize_title(entry.title)
    if not entry_normalized:
        return None, False, [], None

    matched_row = None
    match_type = None
    if entry_normalized in exact_dict:
        matched_row = exact_dict[entry_normalized]
        match_type = 'exact'
        print(f"[SCRAPED VIEW] Exact match found: {entry.title}")
    else:
        for main_normalized, row in normalized_main:
            if main_normalized and calculate_similarity(entry_normalized, main_normalized) > 0.85:
                matched_row = row
                match_type = 'similar'
                print(f"[SCRAPED VIEW] High similarity match: {entry.title} ~ {row.title}")
                break

    if matched_row is None:
        return None, False, [], None

    extra = _extra_content_fields(entry, matched_row)
    return match_type, bool(extra), extra, matched_row.title


def _parse_authors_from_bibtex(bibtex: str):
    authors = []
    bibtex_error = False
    if bibtex:
        try:
            bib_data = parse_bibtex(bibtex)
            if 'authors' in bib_data and isinstance(bib_data['authors'], list):
                authors = bib_data['authors']
            elif 'author' in bib_data:
                authors = [a.strip() for a in re.split(r'\s+and\s+', bib_data['author']) if a.strip()]
        except Exception:
            bibtex_error = True
    return authors, bibtex_error


@router.get("/scraped", response_model=list)
async def get_scraped_publications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all scraped publications for the current user that are not already in the main database"""
    entries = db.query(ScrapedPublication).filter(ScrapedPublication.user_id == current_user.id).order_by(ScrapedPublication.created_at.desc()).all()

    # Pre-compute normalized main titles once — avoids O(n×m) re-normalization
    exact_dict, normalized_main = _build_main_title_index(db)

    result = []
    for entry in entries:
        match_type, has_more_content, extra_fields, matched_title = _check_against_main_db(entry, exact_dict, normalized_main)
        # Hide only exact matches that have nothing new to offer
        if match_type == 'exact' and not has_more_content:
            continue

        authors, bibtex_error = _parse_authors_from_bibtex(entry.bibtex)
        result.append({
            "id": entry.id,
            "title": entry.title,
            "bibtex_error": bibtex_error,
            "raw_text": entry.raw_text,
            "venue": entry.venue,
            "year": entry.year,
            "doi": entry.doi,
            "url": entry.url,
            "bibtex": entry.bibtex,
            "created_at": entry.created_at,
            "publication_type": entry.publication_type,
            "authors": authors,
            "already_in_db": match_type == 'exact',
            "has_more_content": has_more_content,
            "extra_fields": extra_fields,
            "is_similar_match": match_type == 'similar',
            "similar_to": matched_title if match_type == 'similar' else None,
        })

    print(f"[SCRAPED VIEW] Returning {len(result)} scraped publications (filtered from {len(entries)} total)")
    return result


@router.get("/scraped/export/bibtex")
async def export_scraped_bibtex(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export all scraped publications as a BibTeX file"""
    from fastapi.responses import Response
    
    entries = db.query(ScrapedPublication).filter(
        ScrapedPublication.user_id == current_user.id
    ).order_by(ScrapedPublication.created_at.desc()).all()
    
    # Filter out entries already in main database — pre-compute once to avoid O(n×m) loop
    # Keep entries that are not in main DB, or are in main DB but have more content
    exact_dict, normalized_main = _build_main_title_index(db)
    filtered_entries = []
    for entry in entries:
        match_type, has_more_content, _, _ = _check_against_main_db(entry, exact_dict, normalized_main)
        if match_type != 'exact' or has_more_content:
            filtered_entries.append(entry)
    
    # Combine all BibTeX entries
    bibtex_entries = []
    for entry in filtered_entries:
        if entry.bibtex:
            bibtex_entries.append(entry.bibtex.strip())
    
    # Reverse the order so newest publications are at the end (reverse chronological to chronological)
    bibtex_entries.reverse()
    
    bibtex_content = "\n\n".join(bibtex_entries)
    
    # Return as downloadable file
    return Response(
        content=bibtex_content,
        media_type="application/x-bibtex",
        headers={
            "Content-Disposition": f"attachment; filename=scraped_publications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bib"
        }
    )


# Endpoint to reprocess BibTeX for a scraped publication
@router.post("/scraped/{scraped_id}/reprocess", response_model=dict)
async def reprocess_scraped_bibtex(
    scraped_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = db.query(ScrapedPublication).filter(ScrapedPublication.id == scraped_id, ScrapedPublication.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Scraped publication not found")
    # Re-run text_to_bibtex and parse_bibtex using the full raw_text
    bibtex = text_to_bibtex(entry.raw_text)
    entry.bibtex = bibtex
    db.commit()
    # Try to extract authors again
    authors = []
    bibtex_error = False
    try:
        bib_data = parse_bibtex(bibtex)
        if 'authors' in bib_data and isinstance(bib_data['authors'], list):
            authors = bib_data['authors']
        elif 'author' in bib_data:
            authors = [a.strip() for a in re.split(r'\s+and\s+', bib_data['author']) if a.strip()]
    except Exception as e:
        authors = []
        bibtex_error = True
    return {
        "id": entry.id,
        "title": entry.title,
        "raw_text": entry.raw_text,
        "venue": entry.venue,
        "year": entry.year,
        "doi": entry.doi,
        "url": entry.url,
        "bibtex": entry.bibtex,
        "bibtex_error": bibtex_error,
        "created_at": entry.created_at,
        "publication_type": entry.publication_type,
        "authors": authors
    }


@router.post("/scraped/{scraped_id}/add", response_model=dict)
async def add_scraped_to_main(
    scraped_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Promote a ScrapedPublication into the main Publication table."""
    scraped = db.query(ScrapedPublication).filter(ScrapedPublication.id == scraped_id, ScrapedPublication.user_id == current_user.id).first()
    if not scraped:
        raise HTTPException(status_code=404, detail="Scraped publication not found")

    # Create Publication record
    pub = Publication(
        title=scraped.title,
        abstract=scraped.abstract,
        year=scraped.year,
        venue=scraped.venue,
        publication_type=scraped.publication_type,
        doi=scraped.doi,
        url=scraped.url,
        bibtex=scraped.bibtex,
        raw_text=scraped.raw_text,
        user_id=current_user.id,
        is_scraped=True
    )
    db.add(pub)
    db.commit()
    db.refresh(pub)
    upsert_fingerprint(db, "publications", pub.id, pub.title, pub.doi)
    db.commit()
    created_authors = []
    # Try to extract authors from bibtex
    if scraped.bibtex:
        try:
            bib_data = parse_bibtex(scraped.bibtex)
            authors_list = []
            if 'authors' in bib_data and isinstance(bib_data['authors'], list):
                authors_list = bib_data['authors']
            elif 'author' in bib_data:
                authors_list = [a.strip() for a in re.split(r'\s+and\s+', bib_data['author']) if a.strip()]

            for idx, author_name in enumerate(authors_list):
                # Try to find existing author
                author_obj = get_existing_author(db, author_name)
                if not author_obj:
                    # Create a new author
                    forename, lastname = parse_author_name(author_name)
                    author_obj = Author(name=author_name, forename=forename, lastname=lastname)
                    db.add(author_obj)
                    db.commit()
                    db.refresh(author_obj)

                # Create association
                assoc = PublicationAuthor(publication_id=pub.id, author_id=author_obj.id, author_position=idx+1)
                db.add(assoc)
                created_authors.append(author_obj.name)

            db.commit()
        except Exception as e:
            # If parsing authors fails, continue without authors
            print(f"Error extracting authors while promoting scraped publication: {e}")

    # Return the created publication summary
    return {
        "id": pub.id,
        "title": pub.title,
        "year": pub.year,
        "venue": pub.venue,
        "doi": pub.doi,
        "url": pub.url,
        "authors": created_authors
    }


@router.post("/scraped/{scraped_id}/update-main", response_model=dict)
async def update_main_from_scraped(
    scraped_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Patch the matching main Publication with fields that are missing there but present in the scraped entry."""
    scraped = db.query(ScrapedPublication).filter(
        ScrapedPublication.id == scraped_id,
        ScrapedPublication.user_id == current_user.id
    ).first()
    if not scraped:
        raise HTTPException(status_code=404, detail="Scraped publication not found")

    # Find the matching main publication by title
    main_pubs = db.query(Publication).filter(Publication.title.isnot(None)).all()
    scraped_normalized = normalize_title(scraped.title) if scraped.title else None
    matched_pub = None
    if scraped_normalized:
        for pub in main_pubs:
            n = normalize_title(pub.title)
            if n == scraped_normalized or (n and calculate_similarity(scraped_normalized, n) > 0.85):
                matched_pub = pub
                break

    if not matched_pub:
        raise HTTPException(status_code=404, detail="No matching publication found in main database")

    # Patch only the fields missing in the main publication
    updated_fields = []
    for field in ('abstract', 'doi', 'url', 'venue'):
        if getattr(scraped, field) and not getattr(matched_pub, field):
            setattr(matched_pub, field, getattr(scraped, field))
            updated_fields.append(field)

    if not updated_fields:
        raise HTTPException(status_code=400, detail="Main publication already has all available fields")

    db.commit()
    upsert_fingerprint(db, "publications", matched_pub.id, matched_pub.title, matched_pub.doi)
    db.commit()
    return {
        "id": matched_pub.id,
        "title": matched_pub.title,
        "updated_fields": updated_fields,
    }


# Endpoint to update a scraped publication (editable fields)
@router.put("/scraped/{scraped_id}", response_model=dict)
async def update_scraped_publication(
    scraped_id: int,
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = db.query(ScrapedPublication).filter(ScrapedPublication.id == scraped_id, ScrapedPublication.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Scraped publication not found")

    # Allowed fields to update
    allowed = {"title", "raw_text", "bibtex", "venue", "year", "doi", "url", "publication_type"}
    updated = False
    for key, val in payload.items():
        if key in allowed:
            setattr(entry, key, val)
            updated = True

    if updated:
        db.commit()
        db.refresh(entry)

    # Recompute authors from bibtex if present
    authors = []
    bibtex_error = False
    if entry.bibtex:
        try:
            bib_data = parse_bibtex(entry.bibtex)
            if 'authors' in bib_data and isinstance(bib_data['authors'], list):
                authors = bib_data['authors']
            elif 'author' in bib_data:
                authors = [a.strip() for a in re.split(r'\s+and\s+', bib_data['author']) if a.strip()]
        except Exception:
            authors = []
            bibtex_error = True

    return {
        "id": entry.id,
        "title": entry.title,
        "raw_text": entry.raw_text,
        "venue": entry.venue,
        "year": entry.year,
        "doi": entry.doi,
        "url": entry.url,
        "bibtex": entry.bibtex,
        "bibtex_error": bibtex_error,
        "created_at": entry.created_at,
        "publication_type": entry.publication_type,
        "authors": authors
    }

class ScrapingRequest(BaseModel):
    url: HttpUrl

def compute_content_hash(text: str) -> str:
    """Return a stable SHA-256 hex digest of the normalised raw text."""
    normalised = " ".join(text.split()).lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _title_hash(title: str) -> str | None:
    """SHA-256 of the normalised title; None if title is empty."""
    n = normalize_title(title)
    if not n:
        return None
    return hashlib.sha256(n.encode("utf-8")).hexdigest()


def upsert_fingerprint(db: Session, source_table: str, source_id: int,
                       title: str | None, doi: str | None) -> None:
    """Insert or update a PublicationFingerprint row for the given source row."""
    from ..models.models import PublicationFingerprint
    clean_doi = doi.strip() if doi and doi.strip() else None
    th = _title_hash(title) if title else None
    fp = db.query(PublicationFingerprint).filter_by(
        source_table=source_table, source_id=source_id
    ).first()
    if fp:
        fp.doi = clean_doi
        fp.title_hash = th
        fp.title = title
    else:
        db.add(PublicationFingerprint(
            source_table=source_table,
            source_id=source_id,
            doi=clean_doi,
            title_hash=th,
            title=title,
        ))


def delete_fingerprint(db: Session, source_table: str, source_id: int) -> None:
    """Remove the fingerprint row for a deleted source row."""
    from ..models.models import PublicationFingerprint
    db.query(PublicationFingerprint).filter_by(
        source_table=source_table, source_id=source_id
    ).delete()

def get_normalized_start(text: str) -> str:
    """Get the first 80 characters of text, normalized to only alphabetical characters"""
    import re
    # Convert to lowercase and remove all non-alphabetical characters
    text = text.lower()
    text = re.sub(r'[^a-z]', '', text)
    return text[:80]

def normalize_title(title: str) -> str:
    """Normalize a title for comparison by removing special characters, lowercasing, and removing extra whitespace"""
    import re
    if not title:
        return ""
    # Convert to lowercase
    title = title.lower()
    # Remove special characters but keep spaces
    title = re.sub(r'[^\w\s]', '', title)
    # Remove extra whitespace
    title = ' '.join(title.split())
    return title

def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity ratio between two strings using a simple character-based approach"""
    if not str1 or not str2:
        return 0.0
    
    str1 = str1.lower()
    str2 = str2.lower()
    
    # Simple Jaccard similarity on character bigrams
    def get_bigrams(s):
        return set(s[i:i+2] for i in range(len(s)-1))
    
    bigrams1 = get_bigrams(str1)
    bigrams2 = get_bigrams(str2)
    
    if not bigrams1 or not bigrams2:
        return 1.0 if str1 == str2 else 0.0
    
    intersection = len(bigrams1 & bigrams2)
    union = len(bigrams1 | bigrams2)
    
    return intersection / union if union > 0 else 0.0

def extract_title_from_raw_text(raw_text: str) -> str:
    """Extract likely title from raw text - usually the first line or first sentence"""
    if not raw_text:
        return ""
    
    # Try to get first line
    lines = raw_text.strip().split('\n')
    if lines:
        first_line = lines[0].strip()
        # If first line is very short, it might be authors, try to get more context
        if len(first_line) > 20:
            return first_line
    
    # Fallback: get first 200 characters
    return raw_text[:200].strip()

def _main_pub_has_missing_fields(pub: Publication) -> bool:
    """Return True if the main publication is missing any enrichable field."""
    return not all([pub.venue, pub.doi, pub.url, pub.abstract])


def check_duplicate_publication(db: Session, raw_text: str, user_id: int) -> tuple[bool, Publication | None, bool]:
    """
    Check if a publication already exists using the fingerprints table (fast indexed lookups),
    with a similarity-scan fallback for near-duplicates not yet fingerprinted.

    Returns (is_duplicate, existing_publication, can_upgrade)
      - is_duplicate   : True when a match is found
      - existing_publication: the matched Publication row, or None
      - can_upgrade    : True when main-DB match has missing fields — caller should
                         still run LLM so the richer version surfaces in the UI
    """
    from ..models.models import ScrapedPublication, PublicationFingerprint

    potential_title = extract_title_from_raw_text(raw_text)
    normalized_potential = normalize_title(potential_title)
    if not normalized_potential:
        return False, None, False

    th = _title_hash(potential_title)

    # ── Fast path 1: title hash lookup in fingerprints table ─────────────────
    if th:
        fp = db.query(PublicationFingerprint).filter(
            PublicationFingerprint.title_hash == th
        ).first()
        if fp:
            if fp.source_table == "publications":
                pub = db.query(Publication).filter(Publication.id == fp.source_id).first()
                if pub:
                    return True, pub, _main_pub_has_missing_fields(pub)
            else:
                return True, None, False

    # ── Fast path 2: DOI lookup (extract DOI from raw_text heuristically) ────
    doi_match = re.search(r'10\.\d{4,}/\S+', raw_text)
    if doi_match:
        candidate_doi = doi_match.group(0).rstrip('.')
        fp = db.query(PublicationFingerprint).filter(
            PublicationFingerprint.doi == candidate_doi
        ).first()
        if fp:
            if fp.source_table == "publications":
                pub = db.query(Publication).filter(Publication.id == fp.source_id).first()
                if pub:
                    return True, pub, _main_pub_has_missing_fields(pub)
            else:
                return True, None, False

    # ── Fallback: similarity scan against all fingerprints ───────────────────
    # Only reaches here for entries not yet in the fingerprints table or with
    # slightly different titles than previously recorded.
    all_fps = db.query(PublicationFingerprint).all()
    for fp in all_fps:
        if not fp.title:
            continue
        fp_normalized = normalize_title(fp.title)
        if fp_normalized and calculate_similarity(fp_normalized, normalized_potential) > 0.85:
            if fp.source_table == "publications":
                pub = db.query(Publication).filter(Publication.id == fp.source_id).first()
                if pub:
                    return True, pub, _main_pub_has_missing_fields(pub)
            else:
                return True, None, False

    # ── Legacy fallback: normalised-start check ───────────────────────────────
    normalized_text = get_normalized_start(raw_text)
    for fp in all_fps:
        if fp.title and get_normalized_start(fp.title) == normalized_text:
            if fp.source_table == "publications":
                pub = db.query(Publication).filter(Publication.id == fp.source_id).first()
                if pub:
                    return True, pub, _main_pub_has_missing_fields(pub)
            else:
                return True, None, False

    return False, None, False


def get_entry_status(processed_value):
    if processed_value == 1:
        return "processed"
    elif processed_value == 2:
        return "duplicate"
    elif processed_value == -1:
        return "error"
    else:
        return "processing"

@router.get("/history", response_model=list)
async def get_scraping_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 200,
    search: str = "",
    status: str = "",
):
    """Get the history of scraping operations"""
    query = db.query(CurrentEntry).filter(CurrentEntry.created_by == current_user.id)

    if status:
        status_map = {"processed": 1, "duplicate": 2, "error": -1, "processing": 0}
        if status in status_map:
            query = query.filter(CurrentEntry.processed == status_map[status])

    entries = query.order_by(CurrentEntry.created_at.desc()).limit(limit).all()

    results = []
    search_lower = search.lower() if search else ""
    for entry in entries:
        title = extract_title_from_raw_text(entry.raw_text) if entry.raw_text else ""
        if search_lower and search_lower not in title.lower() and search_lower not in (entry.url or "").lower():
            continue
        results.append({
            "id": entry.id,
            "url": entry.url,
            "title": title,
            "batch_id": entry.batch_id,
            "status": get_entry_status(entry.processed),
            "bibtex": entry.bibtex,
            "created_at": entry.created_at,
            "processed_at": entry.processed_at,
        })
    return results

@router.delete("/history", response_model=dict)
async def delete_all_scraping_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete all scraping history entries (CurrentEntry rows) for the current user."""
    deleted = db.query(CurrentEntry).filter(
        CurrentEntry.created_by == current_user.id
    ).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}


@router.delete("/{entry_id}", response_model=DeleteResponse)
async def delete_scraping_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a scraping entry"""
    # Find the entry
    entry = db.query(CurrentEntry).filter(
        CurrentEntry.id == entry_id,
        CurrentEntry.created_by == current_user.id
    ).first()
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found"
        )
    
    # Delete the entry
    db.delete(entry)
    db.commit()
    
    return {
        "message": "Entry deleted successfully",
        "id": entry_id
    }

async def process_single_publication(db: Session, entry: CurrentEntry, batch_id: str):
    """Process a single publication and update its status"""
    try:
        # Check for existing publication with improved duplicate detection
        is_duplicate, existing_publication, can_upgrade = check_duplicate_publication(db, entry.raw_text, entry.created_by)

        if is_duplicate and not can_upgrade:
            # Exact duplicate with nothing new — skip
            entry.processed = 2  # Status for duplicates
            entry.processed_at = datetime.utcnow()
            if existing_publication:
                entry.bibtex = existing_publication.bibtex
            db.commit()
            print(f"[DUPLICATE] id={entry.id} title={entry.raw_text[:80]!r}")
        else:
            if can_upgrade:
                print(f"[UPGRADE] id={entry.id} — main DB entry is missing fields, processing for update")
            # Not a duplicate, proceed with text-to-bibtex conversion
            await asyncio.sleep(0.5)
            bibtex = text_to_bibtex(entry.raw_text)
            
            # Update entry with the new bibtex
            entry.bibtex = bibtex
            entry.processed = 1
            entry.processed_at = datetime.utcnow()

            # Process the BibTeX to extract publication data
            from ..models.models import ScrapedPublication
            content_hash = entry.content_hash or compute_content_hash(entry.raw_text)
            try:
                pub_data = parse_bibtex(bibtex)
                # Create new scraped publication with processed data
                new_scraped = ScrapedPublication(
                    title=pub_data["title"],
                    venue=pub_data["venue"],
                    year=pub_data["year"],
                    doi=pub_data["doi"],
                    url=pub_data["url"],
                    bibtex=bibtex,
                    raw_text=entry.raw_text,
                    content_hash=content_hash,
                    user_id=entry.created_by,
                    publication_type=pub_data["publication_type"]
                )
            except Exception as e:
                print(f"Error processing BibTeX: {str(e)}")
                # Fallback to using raw text if BibTeX processing fails
                first_line = entry.raw_text.split('\n')[0].strip()[:255]
                new_scraped = ScrapedPublication(
                    title=first_line,
                    bibtex=bibtex,
                    raw_text=entry.raw_text,
                    content_hash=content_hash,
                    user_id=entry.created_by
                )
            db.add(new_scraped)
            db.flush()
            upsert_fingerprint(db, "scraped_publications", new_scraped.id, new_scraped.title, new_scraped.doi)
            db.commit()
    except Exception as e:
        print(f"Error processing publication: {str(e)}")
        entry.processed = -1
        entry.bibtex = str(e)
        db.commit()

async def process_scraped_content(db: Session, source_url: str, current_user_id: int, publications_list: list, batch_id: str):
    """Process scraped content and convert to BibTeX"""
    try:
        from ..models.database import SessionLocal
        # Create new database session for this background task
        db = SessionLocal()
        total_count = len(publications_list)
        
        try:
            # Create CurrentEntry rows for all publications, storing their content hash
            entries = []
            for publication_text in publications_list:
                h = compute_content_hash(publication_text)
                entry = CurrentEntry(
                    url=source_url,
                    raw_text=publication_text,
                    created_by=current_user_id,
                    processed=0,
                    content_hash=h,
                    batch_id=batch_id
                )
                db.add(entry)
                entries.append(entry)
            db.commit()

            # Process publications in smaller chunks to avoid blocking
            chunk_size = 5  # Process 5 publications at a time
            for i in range(0, len(entries), chunk_size):
                chunk = entries[i:i + chunk_size]
                for entry in chunk:
                    await process_single_publication(db, entry, batch_id)
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"Error in batch processing: {str(e)}")
        finally:
            db.close()
    except Exception as e:
        print(f"Critical error in processing: {str(e)}")

MCML_URLS = {
    'seidl': 'https://mcml.ai/research/groups/seidl/',
    'tresp': 'https://mcml.ai/research/groups/tresp/',
    'schubert': 'https://mcml.ai/research/groups/schubert/',
    'paradies': 'https://mcml.ai/research/groups/paradies/'
}

def scrape_website(url: str):
    """Scrape website content using MCML specific scraping logic"""
    try:
        print(f"\n[SCRAPER] Starting to scrape URL: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        print(f"[SCRAPER] Successfully fetched content from {url}")
        # Get the raw HTML content and ensure proper encoding
        html_content = response.content.decode('utf-8', errors='replace')
        # Parse the HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        publications = []
        
        # Find the publications section - try new structure first (h2 "Publications @MCML"),
        # then fall back to old structure (div id="publications")
        print(f"[SCRAPER] Looking for publications section in {url}")
        pub_anchor_div = None

        # New structure: h2 heading "Publications @MCML" inside a div.row
        for h2 in soup.find_all("h2"):
            if "Publications" in h2.get_text():
                pub_anchor_div = h2.parent  # the div.row containing the heading
                print(f"[SCRAPER] Found publications via h2 heading (new structure)")
                break

        # Old structure fallback: div id="publications"
        if not pub_anchor_div:
            pub_anchor_div = soup.find("div", id="publications")
            if pub_anchor_div:
                print(f"[SCRAPER] Found publications via div#publications (old structure)")

        if not pub_anchor_div:
            print(f"[SCRAPER] !! No publications section found in {url}")
        if pub_anchor_div:
            print(f"[SCRAPER] Found publications anchor, looking for entries...")
            publications_found = 0
            next_div = pub_anchor_div.find_next_sibling("div")
            print(f"[SCRAPER] Next sibling div found: {next_div is not None}")
            while next_div:
                inner_divs = next_div.find_all("div")
                if len(inner_divs) >= 2:
                    second_div = inner_divs[1]
                    # Extract DOI link before removing/stripping anything
                    doi_url = None
                    doi_anchor = second_div.find("a", title="DOI")
                    if doi_anchor and doi_anchor.get("href"):
                        doi_url = doi_anchor["href"].strip()
                    # Remove details tags as they contain additional info we don't need
                    for details_tag in second_div.find_all("details"):
                        details_tag.decompose()
                    publication_text = second_div.get_text().replace('\n', ' ').strip()
                    # Remove bullet characters and similar symbols
                    for char in ['•', '●', '▪', '‣', '◦', '–', '—', '*']:
                        publication_text = publication_text.replace(char, ' and ')
                    publication_text = publication_text.strip()
                    # Append DOI URL so downstream processing can extract it
                    if doi_url:
                        publication_text = f"{publication_text} DOI: {doi_url}"
                    if publication_text:  # Only add non-empty publications
                        publications_found += 1
                        print(f"[SCRAPER] Found publication {publications_found}: {publication_text[:100]}...")
                        publications.append(publication_text)
                    else:
                        print("[SCRAPER] No text found in this div")
                next_div = next_div.find_next_sibling("div")
            
            print(f"[SCRAPER] Found a total of {len(publications)} publications in {url}")
            return publications if publications else []
        
        # Fallback to general content if not MCML structure
        
        print(f"No content found in {url}")
        return []

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to scrape website: {str(e)}"
        )

@router.post("/mcml", response_model=dict)
async def scrape_mcml(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected endpoint to scrape all MCML websites"""
    
    # Initialize results list
    results = []
    batch_id = f"mcml-{int(time.time() * 1000)}"

    # Build a set of hashes already seen (CurrentEntry + ScrapedPublication) to skip known content
    from ..models.models import ScrapedPublication
    existing_hashes = {
        r[0] for r in db.query(CurrentEntry.content_hash).filter(CurrentEntry.content_hash.isnot(None)).all()
    } | {
        r[0] for r in db.query(ScrapedPublication.content_hash).filter(ScrapedPublication.content_hash.isnot(None)).all()
    }

    # Loop through each group and scrape their publications
    total_publications = 0
    print("\n[MCML] ==========================================================")
    print("[MCML] Starting scraping of all MCML group publications")
    print("[MCML] ==========================================================\n")

    for group, url in MCML_URLS.items():
        print(f"[MCML] Processing group {group} at URL: {url}")

        publications = scrape_website(url)
        group_count = len(publications)
        print(f"[MCML] Found {group_count} publications for group {group}")
        print("[MCML] ----------------------------------------------------------")

        # Filter to only publications whose content hash has not been seen before
        new_publications = []
        for pub in publications:
            h = compute_content_hash(pub)
            if h not in existing_hashes:
                new_publications.append((pub, h))
                existing_hashes.add(h)  # prevent duplicates within the same batch

        skipped = group_count - len(new_publications)
        total_publications += len(new_publications)
        print(f"[MCML] {len(new_publications)} new, {skipped} already seen for group {group}")

        if new_publications:
            results.append({
                "group": group,
                "status": "processing",
                "url": url,
                "publications_found": group_count,
                "new_publications": len(new_publications),
            })
            # Pass only the raw texts to the background task (hashes are recomputed there)
            background_tasks.add_task(
                process_scraped_content,
                db=db,
                source_url=url,
                current_user_id=current_user.id,
                publications_list=[pub for pub, _ in new_publications],
                batch_id=batch_id,
            )
        else:
            results.append({
                "group": group,
                "status": "no_new_publications",
                "url": url,
                "publications_found": group_count,
                "new_publications": 0,
            })

    print("\n[MCML] ==========================================================")
    print(f"[MCML] SCRAPING SUMMARY: {total_publications} new publications queued")
    print("[MCML] ==========================================================\n")

    return {
        "results": results,
        "batch_id": batch_id,
        "total_publications": total_publications
    }

@router.post("/", response_model=ScrapingResponse)
async def start_scraping(
    request: ScrapingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected endpoint to start scraping and processing"""
    
    # Check if URL already exists
    existing_entry = db.query(CurrentEntry).filter(CurrentEntry.url == str(request.url)).first()
    if existing_entry:
        return {
            "message": "URL already processed",
            "status": "exists",
            "entry_id": existing_entry.id
        }
    
    # Create new entry
    new_entry = CurrentEntry(
        url=str(request.url),
        created_by=current_user.id,
        processed=0
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    
    batch_id = f"custom-{int(time.time() * 1000)}"
    
    try:
        # Scrape content
        publications = scrape_website(str(request.url))
        
        if publications:
            # Process all publications in background
            background_tasks.add_task(
                process_scraped_content,
                db=db,
                source_url=str(request.url),
                current_user_id=current_user.id,
                publications_list=publications,
                batch_id=batch_id
            )
        
    except Exception as e:
        print(f"Error in scraping: {str(e)}")
    return {
        "message": "Scraping started",
        "status": "processing",
        "url": str(request.url),
        "batch_id": batch_id
    }

@router.get("/{entry_id}", response_model=dict)
async def get_scraping_status(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the status and results of a scraping operation"""
    entry = db.query(CurrentEntry).filter(CurrentEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found"
        )
    
    return {
        "id": entry.id,
        "url": entry.url,
        "status": "processed" if entry.processed else "processing",
        "bibtex": entry.bibtex if entry.processed else None,
        "created_at": entry.created_at,
        "processed_at": entry.processed_at
    }

@router.get("/batch/{batch_id}", response_model=dict)
async def get_batch_entries(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all entries for a specific batch"""
    entries = db.query(CurrentEntry).filter(
        CurrentEntry.batch_id == batch_id,
        CurrentEntry.created_by == current_user.id
    ).all()

    if not entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No entries found for this batch"
        )

    # Get total and processed counts
    total = len(entries)
    processed = len([e for e in entries if e.processed != 0])
    
    # Format entries
    formatted_entries = [{
        "id": e.id,
        "status": get_entry_status(e.processed),
        "created_at": e.created_at,
        "processed_at": e.processed_at,
        "url": e.url,
        "bibtex": e.bibtex if e.processed == 1 else None,
        "error": e.bibtex if e.processed == -1 else None
    } for e in entries]

    return {
        "total": total,
        "processed": processed,
        "progress": (processed / total) * 100 if total > 0 else 0,
        "entries": formatted_entries
    }
