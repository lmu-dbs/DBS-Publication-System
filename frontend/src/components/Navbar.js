import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Navbar as BootstrapNavbar, Nav, Container, Image, Offcanvas, Button } from 'react-bootstrap';
import { authService } from '../services/api';

const Navbar = () => {
  const navigate = useNavigate();
  const isLoggedIn = authService.isAuthenticated();
  const [showMenu, setShowMenu] = useState(false);

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
    setShowMenu(false);
  };

  const handleClose = () => setShowMenu(false);
  const handleShow = () => setShowMenu(true);

  const navbarStyle = {
    backgroundColor: 'white',
    boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
    padding: '12px 0',
    borderBottom: '1px solid #e5e5e5'
  };

  const brandTextStyle = {
    color: '#000000',
    fontWeight: 500,
    fontSize: '1.1rem',
    marginLeft: '10px',
    lineHeight: '1.2'
  };

  const menuIconStyle = {
    cursor: 'pointer',
    padding: '5px',
    borderRadius: '4px',
    border: '1px solid #e5e5e5',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '40px',
    height: '40px',
    backgroundColor: 'rgba(0, 0, 0, 0.05)'
  };

  const navLinkStyle = {
    color: 'white',
    transition: 'all 0.3s ease',
    padding: '10px 15px',
    borderRadius: '4px',
    margin: '2px 0'
  };

  const navLinkHoverStyle = {
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    transform: 'translateX(5px)'
  };

  const logoutButtonStyle = {
    backgroundColor: '#00742c',
    borderColor: '#00742c',
    color: 'white',
    transition: 'all 0.3s ease'
  };

  const logoutButtonHoverStyle = {
    backgroundColor: '#004d00',
    borderColor: '#004d00',
    transform: 'scale(1.05)'
  };

  const offcanvasStyle = {
    backgroundColor: '#00883a'
  };

  const offcanvasHeaderStyle = {
    backgroundColor: '#00883a',
    color: 'white',
    borderBottom: '1px solid rgba(255, 255, 255, 0.2)'
  };

  const [hoveredLink, setHoveredLink] = useState(null);
  const [hoveredButton, setHoveredButton] = useState(false);

  return (
    <>
      <BootstrapNavbar style={navbarStyle} expand={false}>
        <Container className="d-flex justify-content-between align-items-center">
          <BootstrapNavbar.Brand as={Link} to="/" className="d-flex align-items-center">
            <Image 
              src="/images/lmu-logo.png" 
              alt="LMU Logo" 
              height="40" 
              className="me-2" 
            />
            <span style={brandTextStyle}>Database Systems and<br />Data Mining Lab</span>
          </BootstrapNavbar.Brand>
          
          <div style={menuIconStyle} onClick={handleShow}>
            <Image 
              src="/images/menu-icon.svg" 
              alt="Menu" 
              width="20" 
              height="20" 
            />
          </div>
        </Container>
      </BootstrapNavbar>

      <Offcanvas show={showMenu} onHide={handleClose} placement="end" backdropClassName="bg-transparent">
        <Offcanvas.Header closeButton style={offcanvasHeaderStyle}>
          <Offcanvas.Title className="text-white">Menu</Offcanvas.Title>
        </Offcanvas.Header>
        <Offcanvas.Body style={offcanvasStyle}>
          <Nav className="flex-column">
            <Nav.Link 
              as={Link} 
              to="/publications" 
              onClick={handleClose} 
              style={{...navLinkStyle, ...(hoveredLink === 'publications' ? navLinkHoverStyle : {})}} 
              onMouseEnter={() => setHoveredLink('publications')}
              onMouseLeave={() => setHoveredLink(null)}
            >
              Publications
            </Nav.Link>
            {isLoggedIn && (
              <>
                <Nav.Link 
                  as={Link} 
                  to="/publications/create" 
                  onClick={handleClose} 
                  style={{...navLinkStyle, ...(hoveredLink === 'create' ? navLinkHoverStyle : {})}} 
                  onMouseEnter={() => setHoveredLink('create')}
                  onMouseLeave={() => setHoveredLink(null)}
                >
                  Add Publication
                </Nav.Link>
                <Nav.Link 
                  as={Link} 
                  to="/publications/import-bibtex" 
                  onClick={handleClose} 
                  style={{...navLinkStyle, ...(hoveredLink === 'import' ? navLinkHoverStyle : {})}} 
                  onMouseEnter={() => setHoveredLink('import')}
                  onMouseLeave={() => setHoveredLink(null)}
                >
                  Import BibTeX
                </Nav.Link>
              </>
            )}
            <hr style={{borderColor: 'rgba(255, 255, 255, 0.2)'}} />
            {isLoggedIn ? (
              <Button 
                variant="success" 
                onClick={handleLogout} 
                className="mt-2" 
                style={{...logoutButtonStyle, ...(hoveredButton ? logoutButtonHoverStyle : {})}}
                onMouseEnter={() => setHoveredButton(true)}
                onMouseLeave={() => setHoveredButton(false)}
              >
                Logout
              </Button>
            ) : (
              <Nav.Link 
                as={Link} 
                to="/login" 
                onClick={handleClose} 
                style={{...navLinkStyle, ...(hoveredLink === 'login' ? navLinkHoverStyle : {})}} 
                onMouseEnter={() => setHoveredLink('login')}
                onMouseLeave={() => setHoveredLink(null)}
              >
                Admin Login
              </Nav.Link>
            )}
          </Nav>
        </Offcanvas.Body>
      </Offcanvas>
    </>
  );
};

export default Navbar;