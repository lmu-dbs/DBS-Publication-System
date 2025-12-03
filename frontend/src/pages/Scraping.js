import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Form, Button, Card, Alert, Tabs, Tab } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { scrapeUrl, scrapeMCML, getScrapingStatus, getScrapingHistory, deleteScrapingEntry } from '../services/api';

const Scraping = () => {
  const [url, setUrl] = useState('');
  const [results, setResults] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const historyData = await getScrapingHistory();
      setHistory(historyData);
    } catch (err) {
      console.error('Error loading history:', err);
    }
  };

  const handleCustomScrape = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await scrapeUrl(url);
      setResults([response]);
      // Refresh history to show the new entry
      loadHistory();
    } catch (err) {
      setError(err.message || 'Failed to start scraping');
    }
    setLoading(false);
  };

  const handleMCMLScrape = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await scrapeMCML();
      setResults(response.results);
      // Refresh history to show the new entries
      loadHistory();
    } catch (err) {
      setError(err.message || 'Failed to start MCML scraping');
    }
    setLoading(false);
  };

  const handleDelete = async (entryId) => {
    try {
      await deleteScrapingEntry(entryId);
      // Refresh history after deletion
      loadHistory();
      // Remove from current results if present
      setResults(prev => prev.filter(result => result.entry_id !== entryId));
    } catch (err) {
      setError(err.message || 'Failed to delete entry');
    }
  };

  return (
    <Container className="mt-4 mb-4">
      <Card className="mb-4">
        <Card.Body>
          <h2 className="mb-4">Publication Scraping</h2>

          <Tabs defaultActiveKey="new" className="mb-4">
            <Tab eventKey="new" title="New Scraping">
              {/* Custom URL Scraping */}
              <div className="mt-3">
                <Form onSubmit={handleCustomScrape} className="mb-4">
                  <Row className="align-items-center">
                    <Col xs={12} sm={8} className="mb-2 mb-sm-0">
                      <Form.Control
                        type="url"
                        placeholder="Enter URL to scrape"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        disabled={loading}
                      />
                    </Col>
                    <Col xs={12} sm={4}>
                      <Button
                        type="submit"
                        variant="primary"
                        className="w-100"
                        disabled={loading || !url}
                      >
                        Scrape URL
                      </Button>
                    </Col>
                  </Row>
                </Form>

                {/* MCML Scraping */}
                <Button
                  variant="secondary"
                  className="w-100 mb-4"
                  onClick={handleMCMLScrape}
                  disabled={loading}
                >
                  Scrape All MCML Groups
                </Button>

                {/* Error Display */}
                {error && (
                  <Alert variant="danger" className="mb-3">
                    {error}
                  </Alert>
                )}

                {/* Current Results Display */}
                {results.map((result, index) => (
                  <Card key={index} className="mb-3">
                    <Card.Body>
                      <Card.Title>
                        {result.group ? `Group: ${result.group}` : 'Custom URL'}
                      </Card.Title>
                      <Card.Text>
                        Status: {result.status}
                        {result.url && (
                          <div className="text-muted small">
                            URL: {result.url}
                          </div>
                        )}
                        {result.publications_found !== undefined && (
                          <div className="text-muted small">
                            Publications found: {result.publications_found}
                          </div>
                        )}
                      </Card.Text>
                      {result.bibtex && (
                        <pre className="bg-light p-2 mt-2 rounded small">
                          {result.bibtex}
                        </pre>
                      )}
                    </Card.Body>
                  </Card>
                ))}
              </div>
            </Tab>

            <Tab eventKey="history" title="Scraping History">
              <div className="mt-3">
                {history.length === 0 ? (
                  <Alert variant="info">No previous scraping entries found.</Alert>
                ) : (
                  history.map((entry) => (
                    <Card key={entry.id} className="mb-3">
                      <Card.Body>
                        <div className="d-flex justify-content-between align-items-start">
                          <Card.Title>Scraping Entry #{entry.id}</Card.Title>
                          <Button 
                            variant="outline-danger" 
                            size="sm"
                            onClick={() => handleDelete(entry.id)}
                          >
                            Delete
                          </Button>
                        </div>
                        <Card.Text>
                          <div>
                            Status: {' '}
                            <span className={
                              entry.status === 'processed' ? 'text-success' :
                              entry.status === 'error' ? 'text-danger' :
                              'text-warning'
                            }>
                              {entry.status}
                            </span>
                          </div>
                          <div className="text-muted small">URL: {entry.url}</div>
                          <div className="text-muted small">
                            Created: {new Date(entry.created_at).toLocaleString()}
                          </div>
                          {entry.processed_at && (
                            <div className="text-muted small">
                              Processed: {new Date(entry.processed_at).toLocaleString()}
                            </div>
                          )}
                        </Card.Text>
                        {entry.status === 'error' ? (
                          <Alert variant="danger" className="mt-2">
                            Error: {entry.bibtex}
                          </Alert>
                        ) : entry.bibtex && (
                          <pre className="bg-light p-2 mt-2 rounded small">
                            {entry.bibtex}
                          </pre>
                        )}
                      </Card.Body>
                    </Card>
                  ))
                )}
              </div>
            </Tab>
          </Tabs>
        </Card.Body>
      </Card>
    </Container>
  );
};

export default Scraping;
