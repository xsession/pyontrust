/**
 * pyontrust App Shell — Navigation + Status Polling
 *
 * Handles:
 *  - Tool navigation via iframe
 *  - Active link highlighting
 *  - HIL run-status badge polling
 */
(function () {
  'use strict';

  const frame = document.getElementById('tool-frame');
  const badge = document.getElementById('status-badge');
  const navLinks = document.querySelectorAll('#app-nav a[data-tool]');

  // ── Navigation ─────────────────────────────────────────────────
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const href = link.getAttribute('href');
      frame.src = href;
      setActive(link.dataset.tool);
    });
  });

  function setActive(tool) {
    navLinks.forEach(a => a.classList.toggle('active', a.dataset.tool === tool));
  }

  // Detect initial tool from hash or default
  const hash = location.hash.replace('#', '');
  if (hash) {
    const matching = document.querySelector(`#app-nav a[data-tool="${hash}"]`);
    if (matching) {
      frame.src = matching.getAttribute('href');
      setActive(hash);
    } else {
      setActive('hil');
    }
  } else {
    setActive('hil');
  }

  // ── Status badge polling ───────────────────────────────────────
  async function pollStatus() {
    try {
      const res = await fetch('/hil/api/status');
      if (!res.ok) return;
      const data = await res.json();
      const state = data.state || 'idle';
      badge.textContent = '● ' + state;
      badge.style.color = state === 'running' ? 'var(--green)'
                        : state === 'error'   ? 'var(--red)'
                        : state === 'stopping' ? 'var(--yellow)'
                        : 'var(--fg-dim)';
    } catch {
      // Ignore polling errors
    }
  }

  pollStatus();
  setInterval(pollStatus, 5000);
})();
