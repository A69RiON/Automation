(function () {
  'use strict';

  window.__ADMIN_APP_STARTED = true;

  const $ = (id) => document.getElementById(id);
  const config = window.MARKETPLACE_CONFIG || window.DEAL_HUNTER_CONFIG || {};
  const createClient = window.supabase && window.supabase.createClient;

  function setLoginMessage(message) {
    const el = $('loginMsg');
    if (el) el.textContent = message || '';
  }

  if (!createClient) {
    setLoginMessage('Admin app could not load the Supabase browser library. Hard-refresh the page.');
    return;
  }

  const supabaseUrl = config.SUPABASE_URL || config.supabaseUrl || config.url || '';
  const supabaseKey = config.SUPABASE_PUBLISHABLE_KEY || config.SUPABASE_ANON_KEY || config.supabaseAnonKey || config.key || '';

  if (!supabaseUrl || !supabaseKey) {
    setLoginMessage('Configuration error: SUPABASE_URL or publishable key is missing from config.js.');
    return;
  }

  const s = createClient(supabaseUrl, supabaseKey);

  let bookings = [];
  let offerings = [];
  let settings = {};
  let paymentMethods = [];
  let currentStatus = 'pending';
  let currentCatalogue = 'rentals';
  let editingOfferingId = null;

  async function isAdmin() {
    const { data: userData, error: userError } = await s.auth.getUser();
    if (userError || !userData || !userData.user) return false;

    const { data, error } = await s.rpc('is_marketplace_admin');
    if (error) {
      setLoginMessage('Admin verification failed: ' + error.message);
      console.error(error);
      return false;
    }
    return data === true;
  }

  function showAdmin() {
    $('loginPanel').hidden = true;
    $('adminPanel').hidden = false;
    $('logoutBtn').hidden = false;
    setLoginMessage('');
  }

  async function handleLogin() {
    const button = $('loginBtn');
    const username = $('username').value.trim();
    const password = $('password').value;

    if (!username || !password) {
      setLoginMessage('Enter your username and password.');
      return;
    }

    button.disabled = true;
    setLoginMessage('Signing in…');

    try {
      const suffix = config.ADMIN_EMAIL_SUFFIX || '@au-deal-hunter.local';
      const email = username.includes('@') ? username : username + suffix;
      const { error } = await s.auth.signInWithPassword({ email, password });

      if (error) {
        setLoginMessage('Login failed: ' + error.message);
        return;
      }

      const ok = await isAdmin();
      if (!ok) {
        await s.auth.signOut();
        if (!$('loginMsg').textContent.startsWith('Admin verification failed:')) {
          setLoginMessage('Signed in, but this account is not authorised as an admin.');
        }
        return;
      }

      showAdmin();
      await refreshAll();
    } catch (error) {
      console.error(error);
      setLoginMessage('Unexpected login error: ' + (error.message || String(error)));
    } finally {
      button.disabled = false;
    }
  }

  function normalizedStatus(value) {
    return ({ sent: 'active', confirmed: 'active', in_progress: 'active' })[value] || value;
  }

  function ordinal(n) {
    const suffixes = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return n + (suffixes[(v - 20) % 10] || suffixes[v] || suffixes[0]);
  }

  function formatDate(value) {
    if (!value) return '—';
    const d = new Date(value + 'T00:00:00');
    return `${ordinal(d.getDate())} ${d.toLocaleDateString('en-AU', { month: 'short' })} ${d.getFullYear()}`;
  }

  async function refreshAll() {
    const [b, o, st, p] = await Promise.all([
      s.from('bookings').select('*,offerings(title)').order('created_at', { ascending: false }),
      s.from('offerings').select('*').order('created_at', { ascending: false }),
      s.from('marketplace_settings').select('*').limit(1).maybeSingle(),
      s.from('payment_methods').select('*').order('id')
    ]);

    const errors = [b.error, o.error, st.error, p.error].filter(Boolean);
    if (errors.length) console.error('Admin refresh errors:', errors);

    bookings = b.data || [];
    offerings = o.data || [];
    settings = st.data || {};
    paymentMethods = p.data || [];

    renderMetrics();
    renderOrders();
    renderOfferings();
    renderSettings();
    renderPayments();
  }

  function renderMetrics() {
    const counts = { pending: 0, active: 0, completed: 0, cancelled: 0 };
    bookings.forEach((b) => {
      const st = normalizedStatus(b.status);
      if (Object.prototype.hasOwnProperty.call(counts, st)) counts[st] += 1;
    });

    $('metrics').innerHTML = `
      <div class="metric" data-go="orders" data-status="pending"><div class="v">${counts.pending}</div><div class="l">Pending</div></div>
      <div class="metric" data-go="orders" data-status="active"><div class="v">${counts.active}</div><div class="l">Active bookings</div></div>
      <div class="metric" data-go="catalogue"><div class="v">${offerings.filter((o) => o.active && !o.archived).length}</div><div class="l">Active offerings</div></div>
      <div class="metric" data-go="settings"><div class="v">${settings.currency || 'AUD'}</div><div class="l">Default currency</div></div>`;

    document.querySelectorAll('.metric').forEach((el) => {
      el.onclick = () => {
        switchTab(el.dataset.go);
        if (el.dataset.status) {
          currentStatus = el.dataset.status;
          updateOrderTabs();
          renderOrders();
        }
      };
    });
  }

  function updateOrderTabs() {
    document.querySelectorAll('#orderTabs .subtab').forEach((el) => {
      el.classList.toggle('active', el.dataset.status === currentStatus);
    });
  }

  async function loadNotes(bookingId) {
    if (settings.notes_mode !== 'history') return;
    const root = $('notes-' + bookingId);
    if (!root) return;
    const { data, error } = await s.from('booking_admin_notes').select('*').eq('booking_id', bookingId).order('created_at', { ascending: false });
    if (error) {
      root.textContent = error.message;
      return;
    }
    root.innerHTML = (data || []).map((n) => `<div class="note-item">${n.note}<br><span class="meta">${new Date(n.created_at).toLocaleString('en-AU')}</span></div>`).join('');
  }

  async function saveNote(bookingId) {
    const input = document.querySelector(`.note[data-id="${bookingId}"]`);
    if (!input) return;
    const note = input.value.trim();
    if (!note) return;

    if (settings.notes_mode === 'single') {
      const { error } = await s.from('bookings').update({ admin_note: note }).eq('id', bookingId);
      if (error) alert(error.message);
    } else {
      const { data: userData } = await s.auth.getUser();
      const { error } = await s.from('booking_admin_notes').insert({
        booking_id: bookingId,
        note,
        created_by: userData && userData.user ? userData.user.id : null
      });
      if (error) alert(error.message);
      else input.value = '';
    }
    renderOrders();
  }

  function renderOrders() {
    const rows = bookings.filter((b) => normalizedStatus(b.status) === currentStatus);
    $('orders').innerHTML = `
      <table class="table"><thead><tr><th>Booking</th><th>Customer</th><th>Offering</th><th>Access</th><th>Dates</th><th>Total</th><th>Status</th><th>Admin notes</th><th>Actions</th></tr></thead>
      <tbody>${rows.map((b) => `
        <tr>
          <td>${b.booking_number || ''}</td>
          <td>${b.customer_name || ''}<br><span class="meta">${b.customer_email || ''}</span></td>
          <td>${b.offerings && b.offerings.title ? b.offerings.title : 'Removed'}</td>
          <td>${b.access_type || 'Sale'}</td>
          <td>${formatDate(b.start_date)} → ${formatDate(b.end_date)}</td>
          <td>A$${Number(b.total_amount || 0).toFixed(2)}<br><span class="meta">${b.display_currency || 'AUD'} ${Number(b.display_total || b.total_amount || 0).toFixed(2)}</span></td>
          <td><select class="st" data-id="${b.id}">${['pending','active','completed','cancelled'].map((x) => `<option value="${x}" ${normalizedStatus(b.status) === x ? 'selected' : ''}>${x}</option>`).join('')}</select></td>
          <td><div id="notes-${b.id}"></div><textarea class="note" data-id="${b.id}">${settings.notes_mode === 'single' ? (b.admin_note || '') : ''}</textarea><button class="button saveNote" data-id="${b.id}">${settings.notes_mode === 'single' ? 'Save note' : 'Add note'}</button></td>
          <td><button class="button danger deleteBooking" data-id="${b.id}">Delete</button></td>
        </tr>`).join('')}</tbody></table>`;

    document.querySelectorAll('.st').forEach((el) => {
      el.onchange = async () => {
        const { error } = await s.from('bookings').update({ status: el.value }).eq('id', el.dataset.id);
        if (error) alert(error.message);
        currentStatus = el.value;
        await refreshAll();
        updateOrderTabs();
      };
    });

    document.querySelectorAll('.saveNote').forEach((el) => {
      el.onclick = () => saveNote(el.dataset.id);
    });

    document.querySelectorAll('.deleteBooking').forEach((el) => {
      el.onclick = async () => {
        if (!confirm('Permanently delete this booking? Use Cancelled instead if you want to preserve history.')) return;
        const { error } = await s.from('bookings').delete().eq('id', el.dataset.id);
        if (error) alert(error.message);
        else await refreshAll();
      };
    });

    rows.forEach((b) => loadNotes(b.id));
  }

  function renderOfferings() {
    let rows = offerings.slice();
    if (currentCatalogue === 'rentals') rows = rows.filter((o) => o.offering_type === 'digital_rental' && !o.archived);
    if (currentCatalogue === 'sales') rows = rows.filter((o) => o.offering_type === 'digital_product' && !o.archived);
    if (currentCatalogue === 'disabled') rows = rows.filter((o) => !o.active && !o.archived);
    if (currentCatalogue === 'archived') rows = rows.filter((o) => o.archived);

    $('offers').innerHTML = rows.map((o) => `
      <div class="offer-row"><div><strong>${o.title}</strong><div class="meta">${o.offering_type} • ${o.active ? 'Enabled' : 'Disabled'}${o.archived ? ' • Archived' : ''}</div></div>
      <div class="offer-actions">${!o.archived ? `<button class="button edit" data-id="${o.id}">Edit</button><button class="button toggle" data-id="${o.id}">${o.active ? 'Disable' : 'Enable'}</button><button class="button remove" data-id="${o.id}">Remove</button>` : ''}</div></div>`).join('');

    document.querySelectorAll('.edit').forEach((el) => { el.onclick = () => editOffering(el.dataset.id); });
    document.querySelectorAll('.toggle').forEach((el) => {
      el.onclick = async () => {
        const o = offerings.find((x) => x.id === el.dataset.id);
        if (!o) return;
        const { error } = await s.from('offerings').update({ active: !o.active }).eq('id', o.id);
        if (error) alert(error.message);
        await refreshAll();
      };
    });
    document.querySelectorAll('.remove').forEach((el) => {
      el.onclick = async () => {
        if (!confirm('Archive this offering? Existing orders stay intact.')) return;
        const { error } = await s.from('offerings').update({ archived: true, active: false }).eq('id', el.dataset.id);
        if (error) alert(error.message);
        await refreshAll();
      };
    });
  }

  function updateOfferingFields() {
    const isRental = $('type').value === 'digital_rental';
    $('rentalFields').hidden = !isRental;
    $('saleFields').hidden = isRental;
  }

  function editOffering(id) {
    const o = offerings.find((x) => x.id === id);
    if (!o) return;
    editingOfferingId = id;
    $('title').value = o.title || '';
    $('type').value = o.offering_type || 'digital_rental';
    $('platform').value = o.platform || o.category || '';
    $('description').value = o.description || '';
    $('copies').value = o.copies || 1;
    $('pw').value = o.primary_weekly_rate || 0;
    $('pm').value = o.primary_monthly_rate || 0;
    $('sw').value = o.secondary_weekly_rate || 0;
    $('sm').value = o.secondary_monthly_rate || 0;
    $('maxdays').value = o.max_rental_days || 90;
    $('rp').value = o.regular_price || 0;
    $('sp').value = o.sale_price || 0;
    $('stock').value = o.sale_stock || 0;
    $('image').value = o.image_url || '';
    $('featured').checked = !!o.featured;
    $('saveOffer').textContent = 'Save changes';
    $('cancelEdit').hidden = false;
    updateOfferingFields();
  }

  function resetOfferingForm() {
    editingOfferingId = null;
    ['title','platform','description','pw','pm','sw','sm','rp','sp','image'].forEach((id) => { $(id).value = ''; });
    $('copies').value = 1;
    $('maxdays').value = 90;
    $('stock').value = 0;
    $('featured').checked = false;
    $('saveOffer').textContent = 'Publish offering';
    $('cancelEdit').hidden = true;
  }

  async function saveOffering() {
    const payload = {
      title: $('title').value,
      offering_type: $('type').value,
      platform: $('platform').value,
      category: $('platform').value,
      description: $('description').value,
      copies: Number($('copies').value || 1),
      capacity: Number($('copies').value || 1),
      primary_weekly_rate: Number($('pw').value || 0),
      primary_monthly_rate: Number($('pm').value || 0),
      secondary_weekly_rate: Number($('sw').value || 0),
      secondary_monthly_rate: Number($('sm').value || 0),
      max_rental_days: Number($('maxdays').value || 90),
      regular_price: Number($('rp').value || 0),
      sale_price: Number($('sp').value || 0),
      sale_stock: Number($('stock').value || 0),
      image_url: $('image').value || null,
      featured: $('featured').checked,
      active: true,
      archived: false,
      currency: 'AUD',
      market: 'AU'
    };

    const result = editingOfferingId
      ? await s.from('offerings').update(payload).eq('id', editingOfferingId)
      : await s.from('offerings').insert(payload);

    $('offerMsg').textContent = result.error ? result.error.message : (editingOfferingId ? 'Updated.' : 'Published.');
    if (!result.error) {
      resetOfferingForm();
      await refreshAll();
    }
  }

  function renderSettings() {
    $('siteName').value = settings.site_name || '';
    $('heroEye').value = settings.hero_eyebrow || '';
    $('heroTitleAdmin').value = settings.hero_title || '';
    $('heroDescAdmin').value = settings.hero_description || '';
    $('homeLabel').value = settings.nav_home_label || 'Home';
    $('rentLabel').value = settings.nav_rentals_label || 'Rentals';
    $('saleLabel').value = settings.nav_sale_label || 'Sale';
    $('availLabel').value = settings.nav_availability_label || 'Availability';
    $('defcur').value = settings.currency || 'AUD';
    $('allowed').value = (settings.allowed_currencies || ['AUD','USD','BDT']).join(',');
    $('cprompt').checked = settings.currency_prompt_enabled !== false;
    $('noteMode').value = settings.notes_mode || 'history';
    $('saleHead').value = settings.sale_title || 'On Sale';
    $('saleSub').value = settings.sale_subtitle || '';

    s.from('fx_fallback_rates').select('*').then(({ data }) => {
      (data || []).forEach((x) => {
        if (x.currency === 'USD') $('fusd').value = x.rate_from_base;
        if (x.currency === 'BDT') $('fbdt').value = x.rate_from_base;
      });
    });
  }

  async function saveSettings(payload) {
    if (!settings.id) return;
    const { error } = await s.from('marketplace_settings').update(payload).eq('id', settings.id);
    if (error) alert(error.message);
    await refreshAll();
  }

  function renderPayments() {
    $('payments').innerHTML = paymentMethods.map((p) => `
      <div class="payment-row"><div><strong>${p.display_name}</strong></div><div style="min-width:55%">
      <label><input class="pe" data-id="${p.id}" type="checkbox" style="width:auto" ${p.enabled ? 'checked' : ''}> Enabled</label>
      <label>Instructions<input class="pi" data-id="${p.id}" value="${p.customer_instructions || ''}"></label>
      <label><input class="pd" data-id="${p.id}" type="checkbox" style="width:auto" ${p.deployed ? 'checked' : ''}> Deploy to public</label>
      </div></div>`).join('');
  }

  function switchTab(name) {
    document.querySelectorAll('.tab').forEach((el) => el.classList.toggle('active', el.dataset.tab === name));
    ['orders','catalogue','availability','settings'].forEach((x) => { $(x + 'Tab').hidden = x !== name; });
  }

  function wireEvents() {
    $('loginBtn').addEventListener('click', handleLogin);
    $('password').addEventListener('keydown', (e) => { if (e.key === 'Enter') handleLogin(); });
    $('logoutBtn').addEventListener('click', async () => { await s.auth.signOut(); location.reload(); });
    $('refreshBtn').addEventListener('click', refreshAll);
    $('type').addEventListener('change', updateOfferingFields);
    $('cancelEdit').addEventListener('click', resetOfferingForm);
    $('saveOffer').addEventListener('click', saveOffering);

    document.querySelectorAll('.tab').forEach((el) => { el.onclick = () => switchTab(el.dataset.tab); });
    document.querySelectorAll('#orderTabs .subtab').forEach((el) => {
      el.onclick = () => { currentStatus = el.dataset.status; updateOrderTabs(); renderOrders(); };
    });
    document.querySelectorAll('[data-cat]').forEach((el) => {
      el.onclick = () => {
        document.querySelectorAll('[data-cat]').forEach((x) => x.classList.toggle('active', x === el));
        currentCatalogue = el.dataset.cat;
        renderOfferings();
      };
    });
    document.querySelectorAll('#settingsTabs .subtab').forEach((el) => {
      el.onclick = () => {
        document.querySelectorAll('#settingsTabs .subtab').forEach((x) => x.classList.toggle('active', x === el));
        ['general','currency','notes','sale','payments'].forEach((n) => { $(n + 'Pane').hidden = n !== el.dataset.set; });
      };
    });

    $('saveGeneral').onclick = () => saveSettings({
      site_name: $('siteName').value,
      hero_eyebrow: $('heroEye').value,
      hero_title: $('heroTitleAdmin').value,
      hero_description: $('heroDescAdmin').value,
      nav_home_label: $('homeLabel').value,
      nav_rentals_label: $('rentLabel').value,
      nav_sale_label: $('saleLabel').value,
      nav_availability_label: $('availLabel').value
    });

    $('saveNotes').onclick = () => saveSettings({ notes_mode: $('noteMode').value });
    $('saveSale').onclick = () => saveSettings({ sale_title: $('saleHead').value, sale_subtitle: $('saleSub').value });
    $('saveCurrency').onclick = async () => {
      await saveSettings({
        currency: $('defcur').value,
        allowed_currencies: $('allowed').value.split(',').map((x) => x.trim().toUpperCase()).filter(Boolean),
        currency_prompt_enabled: $('cprompt').checked
      });
      const { error } = await s.from('fx_fallback_rates').upsert([
        { currency: 'AUD', rate_from_base: 1 },
        { currency: 'USD', rate_from_base: Number($('fusd').value || 0.65) },
        { currency: 'BDT', rate_from_base: Number($('fbdt').value || 78) }
      ]);
      if (error) alert(error.message);
    };

    $('savePayments').onclick = async () => {
      for (const p of paymentMethods) {
        const enabled = document.querySelector(`.pe[data-id="${p.id}"]`).checked;
        const deployed = document.querySelector(`.pd[data-id="${p.id}"]`).checked;
        const customer_instructions = document.querySelector(`.pi[data-id="${p.id}"]`).value;
        const { error } = await s.from('payment_methods').update({ enabled, deployed, customer_instructions }).eq('id', p.id);
        if (error) alert(error.message);
      }
      await refreshAll();
    };
  }

  async function boot() {
    wireEvents();
    const ok = await isAdmin();
    if (ok) {
      showAdmin();
      await refreshAll();
    }
  }

  boot().catch((error) => {
    console.error(error);
    setLoginMessage('Admin startup error: ' + (error.message || String(error)));
  });

  console.info('Digital Rental Platform V5.2.0 admin loaded');
})();
