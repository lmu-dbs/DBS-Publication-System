import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Form, Button, Card, Alert, Tabs, Tab, Table, InputGroup, Badge } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { scrapeUrl, scrapeMCML, getScrapingStatus, getScrapingHistory, deleteScrapingEntry, deleteAllScrapingHistory } from '../services/api';

const Scraping = () => {
  const [url, setUrl] = useState('');
  const [results, setResults] = useState([]);
  const [history, setHistory] = useState([]);
  const [historySearch, setHistorySearch] = useState('');
  const [historyStatus, setHistoryStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async (search = historySearch, status = historyStatus) => {
    try {
      const historyData = await getScrapingHistory({ search, status });
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
      loadHistory();
      setResults(prev => prev.filter(result => result.entry_id !== entryId));
    } catch (err) {
      setError(err.message || 'Failed to delete entry');
    }
  };

  const handleDeleteAllHistory = async () => {
    if (!window.confirm('Delete all scraping history entries? This cannot be undone.')) return;
    try {
      await deleteAllScrapingHistory();
      loadHistory();
    } catch (err) {
      setError(err.message || 'Failed to delete history');
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
                <Row className="mb-3 g-2">
                  <Col xs={12} md={6}>
                    <InputGroup>
                      <Form.Control
                        placeholder="Search by title or URL…"
                        value={historySearch}
                        onChange={e => {
                          setHistorySearch(e.target.value);
                          loadHistory(e.target.value, historyStatus);
                        }}
                      />
                      {historySearch && (
                        <Button variant="outline-secondary" onClick={() => { setHistorySearch(''); loadHistory('', historyStatus); }}>✕</Button>
                      )}
                    </InputGroup>
                  </Col>
                  <Col xs={12} md={3}>
                    <Form.Select
                      value={historyStatus}
                      onChange={e => { setHistoryStatus(e.target.value); loadHistory(historySearch, e.target.value); }}
                    >
                      <option value="">All statuses</option>
                      <option value="processed">Processed</option>
                      <option value="duplicate">Duplicate</option>
                      <option value="processing">Processing</option>
                      <option value="error">Error</option>
                    </Form.Select>
                  </Col>
                  <Col xs={6} md={2}>
                    <Button variant="outline-secondary" className="w-100" onClick={() => loadHistory()}>
                      Refresh
                    </Button>
                  </Col>
                  <Col xs={6} md={1}>
                    <Button variant="outline-danger" className="w-100" onClick={handleDeleteAllHistory} disabled={history.length === 0}>
                      Delete All
                    </Button>
                  </Col>
                </Row>

                {history.length === 0 ? (
                  <Alert variant="info">No entries found.</Alert>
                ) : (
                  <Table striped bordered hover responsive size="sm">
                    <thead className="table-dark">
                      <tr>
                        <th>#</th>
                        <th>Title</th>
                        <th>URL</th>
                        <th>Batch</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Processed</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map(entry => (
                        <tr key={entry.id}>
                          <td>{entry.id}</td>
                          <td style={{maxWidth: 300}}>
                            <span style={{fontSize: '0.85rem'}}>{entry.title || <span className="text-muted">—</span>}</span>
                          </td>
                          <td style={{maxWidth: 200}}>
                            <span className="text-muted" style={{fontSize: '0.8rem', wordBreak: 'break-all'}}>{entry.url}</span>
                          </td>
                          <td style={{fontSize: '0.8rem'}}>{entry.batch_id || <span className="text-muted">—</span>}</td>
                          <td>
                            <Badge bg={
                              entry.status === 'processed' ? 'success' :
                              entry.status === 'duplicate' ? 'secondary' :
                              entry.status === 'error' ? 'danger' : 'warning'
                            }>
                              {entry.status}
                            </Badge>
                          </td>
                          <td style={{fontSize: '0.8rem', whiteSpace: 'nowrap'}}>{new Date(entry.created_at).toLocaleString()}</td>
                          <td style={{fontSize: '0.8rem', whiteSpace: 'nowrap'}}>{entry.processed_at ? new Date(entry.processed_at).toLocaleString() : <span className="text-muted">—</span>}</td>
                          <td>
                            <Button
                              variant="outline-danger"
                              size="sm"
                              onClick={() => handleDelete(entry.id)}
                            >
                              ✕
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
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
