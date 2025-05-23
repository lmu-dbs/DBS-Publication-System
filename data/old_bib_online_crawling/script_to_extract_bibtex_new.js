(() => {
    const cards = Array.from(document.querySelectorAll('mat-card'));
  
    const entries = cards.map((card, index) => {
      const title = card.querySelector('mat-card-title')?.textContent.trim() || 'No Title';
      const subtitle = card.querySelector('mat-card-subtitle');
      const lines = subtitle?.innerText.split('\n').map(s => s.trim()).filter(Boolean) || [];
  
      const metadataLine = lines[0] || '';
      const authorsP = subtitle?.querySelector('p');
      let authorsRaw = authorsP?.textContent.trim() || 'Unknown';
  
      // ✅ Remove 'née' clause (e.g., ", née Smith")
      authorsRaw = authorsRaw.replace(/,\s*née\s+[^\s,]+/gi, '');
      const authors = authorsRaw.split(',').map(a => a.trim()).join(' and ');
  
      // ===============================
      // 🔍 Parse venue, location, year, pages
      // ===============================
      let venue = 'Unknown Venue';
      let location = '';
      let year = 'Unknown';
      let pages = '';
  
      // Pattern 1: Proceedings ..., City, Country, 2022: 12:34–56
      const pattern1 = metadataLine.match(/^(.*?),\s*(.*?),\s*(\b(19|20)\d{2}\b)[:\s]+([\w:\-–]+)$/);
      if (pattern1) {
        venue = pattern1[1];
        location = pattern1[2];
        year = pattern1[3];
        pages = pattern1[5];
      } 
      // Pattern 2: Advances in X, null(null): null (2022)
      else if (metadataLine.match(/\((19|20)\d{2}\)$/)) {
        const yearMatch = metadataLine.match(/\((19|20)\d{2}\)$/);
        year = yearMatch ? yearMatch[1] : 'Unknown';
        venue = metadataLine.split(',')[0];
      }
      // Pattern 3: InBook - 2018
      else if (metadataLine.toLowerCase().startsWith('inbook')) {
        venue = 'InBook';
        const yearMatch = metadataLine.match(/\b(19|20)\d{2}\b/);
        year = yearMatch ? yearMatch[0] : 'Unknown';
      }
      // Fallback: look for first 4-digit number after comma
      else {
        const yearMatch = metadataLine.match(/,\s*.*?(\b(19|20)\d{2}\b)/);
        year = yearMatch ? yearMatch[1] : 'Unknown';
        venue = metadataLine.split(',')[0];
      }
  
      // ✅ Try to get the link from <span><a href>
      const spanLink = subtitle?.querySelector('span a');
      const url = spanLink?.href || '';
  
      const firstAuthorLastName = authors.split(' and ')[0].split(' ').pop().toLowerCase();
      const key = `${firstAuthorLastName}${year}${index}`;
  
      return `@inproceedings{${key},
    title = {${title}},
    author = {${authors}},
    booktitle = {${venue}},
    year = {${year}},${
        location ? `\n  address = {${location}},` : ''
      }${
        pages ? `\n  pages = {${pages}},` : ''
      }
    note = {${metadataLine}}${
        url ? `,\n  url = {${url}}` : ''
      }
  }`;
    });
  
    const blob = new Blob([entries.join('\n\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'lmu_dbs_publications.bib';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  })();
  