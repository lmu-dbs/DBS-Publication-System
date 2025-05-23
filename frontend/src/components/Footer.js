import React from 'react';

const Footer = () => {
  const footerStyle = {
    marginTop: 'auto',
    padding: '20px 0',
    backgroundColor: '#f8f9fa',
    borderTop: '1px solid #e5e5e5',
    fontSize: '0.9rem'
  };

  const linkStyle = {
    color: '#048850',
    textDecoration: 'none',
    marginRight: '20px'
  };

  return (
    <footer style={footerStyle}>
      <div className="container">
        <div className="d-flex justify-content-between align-items-center">
          <div>
            <a 
              href="https://www.dbs.ifi.lmu.de/cms/kontakt/index.html" 
              target="_blank" 
              rel="noopener noreferrer"
              style={linkStyle}
            >
              Kontakt
            </a>
            <a 
              href="https://www.lmu.de/de/footer/datenschutz/" 
              target="_blank" 
              rel="noopener noreferrer"
              style={linkStyle}
            >
              Datenschutz
            </a>
            <a 
              href="https://www.lmu.de/de/footer/impressum/" 
              target="_blank" 
              rel="noopener noreferrer"
              style={linkStyle}
            >
              Impressum
            </a>
          </div>
          <div className="text-muted">
            © {new Date().getFullYear()} Lehrstuhl für Datenbanksysteme und Data Mining
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;