import re
import logging
from typing import Dict, List, Any, Tuple, Optional

# Only importing the parse_string function that we actually use
from pybtex.database import parse_string
import bibtexparser

from io import StringIO
from sqlalchemy.orm import Session

from ..models.models import Author


# Module logger
logger = logging.getLogger(__name__)


def parse_bibtex(bibtex_string: str) -> Dict[str, Any]:
    """
    Parse a BibTeX string and extract publication information.
    
    Args:
        bibtex_string: A string containing BibTeX data
        
    Returns:
        Dictionary with publication data
    """
    def _try_parse(s: str):
        return parse_string(s, 'bibtex')

    try:
        # Parse the BibTeX string
        bibliography = _try_parse(bibtex_string)
        
        if not bibliography.entries:
            raise ValueError("No entries found in BibTeX")
        
        # We only process the first entry if there are multiple
        entry_key = list(bibliography.entries.keys())[0]
        entry = bibliography.entries[entry_key]
        
        # Extract publication type
        publication_type = entry.type
        
        # Extract basic fields
        fields = entry.fields
        
        # Create a publication dict
        publication_data = {
            "title": fields.get("title", "").replace("{", "").replace("}", ""),
            "year": int(fields.get("year", 0)),
            "venue": fields.get("journal", fields.get("booktitle", "")),
            "publication_type": publication_type,
            "doi": fields.get("doi", ""),
            "url": fields.get("url", ""),
        }
        
        # Extract authors
        authors = []
        for person in entry.persons.get("author", []):
            # Combine name parts into a single string
            name = " ".join([" ".join(part) for part in (person.first(), person.middle(), person.last()) if part])
            authors.append(name)
        
        publication_data["authors"] = authors
        
        # Add abstract if available
        if "abstract" in fields:
            publication_data["abstract"] = fields["abstract"]
        
        return publication_data
    
    except Exception as e:
        # If parsing fails because the author list is comma-separated
        # (e.g. "Durani, W., Jahn, P., Seidl, T."), try a normalization
        # pass that converts sequences of "Last, F., Next, G., ..." into
        # "Last, F. and Next, G. and ..." which pybtex can parse.
        msg = str(e)
        try:
            if 'Too many commas' in msg or 'comma' in msg.lower() or 'author' in msg.lower():
                normalized = _normalize_author_commas(bibtex_string)
                if normalized != bibtex_string:
                    # Log that we attempted a normalization pass
                    logger.info("parse_bibtex: attempting author normalization due to parse error")
                    bibliography = _try_parse(normalized)
                    # If successful, continue with the normalized bibliography
                    # proceed as usual by extracting the first entry
                    entry_key = list(bibliography.entries.keys())[0]
                    entry = bibliography.entries[entry_key]

                    publication_type = entry.type
                    fields = entry.fields

                    publication_data = {
                        "title": fields.get("title", "").replace("{", "").replace("}", ""),
                        "year": int(fields.get("year", 0)),
                        "venue": fields.get("journal", fields.get("booktitle", "")),
                        "publication_type": publication_type,
                        "doi": fields.get("doi", ""),
                        "url": fields.get("url", ""),
                    }

                    authors = []
                    for person in entry.persons.get("author", []):
                        name = " ".join([" ".join(part) for part in (person.first(), person.middle(), person.last()) if part])
                        authors.append(name)

                    publication_data["authors"] = authors
                    if "abstract" in fields:
                        publication_data["abstract"] = fields["abstract"]

                    # Log successful parse after normalization for debugging
                    logger.info(
                        "parse_bibtex: successfully parsed after author normalization; title=%s, authors=%s",
                        publication_data.get("title"), publication_data.get("authors")
                    )
                    return publication_data
        except Exception:
            # fall through to raising the original error
            pass

        raise ValueError(f"Failed to parse BibTeX: {str(e)}")


def _normalize_author_commas(bibtex_string: str) -> str:
    """
    Normalize author fields which are given as a comma-separated list
    like "Durani, W., Jahn, P., Seidl, T." into a string that uses
    " and " between authors: "Durani, W. and Jahn, P. and Seidl, T.".

    This tries to be conservative: only rewrites author fields that
    do not already contain " and ".
    """
    def replace(match):
        prefix = match.group(1)
        authors_text = match.group(2).strip()
        suffix = match.group(3)

        # If it's already using ' and ' or semicolons, leave it
        if ' and ' in authors_text or ';' in authors_text:
            return match.group(0)

        # Split on comma and try to pair tokens into lastname + initials
        tokens = [t.strip() for t in re.split(r',\s*', authors_text) if t.strip()]
        # If we see an even number of tokens and at least 4 (i.e. 2+ authors),
        # assume tokens are [Last, Initials, Last, Initials, ...]
        if len(tokens) >= 4 and len(tokens) % 2 == 0:
            pairs = []
            for i in range(0, len(tokens), 2):
                lastname = tokens[i]
                initials = tokens[i+1]
                pairs.append(f"{lastname}, {initials}")
            new_authors = ' and '.join(pairs)
            logger.info("normalize_author_commas: original=%r normalized=%r", authors_text, new_authors)
            return f"{prefix}{new_authors}{suffix}"

        # If it's not the even-token pattern, try a heuristic: if many commas
        # but no 'and', replace the last few ", " between author groups with " and "
        # Split by comma sequences like '., ' which often terminate initials
        heuristic = re.split(r'(?<=\.),\s*', authors_text)
        if len(heuristic) > 1:
            cleaned = ' and '.join([h.strip() for h in heuristic if h.strip()])
            logger.info("normalize_author_commas (heuristic): original=%r normalized=%r", authors_text, cleaned)
            return f"{prefix}{cleaned}{suffix}"

        # Otherwise leave unchanged
        return match.group(0)

    # Match author = { ... } or author = "..."
    pattern = re.compile(r'(author\s*=\s*[\{\"])(.*?)([\}\"])', re.IGNORECASE | re.DOTALL)
    new = pattern.sub(replace, bibtex_string)
    return new


def generate_bibtex(title: str, authors: List[str], year: int, venue: str, 
                    publication_type: str, doi: str = None) -> str:
    """
    Generate a BibTeX entry from publication data.
    
    Args:
        title: Publication title
        authors: List of author names
        year: Publication year
        venue: Publication venue (journal, conference, etc.)
        publication_type: Type of publication (article, inproceedings, etc.)
        doi: Digital Object Identifier (optional)
        
    Returns:
        BibTeX string
    """
    # Create a citation key from first author's last name and year
    if authors:
        first_author = authors[0]
        # Extract last name
        last_name = first_author.split()[-1]
        citation_key = f"{last_name.lower()}{year}"
    else:
        citation_key = f"publication{year}"
    
    # Start building the BibTeX entry
    bibtex = f"@{publication_type}{{{citation_key},\n"
    
    # Add title
    bibtex += f"  title = {{{title}}},\n"
    
    # Add authors with abbreviated forenames
    if authors:
        abbreviated_authors = []
        for author in authors:
            forename, lastname = parse_author_name(author)
            
            # Abbreviate the forename to initials
            if forename:
                # Split forename into parts and get first letter of each
                forename_parts = forename.split()
                initials = '. '.join([part[0].upper() for part in forename_parts if part]) + '.'
                abbreviated_author = f"{lastname}, {initials}"
            else:
                # If no forename, just use lastname
                abbreviated_author = lastname
            
            abbreviated_authors.append(abbreviated_author)
        
        author_string = " and ".join(abbreviated_authors)
        bibtex += f"  author = {{{author_string}}},\n"
    
    # Add year
    bibtex += f"  year = {{{year}}},\n"
    
    # Add venue (as journal or booktitle depending on publication type)
    if venue:
        if publication_type.lower() == "article":
            bibtex += f"  journal = {{{venue}}},\n"
        else:
            bibtex += f"  booktitle = {{{venue}}},\n"
    
    # Add DOI if available
    if doi:
        bibtex += f"  doi = {{{doi}}},\n"
    
    # Close the entry
    bibtex += "}"
    
    return bibtex


def parse_bibtex_file(bibtex_content: str) -> List[Dict[str, Any]]:
    """
    Parse a BibTeX file content with multiple entries and extract publication information.
    
    Args:
        bibtex_content: A string containing multiple BibTeX entries
        
    Returns:
        List of dictionaries with publication data
    """
    results = []
    
    try:
        # Use bibtexparser for bulk processing
        bibtex_io = StringIO(bibtex_content)
        parser = bibtexparser.bparser.BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        parser.homogenize_fields = False
        
        bibliography = bibtexparser.load(bibtex_io, parser)
        
        if not bibliography.entries:
            raise ValueError("No entries found in BibTeX file")
        
        # Simply reverse the entries to process the last ones first
        entries = bibliography.entries
        entries.reverse()
        
        # Process each entry
        for entry in entries:
            try:
                # Create a publication dict with safe year conversion
                year_value = 0
                try:
                    if 'year' in entry:
                        year_value = int(entry['year'])
                except (ValueError, TypeError):
                    # If year can't be converted to int, use 0
                    pass
                    
                publication_data = {
                    "title": entry.get("title", "").replace("{", "").replace("}", ""),
                    "year": year_value,
                    "venue": entry.get("journal", entry.get("booktitle", "")),
                    "publication_type": entry.get("ENTRYTYPE", ""),
                    "doi": entry.get("doi", ""),
                    "url": entry.get("url", ""),
                }
                
                # Extract authors
                if "author" in entry:
                    # Split authors by "and" and clean up
                    authors = [author.strip() for author in entry["author"].split(" and ")]
                    authors = [author.replace("{", "").replace("}", "") for author in authors]
                    # Remove duplicates while preserving order
                    seen = set()
                    unique_authors = []
                    for author in authors:
                        if author not in seen:
                            seen.add(author)
                            unique_authors.append(author)
                    publication_data["authors"] = unique_authors
                else:
                    publication_data["authors"] = []
                
                # Add abstract if available
                if "abstract" in entry:
                    publication_data["abstract"] = entry["abstract"]
                
                # Add original BibTeX string with abbreviated author names
                original_entry = "@" + entry["ENTRYTYPE"] + "{" + entry["ID"] + ",\n"
                for key, value in entry.items():
                    if key not in ["ENTRYTYPE", "ID"]:
                        # Special handling for author field - abbreviate forenames
                        if key == "author":
                            # Parse and abbreviate each author
                            authors = [author.strip() for author in value.split(" and ")]
                            abbreviated_authors = []
                            for author in authors:
                                forename, lastname = parse_author_name(author)
                                
                                # Abbreviate the forename to initials
                                if forename:
                                    # Split forename into parts and get first letter of each
                                    forename_parts = forename.split()
                                    initials = '. '.join([part[0].upper() for part in forename_parts if part]) + '.'
                                    abbreviated_author = f"{lastname}, {initials}"
                                else:
                                    # If no forename, just use lastname
                                    abbreviated_author = lastname
                                
                                abbreviated_authors.append(abbreviated_author)
                            
                            abbreviated_value = " and ".join(abbreviated_authors)
                            original_entry += f"  {key} = {{{abbreviated_value}}},\n"
                        else:
                            original_entry += f"  {key} = {{{value}}},\n"
                original_entry += "}"
                publication_data["bibtex"] = original_entry
                
                results.append(publication_data)
            except Exception as e:
                # Skip entries that can't be parsed properly
                print(f"Error processing entry: {e}")
                continue
        
        return results
    
    except Exception as e:
        raise ValueError(f"Failed to parse BibTeX file: {str(e)}")


def batch_process_bibtex(bibtex_content: str) -> Tuple[List[Dict[str, Any]], int, int, int, int, List[Dict[str, Any]]]:
    """
    Process a BibTeX file and categorize entries for batch import.
    
    This function parses a BibTeX file containing multiple entries,
    validates each entry, and categorizes them as successful or failed.
    Validation checks for required fields like title and year.
    
    Args:
        bibtex_content: A string containing multiple BibTeX entries
        
    Returns:
        Tuple with:
        - successful_entries: List of valid publication entries
        - success_count: Number of valid entries
        - failed_count: Number of invalid entries
        - duplicate_count: Always 0 (duplicate detection happens at DB layer)
        - total_count: Total number of entries processed
        - failed_entries: List of invalid entries with failure reasons
    """
    successful_entries = []
    failed_entries = []
    failed_count = 0
    
    try:
        entries = parse_bibtex_file(bibtex_content)
        total_count = len(entries)
        
        # Process each entry
        for entry in entries:
            if not entry.get("title") or not entry.get("year"):
                failed_count += 1
                # Add to failed entries list with reason
                reason = []
                if not entry.get("title"):
                    reason.append("Missing title")
                if not entry.get("year"):
                    reason.append("Missing year")
                
                # Extract as much info as possible for the failed entry
                failed_entry = {
                    "title": entry.get("title", "Missing title"),
                    "year": entry.get("year", "Unknown"),
                    "authors": entry.get("authors", []),
                    "reason": ", ".join(reason)
                }
                failed_entries.append(failed_entry)
                continue
                
            successful_entries.append(entry)
        
        # Return tuple with 0 for duplicate_count since duplicates are handled at DB layer
        return successful_entries, len(successful_entries), failed_count, 0, total_count, failed_entries
    except Exception as e:
        raise ValueError(f"Failed to process BibTeX file: {str(e)}")


def get_existing_author(db: Session, author_name: str) -> Optional[Author]:
    """
    Find an existing author in the database by name.
    
    Args:
        db: Database session
        author_name: Name of the author to search for
        
    Returns:
        Author object if found, None otherwise
    """
    # Parse the author name into forename and lastname
    forename, lastname = parse_author_name(author_name)
    
    # Try to find by lastname and forename
    if lastname and forename:
        # First try exact match on lastname and forename
        author = db.query(Author).filter(
            Author.lastname == lastname,
            Author.forename == forename
        ).first()
        if author:
            return author
        
        # Try case-insensitive match
        author = db.query(Author).filter(
            Author.lastname.ilike(lastname),
            Author.forename.ilike(forename)
        ).first()
        if author:
            return author
        
        # Try matching with initials - only if forename is a single initial
        if len(forename) == 1:
            # Find all authors with matching lastname
            lastname_matches = db.query(Author).filter(Author.lastname.ilike(lastname)).all()
            for author in lastname_matches:
                # Check if the author's forename starts with this initial
                if author.forename and author.forename[0].lower() == forename[0].lower():
                    return author
        
        # If forename contains multiple words, try matching on first name only
        forename_parts = forename.split()
        if len(forename_parts) > 1:
            first_name = forename_parts[0]
            # Try exact match on lastname and first name only
            author = db.query(Author).filter(
                Author.lastname.ilike(lastname),
                Author.forename.ilike(first_name + '%')
            ).first()
            if author:
                return author
        
        # If we have both lastname and forename and no match found with forename,
        # we don't try matching just by lastname - create a new author instead
        return None
    
    # If we only have lastname but no forename, try searching by lastname alone
    # Only do this when the lastname is uncommon to avoid false positives
    if lastname and not forename:
        # Check how many authors have this lastname
        lastname_count = db.query(Author).filter(Author.lastname.ilike(lastname)).count()
        # Only match by lastname alone if there's only one person with this lastname
        if lastname_count == 1:
            author = db.query(Author).filter(Author.lastname.ilike(lastname)).first()
            if author:
                return author
    
    # Legacy matching by full name if the above didn't work
    # First try exact match
    author = db.query(Author).filter(Author.name == author_name).first()
    if author:
        return author
    
    # If no exact match, try normalized match (case insensitive)
    normalized_name = author_name.lower().strip()
    authors = db.query(Author).all()
    for author in authors:
        if author.name and author.name.lower().strip() == normalized_name:
            return author
    
    # If still no match, try more advanced matching
    # Split names into parts and compare
    name_parts = set(normalized_name.split())
    for author in authors:
        if not author.name:
            continue
        author_parts = set(author.name.lower().strip().split())
        # If all parts of the shorter name are in the longer name
        if name_parts.issubset(author_parts) or author_parts.issubset(name_parts):
            # Check if the names are similar enough (more than 80% overlap)
            overlap = len(name_parts.intersection(author_parts))
            if overlap / max(len(name_parts), len(author_parts)) > 0.8:
                return author
    
    return None


def parse_author_name(author_name: str) -> tuple:
    """
    Parse an author name into forename and lastname.
    Handles various formats: "Lastname, Forename", "Forename Lastname", and names with initials.
    
    This function implements intelligent name parsing, handling:
    - Comma-separated lastname-first format
    - Space-separated firstname-last format
    - Handling of academic prefixes (van, von, de, etc.)
    - Proper handling of initials with and without periods
    - Unicode character preservation for international names
    
    Args:
        author_name: Full author name as a string
        
    Returns:
        Tuple of (forename, lastname)
    """
    # Clean up the name - remove curly braces that might be in BibTeX
    author_name = author_name.strip().replace("{", "").replace("}", "")
    
    # Handle empty names
    if not author_name:
        return "", ""
    
    # Check if the name is in "Lastname, Forename" format
    if "," in author_name:
        parts = author_name.split(",", 1)
        lastname = parts[0].strip()
        forename = parts[1].strip() if len(parts) > 1 else ""
        
        # Handle cases where lastname might contain multiple words (like "van der Waals")
        # Check if forename looks more like a surname (single word) and lastname has spaces
        if " " in lastname and forename and " " not in forename:
            # This could be a case where the comma format is not actually lastname, firstname
            # But we'll respect the comma format as it's explicit
            pass
    else:
        # Name is in "Forename Lastname" format
        parts = author_name.split()
        
        # Handle single name
        if len(parts) == 1:
            return "", parts[0]
            
        # Check for special last names with prefixes like "van", "de", "von", etc.
        prefixes = ["van", "von", "de", "del", "della", "di", "da", "dos", "du", "la", "le"]
        
        # Default case: last word is the lastname
        lastname_start_idx = len(parts) - 1
        
        # Check for prefixes starting from the second-to-last word
        for i in range(len(parts) - 2, -1, -1):
            if parts[i].lower() in prefixes:
                lastname_start_idx = i
            else:
                break
                
        lastname = " ".join(parts[lastname_start_idx:])
        forename = " ".join(parts[:lastname_start_idx]) if lastname_start_idx > 0 else ""
    
    # Handle cases with initials in the forename
    # Convert patterns like "A. B." to "A B"
    forename = re.sub(r'([A-Z])\.\s*', r'\1 ', forename).strip()
    
    return forename, lastname
