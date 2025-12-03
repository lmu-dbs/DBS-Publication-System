import React, { useEffect, useState } from 'react';
import { getScrapedPublications, reprocessScrapedPublication, updateScrapedPublication, addScrapedToMain, exportScrapedBibtex } from '../services/api';
import { Table, Button, Card, Spinner, Alert } from 'react-bootstrap';

const ScrapedPublications = () => {
  const [publications, setPublications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
      getScrapedPublications()
        .then(data => {
          setPublications(data);
          setLoading(false);
        })
        .catch(err => {
          setError('Failed to fetch scraped publications');
          setLoading(false);
        });
  }, []);

  const handleAddToDatabase = (id) => {
    // Call backend to add scraped publication to main publications
    addScrapedToMain(id)
      .then((created) => {
        // Remove the scraped publication from the list
        setPublications(prev => prev.filter(p => p.id !== id));
        alert(`Publication added to main DB (id: ${created.id})`);
      })
      .catch(err => {
        console.error('Failed to add to main DB', err);
        alert('Failed to add publication to main database');
      });
  };

  const [editingId, setEditingId] = useState(null);
  const [editedData, setEditedData] = useState({});

  const startEdit = (pub) => {
    setEditingId(pub.id);
    // Only raw_text is editable
    setEditedData({ raw_text: pub.raw_text || '' });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditedData({});
  };

  const saveEdit = async (id) => {
    try {
      // Only send raw_text to the backend
      const res = await updateScrapedPublication(id, { raw_text: editedData.raw_text });
      setPublications(pubs => pubs.map(p => p.id === id ? res : p));
      setEditingId(null);
      setEditedData({});
      alert('Saved changes');
    } catch (err) {
      alert('Failed to save changes');
    }
  };

    const handleReprocessBibtex = async (id) => {
      try {
        const res = await reprocessScrapedPublication(id);
        setPublications(pubs => pubs.map(pub => pub.id === id ? res : pub));
        alert('BibTeX reprocessed!');
      } catch (err) {
        alert('Failed to reprocess BibTeX');
      }
    };

  const handleDownloadAll = async () => {
    try {
      const response = await exportScrapedBibtex();
      
      // Create a blob from the response data
      const blob = new Blob([response.data], { type: 'application/x-bibtex' });
      
      // Create a download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Extract filename from response headers or use default
      const contentDisposition = response.headers['content-disposition'];
      let filename = `scraped_publications_${new Date().toISOString().split('T')[0]}.bib`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      alert(`Downloaded ${publications.length} scraped publications as BibTeX`);
    } catch (err) {
      console.error('Failed to download BibTeX:', err);
      alert('Failed to download BibTeX file');
    }
  };

  if (loading) return <div>Loading scraped publications...</div>;
  if (error) return <div>{error}</div>;

    if (loading) return <div className="d-flex justify-content-center align-items-center" style={{height: '60vh'}}><Spinner animation="border" variant="success" /></div>;
    if (error) return <Alert variant="danger">{error}</Alert>;

    return (
      <Card className="shadow-sm mt-4">
        <Card.Body>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <Card.Title as="h2" className="mb-0 text-success">Scraped Publications</Card.Title>
            {publications.length > 0 && (
              <Button 
                variant="outline-success" 
                onClick={handleDownloadAll}
                className="d-flex align-items-center gap-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                  <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
                  <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/>
                </svg>
                Download All as BibTeX
              </Button>
            )}
          </div>
          {publications.length === 0 ? (
            <Alert variant="info">No scraped publications found.</Alert>
          ) : (
            <Table striped bordered hover responsive>
              <thead className="table-success">
                <tr>
                  <th>Raw Text</th>
                  <th>Processed BibTeX</th>
                  <th>Year</th>
                  <th>BibTeX Error</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {publications
                  .slice() // copy array
                  .sort((a, b) => (b.year || 0) - (a.year || 0))
                  .map(pub => {
                    return (
                      <tr key={pub.id}>
                        <td style={{maxWidth: 400}}>
                          {editingId === pub.id ? (
                            <textarea 
                              className="form-control form-control-sm" 
                              rows={4} 
                              value={editedData.raw_text} 
                              onChange={(e) => setEditedData({...editedData, raw_text: e.target.value})} 
                            />
                          ) : (
                            <div style={{maxHeight: 100, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: '0.9rem'}}>
                              {pub.raw_text || <span className="text-muted">-</span>}
                            </div>
                          )}
                        </td>
                        <td style={{maxWidth: 400}}>
                          {pub.bibtex ? (
                            <pre style={{
                              maxHeight: 100, 
                              overflow: 'auto', 
                              fontSize: '0.75rem', 
                              fontFamily: 'monospace',
                              backgroundColor: '#f8f9fa',
                              padding: '8px',
                              borderRadius: '4px',
                              margin: 0,
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word'
                            }}>
                              {pub.bibtex}
                            </pre>
                          ) : (
                            <span className="text-muted">-</span>
                          )}
                        </td>
                        <td style={{textAlign: 'center', verticalAlign: 'middle'}}>
                          {pub.year || <span className="text-muted">-</span>}
                        </td>
                        <td style={{textAlign: 'center', verticalAlign: 'middle'}}>
                          {pub.bibtex_error ? (
                            <span className="badge bg-danger">Yes</span>
                          ) : (
                            <span className="badge bg-success">No</span>
                          )}
                        </td>
                        <td style={{minWidth: 200}}>
                          {editingId === pub.id ? (
                            <div className="d-flex flex-column gap-2">
                              <Button variant="success" size="sm" onClick={() => saveEdit(pub.id)}>Save</Button>
                              <Button variant="secondary" size="sm" onClick={cancelEdit}>Cancel</Button>
                            </div>
                          ) : (
                            <div className="d-flex flex-column gap-2">
                              <Button variant="outline-success" size="sm" onClick={() => handleAddToDatabase(pub.id)}>
                                Add to Main Database
                              </Button>
                              <Button variant="outline-primary" size="sm" onClick={() => handleReprocessBibtex(pub.id)}>
                                Reprocess BibTeX
                              </Button>
                              <Button variant="outline-warning" size="sm" onClick={() => startEdit(pub)}>
                                Edit Raw Text
                              </Button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>
    );
};

export default ScrapedPublications;
