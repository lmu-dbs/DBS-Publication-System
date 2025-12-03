import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Alert, Spinner, Badge } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { authorService } from '../services/api';
import { authService } from '../services/api';

const Authors = () => {
  const [authors, setAuthors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showEditModal, setShowEditModal] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState(false);
  const [selectedAuthor, setSelectedAuthor] = useState(null);
  const [mergeSource, setMergeSource] = useState(null);
  const [mergeTarget, setMergeTarget] = useState('');
  const [editForm, setEditForm] = useState({
    forename: '',
    lastname: '',
    email: '',
    affiliation: ''
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortOrder, setSortOrder] = useState('asc');
  
  const isAuthenticated = authService.isAuthenticated();

  useEffect(() => {
    fetchAuthors();
  }, []);

  const fetchAuthors = async () => {
    try {
      setLoading(true);
      const response = await authorService.getAuthors();
      setAuthors(response.data);
      setError('');
    } catch (error) {
      console.error('Error fetching authors:', error);
      setError('Failed to load authors. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleEditClick = (author) => {
    setSelectedAuthor(author);
    setEditForm({
      forename: author.forename || '',
      lastname: author.lastname || '',
      email: author.email || '',
      affiliation: author.affiliation || ''
    });
    setShowEditModal(true);
    setError('');
    setSuccess('');
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      await authorService.updateAuthor(selectedAuthor.id, editForm);
      setSuccess(`Successfully updated ${selectedAuthor.name}`);
      setShowEditModal(false);
      fetchAuthors();
    } catch (error) {
      console.error('Error updating author:', error);
      setError('Failed to update author. Please try again.');
    }
  };

  const handleDeleteClick = async (author) => {
    if (window.confirm(`Are you sure you want to delete ${author.name}? This will remove the author from ${author.publication_count} publication(s).`)) {
      try {
        await authorService.deleteAuthor(author.id);
        setSuccess(`Successfully deleted ${author.name}`);
        fetchAuthors();
      } catch (error) {
        console.error('Error deleting author:', error);
        setError('Failed to delete author. Please try again.');
      }
    }
  };

  const handleMergeClick = (author) => {
    setMergeSource(author);
    setMergeTarget('');
    setShowMergeModal(true);
    setError('');
    setSuccess('');
  };

  const handleMergeSubmit = async (e) => {
    e.preventDefault();
    if (!mergeTarget) {
      setError('Please select a target author');
      return;
    }
    
    try {
      const response = await authorService.mergeAuthors(mergeSource.id, parseInt(mergeTarget));
      setSuccess(response.data.message);
      setShowMergeModal(false);
      fetchAuthors();
    } catch (error) {
      console.error('Error merging authors:', error);
      setError('Failed to merge authors. Please try again.');
    }
  };

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  const filteredAndSortedAuthors = authors
    .filter(author => {
      if (!searchTerm) return true;
      const searchLower = searchTerm.toLowerCase();
      return (
        author.name.toLowerCase().includes(searchLower) ||
        (author.email && author.email.toLowerCase().includes(searchLower)) ||
        (author.affiliation && author.affiliation.toLowerCase().includes(searchLower))
      );
    })
    .sort((a, b) => {
      let aVal, bVal;
      
      switch (sortBy) {
        case 'name':
          aVal = a.name.toLowerCase();
          bVal = b.name.toLowerCase();
          break;
        case 'publications':
          aVal = a.publication_count;
          bVal = b.publication_count;
          break;
        case 'email':
          aVal = (a.email || '').toLowerCase();
          bVal = (b.email || '').toLowerCase();
          break;
        case 'affiliation':
          aVal = (a.affiliation || '').toLowerCase();
          bVal = (b.affiliation || '').toLowerCase();
          break;
        default:
          return 0;
      }
      
      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

  const formatAuthorName = (author) => {
    if (author.forename && author.lastname) {
      const forename_parts = author.forename.split(' ');
      const initials = forename_parts.map(part => part.charAt(0).toUpperCase() + '.').join(' ');
      return `${initials} ${author.lastname}`;
    }
    return author.name;
  };

  const getSortIcon = (field) => {
    if (sortBy !== field) return '⇅';
    return sortOrder === 'asc' ? '↑' : '↓';
  };

  if (loading) {
    return (
      <div className="text-center mt-5">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </div>
    );
  }

  return (
    <div className="container mt-4">
      <h2>Authors</h2>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert variant="success" dismissible onClose={() => setSuccess('')}>{success}</Alert>}

      <div className="mb-3">
        <Form.Control
          type="text"
          placeholder="Search authors by name, email, or affiliation..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      <div className="mb-3">
        <Badge bg="secondary">Total Authors: {filteredAndSortedAuthors.length}</Badge>
      </div>

      <Table striped bordered hover responsive>
        <thead>
          <tr>
            <th onClick={() => handleSort('name')} style={{ cursor: 'pointer' }}>
              Name {getSortIcon('name')}
            </th>
            <th onClick={() => handleSort('email')} style={{ cursor: 'pointer' }}>
              Email {getSortIcon('email')}
            </th>
            <th onClick={() => handleSort('affiliation')} style={{ cursor: 'pointer' }}>
              Affiliation {getSortIcon('affiliation')}
            </th>
            <th onClick={() => handleSort('publications')} style={{ cursor: 'pointer' }}>
              Publications {getSortIcon('publications')}
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filteredAndSortedAuthors.map((author) => (
            <tr key={author.id}>
              <td>
                <Link to={`/publications?author=${author.id}`}>
                  {formatAuthorName(author)}
                </Link>
              </td>
              <td>{author.email || '-'}</td>
              <td>{author.affiliation || '-'}</td>
              <td>
                <Badge bg="primary">{author.publication_count}</Badge>
              </td>
              <td>
                {isAuthenticated && (
                  <>
                    <Button 
                      variant="outline-primary" 
                      size="sm" 
                      className="me-2"
                      onClick={() => handleEditClick(author)}
                    >
                      Edit
                    </Button>
                    <Button 
                      variant="outline-warning" 
                      size="sm" 
                      className="me-2"
                      onClick={() => handleMergeClick(author)}
                    >
                      Merge
                    </Button>
                    <Button 
                      variant="outline-danger" 
                      size="sm"
                      onClick={() => handleDeleteClick(author)}
                    >
                      Delete
                    </Button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>

      {filteredAndSortedAuthors.length === 0 && (
        <div className="text-center text-muted">
          No authors found matching your search criteria.
        </div>
      )}

      {/* Edit Author Modal */}
      <Modal show={showEditModal} onHide={() => setShowEditModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Edit Author</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form onSubmit={handleEditSubmit}>
            <Form.Group className="mb-3">
              <Form.Label>Forename</Form.Label>
              <Form.Control
                type="text"
                value={editForm.forename}
                onChange={(e) => setEditForm({ ...editForm, forename: e.target.value })}
                placeholder="John William"
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Lastname</Form.Label>
              <Form.Control
                type="text"
                value={editForm.lastname}
                onChange={(e) => setEditForm({ ...editForm, lastname: e.target.value })}
                placeholder="Smith"
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Email</Form.Label>
              <Form.Control
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                placeholder="author@example.com"
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Affiliation</Form.Label>
              <Form.Control
                type="text"
                value={editForm.affiliation}
                onChange={(e) => setEditForm({ ...editForm, affiliation: e.target.value })}
                placeholder="University Name"
              />
            </Form.Group>

            <div className="d-flex justify-content-end">
              <Button variant="secondary" className="me-2" onClick={() => setShowEditModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" type="submit">
                Save Changes
              </Button>
            </div>
          </Form>
        </Modal.Body>
      </Modal>

      {/* Merge Authors Modal */}
      <Modal show={showMergeModal} onHide={() => setShowMergeModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Merge Authors</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {mergeSource && (
            <>
              <Alert variant="warning">
                This will merge <strong>{mergeSource.name}</strong> into another author.
                All publications from {mergeSource.name} will be moved to the target author,
                and {mergeSource.name} will be deleted.
              </Alert>
              
              <Form onSubmit={handleMergeSubmit}>
                <Form.Group className="mb-3">
                  <Form.Label>Source Author (will be deleted)</Form.Label>
                  <Form.Control
                    type="text"
                    value={formatAuthorName(mergeSource)}
                    disabled
                  />
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Target Author (will keep all publications)</Form.Label>
                  <Form.Select
                    value={mergeTarget}
                    onChange={(e) => setMergeTarget(e.target.value)}
                    required
                  >
                    <option value="">Select target author...</option>
                    {authors
                      .filter(a => a.id !== mergeSource.id)
                      .map(author => (
                        <option key={author.id} value={author.id}>
                          {formatAuthorName(author)} ({author.publication_count} publications)
                        </option>
                      ))
                    }
                  </Form.Select>
                </Form.Group>

                <div className="d-flex justify-content-end">
                  <Button variant="secondary" className="me-2" onClick={() => setShowMergeModal(false)}>
                    Cancel
                  </Button>
                  <Button variant="warning" type="submit">
                    Merge Authors
                  </Button>
                </div>
              </Form>
            </>
          )}
        </Modal.Body>
      </Modal>
    </div>
  );
};

export default Authors;
