(() => {
    const cards = Array.from(document.querySelectorAll('mat-card'));
  
    const entries = cards.map((card, index) => {
      const title = card.querySelector('mat-card-title')?.textContent.trim() || 'No Title';
      const subtitle = card.querySelector('mat-card-subtitle');
      const lines = subtitle?.innerText.split('\n').map(s => s.trim()).filter(Boolean) || [];
  
      const metadataLine = lines[0] || '';
      const parts = metadataLine.split(',').map(p => p.trim());
  
      const venue = parts[0] || 'Unknown Venue';
      const location = parts[1] || '';
      const date = parts[2] || '';
      const pages = (metadataLine.match(/pp?\.\s*[\d\-–]+/i) || [''])[0].replace(/pp?\.\s*/i, '');
  
      const authorsP = subtitle?.querySelector('p');
      const authorsRaw = authorsP?.textContent.trim() || 'Unknown';
      const authors = authorsRaw.split(',').map(a => a.trim()).join(' and ');
  
      // ✅ Extract year after a comma (robust)
      const yearMatch = metadataLine.match(/,\s*.*?(\b(19|20)\d{2}\b)/);
      const year = yearMatch ? yearMatch[1] : 'Unknown';
  
      // ✅ Try to get the link from <span><a href>
      const spanLink = subtitle?.querySelector('span a');
      const url = spanLink?.href || '';
  
      const firstAuthorLastName = authors.split(' and ')[0].split(' ').pop().toLowerCase();
      const key = `${firstAuthorLastName}${year}${index}`;
  
      return `@inproceedings{${key},
    title = {${title}},
    author = {${authors}},
    booktitle = {${venue}},
    year = {${year}},
    address = {${location}},
    pages = {${pages}},
    note = {${date}}${url ? `,\n  url = {${url}}` : ''}
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
  