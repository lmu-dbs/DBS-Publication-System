import React, { useState } from 'react';
import { Form, Button, Alert, Tabs, Tab, Accordion, Table } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { publicationService } from '../services/api';

const ImportBibtex = () => {
  const [bibtexInput, setBibtexInput] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [importStats, setImportStats] = useState(null);
  const [activeTab, setActiveTab] = useState('paste');
  const navigate = useNavigate();
  
  const handlePasteSubmit = async (e) => {
    e.preventDefault();
    
    if (!bibtexInput.trim()) {
      setError('Please enter BibTeX data');
      return;
    }
    
    setError('');
    setLoading(true);
    
    try {
      const response = await publicationService.importBibtex(bibtexInput);
      if (response.data) {
        navigate('/publications');
      }
    } catch (error) {
      console.error('Error importing BibTeX:', error);
      setError(error.response?.data?.detail || 'Failed to import BibTeX. Please check your input.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.type !== 'application/x-bibtex' && 
          file.type !== 'text/plain' && 
          !file.name.endsWith('.bib') && 
          !file.name.endsWith('.bibtex') && 
          !file.name.endsWith('.txt')) {
        setError('Please upload a valid BibTeX file (.bib, .bibtex, or .txt)');
        setUploadedFile(null);
      } else {
        setError('');
        setUploadedFile(file);
      }
    }
  };
  
  const handleFileSubmit = async (e) => {
    e.preventDefault();
    
    if (!uploadedFile) {
      setError('Please select a BibTeX file to upload');
      return;
    }
    
    setError('');
    setLoading(true);
    
    try {
      const response = await publicationService.importBibtexFile(uploadedFile);
      setImportStats({
        success: response.data.success_count || 0,
        failed: response.data.failed_count || 0,
        duplicates: response.data.duplicate_count || 0,
        total: response.data.total_count || 0,
        duplicateEntries: response.data.duplicate_entries || [],
        failedEntries: response.data.failed_entries || []
      });
    } catch (error) {
      console.error('Error importing BibTeX file:', error);
      setError(error.response?.data?.detail || 'Failed to import BibTeX file. Please check your file format.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleTabSelect = (key) => {
    setActiveTab(key);
    setError('');
  };
  
  const handleGoToPublications = () => {
    navigate('/publications');
  };
  
  // Helper function to render author names from an array
  const formatAuthors = (authors) => {
    if (!authors || authors.length === 0) return "No authors";
    if (authors.length <= 2) return authors.join(" and ");
    return `${authors[0]} et al.`;
  };
  
  return (
    <div>
      <h2>Import Publications from BibTeX</h2>
      
      {error && <Alert variant="danger">{error}</Alert>}
      
      {importStats ? (
        <div className="mt-4">
          <Alert variant="success">
            <Alert.Heading>Import Complete</Alert.Heading>
            <p>
              Successfully imported: <strong>{importStats.success}</strong> publication(s)<br />
              Total entries processed: <strong>{importStats.total}</strong>
            </p>
            
            {(importStats.duplicates > 0 || importStats.failed > 0) && (
              <Accordion className="mt-3 mb-3">
                {importStats.duplicates > 0 && (
                  <Accordion.Item eventKey="0">
                    <Accordion.Header>
                      <span className="text-warning">Duplicates skipped: <strong>{importStats.duplicates}</strong></span>
                    </Accordion.Header>
                    <Accordion.Body>
                      <p>The following entries were identified as duplicates and skipped:</p>
                      {importStats.duplicateEntries && importStats.duplicateEntries.length > 0 ? (
                        <Table striped bordered hover size="sm">
                          <thead>
                            <tr>
                              <th>#</th>
                              <th>Title</th>
                              <th>Year</th>
                              <th>Authors</th>
                              <th>Reason</th>
                            </tr>
                          </thead>
                          <tbody>
                            {importStats.duplicateEntries.map((entry, idx) => (
                              <tr key={idx}>
                                <td>{idx + 1}</td>
                                <td>{entry.title}</td>
                                <td>{entry.year}</td>
                                <td>{formatAuthors(entry.authors)}</td>
                                <td>{entry.reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </Table>
                      ) : (
                        <div className="border rounded p-2 bg-light">
                          <p className="mb-0 font-monospace">
                            {Array(importStats.duplicates).fill(0).map((_, i) => (
                              <span key={i} className="d-block text-muted">
                                Duplicate #{i+1}: Entry with matching title and year already exists in database
                              </span>
                            ))}
                          </p>
                        </div>
                      )}
                      <small className="text-muted mt-2 d-block">
                        Note: Duplicates are determined by matching title and publication year
                      </small>
                    </Accordion.Body>
                  </Accordion.Item>
                )}
                
                {importStats.failed > 0 && (
                  <Accordion.Item eventKey="1">
                    <Accordion.Header>
                      <span className="text-danger">Failed entries: <strong>{importStats.failed}</strong></span>
                    </Accordion.Header>
                    <Accordion.Body>
                      <p>The following entries could not be processed:</p>
                      {importStats.failedEntries && importStats.failedEntries.length > 0 ? (
                        <Table striped bordered hover size="sm">
                          <thead>
                            <tr>
                              <th>#</th>
                              <th>Title</th>
                              <th>Year</th>
                              <th>Authors</th>
                              <th>Error</th>
                            </tr>
                          </thead>
                          <tbody>
                            {importStats.failedEntries.map((entry, idx) => (
                              <tr key={idx}>
                                <td>{idx + 1}</td>
                                <td>{entry.title}</td>
                                <td>{entry.year}</td>
                                <td>{formatAuthors(entry.authors)}</td>
                                <td>{entry.reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </Table>
                      ) : (
                        <div className="border rounded p-2 bg-light">
                          <p className="mb-0 font-monospace">
                            {Array(importStats.failed).fill(0).map((_, i) => (
                              <span key={i} className="d-block text-muted">
                                Failed #{i+1}: Entry may have missing required fields (title, year) or invalid format
                              </span>
                            ))}
                          </p>
                        </div>
                      )}
                    </Accordion.Body>
                  </Accordion.Item>
                )}
              </Accordion>
            )}
            
            <div className="d-flex justify-content-end">
              <Button variant="outline-success" onClick={handleGoToPublications}>
                View Publications
              </Button>
            </div>
          </Alert>
        </div>
      ) : (
        <Tabs
          activeKey={activeTab}
          onSelect={handleTabSelect}
          id="bibtex-import-tabs"
          className="mb-3"
        >
          <Tab eventKey="paste" title="Paste BibTeX">
            <Form onSubmit={handlePasteSubmit}>
              <Form.Group className="mb-3" controlId="bibtexInput">
                <Form.Label>Paste BibTeX Data</Form.Label>
                <Form.Control
                  as="textarea"
                  rows={10}
                  value={bibtexInput}
                  onChange={(e) => setBibtexInput(e.target.value)}
                  placeholder="Paste BibTeX entry here..."
                  required
                />
                <Form.Text className="text-muted">
                  Example:
                  <pre>
                  {`@article{smith2022example,
  title = {Example Article Title},
  author = {John Smith and Jane Doe},
  journal = {Journal of Examples},
  year = {2022},
  volume = {10},
  pages = {100-110},
  doi = {10.1234/example.2022}
}`}
                  </pre>
                </Form.Text>
              </Form.Group>
              
              <Button variant="primary" type="submit" disabled={loading}>
                {loading ? 'Importing...' : 'Import Publication'}
              </Button>
            </Form>
          </Tab>
          
          <Tab eventKey="file" title="Upload BibTeX File">
            <Form onSubmit={handleFileSubmit}>
              <Form.Group className="mb-3" controlId="bibtexFile">
                <Form.Label>Upload BibTeX File</Form.Label>
                <Form.Control
                  type="file"
                  onChange={handleFileChange}
                  accept=".bib,.bibtex,.txt"
                />
                <Form.Text className="text-muted">
                  Supported file formats: .bib, .bibtex, or .txt
                </Form.Text>
              </Form.Group>
              
              <div className="d-flex align-items-center">
                <Button variant="primary" type="submit" disabled={loading || !uploadedFile}>
                  {loading ? 'Uploading...' : 'Upload and Import File'}
                </Button>
                
                {uploadedFile && (
                  <span className="ms-3 text-success">
                    File selected: {uploadedFile.name}
                  </span>
                )}
              </div>
            </Form>
            
            <div className="mt-4">
              <Alert variant="info">
                <Alert.Heading>Importing Large BibTeX Files</Alert.Heading>
                <p>
                  This feature allows you to upload and import multiple publications at once.
                  The system will:
                </p>
                <ul>
                  <li>Process each BibTeX entry individually</li>
                  <li>Skip duplicate entries (based on title and year)</li>
                  <li>Report successful imports, duplicates, and failed entries</li>
                </ul>
                <p>
                  For very large files (1000+ entries), the import process may take several minutes.
                </p>
              </Alert>
            </div>
          </Tab>
        </Tabs>
      )}
    </div>
  );
};

export default ImportBibtex;