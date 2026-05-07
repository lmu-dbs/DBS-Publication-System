import axios from 'axios';

// In production, API calls will be relative to the current host with /api prefix
// In development, API calls will use the full URL from environment variables or localhost default
const API_URL = process.env.NODE_ENV === 'production' 
  ? '/api'
  : (process.env.REACT_APP_API_URL || 'http://localhost:8000');

// Create axios instance with baseURL
const api = axios.create({
  baseURL: API_URL,
});

// Add request interceptor to include auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export const reprocessScrapedPublication = async (id) => {
  const response = await api.post(`/scraping/scraped/${id}/reprocess`);
  return response.data;
};

// Authentication services
export const authService = {
  login: async (username, password) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await api.post('/users/token', formData);
    if (response.data.access_token) {
      localStorage.setItem('token', response.data.access_token);
    }
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('token');
  },

  isAuthenticated: () => {
    return !!localStorage.getItem('token');
  }
};

// Scraping services
export const scrapeUrl = async (url) => {
  const response = await api.post('/scraping', { url });
  return response.data;
};

export const getScrapedPublications = async () => {
  const response = await api.get('/scraping/scraped');
  return response.data;
};

export const updateScrapedPublication = async (id, data) => {
  const response = await api.put(`/scraping/scraped/${id}`, data);
  return response.data;
};

export const addScrapedToMain = async (id) => {
  const response = await api.post(`/scraping/scraped/${id}/add`);
  return response.data;
};

export const updateMainFromScraped = async (id) => {
  const response = await api.post(`/scraping/scraped/${id}/update-main`);
  return response.data;
};

export const scrapeMCML = async () => {
  const response = await api.post('/scraping/mcml');
  return response.data;
};

export const getScrapingStatus = async (entryId) => {
  const response = await api.get(`/scraping/${entryId}`);
  return response.data;
};

export const getScrapingHistory = async ({ search = '', status = '' } = {}) => {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (status) params.set('status', status);
  const response = await api.get(`/scraping/history?${params.toString()}`);
  return response.data;
};

export const deleteScrapingEntry = async (entryId) => {
  const response = await api.delete(`/scraping/${entryId}`);
  return response.data;
};

export const deleteAllScrapingHistory = async () => {
  const response = await api.delete('/scraping/history');
  return response.data;
};

export const exportScrapedBibtex = async () => {
  const response = await api.get('/scraping/scraped/export/bibtex', {
    responseType: 'blob'
  });
  return response;
};

// Publications services
export const publicationService = {
  deleteScrapedPublications: async () => {
    return await api.delete('/publications/scraped');
  },
  getPublications: async (authorId = null, search = null, venue = null, year = null, keyword = null) => {
    let url = '/publications';
    const params = {};
    
    if (authorId) params.author_id = authorId;
    if (search) params.search = search;
    if (venue) params.venue = venue;
    if (year) params.year = year;
    if (keyword) params.keyword = keyword;
    
    return await api.get(url, { params });
  },

  getPublication: async (id) => {
    return await api.get(`/publications/${id}`);
  },

  createPublication: async (publicationData) => {
    return await api.post('/publications', publicationData);
  },

  updatePublication: async (id, publicationData) => {
    return await api.put(`/publications/${id}`, publicationData);
  },

  deletePublication: async (id) => {
    return await api.delete(`/publications/${id}`);
  },

  importBibtex: async (bibtexString) => {
    return await api.post('/publications/import-bibtex', { bibtex_string: bibtexString });
  },

  importBibtexFile: async (file) => {
    // Create FormData for file upload
    const formData = new FormData();
    formData.append('bibtex_file', file);
    
    return await api.post('/publications/import-bibtex-file', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  exportBibtex: async (id) => {
    return await api.get(`/publications/${id}/export-bibtex`);
  },

  exportJson: async (authorId = null, search = null, venue = null, year = null, keyword = null) => {
    let url = '/publications/bulk-exports/json';
    const params = {};
    
    if (authorId) params.author_id = authorId;
    if (search) params.search = search;
    if (venue) params.venue = venue;
    if (year) params.year = year;
    if (keyword) params.keyword = keyword;
    
    return await api.get(url, { params });
  },
  
  exportBibtexList: async (authorId = null, search = null, venue = null, year = null, keyword = null) => {
    let url = '/publications/bulk-exports/bibtex';
    const params = {};
    
    if (authorId) params.author_id = authorId;
    if (search) params.search = search;
    if (venue) params.venue = venue;
    if (year) params.year = year;
    if (keyword) params.keyword = keyword;
    
    return await api.get(url, { params });
  }
};

// Authors services
export const authorService = {
  getAuthors: async () => {
    return await api.get('/authors');
  },

  getAuthor: async (id) => {
    return await api.get(`/authors/${id}`);
  },

  updateAuthor: async (id, authorData) => {
    return await api.put(`/authors/${id}`, authorData);
  },

  deleteAuthor: async (id) => {
    return await api.delete(`/authors/${id}`);
  },

  mergeAuthors: async (sourceId, targetId) => {
    return await api.post('/authors/merge', null, {
      params: { source_id: sourceId, target_id: targetId }
    });
  }
};
