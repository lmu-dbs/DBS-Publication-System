# Publications System

A Docker-based publication list system that allows users to manage academic publications. This system consists of a FastAPI backend and a React frontend, both containerized with Docker.

**Note**: Most of the code in this project is AI-generated.

![Overview of the Startpage](images/startpage.png "Startpage")

## Features

- **View Publications**: Browse and search through the list of publications
- **Advanced Filtering**: Filter publications by author, venue, year, and keywords
- **Search Functionality**: Search publications by title, abstract, or venue
- **User Authentication**: Register and login to access administrative features
- **Publication Management**: Add, edit, and delete publications (for authenticated users)
- **Web Scraping**: 
  - Scrape publications from custom URLs
  - Scrape publications from MCML website
  - AI-powered text-to-BibTeX conversion using NVIDIA NIM API or local Llama model
  - Review and edit scraped publications before adding to main database
  - Reprocess failed BibTeX entries
  - Export all scraped publications as BibTeX
- **BibTeX Support**: 
  - Import publications from BibTeX data (single entry or batch import)
  - Import publications from BibTeX files 
  - Export individual publications as BibTeX
  - Export bulk publications as BibTeX
- **JSON Export**: Export filtered publication lists as JSON
- **Author Management**: 
  - View all authors with publication counts
  - Edit author information (name, email, affiliation)
  - Merge duplicate authors
  - Filter publications by author
  - Automatically create new authors or link to existing ones
- **Pagination**: Browse through large publication lists with pagination
- **Publication Details**: View comprehensive details for each publication
- **Duplicate Detection**: Prevent duplicate entries during BibTeX import and web scraping
- **Error Handling**: Get detailed feedback on import failures
- **Publication Types**: Support for different academic publication types
- **DOI and URL Support**: Store and display DOI and URL for easy reference

## System Requirements

- Docker and Docker Compose installed on your system
- Internet connection for pulling base images

## Getting Started

### Environment Setup

1. Create a `.env` file in the root directory (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file and configure the following variables:
   - `HF_TOKEN`: Your Hugging Face API token (required for accessing HF models for local Llama fallback)
     - Get your token from: https://huggingface.co/settings/tokens
   - `NVIDIA_TOKEN`: Your NVIDIA NIM API key (optional, but recommended for better performance)
     - Get your key from: https://build.nvidia.com/
   - `SECRET_KEY`: Secret key for JWT token generation (generate with: `openssl rand -hex 32`)
   - `ADMIN_USERNAME`: Admin username for initial setup (default: admin)
   - `ADMIN_PASSWORD`: Admin password - **change this immediately after first login**
   
   **Note**: The system uses NVIDIA NIM API for text-to-BibTeX conversion by default, with automatic fallback to the local Llama model if the API is unavailable or the key is not set.

### Running the Application

1. Clone this repository:
   ```
   git clone https://github.com/merowech/basic-publications-system.git
   cd basic-publications-system
   ```

2. Start the application using Docker Compose:
   ```
   docker-compose up --build
   ```

3. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Using the Application

1. **Browse Publications**:
   - Visit the homepage to see all publications
   - Click on author badges to filter by specific author
   - Use the search box to find publications by title, abstract, or venue
   - Filter publications by year, venue, or keywords using the filter options
   - View up to 1000 publications per page with pagination controls

2. **View Publication Details**:
   - Click on a publication title to see its full details including abstract
   - See all authors with their affiliations
   - Access publication metadata including DOI, URL, and publication type
   - Export the publication as BibTeX from the details page

3. **User Registration and Login**:
   - Register a new account with username, email and password
   - Log in to access administrative features
   - Manage your user profile

4. **Managing Publications** (requires authentication):
   - Add new publications manually with the form interface
   - Import publications from BibTeX data (single entry or batch)
   - Import publications from BibTeX files with error reporting
   - Edit existing publications (title, authors, year, venue, etc.)
   - Delete publications you've created
   - Maintain author order for correct citation formatting

5. **Web Scraping** (requires authentication):
   - Scrape publications from custom URLs or MCML website
   - AI converts raw text to BibTeX format using NVIDIA NIM API or local Llama model
   - Review scraped publications in a dedicated interface
   - Edit raw text and reprocess BibTeX if needed
   - Add approved scraped publications to main database
   - Export all scraped publications as BibTeX file
   - Automatic duplicate detection prevents adding existing publications

6. **BibTeX Management**:
   - Import publications from BibTeX strings or files
   - Export individual publications as BibTeX
   - Export bulk publications as BibTeX (all or filtered)
   - Automatic duplicate detection during import
   - Detailed error reporting for failed imports

7. **Data Export**:
   - Export individual publications as BibTeX
   - Export filtered or searched publication lists as JSON or BibTeX
   - Export all scraped publications as BibTeX
   - Use exported data for integration with other systems

8. **Author Management**:
   - View all authors with publication counts
   - Edit author details (forename, lastname, email, affiliation)
   - Merge duplicate author entries
   - Delete authors (removes from all publications)
   - Authors are automatically created during publication import
   - Filter publications by specific author
   - Maintain consistent author information across publications

## Development

### Project Structure

- `backend/`: FastAPI backend service
  - `app/`: Application code
    - `models/`: Database models
      - `database.py`: Database connection and session management
      - `models.py`: SQLAlchemy models (Publication, Author, User, ScrapedPublication, etc.)
    - `routers/`: API endpoints
      - `publications.py`: Publication CRUD and BibTeX import/export
      - `users.py`: User authentication and management
      - `scraping.py`: Web scraping and text-to-BibTeX conversion
      - `authors.py`: Author management (view, edit, merge, delete)
    - `schemas/`: Pydantic schemas for data validation
      - `schemas.py`: Request/response models for API endpoints
    - `auth/`: Authentication logic
      - `auth.py`: JWT token generation and verification
      - `login_tracker.py`: Login attempt tracking and security
    - `utils/`: Utility functions
      - `bibtex_processor.py`: BibTeX parsing and generation with author name abbreviation
      - `sql_importer.py`: SQL database import utilities
  - `requirements.txt`: Python dependencies
  - `Dockerfile`: Container configuration for development
- `frontend/`: React frontend
  - `src/`: Source code
    - `components/`: Reusable React components
      - `Navbar.js`: Navigation bar with authentication state
      - `Footer.js`: Application footer
    - `pages/`: Page components for all features
      - `PublicationsList.js`: Main publications view with filtering
      - `PublicationDetail.js`: Detailed publication view
      - `CreatePublication.js`: Manual publication creation form
      - `EditPublication.js`: Publication editing interface
      - `ImportBibtex.js`: BibTeX file/text import interface
      - `Scraping.js`: Web scraping interface (MCML and custom URLs)
      - `ScrapedPublications.js`: Review and manage scraped publications
      - `Authors.js`: Author management interface
      - `Login.js`: User authentication
      - `Register.js`: User registration
    - `services/`: API services
      - `api.js`: Axios-based API client for backend communication
    - `styles/`: CSS styles
      - `App.css`: Application-wide styles
  - `public/`: Static assets and images
  - `package.json`: Node.js dependencies
  - `Dockerfile`: Container configuration for development
- `production/`: Production deployment configuration
  - `Dockerfile.production`: Multi-stage Docker build for production
  - `nginx.conf`: Nginx configuration for serving frontend and proxying API
  - `supervisord.conf`: Process management for running both frontend and backend
- `data/`: Persistent data storage and import utilities
  - `publications.db`: SQLite database for development
- `docker-compose.yml`: Development environment orchestration
- `docker-compose.production.yml`: Production environment orchestration
- `.env.example`: Environment variable template
- `README.md`: This file

### Data Processing Capabilities

The system includes several utilities for importing publication data:

1. **BibTeX Processing**: Parse and generate BibTeX entries with proper formatting
2. **SQL Import**: Import publications from SQL dumps via the included utilities
3. **Web Crawling**: Extract publication data from web sources
4. **Batch Processing**: Handle multiple publications in a single import operation
5. **Data Validation**: Validate imported data with Pydantic schemas
6. **Error Handling**: Detailed error reporting for failed imports

### Customization

You can customize this application by:

1. Modifying the environment variables in `docker-compose.yml`
2. Changing the database by updating the `DATABASE_URL` environment variable
3. Extending the data models in `backend/app/models/models.py`
4. Adding new API endpoints in the `backend/app/routers/` directory

## Security Notes

For production deployment:

1. Change the `SECRET_KEY` in the `docker-compose.yml` file
2. Configure CORS settings in `backend/app/main.py`
3. Set up HTTPS for both frontend and backend
4. Consider using a more robust database like PostgreSQL

## Disclaimer

**AI-Generated Code**: Most of the code in this project has been generated using AI assistance. While functional, it may not follow all best practices or optimal design patterns. Use in production environments at your own discretion and ensure thorough testing and security review.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
