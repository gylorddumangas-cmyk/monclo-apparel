"""Monclo storefront logic, running entirely in browser-side Python via PyScript."""
import asyncio
import html
import json
import uuid
from pyscript import document, window
from pyodide.ffi import create_proxy

products = []
selected_category = "All Products"
selected_size = "All Sizes"
selected_price = "All Prices"
selected_sort = "featured"
search_text = ""
CART_KEY = "monclo_cart_v1"
BUY_KEY = "monclo_buy_now_v1"
CONFIRM_KEY = "monclo_confirm_v1"
ORDER_KEY = "monclo_pending_order_key"
placing_order = False
admin_state = None
admin_products = []
admin_tab = "products"
editing_id = None


def esc(value):
    return html.escape(str(value), quote=True)


def peso(cents):
    return "₱" + f"{cents/100:,.2f}"


def image(url, alt, extra=""):
    return f'<img src="{esc(url)}" alt="{esc(alt)}" loading="lazy" {extra}>'


def get_route():
    return str(window.location.hash or "#/").split("?")[0][1:] or "/"


def page(content):
    document.getElementById("page-content").innerHTML = content
    route = get_route().strip("/").split("/")[0] or "home"
    for link in document.querySelectorAll("[data-nav]"):
        link.classList.toggle("active", link.getAttribute("data-nav") == route)
    window.scrollTo(0, 0)


def hero(title, subtitle, eyebrow="THE MONCLO COLLECTION"):
    return f'<div class="page-hero"><div class="container"><span class="eyebrow">{esc(eyebrow)}</span><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div></div>'


def product_card(p):
    available = p["stock"] > 0
    size_options = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in p["sizes"])
    color_options = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in p["colors"])
    disabled = "" if available else "disabled"
    return f'''<article class="product-card"><div class="product-photo">{image(p['image_url'],p['name'])}<span class="badge-stock">{'IN STOCK' if available else 'SOLD OUT'}</span></div><div class="product-info"><div class="product-category">{esc(p['category'])}</div><h3 class="product-name">{esc(p['name'])}</h3><p class="product-description">{esc(p['description'])}</p><div class="product-meta"><span class="product-price">{peso(p['price_cents'])}</span><span class="small muted">{p['stock']} left</span></div><div class="product-selects"><label class="sr-only" for="size-{p['id']}">Size</label><select class="mini-select" id="size-{p['id']}">{size_options}</select><label class="sr-only" for="color-{p['id']}">Color</label><select class="mini-select" id="color-{p['id']}">{color_options}</select></div><div class="product-selects"><label for="qty-{p['id']}" class="small muted">QUANTITY</label><input class="mini-select" type="number" id="qty-{p['id']}" min="1" max="{p['stock']}" value="1" {disabled}></div><div class="product-actions"><button class="btn btn-sm btn-outline" data-action="add" data-id="{p['id']}" {disabled}>ADD TO BAG</button><button class="btn btn-sm" data-action="buy" data-id="{p['id']}" {disabled}>BUY NOW ↗</button></div></div></article>'''


def render_home():
    page('''<section class="hero"><div class="container hero-inner"><div class="hero-copy"><span class="hero-kicker">MONCLO APPAREL · EST. 2026</span><h1>Wear Your Style.<br><em>Define Your Identity.</em></h1><p>Discover modern essentials and everyday streetwear designed to express your individuality.</p><a class="btn" href="#/shop">EXPLORE THE COLLECTION <span>↗</span></a></div><div class="hero-visual"><img src="https://images.unsplash.com/photo-1529139574466-a303027c1d8b?w=1000&q=85&fit=crop" alt="Contemporary streetwear fashion editorial"></div></div></section>
      <div class="container benefit-row"><div class="benefit-mini"><span>✦</span> EVERYDAY ESSENTIALS</div><div class="benefit-mini"><span>◇</span> CURATED FOR COMFORT</div><div class="benefit-mini"><span>↗</span> CASH ON DELIVERY</div></div>
      <section class="section"><div class="container"><div class="section-head"><div><span class="eyebrow">CURATED FOR YOU</span><h2>The Current Edit.</h2></div><a class="text-link" href="#/shop">VIEW ALL PRODUCTS ↗</a></div><div class="product-grid">'''+"".join(product_card(p) for p in products if p["featured"])+'''</div></div></section>
      <section class="section section-alt"><div class="container about-layout"><div class="about-panel"><img src="https://images.unsplash.com/photo-1483985988355-763728e1935b?w=1050&q=85&fit=crop" alt="Minimal streetwear fashion selection" loading="lazy"></div><div class="about-content"><span class="eyebrow">A LITTLE ABOUT US</span><h2>Style that speaks for itself.</h2><p>Monclo Apparel is built for the everyday individual. We believe the best pieces don't shout — they just fit perfectly into your story.</p><p>Versatile, comfortable, intentionally selected. Wear what feels like you.</p><a class="btn btn-outline" href="#/shop">DISCOVER MONCLO ↗</a></div></div></section>
      <section class="section"><div class="container"><div class="section-head"><div><span class="eyebrow">THE MONCLO DIFFERENCE</span><h2>Why shop with us?</h2></div></div><div class="features-grid"><div class="feature"><div class="feature-icon">✦</div><h3>Made for everyday style</h3><p>Versatile pieces designed to work with your wardrobe, every day.</p></div><div class="feature"><div class="feature-icon">◇</div><h3>Shopping made simple</h3><p>A seamless way to find your fit and discover your next favorite.</p></div><div class="feature"><div class="feature-icon">↗</div><h3>Easy Cash on Delivery</h3><p>Order with confidence and pay when your parcel arrives.</p></div></div></div></section>
      <section class="newsletter"><span class="eyebrow">THE MONCLO WAY</span><h2>Your next favorite fit starts here.</h2><p>Find pieces that feel as good as they look.</p><a class="btn btn-light" href="#/shop">SHOP THE COLLECTION ↗</a></section>''')


def visible_products():
    result = [p for p in products if (selected_category == "All Products" or p["category"] == selected_category) and (selected_size == "All Sizes" or selected_size in p["sizes"]) and search_text.lower() in p["name"].lower()]
    result = [p for p in result if selected_price == "All Prices" or (selected_price == "Under ₱1,000" and p["price_cents"] < 100000) or (selected_price == "₱1,000 – ₱1,500" and 100000 <= p["price_cents"] <= 150000) or (selected_price == "Over ₱1,500" and p["price_cents"] > 150000)]
    if selected_sort == "low": result.sort(key=lambda p: p["price_cents"])
    if selected_sort == "high": result.sort(key=lambda p: -p["price_cents"])
    if selected_sort == "name": result.sort(key=lambda p: p["name"].lower())
    return result


def result_grid():
    found = visible_products()
    if not found: return '<div class="empty-state"><h3>No items found.</h3><p>Try another size, category or search.</p><button class="btn btn-outline" data-action="clear-filters">CLEAR FILTERS</button></div>'
    return '<div class="product-grid">'+"".join(product_card(p) for p in found)+'</div>'


def option_menu(values, current):
    return "".join(f'<option value="{esc(v)}" {"selected" if v==current else ""}>{esc(v)}</option>' for v in values)


def render_shop():
    categories = ["All Products"] + sorted(set(p["category"] for p in products))
    buttons = "".join(f'<button class="cat-btn {"active" if c==selected_category else ""}" data-action="category" data-category="{esc(c)}">{esc(c)}</button>' for c in categories)
    page(hero("Explore Our Collection", "Find your next everyday essential.") + f'''<section class="section"><div class="container shop-layout"><aside class="filters" aria-label="Product filters"><div class="filter-block"><span class="filter-label">Category</span>{buttons}</div><div class="filter-block"><label for="shop-search" class="filter-label">Search products</label><input class="field" type="search" id="shop-search" placeholder="Find your fit..." value="{esc(search_text)}"></div><div class="filter-block"><label for="filter-size" class="filter-label">Size</label><select class="field" id="filter-size">{option_menu(['All Sizes','S','M','L','XL'],selected_size)}</select></div><div class="filter-block"><label for="filter-price" class="filter-label">Price range</label><select class="field" id="filter-price">{option_menu(['All Prices','Under ₱1,000','₱1,000 – ₱1,500','Over ₱1,500'],selected_price)}</select></div></aside><div><div class="shop-topline"><span id="results-count" class="small muted">{len(visible_products())} products</span><label class="small" for="shop-sort">Sort by <select class="mini-select" id="shop-sort">{option_menu(['featured','low','high','name'],selected_sort)}</select></label></div><div id="shop-results">{result_grid()}</div></div></div></section>''')


def update_shop_results():
    grid = document.getElementById("shop-results")
    if grid:
        grid.innerHTML = result_grid()
        document.getElementById("results-count").textContent = f"{len(visible_products())} products"


def lookup(product_id):
    return next((p for p in products if p["id"] == product_id), None)


def read_items(storage, key):
    try:
        value = json.loads(str(storage.getItem(key) or "[]"))
        if not isinstance(value, list): return []
        valid = []
        for item in value:
            if not isinstance(item, dict): continue
            pid, size, color, qty = item.get("product_id"), item.get("size"), item.get("color"), item.get("quantity")
            p = lookup(pid)
            if p and isinstance(qty, int) and 1 <= qty <= p["stock"] and size in p["sizes"] and color in p["colors"]:
                valid.append({"product_id": pid, "size": size, "color": color, "quantity": qty})
        return valid
    except Exception:
        return []


def cart_items():
    return read_items(window.localStorage, CART_KEY)


def checkout_items():
    chosen = read_items(window.sessionStorage, BUY_KEY)
    return chosen if chosen else cart_items()


def save_cart(items):
    window.localStorage.setItem(CART_KEY, json.dumps(items))
    update_badge()


def update_badge():
    document.getElementById("cart-count").textContent = str(sum(item["quantity"] for item in cart_items()))


async def hide_toast_later():
    await asyncio.sleep(3)
    document.getElementById("toast").classList.remove("show")


def toast(text):
    element = document.getElementById("toast")
    element.textContent = text
    element.classList.add("show")
    document.getElementById("app-status").textContent = text
    asyncio.create_task(hide_toast_later())


def add_product(pid, buy=False):
    p = lookup(pid)
    if not p or p["stock"] < 1:
        toast("Sorry, this item is no longer available."); return
    try: qty = int(document.getElementById(f"qty-{pid}").value)
    except Exception: qty = 0
    if not (1 <= qty <= p["stock"]):
        toast("Please enter a valid quantity."); return
    size = str(document.getElementById(f"size-{pid}").value)
    color = str(document.getElementById(f"color-{pid}").value)
    if size not in p["sizes"] or color not in p["colors"]:
        toast("Please choose a valid size and color."); return
    item = {"product_id":pid,"size":size,"color":color,"quantity":qty}
    window.sessionStorage.removeItem(ORDER_KEY)
    if buy:
        window.sessionStorage.setItem(BUY_KEY, json.dumps([item]))
        window.location.hash = "/checkout"
        return
    current = cart_items()
    used = sum(i["quantity"] for i in current if i["product_id"] == pid)
    if used + qty > p["stock"]:
        toast("Not enough stock for that quantity."); return
    match = next((i for i in current if (i["product_id"],i["size"],i["color"]) == (pid,size,color)), None)
    if match: match["quantity"] += qty
    else: current.append(item)
    save_cart(current)
    toast(f"{p['name']} added to your bag.")


def delivery_cents(items):
    return 12000 if items else 0


def totals(items):
    subtotal = sum(lookup(i["product_id"])["price_cents"]*i["quantity"] for i in items if lookup(i["product_id"]))
    return subtotal, delivery_cents(items), subtotal+delivery_cents(items)


def summary(items, checkout=False):
    sub, delivery, total = totals(items)
    detail = "".join(f'<div class="total-row small"><span>{esc(lookup(i["product_id"])["name"])} · {esc(i["size"])} / {esc(i["color"])} ×{i["quantity"]}</span><strong>{peso(lookup(i["product_id"])["price_cents"]*i["quantity"])}</strong></div>' for i in items if lookup(i["product_id"]))
    action = '<button class="btn btn-block" data-action="checkout">PROCEED TO CHECKOUT ↗</button>' if not checkout else ''
    return f'<aside class="summary-card"><h3>Order summary</h3>{detail}<div class="total-row"><span>Subtotal</span><strong>{peso(sub)}</strong></div><div class="total-row"><span>Delivery fee</span><strong>{peso(delivery)}</strong></div><div class="total-row major"><span>Total due</span><span>{peso(total)}</span></div>{action}<div class="help-note">Secure checkout · Cash on Delivery only</div></aside>'


def render_cart():
    items = cart_items()
    if not items:
        page(hero("Your Shopping Bag", "Your next favorite piece is one click away.")+'''<section class="section"><div class="container"><div class="empty-state"><h3>Your bag is feeling a little light.</h3><p>Explore our collection and add something you love.</p><a href="#/shop" class="btn">CONTINUE SHOPPING ↗</a></div></div></section>''')
        return
    cards = ""
    for index, item in enumerate(items):
        p = lookup(item["product_id"])
        if not p: continue
        cards += f'''<article class="cart-item">{image(p['image_url'],p['name'],'class="cart-thumb"')}<div><h3>{esc(p['name'])}</h3><p>Size: {esc(item['size'])} · Color: {esc(item['color'])}</p><div class="qty-control"><button data-action="cart-minus" data-index="{index}" aria-label="Decrease quantity">−</button><span>{item['quantity']}</span><button data-action="cart-plus" data-index="{index}" aria-label="Increase quantity">+</button></div><p><button class="remove-btn" data-action="cart-remove" data-index="{index}">Remove</button></p></div><strong>{peso(p['price_cents']*item['quantity'])}</strong></article>'''
    page(hero("Your Shopping Bag", "Review your picks before checkout.")+f'<section class="section"><div class="container cart-layout"><div><span class="eyebrow">YOUR SELECTION · {sum(i["quantity"] for i in items)} ITEMS</span>{cards}<a href="#/shop" class="text-link" style="display:inline-block;margin-top:23px">← CONTINUE SHOPPING</a></div>{summary(items)}</div></section>')


def modify_cart(action, index):
    items = cart_items()
    if not 0 <= index < len(items): return
    item = items[index]
    if action == "cart-remove": items.pop(index)
    elif action == "cart-minus":
        item["quantity"] -= 1
        if item["quantity"] < 1: items.pop(index)
    elif action == "cart-plus":
        p = lookup(item["product_id"])
        all_qty = sum(i["quantity"] for i in items if i["product_id"]==item["product_id"])
        if p and all_qty >= p["stock"]:
            toast("You have reached available stock."); return
        item["quantity"] += 1
    window.sessionStorage.removeItem(ORDER_KEY)
    save_cart(items)
    render_cart()


def form_field(label, name, required=True, kind="text", wide=False, placeholder="", attrs=""):
    req = "required" if required else ""
    return f'<label class="form-field {"wide" if wide else ""}">{esc(label)}<input class="field" type="{kind}" name="{esc(name)}" placeholder="{esc(placeholder)}" {req} {attrs}></label>'


def render_checkout():
    items = checkout_items()
    if not items:
        page(hero("Checkout", "Finish your order with Cash on Delivery.")+'<section class="section"><div class="container empty-state"><h3>Your checkout is empty.</h3><p>Please select an item before checking out.</p><a class="btn" href="#/shop">SHOP NOW ↗</a></div></section>')
        return
    fields = (form_field("Full name *", "customer_name", attrs='minlength="2" maxlength="90"') +
              form_field("Mobile number *", "phone", kind="tel", placeholder="09xxxxxxxxx", attrs='pattern="(09[0-9]{9}|[+]639[0-9]{9})"') +
              form_field("Complete delivery address *", "address", wide=True, attrs='minlength="8" maxlength="240"') +
              form_field("City / Municipality *", "city", attrs='minlength="2" maxlength="90"') +
              form_field("Province *", "province", attrs='minlength="2" maxlength="90"') +
              form_field("Postal code (optional)", "postal_code", attrs='pattern="[0-9]{4}" maxlength="4"') +
              '<div></div><label class="form-field wide">Delivery instructions (optional)<textarea class="field" name="instructions" maxlength="500" placeholder="Landmark, building, or preferred delivery notes..."></textarea></label>')
    form = f'''<form id="order-form"><div class="form-section"><span class="eyebrow">STEP 01 / DELIVERY</span><h3>Where should we send your order?</h3><div class="form-grid">{fields}</div></div><div class="form-section"><span class="eyebrow">STEP 02 / PAYMENT</span><h3>Payment method</h3><div class="cod-card"><strong>◉ &nbsp;Cash on Delivery (COD)</strong><p>Pay for your order in cash when it arrives at your delivery address.</p></div></div><div class="form-section"><p class="notice">Please check your items and delivery information carefully before confirming your order.</p><p id="order-error" class="form-error" role="alert"></p><button type="submit" class="btn btn-block" id="place-order">PLACE ORDER · CASH ON DELIVERY ↗</button></div></form>'''
    page(hero("Secure Checkout", "One last step to your next favorite fit.")+f'<section class="section"><div class="container checkout-layout"><div>{form}</div>{summary(items, True)}</div></section>')


async def api_request(path, data=None, method="GET", csrf=None):
    options = {"method": method, "headers": {"Content-Type": "application/json"}}
    if csrf: options["headers"]["X-CSRF-Token"] = csrf
    if data is not None: options["body"] = json.dumps(data)
    response = await window.fetch(path, window.JSON.parse(json.dumps(options)))
    payload = (await response.json()).to_py()
    if not response.ok: raise ValueError(payload.get("error", "The request failed."))
    return payload


async def place_order():
    global placing_order, products
    if placing_order: return
    items = checkout_items()
    if not items: toast("Your checkout is empty."); return
    form = document.getElementById("order-form")
    if not form or not form.checkValidity():
        if form: form.reportValidity()
        return
    values = {field: str(form.elements.namedItem(field).value).strip() for field in ("customer_name", "phone", "address", "city", "province", "postal_code", "instructions")}
    key = str(window.sessionStorage.getItem(ORDER_KEY) or uuid.uuid4())
    window.sessionStorage.setItem(ORDER_KEY, key)
    btn = document.getElementById("place-order")
    placing_order = True
    btn.disabled = True
    btn.textContent = "SAVING YOUR ORDER..."
    try:
        data = await api_request("/api/orders", {**values, "payment_method":"COD", "items":items, "idempotency_key":key}, "POST")
        window.sessionStorage.setItem(CONFIRM_KEY, json.dumps(data))
        if not window.sessionStorage.getItem(BUY_KEY):
            save_cart([])
        window.sessionStorage.removeItem(BUY_KEY)
        window.sessionStorage.removeItem(ORDER_KEY)
        try:
            result = await window.fetch("/api/products")
            if result.ok: products = (await result.json()).to_py()["products"]
        except Exception: pass
        window.location.hash = "/confirmation"
        render_confirmation()
    except Exception as exc:
        error = document.getElementById("order-error")
        if error: error.textContent = str(exc)
        btn.disabled = False
        btn.textContent = "RETRY PLACE ORDER ↗"
    finally:
        placing_order = False


def render_confirmation():
    try:
        order = json.loads(str(window.sessionStorage.getItem(CONFIRM_KEY) or "null"))
    except Exception:
        order = None
    if not isinstance(order, dict) or "reference" not in order:
        page(hero("Order confirmation", "Cash on Delivery checkout.")+'<section class="section"><div class="container empty-state"><p>No confirmed order is available in this browser tab.</p><a class="btn" href="#/shop">RETURN TO SHOP</a></div></section>')
        return
    details = "".join(f'<div class="total-row"><span>{esc(i["name"])} · {esc(i["size"])} / {esc(i["color"])} × {i["quantity"]}</span><strong>{peso(i["unit_cents"]*i["quantity"])}</strong></div>' for i in order["items"])
    address = ", ".join(esc(order[k]) for k in ("address", "city", "province", "postal_code") if order.get(k))
    page(f'''<section class="section"><div class="container"><div class="success-panel"><div class="success-mark">✓</div><span class="eyebrow">ORDER SAVED SUCCESSFULLY</span><h2>Thank you for your order!</h2><p>Your order has been placed with Cash on Delivery.<br>Save your reference number for any order inquiries.</p><h3 style="font-size:25px;margin:22px 0">{esc(order["reference"])}</h3><div class="order-details">{details}<div class="total-row"><span>Subtotal</span><strong>{peso(order["subtotal_cents"])}</strong></div><div class="total-row"><span>Delivery fee</span><strong>{peso(order["delivery_cents"])}</strong></div><div class="total-row major"><span>Total to pay on delivery</span><strong>{peso(order["total_cents"])}</strong></div><p class="small"><strong>Payment:</strong> Cash on Delivery (COD)<br><strong>Recipient:</strong> {esc(order["customer_name"])}<br><strong>Mobile:</strong> {esc(order["phone"])}<br><strong>Delivery address:</strong> {address}</p></div><a class="btn" href="#/shop">BACK TO SHOP ↗</a></div></div></section>''')


def render_support():
    categories = ["General Inquiry", "Product Question", "Order Concern", "Website Feedback", "Suggestion", "Other"]
    options = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in categories)
    form = f'''<div><span class="eyebrow">GET IN TOUCH</span><h2>Send us a message.</h2><p class="muted">Have a question, suggestion, or concern? Contact Monclo Apparel. Your feedback helps us improve your shopping experience.</p><form class="form-section" id="support-form"><div class="form-grid"><label class="form-field">Full name *<input class="field" name="name" required minlength="2" maxlength="90" autocomplete="name"></label><label class="form-field">Email address *<input class="field" type="email" name="email" required autocomplete="email" maxlength="254"></label><label class="form-field wide">How can we help? *<select class="field" name="category" required>{options}</select></label><label class="form-field wide">Your message *<textarea class="field" name="message" minlength="10" maxlength="3000" required placeholder="Tell us how we can help..."></textarea></label></div><p class="form-error" id="feedback-error" role="alert"></p><button id="feedback-submit" type="submit" class="btn" style="margin-top:19px">SUBMIT FEEDBACK ↗</button></form></div>'''
    faqs = [("How do I place an order?", "Browse the Shop, choose your size, color and quantity, then select Add to Bag or Buy Now. Review your details, select Cash on Delivery and place your order."),
            ("How does Cash on Delivery work?", "You pay in cash when your order arrives at the address you provided. Monclo does not ask for credit card details."),
            ("What is the delivery fee?", "The sample store applies a flat ₱120 delivery fee per order. Update the fee in the Python checkout backend and storefront together for your real delivery rates."),
            ("Can I change my cart before checkout?", "Yes. Open Your Bag to change quantities or remove products. You can also select Buy Now to checkout one product directly."),
            ("What if my order cannot be submitted?", "Check the required delivery fields and your product quantities. If the store reports an error, no success confirmation is shown unless your order was saved."),
            ("How can I ask about my order?", "Choose Order Concern in this form, describe your issue, and include your Monclo order reference number in the message.")]
    accordion = "".join(f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q,a in faqs)
    side = f'<div><span class="eyebrow">GOOD TO KNOW</span><h2>Frequently asked questions.</h2><div class="faq-list">{accordion}</div><div class="notice" style="margin-top:25px">Need more help? Send us a message through the form and our team can review it in the store admin panel.</div></div>'
    page(hero("We're Here to Help", "Real questions deserve helpful answers.", "MONCLO CUSTOMER CARE") + f'<section class="section"><div class="container support-grid">{form}{side}</div></section>')


async def submit_feedback():
    form = document.getElementById("support-form")
    if not form or not form.checkValidity():
        if form: form.reportValidity()
        return
    data = {k: str(form.elements.namedItem(k).value).strip() for k in ("name", "email", "category", "message")}
    btn = document.getElementById("feedback-submit")
    btn.disabled = True
    btn.textContent = "SAVING FEEDBACK..."
    try:
        response = await api_request("/api/feedback", data, "POST")
        form.reset()
        document.getElementById("feedback-error").textContent = ""
        toast(response["message"])
        btn.textContent = "SEND ANOTHER MESSAGE ↗"
        btn.disabled = False
    except Exception as exc:
        document.getElementById("feedback-error").textContent = str(exc)
        btn.disabled = False
        btn.textContent = "SUBMIT FEEDBACK ↗"


async def load_admin():
    global admin_state
    page(hero("Store Administration", "Inventory, orders and customer feedback.", "AUTHORIZED TEAM ONLY")+'<section class="section"><div class="container"><div class="loading-screen"><div class="spinner"></div>Checking access...</div></div></section>')
    try:
        admin_state = await api_request("/api/admin/session")
    except Exception:
        page(hero("Store Administration", "Access unavailable")+'<div class="container empty-state">Cannot reach the administrator service.</div>')
        return
    if not admin_state.get("enabled"):
        page(hero("Store Administration", "Secure admin setup is required.")+'<section class="section"><div class="container empty-state"><p>Set <code>MONCLO_ADMIN_PASSWORD</code> and <code>MONCLO_SECRET_KEY</code> on the server to activate administration.</p><a href="#/shop" class="btn">BACK TO STORE</a></div></section>')
    elif not admin_state.get("authenticated"):
        page(hero("Store Administration", "Authorized team members only.")+'<section class="section"><div class="container" style="max-width:570px"><form id="admin-login-form" class="form-section"><h3>Admin login</h3><div class="form-grid"><label class="form-field wide">Username<input class="field" name="username" value="admin" required autocomplete="username"></label><label class="form-field wide">Password<input class="field" type="password" name="password" required autocomplete="current-password"></label></div><p id="admin-error" class="form-error" role="alert"></p><button class="btn" type="submit">SIGN IN ↗</button></form></div></section>')
    else:
        await load_admin_tab(admin_tab)


async def admin_login():
    global admin_state
    form = document.getElementById("admin-login-form")
    try:
        admin_state = await api_request("/api/admin/login", {"username":str(form.elements.namedItem("username").value), "password":str(form.elements.namedItem("password").value)}, "POST")
        await load_admin_tab("products")
    except Exception as exc:
        document.getElementById("admin-error").textContent = str(exc)


def admin_shell(body):
    nav = "".join(f'<button class="admin-tab {"active" if admin_tab==tab else ""}" data-action="admin-tab" data-tab="{tab}">{tab.title()}</button>' for tab in ("products", "orders", "feedback"))
    page(hero("Store Administration", "Keep your collection and orders organized.", "PRIVATE ADMIN AREA")+f'<section class="section"><div class="container"><div class="admin-tabs">{nav}<button class="admin-tab" data-action="admin-logout">Sign out</button></div><div id="admin-panel">{body}</div></div></section>')


async def load_admin_tab(tab):
    global admin_tab, admin_products, editing_id
    admin_tab = tab
    editing_id = None
    try:
        if tab == "products":
            result = await api_request("/api/admin/products")
            admin_products = result["products"]
            rows = "".join(f'<tr><td>#{p["id"]}</td><td>{esc(p["name"])}</td><td>{esc(p["category"])}</td><td>{peso(p["price_cents"])}</td><td>{p["stock"]}</td><td>{"Active" if p["active"] else "Hidden"}</td><td><button class="btn btn-sm btn-outline" data-action="admin-edit" data-id="{p["id"]}">Edit</button> <button class="btn btn-sm btn-outline" data-action="admin-delete" data-id="{p["id"]}">Hide</button></td></tr>' for p in admin_products)
            admin_shell(f'<div class="admin-card"><button class="btn" data-action="admin-new">+ ADD PRODUCT</button><p class="small muted" style="margin-top:13px">Products are hidden rather than permanently deleted to protect order history.</p></div><div id="admin-product-editor"></div><div class="admin-table"><table><thead><tr><th>ID</th><th>Product</th><th>Category</th><th>Price</th><th>Stock</th><th>Visibility</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div>')
        elif tab == "orders":
            result = await api_request("/api/admin/orders")
            rows = ""
            for o in result["orders"]:
                options = option_menu(["Pending", "Confirmed", "Processing", "Shipped", "Delivered"],o["status"])
                items = "; ".join(f'{i["name"]} ({i["size"]}/{i["color"]}) ×{i["quantity"]}' for i in o["items"])
                rows += f'''<tr><td><strong>{esc(o["reference"])}</strong><br>{esc(o["created_at"])}</td><td>{esc(o["customer_name"])}<br>{esc(o["phone"])}</td><td>{esc(o["address"])}, {esc(o["city"])}, {esc(o["province"])} {esc(o["postal_code"])}<br>{esc(o["instructions"])}</td><td>{esc(items)}</td><td>{peso(o["total_cents"])}</td><td><select class="mini-select" id="status-{o["id"]}">{options}</select><button class="btn btn-sm" data-action="admin-status" data-id="{o["id"]}">UPDATE</button></td></tr>'''
            admin_shell('<div class="admin-table"><table><thead><tr><th>Order</th><th>Customer</th><th>Delivery</th><th>Items</th><th>COD Total</th><th>Status</th></tr></thead><tbody>'+rows+'</tbody></table></div>' if rows else '<div class="empty-state">No orders submitted yet.</div>')
        elif tab == "feedback":
            result = await api_request("/api/admin/feedback")
            rows = "".join(f'<tr><td>{esc(f["created_at"])}</td><td>{esc(f["name"])}<br>{esc(f["email"])}</td><td>{esc(f["category"])}</td><td>{esc(f["message"])}</td></tr>' for f in result["feedback"])
            admin_shell('<div class="admin-table"><table><thead><tr><th>Received</th><th>Customer</th><th>Category</th><th>Message</th></tr></thead><tbody>'+rows+'</tbody></table></div>' if rows else '<div class="empty-state">No feedback submissions yet.</div>')
    except Exception as exc:
        toast("Admin load failed: " + str(exc))


def edit_product_admin(product_id):
    global editing_id
    editing_id = product_id
    p = next((x for x in admin_products if x["id"]==product_id), None)
    def value(key, fallback=""):
        return esc(p[key] if p else fallback)
    categories = ["T-Shirts", "Oversized Shirts", "Polo Shirts", "Hoodies", "Other Apparel"]
    selected_cat = p["category"] if p else "T-Shirts"
    opts = option_menu(categories,selected_cat)
    sizes = ", ".join(p["sizes"]) if p else "S, M, L, XL"
    colors = ", ".join(p["colors"]) if p else "Black, White"
    price = f'{p["price_cents"]/100:.2f}' if p else "699.00"
    editor = f'''<div class="admin-card"><h3>{"Edit product #"+str(product_id) if p else "Add a new product"}</h3><form id="admin-product-form"><div class="form-grid"><label class="form-field">Product name<input class="field" name="name" value="{value("name")}" maxlength="100" required></label><label class="form-field">Category<select class="field" name="category">{opts}</select></label><label class="form-field wide">Description<input class="field" name="description" value="{value("description")}" maxlength="500" required></label><label class="form-field">Price (PHP)<input class="field" name="price_pesos" type="number" min="0.01" step="0.01" value="{price}" required></label><label class="form-field">Stock quantity<input class="field" name="stock" type="number" min="0" step="1" value="{value("stock",12)}" required></label><label class="form-field">Sizes (comma separated)<input class="field" name="sizes" value="{esc(sizes)}" required></label><label class="form-field">Colors (comma separated)<input class="field" name="colors" value="{esc(colors)}" required></label><label class="form-field wide">Product image URL<input class="field" name="image_url" id="product-image-url" value="{value("image_url")}" placeholder="https://images... or upload below" required></label><label class="form-field"><span><input type="checkbox" name="featured" {"checked" if p and p["featured"] else ""}> Featured</span></label><label class="form-field"><span><input type="checkbox" name="active" {"checked" if not p or p["active"] else ""}> Visible in store</span></label></div><p id="admin-save-error" class="form-error" role="alert"></p><button class="btn" type="submit">SAVE PRODUCT ↗</button></form><form id="admin-upload-form" style="margin-top:24px;border-top:1px solid #e5e7eb;padding-top:18px"><label class="form-field">Upload JPG, PNG or WEBP image (up to 5 MB)<input class="field" type="file" name="image" id="product-image-file" accept="image/jpeg,image/png,image/webp" required></label><button class="btn btn-outline btn-sm" style="margin-top:12px" type="submit">UPLOAD IMAGE</button></form></div>'''
    document.getElementById("admin-product-editor").innerHTML = editor


async def admin_save_product():
    form = document.getElementById("admin-product-form")
    if not form or not form.checkValidity():
        if form: form.reportValidity()
        return
    names = ("name", "category", "description", "image_url", "price_pesos")
    payload = {k:str(form.elements.namedItem(k).value).strip() for k in names}
    try: payload["stock"] = int(form.elements.namedItem("stock").value)
    except Exception: payload["stock"] = -1
    payload["sizes"] = [x.strip() for x in str(form.elements.namedItem("sizes").value).split(",") if x.strip()]
    payload["colors"] = [x.strip() for x in str(form.elements.namedItem("colors").value).split(",") if x.strip()]
    payload["featured"] = bool(form.elements.namedItem("featured").checked)
    payload["active"] = bool(form.elements.namedItem("active").checked)
    path = "/api/admin/products" + (f"/{editing_id}" if editing_id else "")
    try:
        await api_request(path,payload,"PUT" if editing_id else "POST",admin_state["csrf"])
        toast("Product saved successfully.")
        await load_admin_tab("products")
        await refresh_catalog()
    except Exception as exc:
        document.getElementById("admin-save-error").textContent = str(exc)


async def refresh_catalog():
    global products
    resp = await window.fetch("/api/products")
    if resp.ok: products = (await resp.json()).to_py()["products"]
    update_badge()


async def admin_upload():
    file = document.getElementById("product-image-file").files.item(0)
    if not file: return
    try:
        data = window.FormData.new()
        data.append("image",file)
        opts = window.JSON.parse('{"method":"POST"}')
        opts.body = data
        opts.headers = window.JSON.parse(json.dumps({"X-CSRF-Token":admin_state["csrf"]}))
        resp = await window.fetch("/api/admin/upload",opts)
        result = (await resp.json()).to_py()
        if not resp.ok: raise ValueError(result.get("error","Upload failed."))
        document.getElementById("product-image-url").value = result["image_url"]
        toast("Image uploaded. Save the product to apply it.")
    except Exception as exc:
        toast(str(exc))


async def admin_delete_product(pid):
    if not window.confirm("Hide this product from the public storefront?"): return
    try:
        await api_request(f"/api/admin/products/{pid}",method="DELETE",csrf=admin_state["csrf"])
        await load_admin_tab("products")
        await refresh_catalog()
        toast("Product hidden.")
    except Exception as exc: toast(str(exc))


async def admin_update_status(order_id):
    status = str(document.getElementById(f"status-{order_id}").value)
    try:
        await api_request(f"/api/admin/orders/{order_id}",{"status":status},"PATCH",admin_state["csrf"])
        toast("Order status updated.")
        await load_admin_tab("orders")
    except Exception as exc: toast(str(exc))


async def admin_logout():
    global admin_state
    try:
        await api_request("/api/admin/logout",method="POST",csrf=admin_state["csrf"])
        admin_state = None
        await load_admin()
    except Exception as exc: toast(str(exc))


def render():
    route = get_route()
    if route == "/shop": render_shop()
    elif route == "/cart": render_cart()
    elif route == "/checkout": render_checkout()
    elif route == "/confirmation": render_confirmation()
    elif route == "/support": render_support()
    elif route == "/admin": asyncio.create_task(load_admin())
    else: render_home()


def on_click(event):
    global selected_category, selected_size, selected_price, search_text
    el = event.target.closest("[data-action]")
    if not el: return
    action = el.getAttribute("data-action")
    if action == "category":
        selected_category = el.getAttribute("data-category")
        render_shop()
    elif action in ("add", "buy"):
        add_product(int(el.getAttribute("data-id")), action == "buy")
    elif action in ("cart-plus", "cart-minus", "cart-remove"):
        modify_cart(action, int(el.getAttribute("data-index")))
    elif action == "checkout":
        window.sessionStorage.removeItem(BUY_KEY)
        window.sessionStorage.removeItem(ORDER_KEY)
        window.location.hash = "/checkout"
    elif action == "admin-tab":
        asyncio.create_task(load_admin_tab(str(el.getAttribute("data-tab"))))
    elif action == "admin-edit":
        edit_product_admin(int(el.getAttribute("data-id")))
    elif action == "admin-new":
        edit_product_admin(None)
    elif action == "admin-delete":
        asyncio.create_task(admin_delete_product(int(el.getAttribute("data-id"))))
    elif action == "admin-status":
        asyncio.create_task(admin_update_status(int(el.getAttribute("data-id"))))
    elif action == "admin-logout":
        asyncio.create_task(admin_logout())
    elif action == "clear-filters":
        selected_category, selected_size, selected_price, search_text = "All Products", "All Sizes", "All Prices", ""
        render_shop()


def on_submit(event):
    if event.target.id == "admin-login-form":
        event.preventDefault()
        asyncio.create_task(admin_login())
    elif event.target.id == "admin-product-form":
        event.preventDefault()
        asyncio.create_task(admin_save_product())
    elif event.target.id == "admin-upload-form":
        event.preventDefault()
        asyncio.create_task(admin_upload())
    elif event.target.id == "support-form":
        event.preventDefault()
        asyncio.create_task(submit_feedback())
    elif event.target.id == "order-form":
        event.preventDefault()
        asyncio.create_task(place_order())

def on_input(event):
    global search_text
    if event.target.id == "shop-search":
        search_text = str(event.target.value)
        update_shop_results()


def on_change(event):
    global selected_size, selected_price, selected_sort
    el = event.target
    if el.id == "filter-size": selected_size = str(el.value); update_shop_results()
    elif el.id == "filter-price": selected_price = str(el.value); update_shop_results()
    elif el.id == "shop-sort": selected_sort = str(el.value); update_shop_results()


async def init():
    global products
    try:
        resp = await window.fetch("/api/products")
        if not resp.ok: raise RuntimeError("Product service unavailable")
        products = (await resp.json()).to_py()["products"]
        update_badge()
        try:
            cfg_resp = await window.fetch("/api/config")
            if cfg_resp.ok:
                cfg = (await cfg_resp.json()).to_py()
                if cfg.get("contact_email"):
                    e = document.getElementById("email-link")
                    e.href = "mailto:" + cfg["contact_email"]
                    e.textContent = "Email: " + cfg["contact_email"]
                if cfg.get("instagram_url", "").startswith("https://"):
                    s = document.getElementById("social-link")
                    s.href = cfg["instagram_url"]
                    s.textContent = "Instagram ↗"
                    s.target = "_blank"
        except Exception: pass
        render()
    except Exception:
        document.getElementById("page-content").innerHTML = '<div class="container empty-state"><h2>Our collection is temporarily unavailable.</h2><p>Please refresh the page or try again shortly.</p></div>'


# Keep strong references to proxies so Pyodide never garbage-collects live handlers.
_handlers = [create_proxy(on_click), create_proxy(on_input), create_proxy(on_change), create_proxy(lambda event: render()), create_proxy(on_submit)]
document.addEventListener("click", _handlers[0])
document.addEventListener("input", _handlers[1])
document.addEventListener("change", _handlers[2])
document.addEventListener("submit", _handlers[4])
window.addEventListener("hashchange", _handlers[3])
asyncio.create_task(init())
