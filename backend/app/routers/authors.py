from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..models.database import get_db
from ..models.models import Author, PublicationAuthor
from ..schemas.schemas import AuthorResponse, AuthorUpdate, AuthorCreate
from ..auth.auth import get_current_user


router = APIRouter(
    prefix="/authors",
    tags=["authors"]
)


@router.get("/", response_model=List[AuthorResponse])
def get_all_authors(
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """
    Get all authors with their publication count
    """
    authors = db.query(Author).offset(skip).limit(limit).all()
    
    # Add publication count to each author
    result = []
    for author in authors:
        author_dict = {
            "id": author.id,
            "name": author.name,
            "forename": author.forename,
            "lastname": author.lastname,
            "email": author.email,
            "affiliation": author.affiliation,
            "publication_count": len(author.publication_associations)
        }
        result.append(author_dict)
    
    return result


@router.get("/{author_id}", response_model=AuthorResponse)
def get_author(
    author_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific author by ID
    """
    author = db.query(Author).filter(Author.id == author_id).first()
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    
    return {
        "id": author.id,
        "name": author.name,
        "forename": author.forename,
        "lastname": author.lastname,
        "email": author.email,
        "affiliation": author.affiliation,
        "publication_count": len(author.publication_associations)
    }


@router.put("/{author_id}", response_model=AuthorResponse)
def update_author(
    author_id: int,
    author_update: AuthorUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update an author's information (requires authentication)
    """
    author = db.query(Author).filter(Author.id == author_id).first()
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    
    # Update fields if provided
    update_data = author_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(author, field, value)
    
    # Update name if forename or lastname changed
    if author.forename and author.lastname:
        # Abbreviate forename to initials
        forename_parts = author.forename.split(' ')
        initials = ' '.join([part[0].upper() + '.' for part in forename_parts if part])
        author.name = f"{initials} {author.lastname}"
    
    db.commit()
    db.refresh(author)
    
    return {
        "id": author.id,
        "name": author.name,
        "forename": author.forename,
        "lastname": author.lastname,
        "email": author.email,
        "affiliation": author.affiliation,
        "publication_count": len(author.publication_associations)
    }


@router.delete("/{author_id}")
def delete_author(
    author_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete an author (requires authentication)
    Note: This will also remove the author from all publications
    """
    author = db.query(Author).filter(Author.id == author_id).first()
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    
    # Check if author has publications
    pub_count = len(author.publication_associations)
    
    db.delete(author)
    db.commit()
    
    return {
        "message": f"Author deleted successfully. Removed from {pub_count} publication(s)."
    }


@router.post("/merge")
def merge_authors(
    source_id: int,
    target_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Merge two authors: move all publications from source to target, then delete source
    """
    source = db.query(Author).filter(Author.id == source_id).first()
    target = db.query(Author).filter(Author.id == target_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source author not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target author not found")
    
    if source_id == target_id:
        raise HTTPException(status_code=400, detail="Cannot merge author with itself")
    
    # Move all publication associations from source to target
    moved_count = 0
    for assoc in source.publication_associations[:]:  # Create a copy of the list
        # Check if target already has this publication
        existing = db.query(PublicationAuthor).filter(
            PublicationAuthor.publication_id == assoc.publication_id,
            PublicationAuthor.author_id == target_id
        ).first()
        
        if not existing:
            # Update the association to point to target author
            assoc.author_id = target_id
            moved_count += 1
        else:
            # Target already has this publication, just delete the source association
            db.delete(assoc)
    
    # Delete source author
    db.delete(source)
    db.commit()
    
    return {
        "message": f"Successfully merged authors. Moved {moved_count} publication(s) from '{source.name}' to '{target.name}'.",
        "target_author_id": target_id
    }
