// QuickPOS — Cart & checkout logic
let cart = [];
let selectedCustomer = null;
let selectedPayment = 'cash';
let totalDirty = false;

function addToCart(productId, name, price, cost, stock) {
  const existing = cart.find(i => i.productId === productId);
  if (existing) {
    if (existing.quantity >= stock) return;
    existing.quantity += 1;
  } else {
    const unit = Math.round((parseFloat(price) || 0) * 100) / 100;
    cart.push({ productId, name, price: unit, catalogPrice: unit, cost, stock, quantity: 1 });
  }
  totalDirty = false;
  renderCart();
}

function removeFromCart(productId) {
  cart = cart.filter(i => i.productId !== productId);
  totalDirty = false;
  renderCart();
}

function updateQuantity(productId, qty) {
  const item = cart.find(i => i.productId === productId);
  if (!item) return;
  qty = Math.max(0, Math.min(parseInt(qty) || 0, item.stock));
  if (qty === 0) {
    removeFromCart(productId);
    return;
  }
  item.quantity = qty;
  totalDirty = false;
  renderCart();
}

function updateItemPrice(productId, value) {
  const item = cart.find(i => i.productId === productId);
  if (!item) return;
  const price = Math.max(0, parseFloat(value) || 0);
  item.price = Math.round(price * 100) / 100;
  const sym = window.currencySymbol || '';
  const line = document.querySelector('[data-line-total="' + productId + '"]');
  if (line) line.textContent = sym + (item.price * item.quantity).toFixed(2);
  const coLine = document.querySelector('[data-co-line-total="' + productId + '"]');
  if (coLine) coLine.textContent = sym + (item.price * item.quantity).toFixed(2);
  document.querySelectorAll('[data-item-price="' + productId + '"]').forEach(function (inp) {
    if (inp !== document.activeElement) inp.value = item.price.toFixed(2);
  });
  totalDirty = false;
  updateTotals();
}

function onFinalTotalInput(value, source) {
  totalDirty = true;
  const n = Math.max(0, parseFloat(value) || 0);
  const cartInput = document.getElementById('totalInput');
  const coInput = document.getElementById('coTotalInput');
  if (source !== 'cart' && cartInput && cartInput !== document.activeElement) {
    cartInput.value = n.toFixed(2);
  }
  if (source !== 'checkout' && coInput && coInput !== document.activeElement) {
    coInput.value = n.toFixed(2);
  }
  const chargeAmount = document.getElementById('chargeAmount');
  if (chargeAmount) chargeAmount.textContent = (window.currencySymbol || '') + n.toFixed(2);
  refreshQuickCash(n);
  updateChange();
}

function onDiscountInput() {
  totalDirty = false;
  updateTotals();
}

function clearCart() {
  cart = [];
  totalDirty = false;
  var discountInput = document.getElementById('discountInput');
  if (discountInput) discountInput.value = 0;
  var totalInput = document.getElementById('totalInput');
  if (totalInput) totalInput.value = '0.00';
  var coTotalInput = document.getElementById('coTotalInput');
  if (coTotalInput) coTotalInput.value = '0.00';
  clearCustomer();
  renderCart();
}

function selectCustomer(id, name, phone) {
  selectedCustomer = id || null;
  var tag = document.getElementById('customerTag');
  var input = document.getElementById('customerSearch');
  if (id) {
    tag.classList.remove('hidden');
    input.classList.add('hidden');
    document.getElementById('customerTagName').textContent = name;
    document.getElementById('customerTagPhone').textContent = phone ? phone + ' · #' + id : ('#' + id);
  } else {
    tag.classList.add('hidden');
    input.classList.remove('hidden');
    input.value = '';
    input.focus();
  }
  closeCustomerDropdown();
}

function clearCustomer() {
  selectCustomer(null);
}

function openCustomerDropdown() {
  document.getElementById('customerDropdown').classList.remove('hidden');
}

function closeCustomerDropdown() {
  var dd = document.getElementById('customerDropdown');
  var no = document.getElementById('noCustomers');
  if (dd) dd.classList.add('hidden');
  if (no) no.classList.add('hidden');
}

function filterCustomers() {
  var q = document.getElementById('customerSearch').value.toLowerCase().trim();
  var dd = document.getElementById('customerDropdown');
  var no = document.getElementById('noCustomers');
  if (!q) { dd.classList.add('hidden'); no.classList.add('hidden'); return; }

  var customers = window.customers || [];

  var filtered = customers.filter(function (c) {
    return c.name.toLowerCase().includes(q) || c.phone.toLowerCase().includes(q);
  });

  if (filtered.length === 0) {
    dd.classList.add('hidden');
    no.classList.remove('hidden');
    return;
  }

  no.classList.add('hidden');
  dd.classList.remove('hidden');
  dd.innerHTML = filtered.map(function (c) {
    return '<button type="button" onclick="selectCustomer(\'' + c.id + '\',\'' + c.name.replace(/'/g, "\\'") + '\',\'' + (c.phone || '').replace(/'/g, "\\'") + '\')" class="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center gap-3 text-xs border-b border-gray-100 dark:border-gray-800 last:border-0">' +
      '<div class="w-7 h-7 rounded-full bg-primary-100 dark:bg-primary-900/40 grid place-items-center text-primary-600 font-semibold text-[10px] shrink-0">' + c.name.charAt(0).toUpperCase() + '</div>' +
      '<div class="flex-1 min-w-0"><p class="font-medium truncate">' + c.name + '</p><p class="text-[10px] text-gray-500 truncate">' + (c.phone || 'No phone') + ' · ' + c.pts + ' pts</p></div>' +
      '</button>';
  }).join('');
}

function renderCart() {
  const cartEl = document.getElementById('cart');
  const countEl = document.getElementById('cartCount');
  const clearBtn = document.getElementById('clearBtn');
  const chargeBtn = document.getElementById('chargeBtn');
  if (!cartEl || !countEl || !clearBtn || !chargeBtn) return;

  if (cart.length === 0) {
    cartEl.innerHTML = `
        <div id="emptyCart" class="h-full grid place-items-center text-center text-gray-500 dark:text-gray-400 py-16">
          <div>
            <i data-lucide="shopping-cart" class="w-10 h-10 mx-auto mb-2 opacity-30"></i>
            <p class="text-sm font-medium text-gray-700 dark:text-gray-200">Empty cart</p>
            <p class="text-xs mt-1">Tap products to start a sale</p>
          </div>
        </div>`;
    countEl.classList.add('hidden');
    clearBtn.classList.add('hidden');
    chargeBtn.disabled = true;
  } else {
    countEl.classList.remove('hidden');
    clearBtn.classList.remove('hidden');
    chargeBtn.disabled = false;

    const sym = window.currencySymbol || '';
    cartEl.innerHTML = cart.map(item => `
      <div class="flex items-center gap-2 bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg p-2 text-gray-900 dark:text-gray-100">
        <div class="flex-1 min-w-0">
          <p class="text-xs font-medium truncate text-gray-900 dark:text-gray-100">${item.name}</p>
          <div class="flex items-center gap-1 mt-1">
            <span class="text-[10px] text-gray-500 shrink-0">${sym}</span>
            <input type="number" min="0" step="0.01" data-item-price="${item.productId}" value="${item.price.toFixed(2)}"
              oninput="updateItemPrice('${item.productId}', this.value)"
              class="w-[4.5rem] h-6 text-right text-xs p-0 px-1 tabular-nums rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:border-primary-500 focus:outline-none" />
            <span class="text-[10px] text-gray-500">ea · ${item.stock} in stock</span>
          </div>
        </div>
        <div class="flex items-center gap-1">
          <button onclick="updateQuantity('${item.productId}', ${item.quantity - 1})" class="grid place-items-center w-6 h-6 rounded border border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-200 hover:bg-white dark:hover:bg-gray-700"><i data-lucide="minus" class="w-3 h-3"></i></button>
          <input type="number" value="${item.quantity}" onchange="updateQuantity('${item.productId}', this.value)" class="w-10 h-6 text-center text-xs p-0 tabular-nums rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
          <button onclick="updateQuantity('${item.productId}', ${item.quantity + 1})" ${item.quantity >= item.stock ? 'disabled' : ''} class="grid place-items-center w-6 h-6 rounded border border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-200 hover:bg-white dark:hover:bg-gray-700 disabled:opacity-30"><i data-lucide="plus" class="w-3 h-3"></i></button>
        </div>
        <div class="w-16 text-right shrink-0">
          <p data-line-total="${item.productId}" class="text-xs font-semibold tabular-nums text-gray-900 dark:text-gray-100">${sym}${(item.price * item.quantity).toFixed(2)}</p>
        </div>
        <button onclick="removeFromCart('${item.productId}')" class="text-gray-400 hover:text-red-600 shrink-0"><i data-lucide="x" class="w-3 h-3"></i></button>
      </div>
    `).join('');

    const totalItems = cart.reduce((s, i) => s + i.quantity, 0);
    countEl.textContent = `${totalItems} items`;
  }

  if (window.lucide) lucide.createIcons();
  updateTotals();
}

function getComputedTotals() {
  const subtotal = Math.round(cart.reduce((s, i) => s + i.price * i.quantity, 0) * 100) / 100;
  const tax = Math.round(subtotal * (window.taxRate || 0) / 100 * 100) / 100;
  const discount = parseFloat((document.getElementById('discountInput') || {}).value) || 0;
  const computed = Math.round((subtotal + tax - discount) * 100) / 100;
  return { subtotal, tax, discount, computed };
}

function getChargedTotal() {
  const computed = getComputedTotals().computed;
  const modal = document.getElementById('checkoutModal');
  const checkoutOpen = modal && !modal.classList.contains('hidden');
  const el = (checkoutOpen && document.getElementById('coTotalInput')) || document.getElementById('totalInput');
  if (totalDirty && el && el.value !== '') {
    const n = parseFloat(el.value);
    if (!isNaN(n)) return Math.round(Math.max(0, n) * 100) / 100;
  }
  return computed;
}

function updateTotals() {
  const subtotalEl = document.getElementById('subtotal');
  const discountInput = document.getElementById('discountInput');
  if (!subtotalEl || !discountInput) return;
  const { subtotal, tax, computed } = getComputedTotals();
  const total = totalDirty ? getChargedTotal() : computed;
  const sym = window.currencySymbol || '';

  subtotalEl.textContent = sym + subtotal.toFixed(2);
  document.getElementById('tax').textContent = sym + tax.toFixed(2);

  const totalInput = document.getElementById('totalInput');
  if (totalInput && document.activeElement !== totalInput) {
    totalInput.value = total.toFixed(2);
  }
  const coTotalInput = document.getElementById('coTotalInput');
  if (coTotalInput && document.activeElement !== coTotalInput) {
    coTotalInput.value = total.toFixed(2);
  }
  const coSubtotal = document.getElementById('coSubtotal');
  if (coSubtotal) coSubtotal.textContent = sym + subtotal.toFixed(2);
  const coTax = document.getElementById('coTax');
  if (coTax) coTax.textContent = sym + tax.toFixed(2);
  const discRow = document.getElementById('coDiscRow');
  if (discRow) {
    if (discountInput && (parseFloat(discountInput.value) || 0) > 0) {
      discRow.classList.remove('hidden');
      document.getElementById('coDiscount').textContent = '-' + sym + (parseFloat(discountInput.value) || 0).toFixed(2);
    } else {
      discRow.classList.add('hidden');
    }
  }

  const chargeAmount = document.getElementById('chargeAmount');
  if (chargeAmount) chargeAmount.textContent = sym + total.toFixed(2);
  refreshQuickCash(total);
  updateChange();
}

function refreshQuickCash(total) {
  const quickCash = document.getElementById('quickCash');
  const modal = document.getElementById('checkoutModal');
  if (!quickCash || !modal || modal.classList.contains('hidden')) return;
  const sym = window.currencySymbol || '';
  const amounts = [total, Math.ceil(total / 5) * 5, Math.ceil(total / 10) * 10, Math.ceil(total / 20) * 20];
  const unique = amounts.filter(function (amt, i, arr) { return arr.indexOf(amt) === i; });
  quickCash.innerHTML = unique.map(amt => `
    <button onclick="document.getElementById('paidAmount').value='${amt.toFixed(2)}'; updateChange()" class="flex-1 text-xs h-8 rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800">${sym}${amt.toFixed(2)}</button>
  `).join('');
}

function filterProducts() {
  const q = document.getElementById('productSearch').value.toLowerCase();
  document.querySelectorAll('#productGrid button').forEach(btn => {
    const name = btn.dataset.productName || '';
    const sku = btn.dataset.productSku || '';
    const bc = btn.dataset.productBarcode || '';
    btn.style.display = (name.includes(q) || sku.includes(q) || bc.includes(q)) ? '' : 'none';
  });
}

// ── Barcode scanning ──────────────────────────────────────

function handleBarcodeScan(barcode) {
  const input = document.getElementById('barcodeInput');
  if (!input) return;
  input.value = '';
  input.focus();

  fetch('/api/products/by-barcode/' + encodeURIComponent(barcode))
    .then(function (r) {
      if (!r.ok) throw new Error('Product not found');
      return r.json();
    })
    .then(function (p) {
      addToCart(p.id, p.name, p.price, p.cost, p.stock);
    })
    .catch(function () {
      input.placeholder = 'Not found — scan again';
      input.classList.add('border-red-400', 'placeholder:text-red-300');
      setTimeout(function () {
        input.placeholder = 'Scan barcode...';
        input.classList.remove('border-red-400', 'placeholder:text-red-300');
      }, 1500);
    });
}

(function bindPosEvents() {
  if (window.__qpPosBound) return;
  window.__qpPosBound = true;

  document.addEventListener('click', function (e) {
    var tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || tag === 'BUTTON') return;
    if (e.target.closest('#cart') || e.target.closest('#checkoutModal') || e.target.closest('#receiptModal')) return;
    if (e.target.closest('#customerPicker')) return;
    closeCustomerDropdown();
    var barcodeInput = document.getElementById('barcodeInput');
    if (barcodeInput) barcodeInput.focus();
  });

  document.addEventListener('keydown', function (e) {
    if (e.target && e.target.id === 'barcodeInput' && e.key === 'Enter') {
      e.preventDefault();
      var val = e.target.value.trim();
      if (val) handleBarcodeScan(val);
    }
    if (e.target && e.target.id === 'customerSearch' && e.key === 'Escape') {
      closeCustomerDropdown();
    }
  });

  document.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'customerSearch') filterCustomers();
  });
  document.addEventListener('focusin', function (e) {
    if (e.target && e.target.id === 'customerSearch' && e.target.value.trim()) filterCustomers();
  });
})();

function initPosPage() {
  var barcodeInput = document.getElementById('barcodeInput');
  if (barcodeInput) barcodeInput.focus();
  var queued = window._qpCartQueue || [];
  window._qpCartQueue = [];
  queued.forEach(function (args) { addToCart.apply(null, args); });
  renderCart();
}
window.initPosPage = initPosPage;
window.addToCart = addToCart;
window.setCategory = setCategory;
window.clearCart = clearCart;
window.filterProducts = filterProducts;
window.updateItemPrice = updateItemPrice;
window.onFinalTotalInput = onFinalTotalInput;
window.onDiscountInput = onDiscountInput;

if (document.getElementById('productGrid')) {
  initPosPage();
}

function setCategory(catId) {
  document.querySelectorAll('#categoryTabs button').forEach(btn => {
    btn.classList.toggle('is-active', btn.dataset.cat === catId);
  });

  document.querySelectorAll('#productGrid button').forEach(btn => {
    if (catId === 'all' || btn.dataset.productCat === catId) {
      btn.style.display = '';
    } else {
      btn.style.display = 'none';
    }
  });
}

// Checkout flow
function openCheckout() {
  if (cart.length === 0) return;
  const { subtotal, tax, discount } = getComputedTotals();
  const total = getChargedTotal();
  const sym = window.currencySymbol || '';

  const itemsEl = document.getElementById('coItems');
  if (itemsEl) {
    itemsEl.innerHTML = cart.map(item => `
      <div class="flex items-center gap-2 text-xs">
        <span class="flex-1 min-w-0 truncate text-gray-700 dark:text-gray-200">${item.name} × ${item.quantity}</span>
        <span class="text-gray-400 shrink-0">${sym}</span>
        <input type="number" min="0" step="0.01" data-item-price="${item.productId}" value="${item.price.toFixed(2)}"
          oninput="updateItemPrice('${item.productId}', this.value)"
          class="w-20 h-7 text-right text-xs tabular-nums rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-1.5 focus:border-primary-500 focus:outline-none" />
        <span data-co-line-total="${item.productId}" class="w-16 text-right tabular-nums shrink-0">${sym}${(item.price * item.quantity).toFixed(2)}</span>
      </div>
    `).join('');
  }

  document.getElementById('coSubtotal').textContent = sym + subtotal.toFixed(2);
  document.getElementById('coTax').textContent = sym + tax.toFixed(2);
  const discRow = document.getElementById('coDiscRow');
  if (discount > 0) {
    discRow.classList.remove('hidden');
    document.getElementById('coDiscount').textContent = '-' + sym + discount.toFixed(2);
  } else {
    discRow.classList.add('hidden');
  }
  const coTotalInput = document.getElementById('coTotalInput');
  if (coTotalInput) coTotalInput.value = total.toFixed(2);

  // Quick cash buttons
  const quickCash = document.getElementById('quickCash');
  const amounts = [total, Math.ceil(total / 5) * 5, Math.ceil(total / 10) * 10, Math.ceil(total / 20) * 20];
  const unique = amounts.filter(function (amt, i, arr) { return arr.indexOf(amt) === i; });
  quickCash.innerHTML = unique.map(amt => `
    <button onclick="document.getElementById('paidAmount').value='${amt.toFixed(2)}'; updateChange()" class="flex-1 text-xs h-8 rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800">${sym}${amt.toFixed(2)}</button>
  `).join('');

  document.getElementById('paidAmount').value = '';
  document.getElementById('changeRow').classList.add('hidden');

  setPayment('cash');
  document.getElementById('checkoutModal').classList.remove('hidden');
  document.getElementById('checkoutModal').classList.add('flex');
  if (window.lucide) lucide.createIcons();
}

function closeCheckout() {
  document.getElementById('checkoutModal').classList.add('hidden');
  document.getElementById('checkoutModal').classList.remove('flex');
}

function setPayment(method) {
  selectedPayment = method;
  ['cash', 'card', 'wallet'].forEach(m => {
    const btn = document.getElementById('pay-' + m);
    if (!btn) return;
    if (m === method) {
      btn.classList.remove('border-gray-200', 'dark:border-gray-700');
      btn.classList.add('border-primary-500', 'bg-primary-50', 'dark:bg-emerald-900/20');
      btn.querySelector('i')?.classList.remove('text-gray-400');
      btn.querySelector('i')?.classList.add('text-primary-600');
      btn.querySelector('span')?.classList.add('text-primary-600');
    } else {
      btn.classList.add('border-gray-200', 'dark:border-gray-700');
      btn.classList.remove('border-primary-500', 'bg-primary-50', 'dark:bg-emerald-900/20');
      btn.querySelector('i')?.classList.add('text-gray-400');
      btn.querySelector('i')?.classList.remove('text-primary-600');
      btn.querySelector('span')?.classList.remove('text-primary-600');
    }
  });
  document.getElementById('cashSection').style.display = method === 'cash' ? 'block' : 'none';
}

function updateChange() {
  const changeRow = document.getElementById('changeRow');
  const paidEl = document.getElementById('paidAmount');
  if (!changeRow || !paidEl) return;
  const total = getChargedTotal();
  const paid = parseFloat(paidEl.value) || 0;
  const sym = window.currencySymbol || '';
  if (paid >= total && paidEl.value !== '') {
    changeRow.classList.remove('hidden');
    document.getElementById('changeAmount').textContent = sym + (paid - total).toFixed(2);
  } else {
    changeRow.classList.add('hidden');
  }
}

async function processSale() {
  const total = getChargedTotal();
  const paid = parseFloat(document.getElementById('paidAmount').value) || 0;
  if (selectedPayment === 'cash') {
    if (paid < total) {
      alert('Insufficient cash received');
      return;
    }
  }

  const btn = document.getElementById('processBtn');
  btn.disabled = true;
  btn.textContent = 'Processing...';

  try {
    const discount = parseFloat(document.getElementById('discountInput').value) || 0;
    const res = await fetch('/api/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: cart.map(i => ({ productId: i.productId, quantity: i.quantity, price: i.price })),
        customer_id: selectedCustomer,
        tax_rate: window.taxRate,
        discount: discount,
        total: total,
        cash_received: selectedPayment === 'cash' ? paid : null,
        payment_method: selectedPayment,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Checkout failed');

    closeCheckout();
    showReceipt(data.order);
    clearCart();
  } catch (e) {
    alert(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Complete Sale';
  }
}

function showReceipt(order) {
  document.getElementById('receiptOrderNumber').textContent = 'Order ' + order.order_number;
  const body = document.getElementById('receiptBody');
  body.innerHTML = `
    <div class="bg-white text-black rounded-lg p-4 font-mono text-xs space-y-1 border border-dashed border-gray-300">
      <div class="text-center pb-2 border-b border-dashed border-gray-300">
        <p class="font-bold text-sm">${window.storeName}</p>
        <p class="text-[10px]">${window.storeAddress}</p>
        <p class="text-[10px]">${window.storePhone}</p>
      </div>
      <div class="py-2 border-b border-dashed border-gray-300 text-[10px]">
        <div class="flex justify-between"><span>Order:</span><span>${order.order_number}</span></div>
        <div class="flex justify-between"><span>Date:</span><span>${new Date(order.created_at).toLocaleString()}</span></div>
        <div class="flex justify-between"><span>Cashier:</span><span>${order.cashier_name}</span></div>
        <div class="flex justify-between"><span>Customer:</span><span>${order.customer_name}</span></div>
      </div>
      <div class="py-2 border-b border-dashed border-gray-300 space-y-1">
        ${order.items.map(item => {
          const orig = item.original_price != null ? Number(item.original_price) : Number(item.price);
          const sold = Number(item.price);
          const changed = Math.abs(orig - sold) > 0.001;
          return `<div class="flex justify-between text-[10px]"><span>${item.quantity}× ${item.name}${changed ? ` <span class="text-gray-400">(${currencySymbol}${orig.toFixed(2)}→${currencySymbol}${sold.toFixed(2)})</span>` : ''}</span><span>${currencySymbol}${item.subtotal.toFixed(2)}</span></div>`;
        }).join('')}
      </div>
      <div class="py-2 space-y-1 text-[10px]">
        <div class="flex justify-between"><span>Subtotal</span><span>${currencySymbol}${order.subtotal.toFixed(2)}</span></div>
        <div class="flex justify-between"><span>Tax (${order.tax_rate}%)</span><span>${currencySymbol}${order.tax.toFixed(2)}</span></div>
        ${order.discount > 0 ? `<div class="flex justify-between"><span>Discount</span><span>-${currencySymbol}${order.discount.toFixed(2)}</span></div>` : ''}
        ${order.original_total != null && Math.abs(Number(order.original_total) - Number(order.total)) > 0.001 ? `<div class="flex justify-between"><span>Original</span><span>${currencySymbol}${Number(order.original_total).toFixed(2)}</span></div>` : ''}
        <div class="flex justify-between font-bold text-xs pt-1 border-t border-gray-300"><span>TOTAL</span><span>${currencySymbol}${order.total.toFixed(2)}</span></div>
        <div class="flex justify-between"><span>Paid via ${order.payment_method}</span><span>${currencySymbol}${order.total.toFixed(2)}</span></div>
        ${order.payment_method === 'cash' && order.cash_received != null ? `
        <div class="flex justify-between"><span>Cash received</span><span>${currencySymbol}${Number(order.cash_received).toFixed(2)}</span></div>
        <div class="flex justify-between"><span>Change</span><span>${currencySymbol}${(Number(order.cash_received) - order.total).toFixed(2)}</span></div>` : ''}
      </div>
      <div class="text-center pt-2 text-[10px]">${window.receiptFooter}</div>
    </div>
  `;
  document.getElementById('receiptModal').classList.remove('hidden');
  document.getElementById('receiptModal').classList.add('flex');
  if (window.lucide) lucide.createIcons();
}

function closeReceipt() {
  document.getElementById('receiptModal').classList.add('hidden');
  document.getElementById('receiptModal').classList.remove('flex');
  location.reload();
}
