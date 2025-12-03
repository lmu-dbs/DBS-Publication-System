from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Association model for publications and authors (with order)
class PublicationAuthor(Base):
    __tablename__ = "publication_authors"
    
    publication_id = Column(Integer, ForeignKey("publications.id"), primary_key=True)
    author_id = Column(Integer, ForeignKey("authors.id"), primary_key=True)
    author_position = Column(Integer, nullable=False)  # To preserve author order
    
    # Relationships
    author = relationship("Author", back_populates="publication_associations")
    publication = relationship("Publication", back_populates="author_associations")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CurrentEntry(Base):
    __tablename__ = "current_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)
    raw_text = Column(Text)
    bibtex = Column(Text, nullable=True)
    processed = Column(Integer, default=0)  # 0=new, 1=processed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    batch_id = Column(String, nullable=True, index=True)


class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    forename = Column(String, nullable=True)
    lastname = Column(String, nullable=True, index=True)
    email = Column(String, nullable=True)
    affiliation = Column(String, nullable=True)
    
    # Relationship to publications through association model
    publication_associations = relationship(
        "PublicationAuthor",
        back_populates="author",
        cascade="all, delete-orphan"
    )
    
    # Convenience property to access publications
    @property
    def publications(self):
        return [assoc.publication for assoc in self.publication_associations]


class Publication(Base):
    is_scraped = Column(Boolean, default=False, nullable=False, index=True, comment="True if publication was scraped from the web")
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    abstract = Column(Text, nullable=True)
    year = Column(Integer, index=True, nullable=True)
    venue = Column(String, nullable=True)
    publication_type = Column(String, index=True, nullable=True, default='article')  # e.g., 'article', 'inproceedings', 'book'
    doi = Column(String, nullable=True)
    url = Column(String, nullable=True)
    bibtex = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to authors through association model
    author_associations = relationship(
        "PublicationAuthor",
        back_populates="publication",
        cascade="all, delete-orphan",
        order_by="PublicationAuthor.author_position"
    )
    
    # Convenience property to access authors in correct order
    @property
    def authors(self):
        return [assoc.author for assoc in self.author_associations]
    
    # Created by which user
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User")


# New model for storing scraped publications before approval
class ScrapedPublication(Base):
    __tablename__ = "scraped_publications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    abstract = Column(Text, nullable=True)
    year = Column(Integer, index=True, nullable=True)
    venue = Column(String, nullable=True)
    publication_type = Column(String, index=True, nullable=True, default='article')
    doi = Column(String, nullable=True)
    url = Column(String, nullable=True)
    bibtex = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Created by which user
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User")
