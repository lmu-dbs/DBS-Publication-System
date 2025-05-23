import os
import logging
import sqlite3
from pathlib import Path
from sqlalchemy import text

logger = logging.getLogger(__name__)

def execute_sql_file_sqlite(engine, sql_file_path):
    """
    Execute an SQL file against a SQLite database
    
    Args:
        engine: SQLAlchemy engine
        sql_file_path: Path to the SQL file
    """
    try:
        # Check if file exists
        if not os.path.exists(sql_file_path):
            logger.error(f"SQL file not found: {sql_file_path}")
            return False
            
        logger.info(f"Executing SQL file for SQLite: {sql_file_path}")
        
        # For SQLite, we need to modify MySQL-style SQL to be compatible
        with open(sql_file_path, 'r', encoding='utf-8') as file:
            sql_content = file.read()
        
        # Adaptations for SQLite (modify as needed for your specific SQL file)
        # Remove MySQL-specific syntax
        sql_content = sql_content.replace('AUTO_INCREMENT', '')
        
        # SQLite doesn't support multiple value inserts in the same format as MySQL
        # This is a simplified approach - complex SQL files might need more parsing
        
        # Split the SQL into statements
        statements = []
        current_statement = ""
        for line in sql_content.split('\n'):
            # Skip comments and empty lines
            if line.strip().startswith('--') or line.strip() == '':
                continue
                
            current_statement += line + " "
            
            if line.strip().endswith(';'):
                statements.append(current_statement.strip())
                current_statement = ""
        
        # If there's an unterminated statement, add it
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        # Get the database path from the engine URL
        # SQLite URL format: sqlite:///path/to/database.db
        db_path = engine.url.database
        
        # Connect directly to the SQLite database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            for statement in statements:
                if statement.strip():
                    try:
                        cursor.execute(statement)
                    except sqlite3.Error as e:
                        logger.error(f"Error executing SQLite statement: {e}")
                        logger.error(f"Statement: {statement}")
                        # Continue with other statements
            
            conn.commit()
        
        logger.info("SQLite import completed successfully")
        return True
            
    except Exception as e:
        logger.error(f"Error executing SQL file for SQLite: {str(e)}")
        return False

def initialize_database_from_sql(engine):
    """
    Initialize the database with data from SQL files if needed
    
    Args:
        engine: SQLAlchemy engine
    """
    # Only proceed if it's a SQLite database
    if 'sqlite' not in engine.url.drivername:
        logger.warning("Not a SQLite database, skipping initialization")
        return False
    
    # Find SQL files to import
    sql_paths = [
        # Common locations for SQL files
        Path(__file__).parent.parent.parent.parent / "data" / "bib.sql",
        Path(__file__).parent.parent.parent.parent / "data" / "sqlite.sql"
    ]
    
    # Try to load from any of the possible paths
    for path in sql_paths:
        if path.exists():
            logger.info(f"Found SQL file: {path}")
            success = execute_sql_file_sqlite(engine, str(path))
            if success:
                logger.info(f"Database initialized with {path}")
                return True
    
    logger.warning("No SQL files found or initialization failed")
    return False