import React from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import './styles/App.css';

// Import components
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import PublicationsList from './pages/PublicationsList';
import PublicationDetail from './pages/PublicationDetail';
import CreatePublication from './pages/CreatePublication';
import EditPublication from './pages/EditPublication';
import Login from './pages/Login';
import ImportBibtex from './pages/ImportBibtex';
import { authService } from './services/api';

// Protected route component
const ProtectedRoute = ({ children }) => {
  const isAuthenticated = authService.isAuthenticated();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

function App() {
  return (
    <Router>
      <div className="App">
        <Navbar />
        <div className="container mt-4">
          <Routes>
            <Route path="/" element={<PublicationsList />} />
            <Route path="/publications" element={<PublicationsList />} />
            <Route path="/publications/author/:authorId" element={<PublicationsList />} />
            <Route path="/publications/:id" element={<PublicationDetail />} />
            <Route 
              path="/publications/create" 
              element={
                <ProtectedRoute>
                  <CreatePublication />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/publications/edit/:id" 
              element={
                <ProtectedRoute>
                  <EditPublication />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/publications/import-bibtex" 
              element={
                <ProtectedRoute>
                  <ImportBibtex />
                </ProtectedRoute>
              } 
            />
            <Route path="/login" element={<Login />} />
          </Routes>
        </div>
        <Footer />
      </div>
    </Router>
  );
}

export default App;