from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime

# Author schemas
class AuthorBase(BaseModel):
    name: str
    forename: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    affiliation: Optional[str] = None

class AuthorCreate(AuthorBase):
    pass

class Author(AuthorBase):
    id: int
    
    class Config:
        from_attributes = True

# Publication schemas
class PublicationBase(BaseModel):
    title: str
    abstract: Optional[str] = None
    year: int
    venue: Optional[str] = None
    publication_type: str
    doi: Optional[str] = None
    url: Optional[str] = None
    bibtex: Optional[str] = None

class PublicationCreate(PublicationBase):
    authors: List[Union[int, AuthorCreate]] = []  # Can be IDs of existing authors or new author objects

class PublicationUpdate(BaseModel):
    title: Optional[str] = None
    abstract: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    publication_type: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    bibtex: Optional[str] = None
    authors: Optional[List[Union[int, AuthorCreate]]] = None

class Publication(PublicationBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    authors: List[Author] = []
    user_id: int
    
    class Config:
        from_attributes = True

# User schemas
class UserBase(BaseModel):
    email: str
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# BibTeX import/export schema
class BibTexImport(BaseModel):
    bibtex_string: str

# Search schema
class SearchQuery(BaseModel):
    query: str = ""
    author_id: Optional[int] = None
