import React, { useState, useEffect, useCallback } from 'react';
import { Form, InputGroup, Button, Alert } from 'react-bootstrap';
import { Link, useParams, useNavigate, useLocation } from 'react-router-dom';
import { publicationService, authService } from '../services/api';

const PublicationsList = () => {
  const [publications, setPublications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [venueFilter, setVenueFilter] = useState('');
  const [yearFilter, setYearFilter] = useState('');
  const [keywordFilter, setKeywordFilter] = useState('');
  const [authorName, setAuthorName] = useState('');
  const { authorId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const isAuthenticated = authService.isAuthenticated();
  

  // Removed the "Remove Scraped Publications" button and handler per request
  
  // Parse URL query parameters
  useEffect(() => {
    const queryParams = new URLSearchParams(location.search);
    const keywordParam = queryParams.get('keyword');
    const venueParam = queryParams.get('venue');
    const yearParam = queryParams.get('year');
    
    if (keywordParam) {
      setKeywordFilter(keywordParam);
      setSearchTerm(keywordParam);
    } else {
      setKeywordFilter('');
      setSearchTerm('');
    }
    
    if (venueParam) {
      setVenueFilter(venueParam);
    } else {
      setVenueFilter('');
    }
    
    if (yearParam) {
      setYearFilter(yearParam);
    } else {
      setYearFilter('');
    }
    
    // Important: Fetch publications whenever URL parameters change
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await publicationService.getPublications(
          authorId,
          keywordParam || '', 
          venueParam || '',
          yearParam || '',
          keywordParam || ''
        );
        setPublications(response.data);
        
        // If there's an authorId and we have publications, get the author name
        if (authorId && response.data.length > 0) {
          // Find the first publication where this author appears
          const publication = response.data.find(pub => 
            pub.authors.some(author => author.id === parseInt(authorId))
          );
          
          if (publication) {
            // Find the author in the authors array
            const author = publication.authors.find(a => a.id === parseInt(authorId));
            if (author) {
              setAuthorName(author.name);
            }
          }
        } else {
          setAuthorName('');
        }
      } catch (error) {
        console.error('Error fetching publications:', error);
        setError('Failed to load publications. Please try again later.');
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [location.search, authorId]);
  
  const handleSearch = (e) => {
    e.preventDefault();
    // Update URL with search parameters
    const queryParams = new URLSearchParams();
    
    if (searchTerm) {
      queryParams.set('keyword', searchTerm);
    }
    
    if (venueFilter) {
      queryParams.set('venue', venueFilter);
    }
    
    if (yearFilter) {
      queryParams.set('year', yearFilter);
    }
    
    navigate({
      pathname: authorId ? `/publications/author/${authorId}` : '/publications',
      search: queryParams.toString()
    });
    // No need to call fetchPublications here, the useEffect will handle it
  };
  
  const handleExportJson = async () => {
    try {
      const response = await publicationService.exportJson(
        authorId, 
        keywordFilter, 
        venueFilter,
        yearFilter,
        keywordFilter
      );
      
      // Create a blob and download the JSON file
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'publications.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting JSON:', error);
      setError('Failed to export publications as JSON.');
    }
  };
  
  const handleExportBibtex = async () => {
    try {
      const response = await publicationService.exportBibtexList(
        authorId, 
        keywordFilter, 
        venueFilter,
        yearFilter,
        keywordFilter
      );
      
      // Create a blob and download the BibTeX file
      const blob = new Blob([response.data.bibtex], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Create filename with current filters
      let filename = 'publications';
      if (authorName) {
        filename += `_by_${authorName.toLowerCase().replace(/\s+/g, '_')}`;
      }
      if (venueFilter) {
        filename += `_venue_${venueFilter.toLowerCase().replace(/\s+/g, '_')}`;
      }
      if (yearFilter) {
        filename += `_year_${yearFilter}`;
      }
      if (keywordFilter) {
        filename += `_keyword_${keywordFilter.toLowerCase().replace(/\s+/g, '_')}`;
      }
      
      a.download = `${filename}.bib`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting BibTeX:', error);
      setError('Failed to export publications as BibTeX.');
    }
  };
  
  const clearFilters = () => {
    setSearchTerm('');
    setVenueFilter('');
    setYearFilter('');
    setKeywordFilter('');
    navigate({
      pathname: authorId ? `/publications/author/${authorId}` : '/publications'
    });
  };
  
  // Group publications by year
  const groupPublicationsByYear = () => {
    const grouped = {};
    
    publications.forEach(pub => {
      if (!grouped[pub.year]) {
        grouped[pub.year] = [];
      }
      grouped[pub.year].push(pub);
    });
    
    // Sort years in descending order
    return Object.keys(grouped)
      .sort((a, b) => b - a)
      .map(year => ({
        year,
        publications: grouped[year]
      }));
  };
  
  // Format authors list with commas and "and"
  const formatAuthors = (authors) => {
    if (!authors || authors.length === 0) return '';
    
    if (authors.length === 1) {
      return formatAuthorName(authors[0]);
    }
    
    const lastAuthor = formatAuthorName(authors[authors.length - 1]);
    const otherAuthors = authors.slice(0, -1).map(a => formatAuthorName(a)).join(', ');
    
    return `${otherAuthors}, and ${lastAuthor}`;
  };
  
  // Display author name using abbreviated forename and full lastname
  const formatAuthorName = (author) => {
    if (author.forename && author.lastname) {
      // Abbreviate forename to initials
      const forename_parts = author.forename.split(' ');
      const initials = forename_parts.map(part => part.charAt(0).toUpperCase() + '.').join(' ');
      return `${initials} ${author.lastname}`;
    }
    return author.name;
  };
  
  const yearGroups = groupPublicationsByYear();
  
  const buildFilterDescription = () => {
    const filters = [];
    
    if (authorId && authorName) {
      filters.push(`author: "${authorName}"`);
    }
    
    if (searchTerm) filters.push(`keyword: "${searchTerm}"`);
    if (venueFilter) filters.push(`venue: "${venueFilter}"`);
    if (yearFilter) filters.push(`year: ${yearFilter}`);
    
    return filters.length > 0 ? `filtered by ${filters.join(', ')}` : '';
  };

  // Function to extract common keywords from text
  const extractKeywords = (text) => {
    if (!text) return [];
    
    // List of common keywords in academic publications
    const commonKeywords = [
      'algorithm', 'analysis', 'learning', 'model', 'system', 'network',
      'data', 'neural', 'training', 'intelligence', 'artificial', 'machine',
      'deep', 'reinforcement', 'knowledge', 'semantic', 'language',
      'computing', 'computer', 'software', 'hardware', 'architecture',
      'security', 'privacy', 'blockchain', 'cloud', 'distributed',
      'parallel', 'database', 'optimization', 'detection', 'classification',
      'recognition', 'prediction', 'vision', 'image', 'processing',
      'natural', 'human', 'interactive', 'autonomous', 'robotic',
      'framework', 'research'
    ];
    
    // Check for each keyword in the text
    return commonKeywords.filter(keyword => 
      text.toLowerCase().includes(keyword.toLowerCase())
    ).slice(0, 5); // Limit to 5 keywords to avoid clutter
  };
  
  // Function to apply keyword filter
  const applyKeywordFilter = (keyword) => {
    const queryParams = new URLSearchParams(location.search);
    queryParams.set('keyword', keyword);
    navigate({
      pathname: location.pathname,
      search: queryParams.toString()
    });
    // No need to call fetchPublications or update state directly - the useEffect will handle it
  };
  
  return (
    <div className="publications-container">
      <div className="publications-header">
        <h2>
          {authorId ? `Publications by ${authorName || 'Author'}` : 'Publications'}
          {(searchTerm || venueFilter || yearFilter || (authorId && authorName)) && 
            <small className="ms-2 text-muted">{buildFilterDescription()}</small>
          }
        </h2>
        <div className="mt-3">
          {isAuthenticated && (
            <>
              <Link to="/publications/create" className="btn btn-primary me-2">
                Add Publication
              </Link>
              {/* Remove Scraped Publications button removed per request */}
            </>
          )}
        </div>
      </div>
      
      <div className="publications-filters">
        {authorId && (
          <div className="mb-3">
            <Link to={location.search ? `/publications${location.search}` : "/publications"} className="btn btn-outline-secondary btn-sm">
              ← Back to All Publications
            </Link>
          </div>
        )}
        
        <Form onSubmit={handleSearch} className="mb-4">
          <div className="mb-3">
            <InputGroup>
              <Form.Control
                placeholder="Search in titles, abstracts, venues, and authors..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <Button variant="outline-secondary" type="submit">
                Search
              </Button>
            </InputGroup>
            <Form.Text className="text-muted">
              Your search will find matches in publication titles, abstracts, venues, and author names.
            </Form.Text>
          </div>
          
          <div className="row">
            <div className="col-md-4 mb-2">
              <InputGroup>
                <InputGroup.Text>Venue</InputGroup.Text>
                <Form.Control
                  placeholder="Filter by venue (e.g., AAAI)"
                  value={venueFilter}
                  onChange={(e) => setVenueFilter(e.target.value)}
                />
              </InputGroup>
            </div>
            
            <div className="col-md-4 mb-2">
              <InputGroup>
                <InputGroup.Text>Year</InputGroup.Text>
                <Form.Control
                  placeholder="Filter by year"
                  type="number"
                  value={yearFilter}
                  onChange={(e) => setYearFilter(e.target.value)}
                />
              </InputGroup>
            </div>
            
            <div className="col-md-4 mb-2">
              <Button variant="outline-secondary" type="submit" className="me-2">
                Apply Filters
              </Button>
              
              {(searchTerm || venueFilter || yearFilter) && (
                <Button 
                  variant="outline-danger" 
                  onClick={clearFilters}
                >
                  Clear All
                </Button>
              )}
            </div>
          </div>
        </Form>
      </div>
      
      {error && <Alert variant="danger">{error}</Alert>}
      
      {loading ? (
        <p>Loading publications...</p>
      ) : publications.length === 0 ? (
        <div className="text-center my-5">
          <p className="lead">No publications found.</p>
          {isAuthenticated && (
            <Link to="/publications/create" className="btn btn-primary mt-3">
              Add a Publication
            </Link>
          )}
        </div>
      ) : (
        <div>
          {yearGroups.map(group => (
            <div key={group.year} className="year-section">
              <h3 className="year-header">{group.year}</h3>
              <div>
                {group.publications.map(publication => (
                  <div key={publication.id} className="publication-item">
                    <div className="publication-title">
                      <Link to={`/publications/${publication.id}`}>
                        {publication.title}
                      </Link>
                    </div>
                    <div className="publication-authors">
                      {publication.authors.map((author, index) => (
                        <React.Fragment key={author.id}>
                          {index > 0 && (
                            <span>
                              {index === publication.authors.length - 1 ? ' and ' : ', '}
                            </span>
                          )}
                          <Link to={`/publications/author/${author.id}${location.search}`}>
                            {author.forename && author.lastname 
                              ? formatAuthorName(author)
                              : author.name}
                          </Link>
                        </React.Fragment>
                      ))}
                    </div>
                    <div className="publication-venue">
                      <span
                        className="venue-tag"
                        onClick={() => {
                          const queryParams = new URLSearchParams(location.search);
                          queryParams.set('venue', publication.venue || 'Preprint');
                          navigate({
                            pathname: location.pathname,
                            search: queryParams.toString()
                          });
                        }}
                        style={{ cursor: 'pointer', textDecoration: 'underline' }}
                      >
                        {publication.venue 
                          ? `${publication.venue} (${publication.year})` 
                          : `Preprint (${publication.year})`}
                      </span>
                    </div>
                    
                    {/* Add keywords section */}
                    {publication.abstract && (
                      <div className="publication-keywords">
                        <small>
                          Keywords: {
                            extractKeywords(publication.title + ' ' + publication.abstract)
                              .map((keyword, idx) => (
                                <span key={idx}>
                                  {idx > 0 && ', '}
                                  <span
                                    className="keyword-tag"
                                    onClick={() => applyKeywordFilter(keyword)}
                                    style={{ cursor: 'pointer', textDecoration: 'underline', color: '#007bff' }}
                                  >
                                    {keyword}
                                  </span>
                                </span>
                              ))
                          }
                        </small>
                      </div>
                    )}
                    
                    <div className="publication-links">
                      <Link to={`/publications/${publication.id}`}>
                        Details
                      </Link>
                      {publication.doi && (
                        <a href={`https://doi.org/${publication.doi}`} target="_blank" rel="noopener noreferrer">
                          DOI
                        </a>
                      )}
                      {publication.url && (
                        <a href={publication.url} target="_blank" rel="noopener noreferrer">
                          Link
                        </a>
                      )}
                      {isAuthenticated && (
                        <Link to={`/publications/edit/${publication.id}`}>
                          Edit
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          
          <div className="text-center mt-5 mb-4 pt-3 border-top">
            <Button variant="outline-secondary" onClick={handleExportJson} className="me-2">
              Export as JSON
            </Button>
            <Button variant="outline-secondary" onClick={handleExportBibtex}>
              Export as BibTeX
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PublicationsList;