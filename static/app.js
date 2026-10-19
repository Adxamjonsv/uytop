"use strict";

const tg = window.Telegram?.WebApp;
const screen = document.getElementById("screen");
const toastNode = document.getElementById("toast");
const state = { page: "home", offset: 0, hasMore: false, filters: {}, draft: { current_step: 1, data: {} }, detailId: null, loading: false };
let districts = ["Yunusobod", "Chilonzor", "Mirobod", "Shayxontohur", "Yakkasaroy", "Mirzo Ulug‘bek", "Sergeli", "Olmazor", "Uchtepa", "Yashnobod", "Bektemir", "Yangihayot"];
let names = { apartment: "Kvartira", household: "Xonadon", house: "Uy", dormitory: "Yotoqxona", rent: "Ijara", sale: "Sotuv", daily: "Kunlik ijara" };
let toastTimer;
const photoCache = new Map();

if (tg) { tg.ready(); tg.expand(); tg.setHeaderColor?.("#f3efe6"); tg.setBackgroundColor?.("#f3efe6"); }

function toast(message) { toastNode.textContent = message; toastNode.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => toastNode.classList.remove("show"), 2800); }
function escapeText(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;"); }
function authHeaders(extra = {}) { return { Authorization: `tma ${tg?.initData || ""}`, ...extra }; }
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: authHeaders(options.headers || {}) });
  let data = {};
  try { data = await response.json(); } catch (_) { /* empty response */ }
  if (!response.ok) throw new Error(data.detail || "So‘rov bajarilmadi. Qayta urinib ko‘ring.");
  return data;
}
function setPage(page) {
  state.page = page; state.offset = 0; state.detailId = null;
  document.querySelectorAll(".bottom-nav button").forEach(button => button.classList.toggle("active", button.dataset.page === page));
  if (page === "home") renderHome();
  else if (page === "search") renderSearch();
  else if (page === "add") openDraft();
  else if (page === "favorites") renderFavorites();
  else renderMyProfile();
}
function skeleton() { screen.innerHTML = '<section class="hero"><div class="skeleton wide"></div></section><div class="skeleton"></div><div class="skeleton"></div>'; }
function fail(error) { screen.innerHTML = `<div class="error-state">${escapeText(error.message)}<div class="spacer"></div><button class="secondary-button" onclick="setPage('home')">Qayta urinish</button></div>`; }

function createListingCard(item) {
  const card = document.createElement("article"); card.className = "card"; card.dataset.id = item.id;
  const photo = document.createElement("div"); photo.className = "card-photo photo-placeholder"; photo.textContent = "⌂";
  if (item.photos?.[0]) loadPhoto(item.photos[0]).then(url => { const img = document.createElement("img"); img.className = "card-photo"; img.alt = item.title; img.src = url; photo.replaceWith(img); }).catch(() => {});
  const body = document.createElement("div"); body.className = "card-body";
  const favorite = document.createElement("button"); favorite.className = "favorite-button"; favorite.textContent = item.is_favorite ? "♥" : "♡"; favorite.setAttribute("aria-label", "Sevimlilarga saqlash"); favorite.onclick = async event => { event.stopPropagation(); try { if (favorite.textContent === "♥") { await api(`/api/favorites/${item.id}`, { method: "DELETE" }); favorite.textContent = "♡"; } else { await api(`/api/favorites/${item.id}`, { method: "PUT" }); favorite.textContent = "♥"; } } catch (error) { toast(error.message); } };
  const title = document.createElement("h3"); title.textContent = item.title;
  const location = document.createElement("p"); location.className = "location"; location.textContent = `⌖ ${item.district}${item.neighborhood ? ` · ${item.neighborhood}` : ""}`;
  const price = document.createElement("p"); price.className = "price"; price.textContent = `${formatPrice(item.price)} ${item.currency}${item.deal_type === "daily" ? "/kun" : item.deal_type === "rent" ? "/oy" : ""}`;
  const facts = document.createElement("div"); facts.className = "facts"; facts.textContent = `${item.rooms ?? "—"} xona · ${item.area_m2 ?? "—"} m²`;
  body.append(favorite, title, location, price, facts); card.append(photo, body); card.onclick = () => showDetail(item.id); return card;
}
function formatPrice(value) { return new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 0 }).format(Number(value)); }
async function loadPhoto(path) {
  if (photoCache.has(path)) return photoCache.get(path);
  const response = await fetch(path, { headers: authHeaders() }); if (!response.ok) throw new Error("Rasm yuklanmadi");
  const url = URL.createObjectURL(await response.blob()); photoCache.set(path, url); return url;
}
function renderCards(items, container) { container.replaceChildren(...items.map(createListingCard)); }

async function renderHome() {
  skeleton();
  try {
    const result = await api("/api/listings?limit=8");
    screen.replaceChildren();
    const hero = document.createElement("section"); hero.className = "hero";
    const eyebrow = document.createElement("div"); eyebrow.className = "eyebrow"; eyebrow.textContent = "UyTop · Toshkent";
    const title = document.createElement("h1"); title.textContent = "Maklersiz uy toping";
    const subtitle = document.createElement("p"); subtitle.textContent = "Egasi bilan to‘g‘ridan-to‘g‘ri bog‘laning.";
    const searchButton = document.createElement("button"); searchButton.className = "searchbar"; searchButton.textContent = "⌕   Tuman yoki uy turini qidiring"; searchButton.onclick = () => setPage("search");
    hero.append(eyebrow, title, subtitle, searchButton);
    const categoryHead = document.createElement("div"); categoryHead.className = "section-head"; categoryHead.innerHTML = "<h2>Uy turini tanlang</h2>";
    const chips = document.createElement("div"); chips.className = "chips";
    [["Barchasi", ""], ["Kvartira", "apartment"], ["Xonadon", "household"], ["Uy", "house"], ["Kunlik", "daily"]].forEach(([label, value], i) => { const button = document.createElement("button"); button.className = `chip${i === 0 ? " selected" : ""}`; button.textContent = label; button.onclick = () => { state.filters = value === "daily" ? { deal_type: "daily" } : value ? { property_type: value } : {}; setPage("search"); }; chips.append(button); });
    const head = document.createElement("div"); head.className = "section-head"; head.innerHTML = `<h2>Tavsiya etilgan e’lonlar</h2><button id="all-listings">Barchasi →</button>`;
    const cards = document.createElement("div"); cards.className = "cards";
    screen.append(hero, categoryHead, chips, head, cards); head.querySelector("button").onclick = () => setPage("search");
    if (!result.items.length) cards.innerHTML = '<div class="empty">Hozircha faol e’lon yo‘q. Keyinroq qayta tekshiring.</div>';
    else renderCards(result.items, cards);
  } catch (error) { fail(error); }
}

function selectOptions(values, selected, placeholder) { return `<option value="">${escapeText(placeholder)}</option>` + values.map(value => `<option value="${escapeText(value)}" ${selected === value ? "selected" : ""}>${escapeText(value)}</option>`).join(""); }
function renderSearch() {
  screen.innerHTML = `<h1 class="page-title">Uy qidirish</h1><section class="filter-panel"><div class="chips" id="deal-chips"></div><label class="field">Tuman<select id="district">${selectOptions(districts, state.filters.district, "Barcha tumanlar")}</select></label><label class="field">Uy turi<select id="property"><option value="">Barcha uy turlari</option>${Object.entries(names).filter(([key])=>["apartment","household","house","dormitory"].includes(key)).map(([key,label])=>`<option value="${escapeText(key)}">${escapeText(label)}</option>`).join("")}</select></label><div class="row-fields"><label class="field">Narxdan<input id="min-price" type="number" min="0" placeholder="0"></label><label class="field">Narxgacha<input id="max-price" type="number" min="0" placeholder="Istalgan"></label></div><label class="field">Xona soni<select id="rooms">${selectOptions(["1","2","3","4","5"], state.filters.rooms, "Barchasi")}</select></label><label class="field">Saralash<select id="sort"><option value="newest">Eng yangi</option><option value="price_asc">Arzonidan boshlab</option><option value="price_desc">Qimmatidan boshlab</option></select></label><button class="primary-button full" id="apply-filter">Natijalarni ko‘rsatish</button><button class="secondary-button full" id="save-search">Qidiruvni saqlash</button></section><div class="section-head"><h2>Faol e’lonlar</h2><span class="muted" id="result-count"></span></div><div class="cards" id="results"></div><button class="secondary-button full" id="load-more" hidden>Yana e’lonlar</button>`;
  const deals = document.getElementById("deal-chips");
  [["Ijara", "rent"], ["Sotuv", "sale"], ["Kunlik", "daily"]].forEach(([label, value]) => { const button = document.createElement("button"); button.className = `chip${state.filters.deal_type === value ? " selected" : ""}`; button.textContent = label; button.onclick = () => { state.filters.deal_type = state.filters.deal_type === value ? undefined : value; renderSearch(); }; deals.append(button); });
  const extras=document.createElement("div"); extras.className="filter-extras";
  const areaLabel=document.createElement("div"); areaLabel.className="field"; areaLabel.textContent="Maydon (m²)";
  const areaRow=document.createElement("div"); areaRow.className="row-fields";
  const areaMin=document.createElement("input"); areaMin.id="min-area"; areaMin.type="number"; areaMin.min="1"; areaMin.placeholder="Dan"; areaMin.value=state.filters.min_area||"";
  const areaMax=document.createElement("input"); areaMax.id="max-area"; areaMax.type="number"; areaMax.min="1"; areaMax.placeholder="Gacha"; areaMax.value=state.filters.max_area||"";
  areaRow.append(areaMin,areaMax); areaLabel.append(areaRow); extras.append(areaLabel);
  const amenityLabel=document.createElement("div"); amenityLabel.className="field"; amenityLabel.textContent="Qulayliklar";
  const amenityRow=document.createElement("div"); amenityRow.className="amenity-filters";
  ["Mebel","Konditsioner","Wi-Fi","Avtoturargoh","Faqat oilaga","Hayvonlarga ruxsat"].forEach(value=>{const label=document.createElement("label");label.className="inline amenity-option";const checkbox=document.createElement("input");checkbox.type="checkbox";checkbox.value=value;checkbox.checked=(state.filters.amenity||[]).includes(value);label.append(checkbox,document.createTextNode(value));amenityRow.append(label);});
  amenityLabel.append(amenityRow); extras.append(amenityLabel); document.getElementById("rooms").closest(".field").after(extras);
  document.getElementById("district").value = state.filters.district || ""; document.getElementById("property").value = state.filters.property_type || ""; document.getElementById("rooms").value = state.filters.rooms || "";
  document.getElementById("sort").value=state.filters.sort||"newest";
  document.getElementById("apply-filter").onclick = () => { const district = document.getElementById("district").value; const property_type = document.getElementById("property").value; const min = document.getElementById("min-price").value; const max = document.getElementById("max-price").value; const rooms = document.getElementById("rooms").value; const sort=document.getElementById("sort").value; const min_area=document.getElementById("min-area").value; const max_area=document.getElementById("max-area").value; const amenity=[...amenityRow.querySelectorAll("input:checked")].map(input=>input.value); Object.assign(state.filters, { district: district || undefined, property_type: property_type || undefined, min_price: min || undefined, max_price: max || undefined, rooms: rooms || undefined, sort, min_area:min_area||undefined,max_area:max_area||undefined,amenity }); state.offset = 0; loadResults(true); };
  document.getElementById("save-search").onclick=async()=>{const name=window.prompt("Saqlangan qidiruv nomi:",state.filters.district||"Uy qidiruvi");if(!name)return;try{await api("/api/saved-searches",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,filters:state.filters})});toast("Qidiruv saqlandi.");}catch(error){toast(error.message);}};
  document.getElementById("load-more").onclick = () => loadResults(false);
  loadResults(true);
}
async function loadResults(reset) {
  const cards = document.getElementById("results"); if (!cards) return;
  if (reset) { state.offset = 0; cards.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>'; }
  const params = new URLSearchParams({ offset: String(state.offset), limit: "20" });
  Object.entries(state.filters).forEach(([key, value]) => { if (Array.isArray(value)) value.forEach(item=>params.append(key,item)); else if (value !== undefined && value !== "") params.set(key, value); });
  try { const result = await api(`/api/listings?${params}`); if (reset) cards.replaceChildren(); if (result.items.length) cards.append(...result.items.map(createListingCard)); else if (reset) cards.innerHTML = '<div class="empty">Bu filtrlar bo‘yicha e’lon topilmadi.</div>'; state.offset = result.next_offset; state.hasMore = result.has_more; document.getElementById("result-count").textContent = result.items.length ? `${result.items.length} ta ko‘rsatildi` : ""; document.getElementById("load-more").hidden = !state.hasMore; } catch (error) { cards.innerHTML = `<div class="error-state">${escapeText(error.message)}</div>`; }
}

async function showDetail(id) {
  state.detailId = id; skeleton();
  try {
    const item = await api(`/api/listings/${id}`); screen.replaceChildren();
    const panel = document.createElement("article"); panel.className = "detail-panel";
    if (item.photos?.length) {
      const gallery = document.createElement("div");
      const image = document.createElement("img"); image.className = "detail-photo"; image.alt = item.title; image.src = await loadPhoto(item.photos[0]).catch(() => "");
      gallery.append(image);
      if (item.photos.length > 1) {
        let index = 0; const controls = document.createElement("div"); controls.className = "gallery-controls";
        const previous = document.createElement("button"); previous.className = "secondary-button"; previous.textContent = "‹";
        const counter = document.createElement("span"); counter.textContent = `1/${item.photos.length}`;
        const next = document.createElement("button"); next.className = "secondary-button"; next.textContent = "›";
        const change = async step => { index = (index + step + item.photos.length) % item.photos.length; counter.textContent = `${index + 1}/${item.photos.length}`; image.src = await loadPhoto(item.photos[index]).catch(() => ""); };
        previous.onclick = () => change(-1); next.onclick = () => change(1); controls.append(previous, counter, next); gallery.append(controls);
      }
      panel.append(gallery);
    }
    const back = document.createElement("button"); back.className = "text-button"; back.textContent = "← Natijalarga qaytish"; back.onclick = () => state.page === "favorites" ? renderFavorites() : renderSearch(); panel.append(back);
    const heading = document.createElement("h1"); heading.className = "detail-title"; heading.textContent = item.title; panel.append(heading);
    const location = document.createElement("p"); location.className = "muted"; location.textContent = `⌖ ${item.district}${item.neighborhood ? ` · ${item.neighborhood}` : ""}`; panel.append(location);
    const price = document.createElement("p"); price.className = "detail-price"; price.textContent = `${formatPrice(item.price)} ${item.currency}${item.deal_type === "rent" ? "/oy" : item.deal_type === "daily" ? "/kun" : ""}`; panel.append(price);
    const facts = document.createElement("p"); facts.textContent = `${names[item.deal_type]} · ${names[item.property_type]} · ${item.rooms ?? "—"} xona · ${item.area_m2 ?? "—"} m² · ${item.floor ?? "—"}-qavat`; panel.append(facts);
    const map = document.createElement("a"); map.className="text-button"; map.textContent="Xaritada ko‘rish"; map.href=`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent([item.neighborhood,item.district,"Toshkent"].filter(Boolean).join(", "))}`; map.target="_blank"; map.rel="noopener noreferrer"; panel.append(map);
    const desc = document.createElement("p"); desc.textContent = item.description; panel.append(desc);
    const amenities = document.createElement("div"); amenities.className = "amenities"; (item.amenities || []).forEach(value => { const chip = document.createElement("span"); chip.textContent = value; amenities.append(chip); }); panel.append(amenities);
    const actions = document.createElement("div"); actions.className = "contact-actions";
    const save = document.createElement("button"); save.className = "secondary-button"; save.textContent = "♡ Sevimlilarga saqlash"; save.onclick = async () => { try { await api(`/api/favorites/${id}`, { method: "PUT" }); toast("Sevimlilarga saqlandi."); } catch (error) { toast(error.message); } };
    const contact = document.createElement("button"); contact.className = "primary-button"; contact.textContent = "Bog‘lanish"; contact.onclick = async () => { try { const result = await api(`/api/listings/${id}/contact`, { method: "POST" }); if (result.telegram_url) { if (tg?.openTelegramLink) tg.openTelegramLink(result.telegram_url); else window.open(result.telegram_url, "_blank"); } else toast("Uy egasining Telegram username’i yo‘q."); if (result.phone_warning) { const okay = window.confirm(`${result.phone_warning}\nRaqamni ko‘rishni xohlaysizmi?`); if (okay) { const data = await api(`/api/listings/${id}/contact?confirm_phone=true`, { method: "POST" }); if (data.phone) window.alert(`Uy egasi telefoni: ${data.phone}`); else toast(data.phone_warning); } } } catch (error) { toast(error.message); } };
    const report = document.createElement("button"); report.className = "text-button"; report.textContent = "Shikoyat yuborish"; report.onclick = async () => { const reason = window.prompt("Shikoyat sababini yozing:"); if (reason) { try { await api(`/api/listings/${id}/reports`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reason }) }); toast("Shikoyat yuborildi."); } catch (error) { toast(error.message); } } };
    actions.append(save, contact, report); panel.append(actions); screen.append(panel);
  } catch (error) { fail(error); }
}

async function renderFavorites() { skeleton(); try { const result = await api("/api/favorites"); screen.innerHTML = '<h1 class="page-title">Sevimli e’lonlar</h1><div class="cards" id="favorite-cards"></div>'; if (!result.items.length) document.getElementById("favorite-cards").innerHTML = '<div class="empty">Saqlangan e’lon yo‘q.</div>'; else renderCards(result.items, document.getElementById("favorite-cards")); } catch (error) { fail(error); } }
async function renderMyProfile() {
  skeleton();
  try {
    const [user, listings, viewed, saved] = await Promise.all([api("/api/me"), api("/api/my/listings"), api("/api/my/viewed"), api("/api/saved-searches")]);
    screen.innerHTML = `<h1 class="page-title">Profil</h1><section class="profile-card"><div class="inline"><div class="avatar">${escapeText((user.name || "U").slice(0,1))}</div><div><strong>${escapeText(user.name)}</strong><div class="muted">${user.username ? "@" + escapeText(user.username) : "UyTop foydalanuvchisi"}</div></div></div><label class="inline"><input id="notifications-enabled" type="checkbox" ${user.notifications_enabled ? "checked" : ""}> Bildirishnomalarni olish</label></section><div class="section-head"><h2>Mening e’lonlarim (${listings.items.length})</h2></div><div id="my-listings"></div><section class="profile-card"><h2>Saqlangan qidiruvlar (${saved.items.length})</h2><div id="saved-searches"></div></section><div class="section-head"><h2>Ko‘rilgan e’lonlar</h2></div><div class="cards" id="viewed-listings"></div><section class="profile-card"><h2>Yordam</h2><p class="muted">E’lon bo‘yicha savol yoki shikoyat uchun botdagi /help buyrug‘idan foydalaning.</p><button class="secondary-button" id="help">Yordam</button></section>`;
    document.getElementById("notifications-enabled").onchange = async event => { try { await api("/api/me/notifications", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ notifications_enabled: event.target.checked }) }); toast("Sozlama saqlandi."); } catch (error) { toast(error.message); } };
    const mine = document.getElementById("my-listings");
    if (!listings.items.length) mine.innerHTML = '<div class="empty">Hozircha e’lon joylashtirmagansiz.</div>';
    for (const item of listings.items) {
      const row = document.createElement("article"); row.className = "profile-card";
      const title = document.createElement("h3"); title.textContent = item.title;
      const meta = document.createElement("p"); meta.className = "muted"; meta.textContent = `${item.district} · ${formatPrice(item.price)} ${item.currency} · ${({draft:"Qoralama",pending:"Tekshiruvda",active:"Faol",rejected:"Rad etilgan",rented:"Band",archived:"Arxiv"})[item.status] || item.status}`;
      const actions = document.createElement("div"); actions.className = "button-row";
      if (!["archived","rented"].includes(item.status)) { const edit = document.createElement("button"); edit.className = "secondary-button"; edit.textContent = "Tahrirlash"; edit.onclick = () => openEditListing(item); actions.append(edit); }
      if (item.status === "active") { const rented = document.createElement("button"); rented.className = "secondary-button"; rented.textContent = "Band"; rented.onclick = async () => { try { await api(`/api/listings/${item.id}/rented`, { method: "POST" }); toast("E’lon band deb belgilandi."); renderMyProfile(); } catch (error) { toast(error.message); } }; actions.append(rented); }
      if (!["archived","rented"].includes(item.status)) { const archive = document.createElement("button"); archive.className = "text-button"; archive.textContent = "Arxivlash"; archive.onclick = async () => { try { await api(`/api/listings/${item.id}`, { method: "DELETE" }); toast("E’lon arxivlandi."); renderMyProfile(); } catch (error) { toast(error.message); } }; actions.append(archive); }
      row.append(title, meta, actions); mine.append(row);
    }
    const savedBox = document.getElementById("saved-searches");
    if (!saved.items.length) savedBox.innerHTML = '<p class="muted">Qidiruv sahifasida filtrlarni saqlashingiz mumkin.</p>';
    for (const item of saved.items) { const line=document.createElement("div"); line.className="row"; const name=document.createElement("span"); name.textContent=item.name; const remove=document.createElement("button"); remove.className="text-button"; remove.textContent="O‘chirish"; remove.onclick=async()=>{await api(`/api/saved-searches/${item.id}`,{method:"DELETE"});renderMyProfile();}; line.append(name,remove); savedBox.append(line); }
    const viewedBox=document.getElementById("viewed-listings"); if(viewed.items.length) renderCards(viewed.items,viewedBox); else viewedBox.innerHTML='<div class="empty">Ko‘rilgan e’lonlar yo‘q.</div>';
    document.getElementById("help").onclick=()=>toast("Botdagi /help buyrug‘idan foydalaning.");
  } catch (error) { fail(error); }
}
function openEditListing(item) {
  screen.innerHTML = `<h1 class="page-title">E’lonni tahrirlash</h1><section class="form-panel">${field("Sarlavha","title",item.title)}<label class="field">Narx<input id="edit-price" type="number" min="1" value="${escapeText(item.price)}"></label><label class="field">Tavsif<textarea id="edit-description">${escapeText(item.description)}</textarea></label><label class="inline"><input id="edit-phone-consent" type="checkbox" ${item.phone_consent?"checked":""}> Telefonni ko‘rsatishga roziman</label><label class="field">Telefon raqami<input id="edit-phone" value="${escapeText(item.contact_phone)}"></label><div class="button-row"><button id="edit-cancel" class="secondary-button">Bekor qilish</button><button id="edit-save" class="primary-button">Saqlash</button></div></section>`;
  document.getElementById("edit-cancel").onclick=renderMyProfile;
  document.getElementById("edit-save").onclick=async()=>{try{const response=await api(`/api/listings/${item.id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:document.querySelector('[data-key="title"]').value,price:document.getElementById("edit-price").value,description:document.getElementById("edit-description").value,phone_consent:document.getElementById("edit-phone-consent").checked,contact_phone:document.getElementById("edit-phone").value||null})});toast(response.message);renderMyProfile();}catch(error){toast(error.message);}};
}

async function openDraft() {
  try { state.draft = await api("/api/draft"); state.draft.data ||= {}; renderDraftStep(); }
  catch (error) { fail(error); }
}
function field(label, key, value, type = "text", placeholder = "") { return `<label class="field">${label}<input data-key="${key}" type="${type}" value="${escapeText(value)}" placeholder="${placeholder}" ${type === "number" ? 'min="0"' : ""}></label>`; }
function renderDraftStep() {
  const step = state.draft.current_step; const d = state.draft.data;
  let form = "";
  if (step === 1) form = `<label class="field">Bitim turi<select data-key="deal_type">${Object.entries(names).filter(([key])=>["rent","sale","daily"].includes(key)).map(([key,label])=>`<option value="${escapeText(key)}" ${d.deal_type===key?"selected":""}>${escapeText(label)}</option>`).join("")}</select></label><label class="field">Uy turi<select data-key="property_type">${Object.entries(names).filter(([key])=>["apartment","household","house","dormitory"].includes(key)).map(([key,label])=>`<option value="${escapeText(key)}" ${d.property_type===key?"selected":""}>${escapeText(label)}</option>`).join("")}</select></label>`;
  if (step === 2) form = `<label class="field">Tuman<select data-key="district">${selectOptions(districts,d.district,"Tumanni tanlang")}</select></label>${field("Mahalla","neighborhood",d.neighborhood)}${field("Manzil (ixtiyoriy)","address",d.address)}`;
  if (step === 3) form = `<div class="row-fields">${field("Narx","price",d.price,"number")}<label class="field">Valyuta<select data-key="currency"><option value="UZS">UZS — so‘m</option><option value="USD">USD — dollar</option></select></label></div><div class="row-fields">${field("Xona soni","rooms",d.rooms,"number")}${field("Maydon (m²)","area_m2",d.area_m2,"number")}</div><div class="row-fields">${field("Qavat","floor",d.floor,"number")}${field("Qavatlar soni","total_floors",d.total_floors,"number")}</div>`;
  if (step === 4) form = `${field("E’lon sarlavhasi","title",d.title)}<label class="field">Tavsif<textarea data-key="description" maxlength="5000">${escapeText(d.description)}</textarea></label><label class="field">Qulayliklar (vergul bilan)<input data-key="amenities" value="${escapeText((d.amenities||[]).join(", "))}" placeholder="Mebel, Wi-Fi, konditsioner"></label>`;
  if (step === 5) form = `<label class="field">Rasmlar (12 tagacha)<input id="photo-files" type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple><span class="step-note">Har biri 8 MB gacha. Rasmlar Telegram’da saqlanadi.</span></label><p class="muted" id="photo-count">Saqlangan rasmlar: ${(d.photo_file_ids||[]).length}</p><label class="field">Aloqa usuli<select data-key="contact_method"><option value="telegram">Telegram</option><option value="phone">Telefon</option><option value="both">Ikkalasi</option></select></label><label class="field">Telefon raqami<input data-key="contact_phone" value="${escapeText(d.contact_phone)}" placeholder="+998..."></label><label class="inline"><input data-key="phone_consent" type="checkbox" ${d.phone_consent?"checked":""}> Telefon raqamimni ko‘rsatishga roziman</label>`;
  if (step === 6) form = `<h2>Tekshirish</h2><p><strong>${escapeText(d.title)}</strong></p><p>${escapeText(d.district)} · ${escapeText(d.rooms)} xona · ${escapeText(d.area_m2)} m²</p><p class="detail-price">${escapeText(d.price)} ${escapeText(d.currency)}</p><p>${escapeText(d.description)}</p><p class="muted">Rasmlar: ${(d.photo_file_ids||[]).length}. E’lon moderatsiyadan keyin qidiruvda ko‘rinadi.</p>`;
  screen.innerHTML = `<h1 class="page-title">E’lon joylashtirish</h1><section class="form-panel"><div class="step-note">${step < 6 ? `Bosqich ${step}/5` : "Yakuniy ko‘rib chiqish"}</div><div class="progress"><span style="width:${Math.min(100,step/5*100)}%"></span></div>${form}<div class="button-row">${step>1?'<button class="secondary-button" id="back-step">Orqaga</button>':""}<button class="primary-button" id="next-step">${step<6?"Keyingisi →":"Moderatsiyaga yuborish"}</button></div></section>`;
  if (step === 2) document.querySelector('[data-key="district"]').value = d.district || "";
  if (step === 3) document.querySelector('[data-key="currency"]').value=d.currency||"UZS";
  if (step === 5) { document.querySelector('[data-key="contact_method"]').value=d.contact_method||"telegram"; document.getElementById("photo-files").onchange = uploadPhotos; }
  document.getElementById("back-step")?.addEventListener("click", () => moveDraft(-1));
  document.getElementById("next-step").addEventListener("click", step === 6 ? submitMiniListing : () => moveDraft(1));
}
async function uploadPhotos(event) {
  const input = event.target; const files = [...input.files].slice(0, Math.max(0,12-(state.draft.data.photo_file_ids||[]).length));
  for (const file of files) { if (file.size > 8*1024*1024) { toast(`${file.name}: 8 MB dan katta.`); continue; } const body = new FormData(); body.append("photo",file); try { const result = await api("/api/uploads/photos",{method:"POST",body}); state.draft.data.photo_file_ids ||= []; state.draft.data.photo_file_ids.push(result.file_id); toast("Rasm Telegram’da saqlandi."); } catch(error) { toast(error.message); } }
  document.getElementById("photo-count").textContent = `Saqlangan rasmlar: ${(state.draft.data.photo_file_ids||[]).length}`; input.value=""; await saveDraft();
}
async function moveDraft(direction) {
  document.querySelectorAll("[data-key]").forEach(node => { const key=node.dataset.key; if (node.type==="checkbox") state.draft.data[key]=node.checked; else if (node.tagName==="SELECT" || node.tagName==="INPUT" || node.tagName==="TEXTAREA") state.draft.data[key]=node.value; });
  if (state.draft.current_step===4) state.draft.data.amenities=(state.draft.data.amenities||"").split(",").map(x=>x.trim()).filter(Boolean).slice(0,20);
  if (state.draft.current_step===1 && (!state.draft.data.deal_type || !state.draft.data.property_type)) return toast("Bitim va uy turini tanlang.");
  if (state.draft.current_step===2 && !state.draft.data.district) return toast("Tumanni tanlang.");
  if (state.draft.current_step===3 && (!state.draft.data.price || Number(state.draft.data.price)<=0)) return toast("Narxni to‘g‘ri kiriting.");
  if (state.draft.current_step===4 && (!state.draft.data.title || !state.draft.data.description)) return toast("Sarlavha va tavsifni to‘ldiring.");
  if (state.draft.current_step===5 && state.draft.data.contact_phone && !state.draft.data.phone_consent) return toast("Telefonni saqlash uchun rozilikni belgilang.");
  state.draft.current_step=Math.max(1,Math.min(6,state.draft.current_step+direction)); await saveDraft(); renderDraftStep();
}
async function saveDraft() { try { await api("/api/draft",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(state.draft)}); } catch(error) { toast(error.message); } }
async function submitMiniListing() {
  const d=state.draft.data;
  const payload={...d,price:Number(d.price),rooms:d.rooms?Number(d.rooms):null,area_m2:d.area_m2?Number(d.area_m2):null,floor:d.floor?Number(d.floor):null,total_floors:d.total_floors?Number(d.total_floors):null,currency:d.currency||"UZS",phone_consent:Boolean(d.phone_consent),photo_file_ids:d.photo_file_ids||[],amenities:d.amenities||[]};
  try { const result=await api("/api/listings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); await api("/api/draft",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({current_step:1,data:{}})}); toast(result.message); state.page="profile"; renderMyProfile(); }
  catch(error) { toast(error.message); }
}

document.querySelectorAll(".bottom-nav button").forEach(button=>button.addEventListener("click",()=>setPage(button.dataset.page)));
document.getElementById("profile-shortcut").addEventListener("click",()=>setPage("profile"));
document.getElementById("language-switch").addEventListener("click",async()=>{
  const selected=window.UyTopLang.toggle();
  if(tg?.initData){try{await api("/api/me/language?language_code="+selected,{method:"PUT"});}catch(error){toast(error.message);}}
});
if (!tg?.initData) { screen.innerHTML='<section class="hero"><h1>UyTop’ga xush kelibsiz</h1><p>Bu Mini App’ni Telegram ichidagi bot tugmasidan oching.</p><button class="searchbar" onclick="window.location.href=\\'https://t.me/Boshpanagobot\\'">Telegram’ga o‘tish</button></section>'; }
else api("/api/me").then(user=>{if(user.language_code)window.UyTopLang.set(user.language_code);return api("/api/catalogs");}).then(catalogs=>{districts=catalogs.districts||districts;names={...names,...Object.fromEntries((catalogs.property_types||[]).map(item=>[item.code,item.label]))};renderHome();}).catch(fail);
