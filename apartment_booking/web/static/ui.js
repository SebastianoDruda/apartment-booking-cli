"use strict";

(() => {
  const state = {
    role: "booker",
    activeView: "search-view",
    apartments: [],
    bookings: [],
    availabilityResults: [],
    lastSearch: {
      start_date: "2026-11-10",
      end_date: "2026-11-15",
      num_people: 2,
    },
    directoryMode: "table",
    instantBookTarget: null,
    changeBookingTarget: null,
    cancelBookingTarget: null,
    priceUpdateTarget: null,
    deleteApartmentTarget: null,
  };

  const VIEW_TITLES = {
    "search-view": "Search Availability & Instant Book",
    "bookings-view": "Create & Manage Bookings",
    "directory-view": "Apartments Directory",
    "inventory-view": "Apartments Inventory & Pricing",
    "overview-view": "Global Bookings Overview",
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function formatMoney(amount) {
    const num = Number(amount);
    if (!Number.isFinite(num)) {
      return "€0.00";
    }
    return `€${num.toFixed(2)}`;
  }

  function parseFlexibleDate(value) {
    if (!value || typeof value !== "string") {
      return null;
    }
    const trimmed = value.trim();
    const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
    if (isoMatch) {
      const year = Number(isoMatch[1]);
      const month = Number(isoMatch[2]);
      const day = Number(isoMatch[3]);
      return Date.UTC(year, month - 1, day);
    }
    const euMatch = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(trimmed);
    if (euMatch) {
      const day = Number(euMatch[1]);
      const month = Number(euMatch[2]);
      const year = Number(euMatch[3]);
      return Date.UTC(year, month - 1, day);
    }
    return null;
  }

  function calculateNights(startStr, endStr) {
    const startUtc = parseFlexibleDate(startStr);
    const endUtc = parseFlexibleDate(endStr);
    if (startUtc === null || endUtc === null || endUtc <= startUtc) {
      return 1;
    }
    return Math.max(1, Math.round((endUtc - startUtc) / (1000 * 60 * 60 * 24)));
  }

  function updateTelemetry(method, endpoint, status, durationMs) {
    byId("telemetry-method").textContent = method;
    byId("telemetry-endpoint").textContent = endpoint;
    byId("telemetry-status").textContent = `${status} • ${Math.round(durationMs)}ms`;
  }

  function showBanner(kind, statusCode, title, message) {
    const banner = byId("status-banner");
    banner.className = "status-banner";
    if (kind === "error") {
      banner.classList.add("error");
    } else if (kind === "warning") {
      banner.classList.add("warning");
    }
    byId("status-banner-code").textContent = statusCode;
    byId("status-banner-title").textContent = title;
    byId("status-banner-message").textContent = message;
    banner.hidden = false;
  }

  function hideBanner() {
    byId("status-banner").hidden = true;
  }

  async function apiRequest(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = { Accept: "application/json" };
    let body;
    if (options.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.json);
    }
    const started = performance.now();
    const response = await fetch(path, { method, headers, body });
    const elapsed = performance.now() - started;
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    updateTelemetry(method, path, response.status, elapsed);
    return { ok: response.ok, status: response.status, payload };
  }

  function showApiError(status, payload, fallbackTitle = "Request Failed") {
    const errMsg =
      payload && payload.error && payload.error.message
        ? payload.error.message
        : `HTTP ${status} error occurred.`;
    const errCode =
      payload && payload.error && payload.error.code
        ? payload.error.code
        : "error";
    const kind = status === 409 || status === 404 || status === 503 ? "warning" : "error";
    showBanner(kind, `${status} ${errCode.toUpperCase()}`, fallbackTitle, errMsg);
  }

  async function checkHealth(showToast = false) {
    const badge = byId("health-badge");
    const text = byId("health-text");
    try {
      const res = await apiRequest("/api/health");
      if (res.ok && res.payload && res.payload.data && res.payload.data.status === "ok") {
        badge.classList.remove("unhealthy");
        badge.classList.add("healthy");
        text.textContent = "System Healthy • SQLite OK";
        if (showToast) {
          showBanner("success", "200 OK", "Health Check Passed", "SQLite database and HTTP server are healthy.");
        }
      } else {
        badge.classList.remove("healthy");
        badge.classList.add("unhealthy");
        text.textContent = `Degraded (${res.status})`;
        if (showToast) {
          showApiError(res.status, res.payload, "Health Check Failed");
        }
      }
    } catch {
      badge.classList.remove("healthy");
      badge.classList.add("unhealthy");
      text.textContent = "Server Unreachable";
    }
  }

  function switchView(viewId) {
    state.activeView = viewId;
    document.querySelectorAll(".view-section").forEach((section) => {
      const isMatch = section.id === viewId;
      section.hidden = !isMatch;
      section.classList.toggle("active", isMatch);
    });
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.view === viewId);
    });
    byId("active-view-title").textContent = VIEW_TITLES[viewId] || "Console";
  }

  function switchRole(role, switchDefaultTab = true) {
    state.role = role;
    const isBooker = role === "booker";
    byId("role-booker-btn").classList.toggle("active", isBooker);
    byId("role-booker-btn").setAttribute("aria-selected", String(isBooker));
    byId("role-manager-btn").classList.toggle("active", !isBooker);
    byId("role-manager-btn").setAttribute("aria-selected", String(!isBooker));
    byId("active-role-badge").textContent = isBooker
      ? "Role 1: Apartment Booker"
      : "Role 2: System Manager";
    if (switchDefaultTab) {
      switchView(isBooker ? "search-view" : "inventory-view");
    }
  }

  // RENDERING HELPERS
  function populateApartmentSelects() {
    const bookingSelect = byId("booking-apartment-select");
    const currentVal = bookingSelect.value;
    bookingSelect.replaceChildren();

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent =
      state.apartments.length > 0
        ? "Select an apartment…"
        : "No apartments registered yet";
    bookingSelect.appendChild(placeholder);

    state.apartments.forEach((apt) => {
      const opt = document.createElement("option");
      opt.value = apt.name;
      opt.dataset.rate = String(apt.price_per_night);
      opt.dataset.max = String(apt.max_people);
      opt.textContent = `${apt.name} (Max ${apt.max_people} • ${formatMoney(apt.price_per_night)}/night)`;
      bookingSelect.appendChild(opt);
    });

    if (currentVal && state.apartments.some((a) => a.name === currentVal)) {
      bookingSelect.value = currentVal;
    } else if (state.apartments.length > 0) {
      bookingSelect.value = state.apartments[0].name;
    }

    const overviewSelect = byId("overview-apartment-filter");
    const currentFilter = overviewSelect.value;
    overviewSelect.replaceChildren();
    const allOpt = document.createElement("option");
    allOpt.value = "";
    allOpt.textContent = "All Apartments";
    overviewSelect.appendChild(allOpt);
    state.apartments.forEach((apt) => {
      const opt = document.createElement("option");
      opt.value = apt.name;
      opt.textContent = apt.name;
      overviewSelect.appendChild(opt);
    });
    if (currentFilter && state.apartments.some((a) => a.name === currentFilter)) {
      overviewSelect.value = currentFilter;
    }

    updateBookingCreatorPreview();
  }

  function updateBookingCreatorPreview() {
    const select = byId("booking-apartment-select");
    const selectedName = select.value;
    const apt = state.apartments.find((a) => a.name === selectedName);
    const startVal = byId("booking-start-date").value;
    const endVal = byId("booking-end-date").value;
    const guestsVal = Number(byId("booking-num-people").value) || 1;
    const nights = calculateNights(startVal, endVal);

    byId("calc-nights").textContent = `${nights} night${nights === 1 ? "" : "s"}`;

    if (!apt) {
      byId("booking-capacity-hint").textContent =
        "Select an apartment to view guest capacity and nightly rate.";
      byId("calc-rate").textContent = "€0.00 / night";
      byId("calc-total").textContent = "€0.00 EUR";
      byId("calc-formula").textContent = "Select an apartment to calculate total.";
      return;
    }

    const rate = Number(apt.price_per_night);
    const total = nights * rate;
    byId("calc-rate").textContent = `${formatMoney(rate)} / night`;
    byId("calc-total").textContent = `${formatMoney(total)} EUR`;
    byId("calc-formula").textContent = `Calculated: ${nights} night${nights === 1 ? "" : "s"} × ${formatMoney(rate)} = ${formatMoney(total)} EUR total`;

    const hint = byId("booking-capacity-hint");
    if (guestsVal > apt.max_people) {
      hint.textContent = `Exceeds capacity! ${apt.name} allows max ${apt.max_people} people.`;
    } else {
      hint.textContent = `Selected apartment capacity: max ${apt.max_people} people (${formatMoney(rate)}/night).`;
    }
  }

  function renderAvailabilityResults() {
    const container = byId("availability-results");
    container.replaceChildren();
    const list = state.availabilityResults;
    byId("avail-count-badge").textContent = `${list.length} Available`;
    byId("avail-summary-text").textContent =
      `Showing available units for ${state.lastSearch.start_date} → ${state.lastSearch.end_date} (${state.lastSearch.num_people} guest${state.lastSearch.num_people === 1 ? "" : "s"}).`;

    if (list.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent =
        "No available apartments match the selected dates and guest count. Try adjusting your dates or adding an apartment in System Manager.";
      container.appendChild(empty);
      return;
    }

    list.forEach((apt) => {
      const card = document.createElement("article");
      card.className = "apt-card";
      card.dataset.apartmentCard = apt.name;

      const top = document.createElement("div");
      const header = document.createElement("div");
      header.className = "apt-card-header";

      const titleGroup = document.createElement("div");
      const title = document.createElement("h4");
      title.className = "apt-card-title";
      title.textContent = apt.name;
      const addr = document.createElement("p");
      addr.className = "apt-card-address";
      addr.textContent = apt.address;
      titleGroup.append(title, addr);

      const cap = document.createElement("span");
      cap.className = "capacity-pill";
      cap.textContent = `Max ${apt.max_people}`;
      header.append(titleGroup, cap);

      const pricing = document.createElement("div");
      pricing.className = "apt-card-pricing mt-lg";
      const nightSpan = document.createElement("span");
      nightSpan.className = "apt-price-night";
      nightSpan.textContent = `${formatMoney(apt.price_per_night)} / night • ${apt.nights}n`;
      const totalSpan = document.createElement("span");
      totalSpan.className = "apt-price-total";
      totalSpan.textContent = `${formatMoney(apt.total_price)} EUR`;
      pricing.append(nightSpan, totalSpan);

      top.append(header, pricing);

      const bookBtn = document.createElement("button");
      bookBtn.type = "button";
      bookBtn.className = "btn btn-secondary btn-block";
      bookBtn.dataset.bookApartment = apt.name;
      bookBtn.textContent = `Book This Apartment (${formatMoney(apt.total_price)})`;
      bookBtn.addEventListener("click", () => openInstantBookModal(apt));

      card.append(top, bookBtn);
      container.appendChild(card);
    });
  }

  function renderBookingsTable() {
    const tbody = byId("bookings-table-body");
    tbody.replaceChildren();
    byId("bookings-count-badge").textContent =
      `${state.bookings.length} Active Booking${state.bookings.length === 1 ? "" : "s"}`;

    if (state.bookings.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 9;
      td.className = "empty-state";
      td.textContent = "No active bookings found in SQLite.";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    state.bookings.forEach((booking) => {
      const aptAddress = booking.apartment_address || booking.address || "";
      const aptMaxPeople = booking.apartment_max_people ?? booking.max_people;

      const tr = document.createElement("tr");
      tr.dataset.bookingRow = `${booking.apartment_name}|${booking.start_date}|${booking.end_date}`;

      const tdApt = document.createElement("td");
      const strongApt = document.createElement("strong");
      strongApt.textContent = booking.apartment_name;
      tdApt.appendChild(strongApt);

      const tdAddr = document.createElement("td");
      tdAddr.textContent = aptAddress;

      const tdCap = document.createElement("td");
      tdCap.className = "text-center";
      tdCap.textContent = `Max ${aptMaxPeople}`;

      const tdRate = document.createElement("td");
      tdRate.className = "text-right";
      tdRate.textContent = formatMoney(booking.price_per_night);

      const tdBooker = document.createElement("td");
      tdBooker.textContent = booking.booker_name;

      const tdPeople = document.createElement("td");
      tdPeople.className = "text-center";
      tdPeople.textContent = `${booking.num_people} / ${aptMaxPeople}`;

      const tdDates = document.createElement("td");
      tdDates.textContent = `${booking.start_date} → ${booking.end_date} (${booking.nights}n)`;

      const tdTotal = document.createElement("td");
      tdTotal.className = "text-right";
      const strongTotal = document.createElement("strong");
      strongTotal.textContent = `${formatMoney(booking.total_price)} EUR`;
      tdTotal.appendChild(strongTotal);

      const tdActions = document.createElement("td");
      tdActions.className = "text-right";
      const actionWrap = document.createElement("div");
      actionWrap.className = "table-actions";

      const changeBtn = document.createElement("button");
      changeBtn.type = "button";
      changeBtn.className = "btn btn-outline btn-sm";
      changeBtn.dataset.action = "change-booking";
      changeBtn.textContent = "Change";
      changeBtn.addEventListener("click", () => openChangeBookingModal(booking));

      const cancelBtn = document.createElement("button");
      cancelBtn.type = "button";
      cancelBtn.className = "btn btn-danger-soft btn-sm";
      cancelBtn.dataset.action = "cancel-booking";
      cancelBtn.textContent = "Cancel";
      cancelBtn.addEventListener("click", () => openCancelBookingModal(booking));

      actionWrap.append(changeBtn, cancelBtn);
      tdActions.appendChild(actionWrap);

      tr.append(tdApt, tdAddr, tdCap, tdRate, tdBooker, tdPeople, tdDates, tdTotal, tdActions);
      tbody.appendChild(tr);
    });
  }

  function renderDirectoryView() {
    const query = (byId("dir-search-input").value || "").trim().toLowerCase();
    const minCap = Number(byId("dir-capacity-filter").value) || 0;
    const maxPrice = Number(byId("dir-price-filter").value) || 0;

    const filtered = state.apartments.filter((apt) => {
      const matchesText =
        !query ||
        apt.name.toLowerCase().includes(query) ||
        apt.address.toLowerCase().includes(query);
      const matchesCap = apt.max_people >= minCap;
      const matchesPrice = maxPrice === 0 || apt.price_per_night <= maxPrice;
      return matchesText && matchesCap && matchesPrice;
    });

    const tbody = byId("directory-table-body");
    const cardsWrapper = byId("dir-cards-wrapper");
    tbody.replaceChildren();
    cardsWrapper.replaceChildren();

    if (filtered.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 5;
      td.className = "empty-state";
      td.textContent = "No apartments match the current directory filter.";
      tr.appendChild(td);
      tbody.appendChild(tr);

      const emptyCard = document.createElement("div");
      emptyCard.className = "empty-state";
      emptyCard.textContent = "No apartments match the current directory filter.";
      cardsWrapper.appendChild(emptyCard);
      return;
    }

    filtered.forEach((apt) => {
      // Table row
      const tr = document.createElement("tr");
      const tdName = document.createElement("td");
      const strong = document.createElement("strong");
      strong.textContent = apt.name;
      tdName.appendChild(strong);

      const tdAddr = document.createElement("td");
      tdAddr.textContent = apt.address;

      const tdCap = document.createElement("td");
      tdCap.className = "text-center";
      tdCap.textContent = `Max ${apt.max_people}`;

      const tdPrice = document.createElement("td");
      tdPrice.className = "text-right";
      tdPrice.textContent = `${formatMoney(apt.price_per_night)} EUR`;

      const tdActions = document.createElement("td");
      tdActions.className = "text-right";
      const actions = document.createElement("div");
      actions.className = "table-actions";

      const checkBtn = document.createElement("button");
      checkBtn.type = "button";
      checkBtn.className = "btn btn-secondary btn-sm";
      checkBtn.textContent = "Check Dates";
      checkBtn.addEventListener("click", () => {
        switchView("search-view");
        byId("avail-num-people").value = String(Math.min(2, apt.max_people));
      });

      const inspectBtn = document.createElement("button");
      inspectBtn.type = "button";
      inspectBtn.className = "btn btn-outline btn-sm";
      inspectBtn.textContent = "Details";
      inspectBtn.addEventListener("click", () => openInspectorModal(apt));

      actions.append(checkBtn, inspectBtn);
      tdActions.appendChild(actions);
      tr.append(tdName, tdAddr, tdCap, tdPrice, tdActions);
      tbody.appendChild(tr);

      // Card item
      const card = document.createElement("article");
      card.className = "apt-card";
      const header = document.createElement("div");
      header.className = "apt-card-header";
      const h4 = document.createElement("h4");
      h4.className = "apt-card-title";
      h4.textContent = apt.name;
      const capPill = document.createElement("span");
      capPill.className = "capacity-pill";
      capPill.textContent = `Max ${apt.max_people}`;
      header.append(h4, capPill);

      const addrP = document.createElement("p");
      addrP.className = "apt-card-address";
      addrP.textContent = apt.address;

      const priceDiv = document.createElement("div");
      priceDiv.className = "apt-card-pricing";
      priceDiv.textContent = `${formatMoney(apt.price_per_night)} / night`;

      card.append(header, addrP, priceDiv);
      cardsWrapper.appendChild(card);
    });
  }

  function renderInventoryView() {
    const query = (byId("inventory-search-input").value || "").trim().toLowerCase();
    const tbody = byId("inventory-table-body");
    tbody.replaceChildren();
    byId("inventory-count-badge").textContent =
      `${state.apartments.length} Unit${state.apartments.length === 1 ? "" : "s"} Managed`;

    const filtered = state.apartments.filter(
      (apt) =>
        !query ||
        apt.name.toLowerCase().includes(query) ||
        apt.address.toLowerCase().includes(query)
    );

    if (filtered.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 6;
      td.className = "empty-state";
      td.textContent = "No apartments registered in inventory.";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    filtered.forEach((apt) => {
      const activeStays = state.bookings.filter((b) => b.apartment_name === apt.name).length;
      const tr = document.createElement("tr");
      tr.dataset.inventoryRow = apt.name;

      const tdName = document.createElement("td");
      const strong = document.createElement("strong");
      strong.textContent = apt.name;
      tdName.appendChild(strong);

      const tdAddr = document.createElement("td");
      tdAddr.textContent = apt.address;

      const tdCap = document.createElement("td");
      tdCap.className = "text-center";
      tdCap.textContent = `Max ${apt.max_people}`;

      const tdRate = document.createElement("td");
      tdRate.className = "text-right";
      const strongRate = document.createElement("strong");
      strongRate.textContent = `${formatMoney(apt.price_per_night)} EUR`;
      tdRate.appendChild(strongRate);

      const tdStays = document.createElement("td");
      tdStays.className = "text-center";
      tdStays.textContent = `${activeStays} stay${activeStays === 1 ? "" : "s"}`;

      const tdActions = document.createElement("td");
      tdActions.className = "text-right";
      const actions = document.createElement("div");
      actions.className = "table-actions";

      const updateBtn = document.createElement("button");
      updateBtn.type = "button";
      updateBtn.className = "btn btn-outline btn-sm";
      updateBtn.dataset.action = "update-price";
      updateBtn.textContent = "Update Price";
      updateBtn.addEventListener("click", () => openPriceModal(apt));

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "btn btn-danger-soft btn-sm";
      removeBtn.dataset.action = "remove-apartment";
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", () => openDeleteApartmentModal(apt));

      actions.append(updateBtn, removeBtn);
      tdActions.appendChild(actions);

      tr.append(tdName, tdAddr, tdCap, tdRate, tdStays, tdActions);
      tbody.appendChild(tr);
    });
  }

  function renderOverviewView() {
    const totalBookings = state.bookings.length;
    const totalRevenue = state.bookings.reduce(
      (sum, b) => sum + (Number(b.total_price) || 0),
      0
    );
    const totalNights = state.bookings.reduce(
      (sum, b) => sum + (Number(b.nights) || 0),
      0
    );
    const avgStay = totalBookings > 0 ? (totalNights / totalBookings).toFixed(1) : "0.0";

    byId("kpi-active-bookings").textContent = String(totalBookings);
    byId("kpi-total-revenue").textContent = `${formatMoney(totalRevenue)} EUR`;
    byId("kpi-avg-stay").textContent = `${avgStay} Nights`;
    byId("kpi-total-apartments").textContent = `${state.apartments.length} Units`;

    const aptFilter = byId("overview-apartment-filter").value;
    const searchQuery = (byId("overview-search-input").value || "").trim().toLowerCase();

    const filtered = state.bookings.filter((b) => {
      const aptAddress = b.apartment_address || b.address || "";
      const matchesApt = !aptFilter || b.apartment_name === aptFilter;
      const matchesQuery =
        !searchQuery ||
        b.booker_name.toLowerCase().includes(searchQuery) ||
        b.apartment_name.toLowerCase().includes(searchQuery) ||
        aptAddress.toLowerCase().includes(searchQuery);
      return matchesApt && matchesQuery;
    });

    const tbody = byId("overview-table-body");
    tbody.replaceChildren();

    if (filtered.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 9;
      td.className = "empty-state";
      td.textContent = "No reservations match the current overview filters.";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    filtered.forEach((b) => {
      const aptAddress = b.apartment_address || b.address || "";
      const aptMaxPeople = b.apartment_max_people ?? b.max_people;

      const tr = document.createElement("tr");
      const tdApt = document.createElement("td");
      const strongApt = document.createElement("strong");
      strongApt.textContent = b.apartment_name;
      tdApt.appendChild(strongApt);

      const tdAddr = document.createElement("td");
      tdAddr.textContent = aptAddress;

      const tdBooker = document.createElement("td");
      tdBooker.textContent = b.booker_name;

      const tdPeople = document.createElement("td");
      tdPeople.className = "text-center";
      tdPeople.textContent = `${b.num_people} / Max ${aptMaxPeople}`;

      const tdDates = document.createElement("td");
      tdDates.textContent = `${b.start_date} → ${b.end_date}`;

      const tdNights = document.createElement("td");
      tdNights.className = "text-center";
      tdNights.textContent = `${b.nights}n`;

      const tdRate = document.createElement("td");
      tdRate.className = "text-right";
      tdRate.textContent = formatMoney(b.price_per_night);

      const tdTotal = document.createElement("td");
      tdTotal.className = "text-right";
      const strongTotal = document.createElement("strong");
      strongTotal.textContent = `${formatMoney(b.total_price)} EUR`;
      tdTotal.appendChild(strongTotal);

      const tdAudit = document.createElement("td");
      tdAudit.className = "text-right";
      const inspectBtn = document.createElement("button");
      inspectBtn.type = "button";
      inspectBtn.className = "btn btn-outline btn-sm";
      inspectBtn.dataset.action = "inspect-booking";
      inspectBtn.textContent = "Inspect JSON";
      inspectBtn.addEventListener("click", () => openInspectorModal(b));
      tdAudit.appendChild(inspectBtn);

      tr.append(tdApt, tdAddr, tdBooker, tdPeople, tdDates, tdNights, tdRate, tdTotal, tdAudit);
      tbody.appendChild(tr);
    });
  }

  function renderAll() {
    populateApartmentSelects();
    renderBookingsTable();
    renderDirectoryView();
    renderInventoryView();
    renderOverviewView();
  }

  // DATA FETCHING
  async function loadAllData() {
    const [aptRes, bookRes] = await Promise.all([
      apiRequest("/api/apartments"),
      apiRequest("/api/bookings"),
    ]);
    if (aptRes.ok && aptRes.payload && Array.isArray(aptRes.payload.data)) {
      state.apartments = aptRes.payload.data;
    }
    if (bookRes.ok && bookRes.payload && Array.isArray(bookRes.payload.data)) {
      state.bookings = bookRes.payload.data;
    }
    renderAll();
  }

  async function runAvailabilitySearch(silent = false) {
    const start_date = byId("avail-start-date").value.trim();
    const end_date = byId("avail-end-date").value.trim();
    const num_people = Number(byId("avail-num-people").value);

    state.lastSearch = { start_date, end_date, num_people };
    const params = new URLSearchParams({
      start_date,
      end_date,
      num_people: String(num_people),
    });

    const res = await apiRequest(`/api/availability?${params.toString()}`);
    if (!res.ok) {
      showApiError(res.status, res.payload, "Availability Search Error");
      return;
    }

    state.availabilityResults = res.payload.data || [];
    renderAvailabilityResults();
    if (!silent) {
      showBanner(
        "success",
        "200 OK",
        "Availability Search Complete",
        `Found ${state.availabilityResults.length} available apartment(s) for ${start_date} to ${end_date}.`
      );
    }
  }

  // MODAL HANDLERS
  function openInstantBookModal(apt) {
    state.instantBookTarget = apt;
    byId("instant-apt-name").textContent = apt.name;
    byId("instant-apt-meta").textContent = `${apt.address} • Max ${apt.max_people} guests`;
    byId("instant-stay-summary").textContent =
      `${state.lastSearch.start_date} → ${state.lastSearch.end_date} (${apt.nights} nights, ${state.lastSearch.num_people} guests) • Total: ${formatMoney(apt.total_price)} EUR`;
    byId("instant-booker-name").value = "";
    byId("instant-book-modal").hidden = false;
    byId("instant-booker-name").focus();
  }

  function closeInstantBookModal() {
    byId("instant-book-modal").hidden = true;
    state.instantBookTarget = null;
  }

  function openChangeBookingModal(booking) {
    state.changeBookingTarget = booking;
    const aptMaxPeople = booking.apartment_max_people ?? booking.max_people;
    byId("change-apt-title").textContent = booking.apartment_name;
    byId("change-ref-meta").textContent =
      `Current: ${booking.start_date} → ${booking.end_date} • Booker: ${booking.booker_name} • Max ${aptMaxPeople}`;
    byId("change-start-date").value = booking.start_date;
    byId("change-end-date").value = booking.end_date;
    byId("change-num-people").value = String(booking.num_people);
    byId("change-num-people").max = String(aptMaxPeople);
    updateChangeModalPreview();
    byId("change-booking-modal").hidden = false;
  }

  function updateChangeModalPreview() {
    if (!state.changeBookingTarget) {
      return;
    }
    const nights = calculateNights(
      byId("change-start-date").value,
      byId("change-end-date").value
    );
    const rate = Number(state.changeBookingTarget.price_per_night) || 0;
    byId("change-recalc-total").textContent =
      `${nights} night${nights === 1 ? "" : "s"} × ${formatMoney(rate)} = ${formatMoney(nights * rate)} EUR`;
  }

  function closeChangeBookingModal() {
    byId("change-booking-modal").hidden = true;
    state.changeBookingTarget = null;
  }

  function openCancelBookingModal(booking) {
    state.cancelBookingTarget = booking;
    byId("cancel-modal-booker").textContent = booking.booker_name;
    byId("cancel-modal-apt").textContent = booking.apartment_name;
    byId("cancel-modal-dates").textContent = `${booking.start_date} → ${booking.end_date}`;
    byId("cancel-booking-modal").hidden = false;
  }

  function closeCancelBookingModal() {
    byId("cancel-booking-modal").hidden = true;
    state.cancelBookingTarget = null;
  }

  function openPriceModal(apt) {
    state.priceUpdateTarget = apt;
    byId("price-modal-apt-name").textContent = apt.name;
    byId("price-modal-current").textContent = `${formatMoney(apt.price_per_night)} EUR`;
    byId("new-price-input").value = Number(apt.price_per_night).toFixed(2);
    byId("price-modal").hidden = false;
    byId("new-price-input").focus();
  }

  function closePriceModal() {
    byId("price-modal").hidden = true;
    state.priceUpdateTarget = null;
  }

  function openDeleteApartmentModal(apt) {
    state.deleteApartmentTarget = apt;
    byId("delete-apt-name-target").textContent = apt.name;
    byId("delete-apartment-modal").hidden = false;
  }

  function closeDeleteApartmentModal() {
    byId("delete-apartment-modal").hidden = true;
    state.deleteApartmentTarget = null;
  }

  function openInspectorModal(record) {
    byId("inspector-json-pre").textContent = JSON.stringify(record, null, 2);
    byId("inspector-modal").hidden = false;
  }

  function closeInspectorModal() {
    byId("inspector-modal").hidden = true;
  }

  // EVENT WIRING
  function initEventListeners() {
    // Role switching
    byId("role-booker-btn").addEventListener("click", () => switchRole("booker", true));
    byId("role-manager-btn").addEventListener("click", () => switchRole("manager", true));

    // Sidebar navigation
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        const viewId = btn.dataset.view;
        if (viewId === "inventory-view" || viewId === "overview-view") {
          switchRole("manager", false);
        } else {
          switchRole("booker", false);
        }
        switchView(viewId);
      });
    });

    // Topbar buttons
    byId("health-badge").addEventListener("click", () => checkHealth(true));
    byId("refresh-all-btn").addEventListener("click", async () => {
      await loadAllData();
      await runAvailabilitySearch(true);
      showBanner("success", "200 OK", "Data Refreshed", "Synchronized apartments and bookings with SQLite.");
    });
    byId("help-btn").addEventListener("click", () => {
      byId("help-modal").hidden = false;
    });
    byId("help-modal-close").addEventListener("click", () => {
      byId("help-modal").hidden = true;
    });
    byId("help-modal-done").addEventListener("click", () => {
      byId("help-modal").hidden = true;
    });
    byId("status-banner-close").addEventListener("click", hideBanner);

    // Availability search form & steppers
    byId("avail-people-dec").addEventListener("click", () => {
      const input = byId("avail-num-people");
      input.value = String(Math.max(1, (Number(input.value) || 1) - 1));
    });
    byId("avail-people-inc").addEventListener("click", () => {
      const input = byId("avail-num-people");
      input.value = String((Number(input.value) || 1) + 1);
    });
    byId("availability-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      await runAvailabilitySearch(false);
    });

    // Instant Book modal form
    byId("instant-modal-close").addEventListener("click", closeInstantBookModal);
    byId("instant-modal-cancel").addEventListener("click", closeInstantBookModal);
    byId("instant-book-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!state.instantBookTarget) {
        return;
      }
      const bookerName = byId("instant-booker-name").value.trim();
      const payload = {
        apartment_name: state.instantBookTarget.name,
        start_date: state.lastSearch.start_date,
        end_date: state.lastSearch.end_date,
        booker_name: bookerName,
        num_people: Number(state.lastSearch.num_people),
      };
      const res = await apiRequest("/api/bookings", { method: "POST", json: payload });
      if (!res.ok) {
        showApiError(res.status, res.payload, "Instant Booking Failed");
        return;
      }
      const created = res.payload.data;
      closeInstantBookModal();
      await loadAllData();
      await runAvailabilitySearch(true);
      showBanner(
        "success",
        "201 CREATED",
        "Booking Confirmed",
        `Booked "${created.apartment_name}" for ${created.booker_name} (${created.start_date} → ${created.end_date}) • Total: ${formatMoney(created.total_price)} EUR.`
      );
    });

    // Manual Booking Creator form
    ["booking-apartment-select", "booking-start-date", "booking-end-date", "booking-num-people"].forEach((id) => {
      byId(id).addEventListener("input", updateBookingCreatorPreview);
      byId(id).addEventListener("change", updateBookingCreatorPreview);
    });

    byId("create-booking-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = {
        apartment_name: byId("booking-apartment-select").value,
        start_date: byId("booking-start-date").value.trim(),
        end_date: byId("booking-end-date").value.trim(),
        booker_name: byId("booking-booker-name").value.trim(),
        num_people: Number(byId("booking-num-people").value),
      };
      const res = await apiRequest("/api/bookings", { method: "POST", json: payload });
      if (!res.ok) {
        showApiError(res.status, res.payload, "Booking Creation Failed");
        return;
      }
      const created = res.payload.data;
      byId("booking-booker-name").value = "";
      await loadAllData();
      await runAvailabilitySearch(true);
      showBanner(
        "success",
        "201 CREATED",
        "Reservation Created",
        `Created booking for ${created.booker_name} at "${created.apartment_name}" (${created.nights} nights • ${formatMoney(created.total_price)} EUR).`
      );
    });

    // Change Booking modal
    byId("change-modal-close").addEventListener("click", closeChangeBookingModal);
    byId("change-modal-cancel").addEventListener("click", closeChangeBookingModal);
    byId("change-start-date").addEventListener("input", updateChangeModalPreview);
    byId("change-end-date").addEventListener("input", updateChangeModalPreview);
    byId("change-booking-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!state.changeBookingTarget) {
        return;
      }
      const payload = {
        apartment_name: state.changeBookingTarget.apartment_name,
        start_date: state.changeBookingTarget.start_date,
        end_date: state.changeBookingTarget.end_date,
        new_start_date: byId("change-start-date").value.trim(),
        new_end_date: byId("change-end-date").value.trim(),
        num_people: Number(byId("change-num-people").value),
      };
      const res = await apiRequest("/api/bookings", { method: "PATCH", json: payload });
      if (!res.ok) {
        showApiError(res.status, res.payload, "Booking Change Failed");
        return;
      }
      const updated = res.payload.data;
      closeChangeBookingModal();
      await loadAllData();
      await runAvailabilitySearch(true);
      showBanner(
        "success",
        "200 OK",
        "Booking Updated",
        `Updated booking for ${updated.booker_name} at "${updated.apartment_name}" to ${updated.start_date} → ${updated.end_date} (${formatMoney(updated.total_price)} EUR).`
      );
    });

    // Cancel Booking modal
    byId("cancel-modal-close").addEventListener("click", closeCancelBookingModal);
    byId("cancel-modal-keep").addEventListener("click", closeCancelBookingModal);
    byId("confirm-cancel-booking-btn").addEventListener("click", async () => {
      if (!state.cancelBookingTarget) {
        return;
      }
      const payload = {
        apartment_name: state.cancelBookingTarget.apartment_name,
        start_date: state.cancelBookingTarget.start_date,
        end_date: state.cancelBookingTarget.end_date,
      };
      const res = await apiRequest("/api/bookings", { method: "DELETE", json: payload });
      if (!res.ok) {
        showApiError(res.status, res.payload, "Booking Cancellation Failed");
        return;
      }
      const cancelled = res.payload.data;
      closeCancelBookingModal();
      await loadAllData();
      await runAvailabilitySearch(true);
      showBanner(
        "success",
        "200 OK",
        "Booking Cancelled",
        `Cancelled and removed booking for ${cancelled.booker_name} at "${cancelled.apartment_name}".`
      );
    });

    // Directory filters & view toggles
    byId("dir-search-input").addEventListener("input", renderDirectoryView);
    byId("dir-capacity-filter").addEventListener("change", renderDirectoryView);
    byId("dir-price-filter").addEventListener("change", renderDirectoryView);
    byId("dir-view-table-btn").addEventListener("click", () => {
      byId("dir-table-wrapper").hidden = false;
      byId("dir-cards-wrapper").hidden = true;
      byId("dir-view-table-btn").className = "btn btn-secondary btn-sm active";
      byId("dir-view-cards-btn").className = "btn btn-outline btn-sm";
    });
    byId("dir-view-cards-btn").addEventListener("click", () => {
      byId("dir-table-wrapper").hidden = true;
      byId("dir-cards-wrapper").hidden = false;
      byId("dir-view-cards-btn").className = "btn btn-secondary btn-sm active";
      byId("dir-view-table-btn").className = "btn btn-outline btn-sm";
    });

    // System Manager: Live address preview & Add Apartment form
    const updateAddressPreview = () => {
      const country = byId("apt-country").value.trim() || "Country";
      const city = byId("apt-city").value.trim() || "City";
      const street = byId("apt-street").value.trim() || "Street";
      byId("address-preview-display").textContent = `${country}, ${city}, ${street}`;
    };
    ["apt-country", "apt-city", "apt-street"].forEach((id) => {
      byId(id).addEventListener("input", updateAddressPreview);
    });

    byId("add-apartment-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = {
        name: byId("apt-name").value.trim(),
        country: byId("apt-country").value.trim(),
        city: byId("apt-city").value.trim(),
        street_and_number: byId("apt-street").value.trim(),
        max_people: Number(byId("apt-max-people").value),
        price_per_night: byId("apt-price").value.trim(),
      };
      const res = await apiRequest("/api/apartments", { method: "POST", json: payload });
      if (!res.ok) {
        showApiError(res.status, res.payload, "Add Apartment Failed");
        return;
      }
      const created = res.payload.data;
      byId("apt-name").value = "";
      byId("apt-country").value = "";
      byId("apt-city").value = "";
      byId("apt-street").value = "";
      updateAddressPreview();
      await loadAllData();
      await runAvailabilitySearch(true);
      showBanner(
        "success",
        "201 CREATED",
        "Apartment Added",
        `Registered "${created.name}" (${created.address}) at ${formatMoney(created.price_per_night)} EUR / night.`
      );
    });

    byId("inventory-search-input").addEventListener("input", renderInventoryView);

    // Update Price modal
    byId("price-modal-close").addEventListener("click", closePriceModal);
    byId("price-modal-cancel").addEventListener("click", closePriceModal);
    byId("price-modal-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!state.priceUpdateTarget) {
        return;
      }
      const encodedName = encodeURIComponent(state.priceUpdateTarget.name);
      const newPrice = byId("new-price-input").value.trim();
      const res = await apiRequest(`/api/apartments/${encodedName}/price`, {
        method: "PATCH",
        json: { price_per_night: newPrice },
      });
      if (!res.ok) {
        showApiError(res.status, res.payload, "Price Update Failed");
        return;
      }
      const updated = res.payload.data;
      closePriceModal();
      await loadAllData();
      await runAvailabilitySearch(true);
      showBanner(
        "success",
        "200 OK",
        "Nightly Price Updated",
        `Updated "${updated.name}" nightly price to ${formatMoney(updated.price_per_night)} EUR.`
      );
    });

    // Remove Apartment modal
    byId("delete-apt-modal-close").addEventListener("click", closeDeleteApartmentModal);
    byId("delete-apt-modal-cancel").addEventListener("click", closeDeleteApartmentModal);
    byId("confirm-delete-apartment-btn").addEventListener("click", async () => {
      if (!state.deleteApartmentTarget) {
        return;
      }
      const encodedName = encodeURIComponent(state.deleteApartmentTarget.name);
      const res = await apiRequest(`/api/apartments/${encodedName}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        showApiError(res.status, res.payload, "Remove Apartment Failed");
        return;
      }
      const removed = res.payload.data;
      closeDeleteApartmentModal();
      await loadAllData();
      await runAvailabilitySearch(true);
      showBanner(
        "success",
        "200 OK",
        "Apartment Removed",
        `Removed "${removed.name}" and any associated bookings from SQLite.`
      );
    });

    // Overview filters & JSON Inspector
    byId("overview-apartment-filter").addEventListener("change", renderOverviewView);
    byId("overview-search-input").addEventListener("input", renderOverviewView);
    byId("overview-clear-btn").addEventListener("click", () => {
      byId("overview-apartment-filter").value = "";
      byId("overview-search-input").value = "";
      renderOverviewView();
    });
    byId("inspector-modal-close").addEventListener("click", closeInspectorModal);
    byId("inspector-modal-done").addEventListener("click", closeInspectorModal);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    initEventListeners();
    await checkHealth(false);
    await loadAllData();
    await runAvailabilitySearch(true);
  });
})();
