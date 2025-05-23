#!/usr/bin/env python3
"""
This script connects to the MySQL database loaded from the SQL dumps,
extracts publication data, and converts it to BibTeX format.
"""

import time
import os
import re
import mysql.connector
from pybtex.database import BibliographyData, Entry
from pybtex.database import Person

def get_publication_data():
    """
    Extract publication data from the MySQL database.
    Returns: List of publication records
    """
    try:
        # Connect to the MySQL database - using localhost since we're in the same container
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='root',
            database='bib'
        )
        
        if connection.is_connected():
            print("Connected to MySQL database")

            cursor = connection.cursor(dictionary=True)
            
            # Get list of tables to understand the schema
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print("Tables in the database:", [t[f"Tables_in_bib"] for t in tables])
            
            # Try to get the publication data with a query that adapts to the database schema
            try:
                # First try a simpler query to understand the structure
                cursor.execute("DESCRIBE Publication")
                columns = cursor.fetchall()
                print("Publication table columns:", [col["Field"] for col in columns])
                
                # Check Authors table structure
                cursor.execute("DESCRIBE Author")
                author_cols = cursor.fetchall()
                print("Author table columns:", [col["Field"] for col in author_cols])
                
                # Check if MapPublicationAuthor table exists
                cursor.execute("DESCRIBE MapPublicationAuthor")
                map_pub_author_cols = cursor.fetchall()
                print("MapPublicationAuthor table columns:", [col["Field"] for col in map_pub_author_cols])
                
                # Build the query based on the schema
                query = """
                SELECT p.*, 
                       GROUP_CONCAT(a.AuthorName ORDER BY mpa.Order SEPARATOR '|') as Authors
                FROM Publication p
                LEFT JOIN MapPublicationAuthor mpa ON p.PublicationID = mpa.PublicationID
                LEFT JOIN Author a ON mpa.AuthorID = a.AuthorID
                GROUP BY p.PublicationID
                """
                
                cursor.execute(query)
                publications = cursor.fetchall()
                print(f"Found {len(publications)} publications")
                
                # Get additional information for each publication type
                for pub in publications:
                    pub_id = pub['PublicationID']
                    
                    # Check conference papers
                    cursor.execute(f"SELECT * FROM ConferencePaper WHERE ConferencePaperID = {pub_id}")
                    conf_paper = cursor.fetchone()
                    if (conf_paper):
                        # First check what columns the Conference table has
                        conference_id = conf_paper.get('ConferenceID')
                        if conference_id:
                            # Dynamically create query based on available columns
                            conf_query = "SELECT * FROM Conference WHERE ConferenceID = %s"
                            cursor.execute(conf_query, (conference_id,))
                            conf_info = cursor.fetchone()
                            if conf_info:
                                pub.update(conf_info)
                                pub.update(conf_paper)  # Add all ConferencePaper fields to the publication
                                pub['PublicationType'] = 'inproceedings'
                                # Try to get venue information from Conference table
                                for field in ['ConferenceName', 'ConferenceFullName', 'ConferenceNameFull']:
                                    if conf_info.get(field):
                                        pub['Venue'] = conf_info.get(field)
                                        break
                                if 'Venue' not in pub and conf_info.get('ConferenceShortName'):
                                    pub['Venue'] = conf_info.get('ConferenceShortName')
                    
                    # Check journal papers
                    cursor.execute(f"SELECT * FROM JournalPaper WHERE JournalPaperID = {pub_id}")
                    journal_paper = cursor.fetchone()
                    if journal_paper:
                        journal_id = journal_paper.get('JournalID')
                        if journal_id:
                            cursor.execute("SELECT * FROM Journal WHERE JournalID = %s", (journal_id,))
                            journal_info = cursor.fetchone()
                            if journal_info:
                                pub.update(journal_info)
                                pub.update(journal_paper)
                                pub['PublicationType'] = 'article'
                                # Add venue information from Journal table
                                if journal_info.get('JournalName'):
                                    pub['Venue'] = journal_info.get('JournalName')
                    
                    # Check other publication types
                    for pub_type, table_name, bibtex_type in [
                        ('book', 'Book', 'book'),
                        ('inbook', 'InBook', 'inbook'),
                        ('phdthesis', 'PHDThesis', 'phdthesis'),
                        ('techreport', 'TechReport', 'techreport'),
                        ('misc', 'Misc', 'misc')
                    ]:
                        cursor.execute(f"SELECT * FROM {table_name} WHERE {table_name}ID = {pub_id}")
                        result = cursor.fetchone()
                        if result:
                            pub['PublicationType'] = bibtex_type
                            # Try to extract venue information if available
                            if pub_type == 'phdthesis' and result.get('School'):
                                pub['Venue'] = result.get('School')
                            elif pub_type == 'techreport' and result.get('Institution'):
                                pub['Venue'] = result.get('Institution')
                            elif pub_type == 'book' and result.get('Publisher'):
                                pub['Venue'] = result.get('Publisher')
                            break
                    
                    # Default to inproceedings if not found in any specific type
                    if 'PublicationType' not in pub:
                        pub['PublicationType'] = 'inproceedings'
                
                return publications
                
            except mysql.connector.Error as err:
                print(f"Error executing query: {err}")
                
                # Try an even simpler fallback query
                try:
                    # Just get basic publication data without joins
                    cursor.execute("SELECT * FROM Publication")
                    publications = cursor.fetchall()
                    print(f"Retrieved {len(publications)} publications with basic query")
                    return publications
                except mysql.connector.Error as err2:
                    print(f"Error during fallback query: {err2}")
                    return []

    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL database: {err}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed")
    
    return []

def convert_to_bibtex(publications):
    """
    Convert publication data to BibTeX format
    Args:
        publications: List of publication records from the database
    Returns:
        BibTeX data as string
    """
    bib_data = BibliographyData()
    
    # Keep track of used keys to avoid duplicates
    used_keys = set()
    
    for pub in publications:
        try:
            pub_id = pub.get('PublicationID', '')
            
            # Create an entry key using lastname of first author, first word of title, year and publication ID
            if 'Authors' in pub and pub['Authors'] and pub.get('Title') and pub.get('Year'):
                # Get the last name of the first author
                first_author = pub['Authors'].split('|')[0]
                last_name = first_author.split()[-1].lower()
                
                # Get the first meaningful word of the title (skip articles like "the", "a", etc.)
                title_words = re.findall(r'\b\w+\b', pub.get('Title', '').lower())
                skip_words = {'a', 'an', 'the', 'on', 'in', 'at', 'by', 'for', 'with', 'to'}
                first_word = next((word for word in title_words if word not in skip_words), 'unknown')
                
                # Create the key in format: lastname_firstword_year_publicationID
                entry_key = f"{last_name}_{first_word}_{pub.get('Year', 'unknown')}_{pub_id}"
            else:
                # Fallback if we don't have all the information
                entry_key = f"unknown_{pub_id}_{pub.get('Year', 'unknown')}"
            
            # Make sure the key is unique
            base_key = entry_key
            suffix = 1
            while entry_key in used_keys:
                entry_key = f"{base_key}_{suffix}"
                suffix += 1
            
            used_keys.add(entry_key)
            
            # Determine entry type based on the PublicationType field
            entry_type = 'inproceedings'  # default to inproceedings as requested
            if 'PublicationType' in pub:
                entry_type = pub['PublicationType']
            
            # Create entry fields
            fields = {}
            
            # Add basic fields that should be common to all publication types
            if pub.get('Title'):
                fields['title'] = pub.get('Title')
                
            if pub.get('Year'):
                fields['year'] = str(pub.get('Year'))
                
            if pub.get('Month'):
                fields['month'] = str(pub.get('Month'))
                
            if pub.get('URL-Publisher'):
                fields['url'] = pub.get('URL-Publisher')
                
            if pub.get('URL-PrePrint'):
                fields['eprint'] = pub.get('URL-PrePrint')
                
            if pub.get('Note'):
                fields['note'] = pub.get('Note')
            
            # Add venue information if available
            if pub.get('Venue'):
                fields['venue'] = pub.get('Venue')
            
            # Process authors - split by pipe to handle the GROUP_CONCAT with pipe separator
            persons = {}
            if pub.get('Authors'):
                persons['author'] = [Person(author.strip()) for author in pub.get('Authors', '').split('|')]
            
            # Add specific fields based on publication type
            if entry_type == 'inproceedings':
                # Use dynamically determined conference name field
                # Check different possible column names
                for field in ['ConferenceName', 'ConferenceFullName', 'ConferenceNameFull', 'Name']:
                    if pub.get(field):
                        fields['booktitle'] = pub.get(field)
                        break
                
                # If we still don't have a booktitle, try the ShortName field 
                if 'booktitle' not in fields:
                    for field in ['ConferenceShortName', 'ConferenceNameShort', 'ShortName']:
                        if pub.get(field):
                            fields['booktitle'] = pub.get(field)
                            fields['series'] = pub.get(field)
                            break
                
                # If we have a short name but not as the booktitle
                for field in ['ConferenceShortName', 'ConferenceNameShort', 'ShortName', 'Abbreviation']:
                    if pub.get(field) and 'series' not in fields:
                        fields['series'] = pub.get(field)
                        break
                
                # Add publisher if available
                if pub.get('Publisher'):
                    fields['publisher'] = pub.get('Publisher')
                
                # Add pages if available
                if pub.get('Pages'):
                    fields['pages'] = pub.get('Pages')
                
                # Add address/location if available
                if pub.get('Address'):
                    fields['address'] = pub.get('Address')
                
                # Add additional fields from ConferencePaper table
                if pub.get('City') and pub.get('Country'):
                    if 'address' not in fields:
                        fields['address'] = f"{pub.get('City')}, {pub.get('Country')}"
                    else:
                        fields['location'] = f"{pub.get('City')}, {pub.get('Country')}"
                elif pub.get('City'):
                    if 'address' not in fields:
                        fields['address'] = pub.get('City')
                    else:
                        fields['location'] = pub.get('City')
                elif pub.get('Country'):
                    if 'address' not in fields:
                        fields['address'] = pub.get('Country')
                    else:
                        fields['location'] = pub.get('Country')
                
                # Add editor information
                if pub.get('Editor'):
                    fields['editor'] = pub.get('Editor')
                
                # Add volume and number information
                if pub.get('Volume'):
                    fields['volume'] = pub.get('Volume')
                if pub.get('Number'):
                    fields['number'] = pub.get('Number')
                
                # Add organization information
                if pub.get('Organization'):
                    fields['organization'] = pub.get('Organization')
                
                # Add series information if not already set
                if pub.get('Series') and 'series' not in fields:
                    fields['series'] = pub.get('Series')
                    
            elif entry_type == 'article':
                # Use dynamically determined journal name field
                for field in ['JournalName', 'JournalFullName', 'JournalNameFull']:
                    if pub.get(field):
                        fields['journal'] = pub.get(field)
                        break
                
                if pub.get('Volume'):
                    fields['volume'] = pub.get('Volume')
                if pub.get('Number'):
                    fields['number'] = pub.get('Number')
                if pub.get('Pages'):
                    fields['pages'] = pub.get('Pages')
            
            elif entry_type == 'book':
                if pub.get('Publisher'):
                    fields['publisher'] = pub.get('Publisher')
                if pub.get('Address'):
                    fields['address'] = pub.get('Address')
                if pub.get('Edition'):
                    fields['edition'] = pub.get('Edition')
                if pub.get('ISBN'):
                    fields['isbn'] = pub.get('ISBN')
            
            elif entry_type == 'phdthesis':
                if pub.get('School'):
                    fields['school'] = pub.get('School')
                if pub.get('Address'):
                    fields['address'] = pub.get('Address')
            
            elif entry_type == 'techreport':
                if pub.get('Institution'):
                    fields['institution'] = pub.get('Institution')
                if pub.get('Number'):
                    fields['number'] = pub.get('Number')
                if pub.get('Address'):
                    fields['address'] = pub.get('Address')
            
            # Create the entry
            entry = Entry(entry_type, fields=fields, persons=persons)
            bib_data.add_entry(entry_key, entry)
            
        except Exception as e:
            print(f"Error processing publication {pub.get('PublicationID', 'unknown')}: {e}")
    
    return bib_data.to_string('bibtex')

def main():
    """Main function to orchestrate the conversion process"""
    print("Fetching publication data from MySQL...")
    publications = get_publication_data()
    
    if not publications:
        print("No publications found or error occurred")
        return
    
    print(f"Converting {len(publications)} publications to BibTeX...")
    bibtex_data = convert_to_bibtex(publications)
    
    output_dir = "/bibtex_output"
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "publications.bib")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(bibtex_data)
    
    print(f"BibTeX data written to {output_file}")

if __name__ == "__main__":
    main()
