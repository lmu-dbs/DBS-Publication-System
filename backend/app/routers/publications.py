from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
import json
from datetime import datetime

from ..models.database import get_db
from ..models.models import Publication, Author, User, PublicationAuthor
from ..schemas.schemas import (
    Publication as PublicationSchema,
    PublicationCreate,
    PublicationUpdate,
    Author as AuthorSchema,
    AuthorCreate,
    BibTexImport
)
from ..auth.auth import get_current_active_user
from ..utils.bibtex_processor import parse_bibtex, generate_bibtex, batch_process_bibtex, get_existing_author, parse_author_name

router = APIRouter(
    prefix="/publications",
    tags=["publications"],
)


@router.delete("/scraped", status_code=204)
def delete_scraped_publications(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Delete all publications flagged as scraped."""
    scraped_pubs = db.query(Publication).filter(Publication.is_scraped == True).all()
    for pub in scraped_pubs:
        db.delete(pub)
    db.commit()
    return None

# Get all publications with optional author filter
@router.get("/", response_model=List[PublicationSchema])
def get_publications(
    db: Session = Depends(get_db),
    author_id: Optional[int] = None,
    search: Optional[str] = None,
    venue: Optional[str] = None,
    year: Optional[int] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 1500
):
    query = db.query(Publication)
    
    # Filter by author if author_id is provided
    if author_id is not None:
        query = query.join(Publication.author_associations).filter(PublicationAuthor.author_id == author_id)
    
    # Search functionality
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Publication.title.ilike(search_term),
                Publication.abstract.ilike(search_term),
                Publication.venue.ilike(search_term),
                # Join with authors to search in author names
                Publication.author_associations.any(
                    PublicationAuthor.author.has(
                        Author.name.ilike(search_term)
                    )
                )
            )
        )
    
    # Filter by venue if provided
    if venue:
        venue_term = f"%{venue}%"
        query = query.filter(Publication.venue.ilike(venue_term))
    
    # Filter by year if provided
    if year:
        query = query.filter(Publication.year == year)
    
    # Filter by keyword if provided
    if keyword:
        keyword_term = f"%{keyword}%"
        query = query.filter(
            or_(
                Publication.title.ilike(keyword_term),
                Publication.abstract.ilike(keyword_term),
                Publication.venue.ilike(keyword_term),
                # Join with authors to search in author names
                Publication.author_associations.any(
                    PublicationAuthor.author.has(
                        Author.name.ilike(keyword_term)
                    )
                )
            )
        )
    
    return query.order_by(Publication.year.desc()).offset(skip).limit(limit).all()

# Get a specific publication by ID
@router.get("/{publication_id}", response_model=PublicationSchema)
def get_publication(publication_id: int, db: Session = Depends(get_db)):
    publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return publication

# Create a new publication
@router.post("/", response_model=PublicationSchema, status_code=status.HTTP_201_CREATED)
def create_publication(
    publication: PublicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Create new publication
    db_publication = Publication(
        title=publication.title,
        abstract=publication.abstract,
        year=publication.year,
        venue=publication.venue,
        publication_type=publication.publication_type,
        doi=publication.doi,
        url=publication.url,
        bibtex=publication.bibtex,
        user_id=current_user.id
    )
    
    db.add(db_publication)
    db.flush()  # Get the publication ID
    
    # Process authors with order preservation
    for position, author_data in enumerate(publication.authors):
        if isinstance(author_data, int):
            # Existing author ID
            author = db.query(Author).filter(Author.id == author_data).first()
            if not author:
                raise HTTPException(status_code=404, detail=f"Author with ID {author_data} not found")
        else:
            # New author
            author = db.query(Author).filter(Author.name == author_data.name).first()
            if not author:
                # Parse forename and lastname
                forename, lastname = parse_author_name(author_data.name)
                author = Author(
                    name=author_data.name,
                    forename=forename,
                    lastname=lastname,
                    email=author_data.email,
                    affiliation=author_data.affiliation
                )
                db.add(author)
                db.flush()  # Needed to get the ID before committing
        
        # Create the association with position
        author_assoc = PublicationAuthor(
            publication_id=db_publication.id,
            author_id=author.id,
            author_position=position
        )
        db.add(author_assoc)
    
    db.commit()
    db.refresh(db_publication)
    
    return db_publication

# Update a publication
@router.put("/{publication_id}", response_model=PublicationSchema)
def update_publication(
    publication_id: int,
    publication_update: PublicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if db_publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    # Check if the user is authorized to update this publication
    if db_publication.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this publication")
    
    # Update publication fields if provided
    update_data = publication_update.dict(exclude_unset=True)
    
    # Handle authors separately
    if "authors" in update_data:
        authors = update_data.pop("authors")
        if authors is not None:
            # Delete existing author associations
            db.query(PublicationAuthor).filter(
                PublicationAuthor.publication_id == publication_id
            ).delete()
            
            # Create new author associations with order
            for position, author_data in enumerate(authors):
                if isinstance(author_data, int):
                    # Existing author ID
                    author = db.query(Author).filter(Author.id == author_data).first()
                    if not author:
                        raise HTTPException(status_code=404, detail=f"Author with ID {author_data} not found")
                else:
                    # New author - author_data is now a dict, not an object
                    author = db.query(Author).filter(Author.name == author_data["name"]).first()
                    if not author:
                        # Parse forename and lastname
                        forename, lastname = parse_author_name(author_data["name"])
                        author = Author(
                            name=author_data["name"],
                            forename=forename,
                            lastname=lastname,
                            email=author_data.get("email"),
                            affiliation=author_data.get("affiliation")
                        )
                        db.add(author)
                        db.flush()
                
                # Create the association with position
                author_assoc = PublicationAuthor(
                    publication_id=publication_id,
                    author_id=author.id,
                    author_position=position
                )
                db.add(author_assoc)
    
    # Update other fields
    for key, value in update_data.items():
        setattr(db_publication, key, value)
    
    db_publication.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_publication)
    
    return db_publication

# Delete a publication
@router.delete("/{publication_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_publication(
    publication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if db_publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    # Check if the user is authorized to delete this publication
    if db_publication.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this publication")
    
    db.delete(db_publication)
    db.commit()
    
    return None

# Import publication from BibTeX
@router.post("/import-bibtex", response_model=PublicationSchema)
def import_bibtex(
    bibtex_data: BibTexImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        publication_data = parse_bibtex(bibtex_data.bibtex_string)
        
        # Check if publication with the same title and year already exists
        existing_pub = db.query(Publication).filter(
            Publication.title == publication_data["title"],
            Publication.year == publication_data["year"]
        ).first()
        
        if existing_pub:
            raise HTTPException(status_code=400, detail="A publication with this title and year already exists")
        
        # Get author names in the original order
        author_names = publication_data.pop("authors", [])
        
        # Create publication
        publication_data["user_id"] = current_user.id
        publication_data["bibtex"] = bibtex_data.bibtex_string
        
        db_publication = Publication(**publication_data)
        db.add(db_publication)
        db.flush()
        
        # Create authors with preserved order
        seen_authors = set()  # Track already added authors to avoid duplicates
        for position, author_name in enumerate(author_names):
            # Use the improved author matching function to find existing authors
            author = get_existing_author(db, author_name)
            
            # If no match was found, create a new author
            if not author:
                forename, lastname = parse_author_name(author_name)
                author = Author(
                    name=author_name,
                    forename=forename,
                    lastname=lastname
                )
                db.add(author)
                db.flush()
            
            # Skip if this author is already associated with this publication
            if author.id in seen_authors:
                continue
            
            # Add to seen authors
            seen_authors.add(author.id)
            
            # Create the association with position
            author_assoc = PublicationAuthor(
                publication_id=db_publication.id,
                author_id=author.id,
                author_position=position
            )
            db.add(author_assoc)
        
        db.commit()
        db.refresh(db_publication)
        
        return db_publication
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid BibTeX format: {str(e)}")

# Import publication from BibTeX file
@router.post("/import-bibtex-file")
async def import_bibtex_file(
    bibtex_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Read the file content
        content = await bibtex_file.read()
        
        # Decode content as string
        bibtex_content = content.decode("utf-8")
        
        # Process the BibTeX content
        publications_data, success_count, failed_count, duplicate_count, total_count, processor_failed_entries = batch_process_bibtex(bibtex_content)
        
        # Import successful entries
        processed_duplicate_count = 0
        processed_success_count = 0
        duplicate_entries = []  # Track duplicate entries
        failed_entries = processor_failed_entries.copy()  # Start with failed entries from the processor
        
        for pub_data in publications_data:
            try:
                # Check if publication with the same title and year already exists
                existing_pub = db.query(Publication).filter(
                    Publication.title == pub_data["title"],
                    Publication.year == pub_data["year"]
                ).first()
                
                if existing_pub:
                    processed_duplicate_count += 1
                    # Add detailed info about duplicate
                    duplicate_entries.append({
                        "title": pub_data["title"],
                        "year": pub_data["year"],
                        "authors": pub_data.get("authors", []),
                        "reason": "Entry with matching title and year already exists"
                    })
                    continue
                
                # Get author names
                author_names = pub_data.pop("authors", [])
                
                # Regenerate BibTeX with abbreviated author names to ensure consistency
                if author_names and pub_data.get("title") and pub_data.get("year"):
                    from ..utils.bibtex_processor import generate_bibtex
                    pub_data["bibtex"] = generate_bibtex(
                        title=pub_data["title"],
                        authors=author_names,
                        year=pub_data["year"],
                        venue=pub_data.get("venue", ""),
                        publication_type=pub_data.get("publication_type", "article"),
                        doi=pub_data.get("doi")
                    )
                
                # Create publication
                pub_data["user_id"] = current_user.id
                db_publication = Publication(**pub_data)
                db.add(db_publication)
                db.flush()
                
                # Create authors with preserved order
                seen_authors = set()  # Track already added authors to avoid duplicates
                for position, author_name in enumerate(author_names):
                    # Use the improved author matching function to find existing authors
                    author = get_existing_author(db, author_name)
                    
                    # If no match was found, create a new author
                    if not author:
                        forename, lastname = parse_author_name(author_name)
                        author = Author(
                            name=author_name,
                            forename=forename,
                            lastname=lastname
                        )
                        db.add(author)
                        db.flush()
                    
                    # Skip if this author is already associated with this publication
                    if author.id in seen_authors:
                        continue
                    
                    # Add to seen authors
                    seen_authors.add(author.id)
                    
                    # Create the association with position
                    author_assoc = PublicationAuthor(
                        publication_id=db_publication.id,
                        author_id=author.id,
                        author_position=position
                    )
                    db.add(author_assoc)
                
                processed_success_count += 1
                
            except Exception as e:
                # Log error but continue processing other entries
                error_msg = str(e)
                print(f"Error importing publication: {error_msg}")
                failed_count += 1
                
                # Try to get title and year for error reporting
                entry_info = {
                    "title": pub_data.get("title", "Unknown title"),
                    "year": pub_data.get("year", "Unknown year"),
                    "authors": pub_data.get("authors", []),
                    "reason": f"Import error: {error_msg}"
                }
                failed_entries.append(entry_info)
        
        # Commit all changes at once
        db.commit()
        
        # Return statistics and detailed entry information
        return {
            "message": "BibTeX file processed successfully",
            "success_count": processed_success_count,
            "failed_count": failed_count,
            "duplicate_count": processed_duplicate_count,
            "total_count": total_count,
            "duplicate_entries": duplicate_entries,
            "failed_entries": failed_entries
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing BibTeX file: {str(e)}")

# Export publication as BibTeX
@router.get("/{publication_id}/export-bibtex")
def export_bibtex(publication_id: int, db: Session = Depends(get_db)):
    publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    # If publication has stored BibTeX, return it
    if (publication.bibtex):
        return {"bibtex": publication.bibtex}
    
    # Otherwise, generate BibTeX from publication data
    try:
        # Get authors in the correct order using the property
        authors = [author.name for author in publication.authors]
        bibtex = generate_bibtex(
            publication.title,
            authors,
            publication.year,
            publication.venue,
            publication.publication_type,
            publication.doi
        )
        return {"bibtex": bibtex}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate BibTeX: {str(e)}")

# Export publications as JSON
@router.get("/bulk-exports/json")
def export_json(
    db: Session = Depends(get_db),
    author_id: Optional[int] = None,
    search: Optional[str] = None,
    venue: Optional[str] = None,
    year: Optional[int] = None,
    keyword: Optional[str] = None
):
    # Reuse the same query logic from get_publications
    query = db.query(Publication)
    
    if author_id is not None:
        query = query.join(Publication.author_associations).filter(PublicationAuthor.author_id == author_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Publication.title.ilike(search_term),
                Publication.abstract.ilike(search_term),
                Publication.venue.ilike(search_term),
                # Join with authors to search in author names
                Publication.author_associations.any(
                    PublicationAuthor.author.has(
                        Author.name.ilike(search_term)
                    )
                )
            )
        )
    
    # Filter by venue if provided
    if venue:
        venue_term = f"%{venue}%"
        query = query.filter(Publication.venue.ilike(venue_term))
    
    # Filter by year if provided
    if year:
        query = query.filter(Publication.year == year)
    
    # Filter by keyword if provided
    if keyword:
        keyword_term = f"%{keyword}%"
        query = query.filter(
            or_(
                Publication.title.ilike(keyword_term),
                Publication.abstract.ilike(keyword_term),
                Publication.venue.ilike(keyword_term),
                # Join with authors to search in author names
                Publication.author_associations.any(
                    PublicationAuthor.author.has(
                        Author.name.ilike(keyword_term)
                    )
                )
            )
        )
    
    publications = query.order_by(Publication.year.desc()).all()
    
    # Convert to a list of dictionaries
    result = []
    for pub in publications:
        pub_dict = {
            "id": pub.id,
            "title": pub.title,
            "abstract": pub.abstract,
            "year": pub.year,
            "venue": pub.venue,
            "publication_type": pub.publication_type,
            "doi": pub.doi,
            "url": pub.url,
            "authors": [{"id": author.id, "name": author.name, "affiliation": author.affiliation} for author in pub.authors]
        }
        result.append(pub_dict)
    
    return {"publications": result}

# Export publications as BibTeX
@router.get("/bulk-exports/bibtex")
def export_bibtex_list(
    db: Session = Depends(get_db),
    author_id: Optional[int] = None,
    search: Optional[str] = None,
    venue: Optional[str] = None,
    year: Optional[int] = None,
    keyword: Optional[str] = None
):
    # Reuse the same query logic from get_publications
    query = db.query(Publication)
    
    if author_id is not None:
        query = query.join(Publication.author_associations).filter(PublicationAuthor.author_id == author_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Publication.title.ilike(search_term),
                Publication.abstract.ilike(search_term),
                Publication.venue.ilike(search_term),
                # Join with authors to search in author names
                Publication.author_associations.any(
                    PublicationAuthor.author.has(
                        Author.name.ilike(search_term)
                    )
                )
            )
        )
    
    # Filter by venue if provided
    if venue:
        venue_term = f"%{venue}%"
        query = query.filter(Publication.venue.ilike(venue_term))
    
    # Filter by year if provided
    if year:
        query = query.filter(Publication.year == year)
    
    # Filter by keyword if provided
    if keyword:
        keyword_term = f"%{keyword}%"
        query = query.filter(
            or_(
                Publication.title.ilike(keyword_term),
                Publication.abstract.ilike(keyword_term),
                Publication.venue.ilike(keyword_term),
                # Join with authors to search in author names
                Publication.author_associations.any(
                    PublicationAuthor.author.has(
                        Author.name.ilike(keyword_term)
                    )
                )
            )
        )
    
    publications = query.order_by(Publication.year.desc()).all()
    
    # Generate BibTeX for all publications
    all_bibtex = ""
    
    for pub in publications:
        # If publication has stored BibTeX, use it
        if pub.bibtex:
            all_bibtex += pub.bibtex + "\n\n"
        else:
            # Otherwise, generate BibTeX from publication data
            try:
                # Get authors in the correct order
                authors = [author.name for author in pub.authors]
                bibtex = generate_bibtex(
                    pub.title,
                    authors,
                    pub.year,
                    pub.venue,
                    pub.publication_type,
                    pub.doi
                )
                all_bibtex += bibtex + "\n\n"
            except Exception as e:
                # Skip problematic entries but continue with the rest
                print(f"Error generating BibTeX for publication {pub.id}: {str(e)}")
    
    return {"bibtex": all_bibtex}