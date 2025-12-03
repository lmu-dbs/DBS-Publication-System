from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import sys
import os
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

@router.get("/scraped", response_model=list)
async def get_scraped_publications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all scraped publications for the current user that are not already in the main database"""
    entries = db.query(ScrapedPublication).filter(ScrapedPublication.user_id == current_user.id).order_by(ScrapedPublication.created_at.desc()).all()
    
    # Get all main publications for comparison
    main_publications = db.query(Publication).all()
    
    result = []
    
    for entry in entries:
        # Check if this scraped publication matches any main publication
        is_in_main_db = False
        
        if entry.title:
            entry_normalized = normalize_title(entry.title)
            
            # Check against all main publications
            for main_pub in main_publications:
                if main_pub.title:
                    main_normalized = normalize_title(main_pub.title)
                    
                    # Exact match
                    if entry_normalized and main_normalized and entry_normalized == main_normalized:
                        is_in_main_db = True
                        print(f"[SCRAPED VIEW] Exact match found - Skipping: {entry.title}")
                        break
                    
                    # High similarity match
                    if entry_normalized and main_normalized:
                        similarity = calculate_similarity(entry_normalized, main_normalized)
                        if similarity > 0.85:
                            is_in_main_db = True
                            print(f"[SCRAPED VIEW] High similarity match ({similarity:.2f}) - Skipping: {entry.title}")
                            break
        
        # Skip if found in main database
        if is_in_main_db:
            continue
        
        # Try to extract authors from BibTeX
        authors = []
        bibtex_error = False
        if entry.bibtex:
            try:
                bib_data = parse_bibtex(entry.bibtex)
                # parse_bibtex may return either an 'authors' list or an 'author' string
                if 'authors' in bib_data and isinstance(bib_data['authors'], list):
                    authors = bib_data['authors']
                elif 'author' in bib_data:
                    # Split authors by 'and' and clean up
                    authors = [a.strip() for a in re.split(r'\s+and\s+', bib_data['author']) if a.strip()]
            except Exception as e:
                authors = []
                bibtex_error = True
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
            "authors": authors
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
    
    # Filter out entries already in main database (same logic as get_scraped_publications)
    main_publications = db.query(Publication).all()
    filtered_entries = []
    
    for entry in entries:
        is_in_main_db = False
        
        if entry.title:
            entry_normalized = normalize_title(entry.title)
            
            for main_pub in main_publications:
                if main_pub.title:
                    main_normalized = normalize_title(main_pub.title)
                    
                    if entry_normalized and main_normalized and entry_normalized == main_normalized:
                        is_in_main_db = True
                        break
                    
                    if entry_normalized and main_normalized:
                        similarity = calculate_similarity(entry_normalized, main_normalized)
                        if similarity > 0.85:
                            is_in_main_db = True
                            break
        
        if not is_in_main_db:
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

def check_duplicate_publication(db: Session, raw_text: str, user_id: int) -> tuple[bool, Publication | None]:
    """
    Check if a publication already exists in the database (both main publications and scraped publications).
    Returns (is_duplicate, existing_publication)
    Uses multiple comparison strategies for better accuracy.
    """
    from ..models.models import ScrapedPublication
    
    # Extract likely title from raw text
    potential_title = extract_title_from_raw_text(raw_text)
    normalized_potential = normalize_title(potential_title)
    
    if not normalized_potential:
        return False, None
    
    # Query all publications (both main and scraped)
    publications = db.query(Publication).all()
    scraped_publications = db.query(ScrapedPublication).filter(ScrapedPublication.user_id == user_id).all()
    
    # Strategy 1: Exact normalized title match
    # Check main publications
    for pub in publications:
        if pub.title:
            normalized_existing = normalize_title(pub.title)
            if normalized_existing and normalized_existing == normalized_potential:
                print(f"[DUPLICATE] Exact title match found in main publications: {pub.title}")
                return True, pub
    
    # Check scraped publications
    for scraped in scraped_publications:
        if scraped.title:
            normalized_existing = normalize_title(scraped.title)
            if normalized_existing and normalized_existing == normalized_potential:
                print(f"[DUPLICATE] Exact title match found in scraped publications: {scraped.title}")
                return True, None  # Return None since it's a ScrapedPublication, not Publication
        # Also check raw_text similarity for scraped publications
        if scraped.raw_text:
            scraped_title = extract_title_from_raw_text(scraped.raw_text)
            normalized_scraped = normalize_title(scraped_title)
            if normalized_scraped and normalized_scraped == normalized_potential:
                print(f"[DUPLICATE] Exact raw text match found in scraped publications")
                return True, None
    
    # Strategy 2: High similarity match (>0.85)
    # Check main publications
    for pub in publications:
        if pub.title:
            normalized_existing = normalize_title(pub.title)
            if normalized_existing:
                similarity = calculate_similarity(normalized_existing, normalized_potential)
                if similarity > 0.85:
                    print(f"[DUPLICATE] High similarity match ({similarity:.2f}) in main publications: {pub.title}")
                    return True, pub
    
    # Check scraped publications
    for scraped in scraped_publications:
        if scraped.title:
            normalized_existing = normalize_title(scraped.title)
            if normalized_existing:
                similarity = calculate_similarity(normalized_existing, normalized_potential)
                if similarity > 0.85:
                    print(f"[DUPLICATE] High similarity match ({similarity:.2f}) in scraped publications: {scraped.title}")
                    return True, None
        # Also check raw_text similarity
        if scraped.raw_text:
            scraped_title = extract_title_from_raw_text(scraped.raw_text)
            normalized_scraped = normalize_title(scraped_title)
            if normalized_scraped:
                similarity = calculate_similarity(normalized_scraped, normalized_potential)
                if similarity > 0.85:
                    print(f"[DUPLICATE] High similarity match ({similarity:.2f}) in scraped publications (raw text)")
                    return True, None
    
    # Strategy 3: Check using old method as fallback
    normalized_text = get_normalized_start(raw_text)
    for pub in publications:
        if pub.title and get_normalized_start(pub.title) == normalized_text:
            print(f"[DUPLICATE] Normalized start match found in main publications: {pub.title}")
            return True, pub
    
    for scraped in scraped_publications:
        if scraped.raw_text and get_normalized_start(scraped.raw_text) == normalized_text:
            print(f"[DUPLICATE] Normalized start match found in scraped publications")
            return True, None
    
    return False, None

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
    limit: int = 10
):
    """Get the history of scraping operations"""
    entries = db.query(CurrentEntry)\
        .filter(CurrentEntry.created_by == current_user.id)\
        .order_by(CurrentEntry.created_at.desc())\
        .limit(limit)\
        .all()
    
    return [{
        "id": entry.id,
        "url": entry.url,
        "status": get_entry_status(entry.processed),
        "bibtex": entry.bibtex,
        "created_at": entry.created_at,
        "processed_at": entry.processed_at
    } for entry in entries]

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
        is_duplicate, existing_publication = check_duplicate_publication(db, entry.raw_text, entry.created_by)
        
        if is_duplicate:
            # Mark as duplicate
            entry.processed = 2  # Status for duplicates
            entry.processed_at = datetime.utcnow()
            if existing_publication:
                entry.bibtex = existing_publication.bibtex  # Store the existing bibtex if available
            db.commit()
            print(f"[SKIPPED] Duplicate publication detected, skipping processing")
        else:
            # Not a duplicate, proceed with text-to-bibtex conversion
            bibtex = text_to_bibtex(entry.raw_text)
            
            # Update entry with the new bibtex
            entry.bibtex = bibtex
            entry.processed = 1
            entry.processed_at = datetime.utcnow()
            
            # Process the BibTeX to extract publication data
            from ..models.models import ScrapedPublication
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
                    user_id=entry.created_by
                )
            db.add(new_scraped)
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
            # Create entries for all publications first
            entries = []
            for publication_text in publications_list:
                entry = CurrentEntry(
                    url=source_url,
                    raw_text=publication_text,
                    created_by=current_user_id,
                    processed=0,
                    batch_id=batch_id
                )
                db.add(entry)
                entries.append(entry)
            db.commit()
            
            # Process publications in smaller chunks to avoid blocking
            chunk_size = 5  # Process 5 publications at a time
            for i in range(0, len(entries), chunk_size):
                chunk = entries[i:i + chunk_size]
                # Process each publication in the chunk
                for entry in chunk:
                    await process_single_publication(db, entry, batch_id)
                # Small delay between chunks to allow other requests
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
        
        # Find the publications div and traverse through siblings
        print(f"[SCRAPER] Looking for publications div in {url}")
        publication_div = soup.find("div", id="publications")
        if not publication_div:
            print(f"[SCRAPER] !! No publications div found in {url}")
        if publication_div:
            print(f"[SCRAPER] Found publications div, looking for entries...")
            publications_found = 0
            print("[SCRAPER] Looking at publication div structure:")
            next_div = publication_div.find_next_sibling("div")
            print(f"[SCRAPER] Next sibling div found: {next_div is not None}")
            while next_div:
                inner_divs = next_div.find_all("div")
                if len(inner_divs) >= 2:
                    second_div = inner_divs[1]
                    # Remove details tags as they contain additional info we don't need
                    for details_tag in second_div.find_all("details"):
                        details_tag.decompose()
                    publication_text = second_div.get_text().replace('\n', ' ').strip()
                    # Remove bullet characters and similar symbols
                    for char in ['•', '●', '▪', '‣', '◦', '–', '—', '*']:
                        publication_text = publication_text.replace(char, ' and ')
                    publication_text = publication_text.strip()
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
    
    # Loop through each group and scrape their publications
    total_publications = 0
    print("\n[MCML] ==========================================================")
    print("[MCML] Starting scraping of all MCML group publications")
    print("[MCML] ==========================================================\n")
    
    for group, url in MCML_URLS.items():
        print(f"[MCML] Processing group {group} at URL: {url}")
        
        # Scrape publications first to see if we get any
        publications = scrape_website(url)
        group_count = len(publications)
        total_publications += group_count
        print(f"[MCML] Found {group_count} publications for group {group}")
        print("[MCML] ----------------------------------------------------------")
        
        # If we found publications, then proceed with database operations
        if publications:
            # Check if URL already exists and delete all entries with this URL
            existing_entries = db.query(CurrentEntry).filter(CurrentEntry.url == url).all()
            if existing_entries:
                print(f"[MCML] Found {len(existing_entries)} existing entries for {url}, deleting them...")
                for entry in existing_entries:
                    db.delete(entry)
                db.commit()
            
            # Create new entry for each publication
            for pub in publications:
                new_entry = CurrentEntry(
                    url=url,
                    raw_text=pub,
                    created_by=current_user.id,
                    processed=0,
                    batch_id=batch_id
                )
                db.add(new_entry)
                db.commit()
                db.refresh(new_entry)
                
                print(f"Created entry {new_entry.id} with publication text: {pub[:100]}...")
            
            results.append({
                "group": group,
                "status": "processing",
                "url": url,
                "publications_found": len(publications)
            })
        else:
            results.append({
                "group": group,
                "status": "no_publications",
                "url": url,
                "publications_found": 0
            })
        
        # Process publications in background
        background_tasks.add_task(
            process_scraped_content,
            db=db,
            source_url=url,
            current_user_id=current_user.id,
            publications_list=publications,  # Use already scraped publications
            batch_id=batch_id
        )
    
    print("\n[MCML] ==========================================================")
    print(f"[MCML] SCRAPING SUMMARY:")
    print(f"[MCML] Total publications found across all groups: {total_publications}")
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
