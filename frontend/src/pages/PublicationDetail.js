import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Button, Alert } from 'react-bootstrap';
import { publicationService, authService } from '../services/api';

const PUBLICATION_TYPE_LABELS = {
  article: 'Article',
  inproceedings: 'Conference Paper',
  book: 'Book',
  incollection: 'Book Chapter',
  techreport: 'Technical Report',
  thesis: 'Thesis',
  phdthesis: 'Dissertation',
  unpublished: 'Preprint',
  misc: 'Other',
};

const PublicationDetail = () => {
  const [publication, setPublication] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { id } = useParams();
  const navigate = useNavigate();
  const isAuthenticated = authService.isAuthenticated();
  
  useEffect(() => {
    fetchPublication();
  }, [id]);
  
  const fetchPublication = async () => {
    try {
      setLoading(true);
      const response = await publicationService.getPublication(id);
      setPublication(response.data);
    } catch (error) {
      console.error('Error fetching publication:', error);
      setError('Failed to load publication. It may have been deleted or you may not have permission to view it.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this publication?')) {
      return;
    }
    
    try {
      await publicationService.deletePublication(id);
      navigate('/publications');
    } catch (error) {
      console.error('Error deleting publication:', error);
      setError('Failed to delete publication. You may not have permission to delete it.');
    }
  };
  
  const handleExportBibtex = async () => {
    try {
      const response = await publicationService.exportBibtex(id);
      
      // Create a blob and download the BibTeX file
      const blob = new Blob([response.data.bibtex], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Create filename from publication title
      const filename = publication.title
        .toLowerCase()
        .replace(/[^\w\s]/gi, '')
        .replace(/\s+/g, '_')
        .substring(0, 50);
      
      a.download = `${filename}.bib`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting BibTeX:', error);
      setError('Failed to export BibTeX.');
    }
  };
  
  if (loading) {
    return <p>Loading publication details...</p>;
  }
  
  if (error) {
    return <Alert variant="danger">{error}</Alert>;
  }
  
  if (!publication) {
    return <Alert variant="warning">Publication not found</Alert>;
  }
  
  return (
    <div className="publication-detail-container">
      <div className="publication-detail-header">
        <h1 className="publication-detail-title">{publication.title}</h1>
        
        <div className="publication-detail-authors">
          {publication.authors.map((author, index) => (
            <React.Fragment key={author.id}>
              {index > 0 && (
                <span>
                  {index === publication.authors.length - 1 ? ' and ' : ', '}
                </span>
              )}
              <Link to={`/publications/author/${author.id}`} className="author-link">
                {author.forename && author.lastname 
                  ? (() => {
                      // Abbreviate forename to initials
                      const forename_parts = author.forename.split(' ');
                      const initials = forename_parts.map(part => part.charAt(0).toUpperCase() + '.').join(' ');
                      return `${initials} ${author.lastname}`;
                    })()
                  : author.name}
              </Link>
            </React.Fragment>
          ))}
        </div>
        
        <div className="publication-detail-meta">
          <span className="publication-year">{publication.year}</span>
          {publication.publication_type && (
            <span className="publication-type">
              {PUBLICATION_TYPE_LABELS[publication.publication_type] || publication.publication_type}
            </span>
          )}
          {publication.venue && (
            <span className="publication-venue">{publication.venue}</span>
          )}
        </div>
      </div>
      
      {publication.abstract && (
        <div className="publication-section">
          <h3 className="section-title">Abstract</h3>
          <p className="publication-abstract">{publication.abstract}</p>
        </div>
      )}
      
      <div className="publication-section">
        <h3 className="section-title">Publication Details</h3>
        <div className="publication-details">
          {publication.doi && (
            <div className="detail-item">
              <span className="detail-label">DOI:</span>
              <a href={`https://doi.org/${publication.doi}`} target="_blank" rel="noopener noreferrer" className="detail-value">
                {publication.doi}
              </a>
            </div>
          )}
          {publication.url && (
            <div className="detail-item">
              <span className="detail-label">URL:</span>
              <a href={publication.url} target="_blank" rel="noopener noreferrer" className="detail-value">
                {publication.url}
              </a>
            </div>
          )}
        </div>
      </div>
      
      <div className="publication-actions">
        <Button variant="outline-secondary" onClick={handleExportBibtex} className="me-2">
          Export as BibTeX
        </Button>
        
        {isAuthenticated && (
          <>
            <Link to={`/publications/edit/${publication.id}`} className="btn btn-outline-primary me-2">
              Edit
            </Link>
            <Button variant="outline-danger" onClick={handleDelete}>
              Delete
            </Button>
          </>
        )}
        
        <Link to="/publications" className="btn btn-link">
          Back to Publications
        </Link>
      </div>
    </div>
  );
};

export default PublicationDetail;