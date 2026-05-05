import React, { useState } from 'react';
import { Form, Button, Alert, Row, Col } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { publicationService } from '../services/api';

const CreatePublication = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    title: '',
    abstract: '',
    year: new Date().getFullYear(),
    venue: '',
    publication_type: 'article',
    doi: '',
    url: '',
    authors: [{ name: '', email: '', affiliation: '' }]
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleAuthorChange = (index, field, value) => {
    const newAuthors = [...formData.authors];
    newAuthors[index] = { ...newAuthors[index], [field]: value };
    setFormData({ ...formData, authors: newAuthors });
  };

  const addAuthorField = () => {
    setFormData({
      ...formData,
      authors: [...formData.authors, { name: '', email: '', affiliation: '' }]
    });
  };

  const removeAuthorField = (index) => {
    const newAuthors = formData.authors.filter((_, i) => i !== index);
    setFormData({ ...formData, authors: newAuthors });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Filter out empty authors
      const authors = formData.authors.filter(author => author.name.trim() !== '');
      
      if (authors.length === 0) {
        setError('At least one author with a name is required');
        setLoading(false);
        return;
      }

      const publicationData = {
        ...formData,
        authors,
        year: parseInt(formData.year)
      };

      await publicationService.createPublication(publicationData);
      navigate('/publications');
    } catch (error) {
      console.error('Error creating publication:', error);
      setError(error.response?.data?.detail || 'Failed to create publication. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="mb-4">Add New Publication</h2>

      {error && <Alert variant="danger">{error}</Alert>}

      <Form onSubmit={handleSubmit}>
        <Form.Group className="mb-3" controlId="title">
          <Form.Label>Title*</Form.Label>
          <Form.Control
            type="text"
            name="title"
            value={formData.title}
            onChange={handleChange}
            placeholder="Publication title"
            required
          />
        </Form.Group>

        <Form.Group className="mb-3" controlId="abstract">
          <Form.Label>Abstract</Form.Label>
          <Form.Control
            as="textarea"
            rows={4}
            name="abstract"
            value={formData.abstract}
            onChange={handleChange}
            placeholder="Abstract of the publication"
          />
        </Form.Group>

        <Row>
          <Col md={6}>
            <Form.Group className="mb-3" controlId="year">
              <Form.Label>Year*</Form.Label>
              <Form.Control
                type="number"
                name="year"
                value={formData.year}
                onChange={handleChange}
                placeholder="Publication year"
                min="1900"
                max="2100"
                required
              />
            </Form.Group>
          </Col>
          <Col md={6}>
            <Form.Group className="mb-3" controlId="publication_type">
              <Form.Label>Publication Type*</Form.Label>
              <Form.Select 
                name="publication_type"
                value={formData.publication_type}
                onChange={handleChange}
                required
              >
                <option value="article">Article</option>
                <option value="inproceedings">Conference Paper</option>
                <option value="book">Book</option>
                <option value="incollection">Book Chapter</option>
                <option value="techreport">Technical Report</option>
                <option value="thesis">Thesis</option>
                <option value="phdthesis">Dissertation</option>
                <option value="unpublished">Preprint</option>
                <option value="misc">Other</option>
              </Form.Select>
            </Form.Group>
          </Col>
        </Row>

        <Form.Group className="mb-3" controlId="venue">
          <Form.Label>Venue</Form.Label>
          <Form.Control
            type="text"
            name="venue"
            value={formData.venue}
            onChange={handleChange}
            placeholder="Journal, conference, or publisher name"
          />
        </Form.Group>

        <Row>
          <Col md={6}>
            <Form.Group className="mb-3" controlId="doi">
              <Form.Label>DOI</Form.Label>
              <Form.Control
                type="text"
                name="doi"
                value={formData.doi}
                onChange={handleChange}
                placeholder="Digital Object Identifier"
              />
            </Form.Group>
          </Col>
          <Col md={6}>
            <Form.Group className="mb-3" controlId="url">
              <Form.Label>URL</Form.Label>
              <Form.Control
                type="url"
                name="url"
                value={formData.url}
                onChange={handleChange}
                placeholder="Link to the publication"
              />
            </Form.Group>
          </Col>
        </Row>

        <h4 className="mt-4 mb-3">Authors</h4>
        {formData.authors.map((author, index) => (
          <div key={index} className="author-entry border-top pt-3 mb-3">
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3" controlId={`author-name-${index}`}>
                  <Form.Label>Name*</Form.Label>
                  <Form.Control
                    type="text"
                    value={author.name}
                    onChange={(e) => handleAuthorChange(index, 'name', e.target.value)}
                    placeholder="Author's full name"
                    required={index === 0}
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3" controlId={`author-email-${index}`}>
                  <Form.Label>Email</Form.Label>
                  <Form.Control
                    type="email"
                    value={author.email}
                    onChange={(e) => handleAuthorChange(index, 'email', e.target.value)}
                    placeholder="Author's email"
                  />
                </Form.Group>
              </Col>
            </Row>

            <Form.Group className="mb-3" controlId={`author-affiliation-${index}`}>
              <Form.Label>Affiliation</Form.Label>
              <Form.Control
                type="text"
                value={author.affiliation}
                onChange={(e) => handleAuthorChange(index, 'affiliation', e.target.value)}
                placeholder="Author's institution or organization"
              />
            </Form.Group>

            {index > 0 && (
              <Button 
                variant="outline-danger" 
                size="sm"
                onClick={() => removeAuthorField(index)}
                className="mb-3"
              >
                Remove Author
              </Button>
            )}
          </div>
        ))}

        <Button 
          variant="outline-primary" 
          className="mb-4"
          onClick={addAuthorField}
          type="button"
        >
          Add Another Author
        </Button>

        <div className="d-grid gap-2 mt-4">
          <Button variant="primary" type="submit" disabled={loading}>
            {loading ? 'Saving...' : 'Save Publication'}
          </Button>
        </div>
      </Form>
    </div>
  );
};

export default CreatePublication;