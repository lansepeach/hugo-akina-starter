(function () {
  const searchOverlay = document.getElementById('searchOverlay');
  const searchInput = document.getElementById('searchInput');
  const searchResults = document.getElementById('searchResults');
  const mobilePanel = document.getElementById('mo-nav');
  const pageWrapper = document.getElementById('page');
  let searchIndex = null;
  let mobileMenuScrollY = 0;

  document.querySelectorAll('[data-toggle-search]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (searchOverlay && searchOverlay.classList.contains('open')) closeSearch();
      else await openSearch();
    });
  });

  document.querySelectorAll('#mo-nav .text-input').forEach((input) => {
    const openFromMobile = async () => {
      await openSearch(input.value);
      setMobileMenuOpen(false);
    };
    input.addEventListener('focus', openFromMobile);
    input.addEventListener('click', openFromMobile);
    input.addEventListener('input', openFromMobile);
  });

  document.querySelectorAll('[data-toggle-menu]').forEach((button) => {
    button.addEventListener('click', () => {
      if (!mobilePanel) return;
      const isOpen = pageWrapper ? !pageWrapper.classList.contains('open') : !mobilePanel.classList.contains('open');
      setMobileMenuOpen(isOpen);
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeSearch();
      setMobileMenuOpen(false);
    }
  });

  if (searchOverlay) {
    searchOverlay.addEventListener('click', (event) => {
      if (event.target === searchOverlay) closeSearch();
    });
  }

  if (pageWrapper) {
    pageWrapper.addEventListener('click', (event) => {
      if (!pageWrapper.classList.contains('open')) return;
      if (event.target.closest('[data-toggle-menu]')) return;
      setMobileMenuOpen(false);
    });
  }

  function setMobileMenuOpen(open) {
    if (!mobilePanel) return;
    if (open) {
      mobileMenuScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      if (pageWrapper) {
        pageWrapper.style.setProperty('--mobile-menu-scroll-top', `-${mobileMenuScrollY}px`);
        pageWrapper.classList.add('open');
      }
      mobilePanel.classList.add('open');
    } else {
      const shouldRestore = pageWrapper && pageWrapper.classList.contains('open');
      if (pageWrapper) {
        pageWrapper.classList.remove('open');
        pageWrapper.style.removeProperty('--mobile-menu-scroll-top');
      }
      mobilePanel.classList.remove('open');
      if (shouldRestore) window.scrollTo(0, mobileMenuScrollY);
    }
    mobilePanel.setAttribute('aria-hidden', open ? 'false' : 'true');
    document.querySelectorAll('[data-toggle-menu]').forEach((button) => button.classList.toggle('open', open));
  }

  async function ensureSearchIndex() {
    if (searchIndex) return searchIndex;
    const response = await fetch('/index.json');
    searchIndex = await response.json();
    return searchIndex;
  }

  async function openSearch(initialValue) {
    if (!searchOverlay || !searchInput) return;
    searchOverlay.classList.add('open');
    searchOverlay.setAttribute('aria-hidden', 'false');
    document.documentElement.classList.add('search-open');
    document.body.classList.add('search-open');
    await ensureSearchIndex();
    if (typeof initialValue === 'string' && initialValue.trim()) searchInput.value = initialValue;
    searchInput.focus();
    renderSearch();
  }

  function closeSearch() {
    if (!searchOverlay) return;
    searchOverlay.classList.remove('open');
    searchOverlay.setAttribute('aria-hidden', 'true');
    document.documentElement.classList.remove('search-open');
    document.body.classList.remove('search-open');
  }

  function renderSearch() {
    if (!searchInput || !searchResults) return;
    const query = searchInput.value.trim().toLowerCase();
    if (!query || !searchIndex) {
      searchResults.innerHTML = '<p class="search-hint">输入关键词后显示搜索结果</p>';
      return;
    }
    const matches = searchIndex.filter((item) => {
      return `${item.title} ${item.summary}`.toLowerCase().includes(query);
    }).slice(0, 24);
    searchResults.innerHTML = matches.map((item) => {
      const title = highlightMatch(item.title || '', query);
      const summary = highlightMatch((item.summary || '').slice(0, 110), query);
      return `<a class="search-result" href="${item.url}"><strong>${title}</strong><br><small>${item.date}</small><p>${summary}</p></a>`;
    }).join('') || '<p class="no-comments">没有找到结果</p>';
  }

  function highlightMatch(text, query) {
    const safeText = escapeHtml(text);
    const safeQuery = escapeRegExp(query.trim());
    if (!safeQuery) return safeText;
    return safeText.replace(new RegExp(`(${safeQuery})`, 'gi'), '<mark class="search-highlight">$1</mark>');
  }

  function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  if (searchInput) {
    searchInput.addEventListener('input', renderSearch);
  }

  document.querySelectorAll('.entry-content pre').forEach((pre) => {
    if (pre.parentElement && pre.parentElement.classList.contains('code-block-container')) return;
    pre.classList.add('processed-code');
    const code = pre.querySelector('code');
    const detectedLanguage = highlightCode(code);
    const shell = document.createElement('div');
    shell.className = 'code-block-container';
    const header = document.createElement('div');
    header.className = 'code-block-header';
    const lang = document.createElement('span');
    lang.className = 'code-block-lang';
    lang.textContent = detectedLanguage || languageFromClass(code) || 'code';
    const actions = document.createElement('div');
    actions.className = 'code-block-actions';
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = '复制';
    button.addEventListener('click', async () => {
      const copied = await copyText(pre.textContent);
      button.classList.toggle('copied', copied);
      button.textContent = copied ? '已复制' : '复制失败';
      setTimeout(() => {
        button.classList.remove('copied');
        button.textContent = '复制';
      }, 1400);
    });
    pre.parentNode.insertBefore(shell, pre);
    actions.appendChild(button);
    header.appendChild(lang);
    header.appendChild(actions);
    shell.appendChild(header);
    shell.appendChild(pre);
  });

  document.querySelectorAll('[data-toggle-toc]').forEach((button) => {
    button.addEventListener('click', () => {
      const toc = document.getElementById('tocContainer');
      if (!toc) return;
      toc.classList.toggle('toc-collapsed');
      button.textContent = toc.classList.contains('toc-collapsed') ? '›' : '‹';
    });
  });

  const tocList = document.getElementById('tocList');
  if (tocList) {
    const tocContainer = document.getElementById('tocContainer');
    const headings = Array.from(document.querySelectorAll('.entry-content h2, .entry-content h3'));
    if (headings.length === 0) {
      tocContainer.style.display = 'none';
    } else {
      tocList.innerHTML = headings.map((heading, index) => {
        if (!heading.id) heading.id = `toc-${index + 1}`;
        const level = heading.tagName.toLowerCase() === 'h3' ? 'toc-level-3' : 'toc-level-2';
        return `<li class="${level}"><a href="#${heading.id}">${escapeHtml(heading.textContent)}</a></li>`;
      }).join('');
      tocContainer.classList.add('toc-visible');
      bindTocActiveState(tocList, headings);
    }
  }

  const timeDate = document.getElementById('timeDate');
  const times = document.getElementById('times');
  if (timeDate && times) {
    const start = new Date('2016-10-04T03:39:00+08:00');
    const tick = () => {
      const diff = Math.max(0, Date.now() - start.getTime());
      const days = Math.floor(diff / 86400000);
      const hours = Math.floor(diff / 3600000) % 24;
      const minutes = Math.floor(diff / 60000) % 60;
      const seconds = Math.floor(diff / 1000) % 60;
      timeDate.textContent = `本站已坚持运行了${days}天`;
      times.textContent = `${pad(hours)}小时${pad(minutes)}分${pad(seconds)}秒`;
    };
    tick();
    setInterval(tick, 250);
  }

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  }

  function highlightCode(code) {
    if (!code || !window.hljs) return '';
    const language = languageFromClass(code);
    try {
      if (language && window.hljs.getLanguage(language)) {
        code.innerHTML = window.hljs.highlight(code.textContent, { language }).value;
        code.classList.add('hljs', `language-${language}`);
        return language;
      }
      const result = window.hljs.highlightAuto(code.textContent);
      code.innerHTML = result.value;
      code.classList.add('hljs');
      if (result.language) code.classList.add(`language-${result.language}`);
      return result.language || '';
    } catch (error) {
      code.classList.add('hljs');
      return language || '';
    }
  }

  function languageFromClass(code) {
    if (!code) return '';
    const className = code.className || '';
    const match = className.match(/(?:language-|lang-|hljs\s+)([a-z0-9_+-]+)/i);
    return match ? match[1].toLowerCase() : '';
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (error) {
      // Fall back for HTTP previews or browsers blocking Clipboard API.
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.top = '-9999px';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    let copied = false;
    try {
      copied = document.execCommand('copy');
    } catch (error) {
      copied = false;
    }
    document.body.removeChild(textarea);
    return copied;
  }

  function bindTocActiveState(tocList, headings) {
    const links = Array.from(tocList.querySelectorAll('a'));
    const setActive = () => {
      let current = headings[0];
      headings.forEach((heading) => {
        if (heading.getBoundingClientRect().top <= 120) current = heading;
      });
      links.forEach((link) => {
        link.parentElement.classList.toggle('active', link.getAttribute('href') === `#${current.id}`);
      });
    };
    setActive();
    document.addEventListener('scroll', setActive, { passive: true });
  }
})();
