const grid = document.querySelector('#item-grid');
const searchForm = document.querySelector('#search-form');
const searchInput = document.querySelector('#search-input');
const resultCount = document.querySelector('#result-count');
const notice = document.querySelector('#page-notice');
const detailsDialog = document.querySelector('#details-dialog');
const detailsContent = document.querySelector('#details-content');
let searchTimer;

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[char]);

const formattedDate = (value) => {
  if (!value) return 'Date not provided';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(parsed);
};

const placeholder = `
  <div class="image-placeholder" aria-label="Image not available">
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <rect x="7" y="9" width="34" height="30" rx="4"></rect>
      <circle cx="18" cy="19" r="3"></circle>
      <path d="m9 34 10-10 7 7 5-5 8 8"></path>
    </svg>
  </div>`;

function imageMarkup(src, alt, className) {
  if (!src) return placeholder;
  return `<img class="${className}" src="${escapeHtml(src)}" alt="${escapeHtml(alt)}" loading="lazy">`;
}

function attachImageFallbacks(root) {
  root.querySelectorAll('img.item-image, img.details-image').forEach((image) => {
    image.addEventListener('error', () => {
      const wrapper = document.createElement('div');
      wrapper.innerHTML = placeholder.trim();
      image.replaceWith(wrapper.firstElementChild);
    }, { once: true });
  });
}

function itemCard(item) {
  const statusClass = item.type === 'Found' ? 'found' : '';
  return `
    <article class="item-card">
      <div class="item-image-wrap">
        ${imageMarkup(item.image, item.name, 'item-image')}
        <span class="status-badge ${statusClass}">${escapeHtml(item.type)}</span>
      </div>
      <div class="item-content">
        <div class="item-meta">
          <span class="category-tag">${escapeHtml(item.category)}</span>
          <time class="item-date">${escapeHtml(formattedDate(item.date))}</time>
        </div>
        <h3 title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</h3>
        <p class="item-location">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"></path><circle cx="12" cy="10" r="2.5"></circle></svg>
          ${escapeHtml(item.location)}
        </p>
        <p class="item-description">${escapeHtml(item.description)}</p>
        <button class="view-details" type="button" data-item-id="${escapeHtml(item.id)}" data-source="${escapeHtml(item.source)}">View Details <span aria-hidden="true">→</span></button>
      </div>
    </article>`;
}

function emptyMarkup(hasFilters) {
  return `
    <div class="empty-state">
      <div class="empty-icon">
        <svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="14" cy="14" r="9"></circle><path d="m21 21 7 7"></path></svg>
      </div>
      <h3>${hasFilters ? 'No matching items' : 'No items reported yet'}</h3>
      <p>${hasFilters ? 'Try adjusting your search or clearing some filters.' : 'New lost and found reports will appear here.'}</p>
    </div>`;
}

function getFilters() {
  return {
    search: searchInput.value.trim(),
    type: document.querySelector('input[name="type"]:checked').value,
    category: document.querySelector('#category-filter').value,
    location: document.querySelector('#location-filter').value,
  };
}

async function loadItems() {
  const params = new URLSearchParams(getFilters());
  resultCount.textContent = 'Loading items...';
  try {
    const response = await fetch(`/api/items?${params.toString()}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Items could not be loaded.');
    grid.innerHTML = result.items.length
      ? result.items.map(itemCard).join('')
      : emptyMarkup(Object.values(getFilters()).some(Boolean));
    attachImageFallbacks(grid);
    resultCount.textContent = `${result.items.length} ${result.items.length === 1 ? 'item' : 'items'} found`;
    notice.hidden = result.databaseAvailable;
    notice.textContent = result.databaseAvailable
      ? ''
      : 'The campus database has not been configured or is not available yet. Set CAMPUS_DATABASE to the existing SQLite database file.';
  } catch (error) {
    grid.innerHTML = emptyMarkup(true);
    resultCount.textContent = 'Items unavailable';
    notice.textContent = `${error.message} Please try again later.`;
    notice.hidden = false;
  }
}

function detailField(label, value) {
  return `<div class="detail-field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || 'Not provided')}</strong></div>`;
}

function openDetails(item) {
  detailsContent.innerHTML = `
    ${imageMarkup(item.image, item.name, 'details-image')}
    <div class="details-body">
      <span class="status-badge ${item.type === 'Found' ? 'found' : ''}">${escapeHtml(item.type)}</span>
      <h2 id="details-title">${escapeHtml(item.name)}</h2>
      <p class="detail-description">${escapeHtml(item.description)}</p>
      <div class="detail-list">
        ${detailField('Category', item.category)}
        ${detailField('Location', item.location)}
        ${detailField('Reported date', formattedDate(item.date))}
        ${detailField(item.type === 'Found' ? 'Claim / contact information' : 'Contact information', item.contact)}
      </div>
    </div>`;
  attachImageFallbacks(detailsContent);
  detailsDialog.showModal();
}

searchForm.addEventListener('submit', (event) => {
  event.preventDefault();
  clearTimeout(searchTimer);
  loadItems();
});
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadItems, 250);
});
document.querySelectorAll('input[name="type"], #category-filter, #location-filter')
  .forEach((control) => control.addEventListener('change', loadItems));
document.querySelector('#clear-filters').addEventListener('click', () => {
  searchInput.value = '';
  document.querySelector('input[name="type"][value=""]').checked = true;
  document.querySelector('#category-filter').value = '';
  document.querySelector('#location-filter').value = '';
  loadItems();
});
grid.addEventListener('click', async (event) => {
  const button = event.target.closest('.view-details');
  if (!button) return;
  button.disabled = true;
  try {
    const response = await fetch(`/api/items/${encodeURIComponent(button.dataset.source)}/${encodeURIComponent(button.dataset.itemId)}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Item details could not be loaded.');
    openDetails(result.item);
  } catch (error) {
    notice.textContent = error.message;
    notice.hidden = false;
  } finally {
    button.disabled = false;
  }
});
document.querySelector('#modal-close').addEventListener('click', () => detailsDialog.close());
detailsDialog.addEventListener('click', (event) => {
  if (event.target === detailsDialog) detailsDialog.close();
});
document.querySelector('.nav-toggle').addEventListener('click', (event) => {
  const toggle = event.currentTarget;
  const open = toggle.getAttribute('aria-expanded') === 'true';
  toggle.setAttribute('aria-expanded', String(!open));
  document.querySelector('#nav-links').classList.toggle('open', !open);
});

loadItems();
