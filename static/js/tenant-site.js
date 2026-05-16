document.addEventListener('alpine:init', () => {
  const slug = document.body.dataset.tenantSlug || '';
  const cartKey = `salesdee-cart:${slug}`;
  const compareKey = `salesdee-compare:${slug}`;

  const loadJson = (key, fallback) => {
    try {
      return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
    } catch {
      return fallback;
    }
  };

  Alpine.store('cart', {
    items: loadJson(cartKey, []),
    open: false,
    add(p) {
      const exist = this.items.find((i) => i.id === p.id);
      if (exist) exist.qty += p.qty || 1;
      else this.items.push({ id: p.id, name: p.name, price: p.price, image: p.image || '', qty: p.qty || 1 });
      this._save();
    },
    remove(id) {
      this.items = this.items.filter((i) => i.id !== id);
      this._save();
    },
    inc(id) {
      const i = this.items.find((x) => x.id === id);
      if (i) {
        i.qty += 1;
        this._save();
      }
    },
    dec(id) {
      const i = this.items.find((x) => x.id === id);
      if (i) {
        i.qty = Math.max(1, i.qty - 1);
        this._save();
      }
    },
    total() {
      return this.items.reduce((s, i) => s + i.price * i.qty, 0);
    },
    count() {
      return this.items.reduce((s, i) => s + i.qty, 0);
    },
    clear() {
      this.items = [];
      this._save();
    },
    _save() {
      localStorage.setItem(cartKey, JSON.stringify(this.items));
    },
  });

  Alpine.store('compare', {
    ids: loadJson(compareKey, []),
    toggle(id) {
      if (this.ids.includes(id)) this.ids = this.ids.filter((x) => x !== id);
      else if (this.ids.length < 4) this.ids.push(id);
      localStorage.setItem(compareKey, JSON.stringify(this.ids));
    },
    has(id) {
      return this.ids.includes(id);
    },
    clear() {
      this.ids = [];
      localStorage.setItem(compareKey, JSON.stringify(this.ids));
    },
    url(base) {
      if (!this.ids.length) return base;
      return `${base}?ids=${this.ids.join(',')}`;
    },
  });
});

function tsScrollCats(el, dir) {
  const scroller = el.closest('.lh-cats-scroll-wrap')?.querySelector('.lh-cats');
  if (scroller) scroller.scrollBy({ left: dir * 320, behavior: 'smooth' });
}

document.addEventListener('click', (e) => {
  const btn = e.target.closest('.lh-card-add');
  if (!btn || typeof Alpine === 'undefined') return;
  const id = btn.dataset.productId;
  if (!id) return;
  Alpine.store('cart').add({
    id,
    name: btn.dataset.productName || '',
    price: parseFloat(btn.dataset.productPrice || '0', 10),
    image: btn.dataset.productImage || '',
    qty: 1,
  });
});

function tsInitCatsScrollbar() {
  const scroller = document.getElementById('lh-cats');
  const thumb = document.getElementById('lh-cats-thumb');
  if (!scroller || !thumb) return;
  const sync = () => {
    const max = scroller.scrollWidth - scroller.clientWidth;
    if (max <= 0) {
      thumb.style.width = '100%';
      thumb.style.transform = 'translateX(0)';
      return;
    }
    const ratio = scroller.clientWidth / scroller.scrollWidth;
    thumb.style.width = `${Math.max(12, ratio * 100)}%`;
    const offset = (scroller.scrollLeft / max) * (100 - parseFloat(thumb.style.width));
    thumb.style.transform = `translateX(${offset}%)`;
  };
  scroller.addEventListener('scroll', sync, { passive: true });
  window.addEventListener('resize', sync);
  sync();
}

document.addEventListener('DOMContentLoaded', tsInitCatsScrollbar);
