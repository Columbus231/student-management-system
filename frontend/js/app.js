const API = "/api/v1";
const RESOURCE_CONFIG = {
  users: {
    label: "People",
    description: "Manage campus accounts, roles, and student records.",
    icon: "♙",
    columns: [["full_name", "Name"], ["email", "Email"], ["role", "Role"], ["student_number", "Student no."], ["faculty_number", "Faculty no."]],
    fields: [["full_name", "Full name", "text"], ["email", "Email", "email"], ["role", "Role", "select", [["student", "Student"], ["faculty", "Faculty"], ["admin", "Administrator"]]], ["student_number", "Student number", "text"], ["faculty_number", "Faculty number", "text"], ["department_id", "Department", "resource", "departments"], ["password", "Temporary password", "password"]],
    filters: [["role", "Role", [["student", "Student"], ["faculty", "Faculty"], ["admin", "Administrator"]]], ["department_id", "Department", "departments"]],
  },
  departments: {
    label: "Departments",
    description: "Organize academic programs and departments.",
    icon: "▦",
    columns: [["name", "Department"], ["code", "Code"], ["description", "About"]],
    fields: [["name", "Department name", "text"], ["code", "Department code", "text"], ["description", "Description", "textarea"]],
    filters: [],
  },
  courses: {
    label: "Courses",
    description: "Browse course offerings and course details.",
    icon: "▤",
    columns: [["code", "Code"], ["title", "Course"], ["department_name", "Department"], ["faculty_name", "Faculty"], ["credits", "Credits"]],
    fields: [["code", "Course code", "text"], ["title", "Course title", "text"], ["description", "Description", "textarea"], ["credits", "Credits", "number"], ["department_id", "Department", "resource", "departments"], ["faculty_id", "Faculty", "resource", "users", "faculty"]],
    filters: [["department_id", "Department", "departments"], ["faculty_id", "Faculty", "users", "faculty"]],
  },
  enrollments: {
    label: "Registrations",
    description: "Track student registrations and course enrollment.",
    icon: "＋",
    columns: [["student_name", "Student"], ["course_code", "Course"], ["academic_year", "Year"], ["term", "Term"], ["status", "Status"]],
    fields: [["student_id", "Student", "resource", "users", "student"], ["course_id", "Course", "resource", "courses"], ["academic_year", "Academic year", "text"], ["term", "Term", "text"], ["status", "Status", "select", [["enrolled", "Enrolled"], ["completed", "Completed"], ["withdrawn", "Withdrawn"]]]],
    filters: [["status", "Status", [["enrolled", "Enrolled"], ["completed", "Completed"], ["withdrawn", "Withdrawn"]]], ["academic_year", "Academic year"]],
  },
  attendance: {
    label: "Attendance",
    description: "Record and review course attendance.",
    icon: "◷",
    columns: [["student_name", "Student"], ["course_code", "Course"], ["date", "Date"], ["status", "Status"], ["notes", "Notes"]],
    fields: [["enrollment_id", "Student registration", "resource", "enrollments"], ["date", "Attendance date", "date"], ["status", "Attendance", "select", [["present", "Present"], ["absent", "Absent"], ["late", "Late"], ["excused", "Excused"]]], ["notes", "Notes", "textarea"]],
    filters: [["status", "Attendance", [["present", "Present"], ["absent", "Absent"], ["late", "Late"], ["excused", "Excused"]]], ["date", "Date"]],
  },
  examinations: {
    label: "Examinations",
    description: "Keep examination schedules and maximum marks in one place.",
    icon: "✧",
    columns: [["title", "Examination"], ["course_code", "Course"], ["exam_date", "Date"], ["total_marks", "Total marks"]],
    fields: [["course_id", "Course", "resource", "courses"], ["title", "Examination name", "text"], ["exam_date", "Exam date", "date"], ["total_marks", "Total marks", "number"]],
    filters: [["course_id", "Course", "courses"], ["exam_date", "Date"]],
  },
  results: {
    label: "Results",
    description: "Review academic performance and examination results.",
    icon: "↗",
    columns: [["student_name", "Student"], ["course_code", "Course"], ["exam_title", "Examination"], ["marks", "Marks"], ["grade", "Grade"], ["remarks", "Remarks"]],
    fields: [["examination_id", "Examination", "resource", "examinations"], ["student_id", "Student", "resource", "users", "student"], ["marks", "Marks", "number"], ["grade", "Grade", "text"], ["remarks", "Remarks", "textarea"]],
    filters: [["examination_id", "Examination", "examinations"], ["student_id", "Student", "users", "student"], ["grade", "Grade"]],
  },
  notices: {
    label: "Announcements",
    description: "Stay up to date with campus news and notices.",
    icon: "◉",
    columns: [["title", "Announcement"], ["audience", "Audience"], ["author_name", "Posted by"], ["created_at", "Posted"]],
    fields: [["title", "Title", "text"], ["body", "Announcement", "textarea"], ["audience", "Audience", "select", [["all", "Everyone"], ["students", "Students"], ["faculty", "Faculty"], ["admins", "Administrators"]]]],
    filters: [["audience", "Audience", [["all", "Everyone"], ["students", "Students"], ["faculty", "Faculty"], ["admins", "Administrators"]]]],
  },
};

const ROLE_NAV = {
  admin: ["users", "departments", "courses", "enrollments", "attendance", "examinations", "results", "notices"],
  faculty: ["courses", "enrollments", "attendance", "examinations", "results", "notices"],
  student: ["courses", "enrollments", "attendance", "examinations", "results", "notices"],
};
const PAGE_ICONS = { overview: "⌂", profile: "♙", ...Object.fromEntries(Object.entries(RESOURCE_CONFIG).map(([key, item]) => [key, item.icon])) };
const state = { user: null, entity: null, page: 1, totalPages: 1, search: "", filter: null, editing: null, toastTimer: null };
const elements = Object.fromEntries([
  "auth-screen", "app-shell", "auth-form", "auth-name", "auth-student-number", "auth-email",
  "auth-password", "auth-notice", "auth-switch", "auth-switch-copy", "auth-submit", "auth-title",
  "auth-subtitle", "auth-eyebrow", "register-fields", "primary-nav", "dashboard-summary",
  "page-heading", "current-page", "profile-name", "profile-role", "avatar", "today-label",
  "list-title", "list-description", "search-input", "filter-field", "filter-value", "apply-filter",
  "add-record", "table-container", "pagination", "record-dialog", "record-form", "record-fields",
  "dialog-title", "dialog-close", "dialog-cancel", "dialog-save", "toast", "logout-button",
  "menu-button", "sidebar", "apply-filter",
  "notification-button", "profile-card",
].map((id) => [
  id.replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase()),
  document.getElementById(id),
]));
elements.contentCard = document.querySelector(".content-card");

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function readCookie(name) {
  const prefix = `${name}=`;
  const item = document.cookie.split("; ").find((cookie) => cookie.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

async function request(path, options = {}) {
  const method = options.method || "GET";
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = readCookie("csrf_access_token");
    if (csrf) headers["X-CSRF-TOKEN"] = csrf;
  }
  const response = await fetch(`${API}${path}`, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
  });
  if (response.status === 204) return null;
  let result;
  try {
    result = await response.json();
  } catch {
    if (response.ok) throw new Error("The server returned an invalid JSON response.");
    result = {};
  }
  if (!response.ok) throw new ApiError(result.error || `Request failed (${response.status}).`, response.status);
  return result;
}

function toast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", error);
  elements.toast.classList.remove("hidden");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => elements.toast.classList.add("hidden"), 3400);
}

function displayAuth(message = "") {
  state.user = null;
  elements.authPassword.value = "";
  elements.appShell.classList.add("hidden");
  elements.authScreen.classList.remove("hidden");
  elements.authNotice.textContent = message;
  elements.authNotice.classList.toggle("hidden", !message);
  setAuthMode(false);
}

function setAuthMode(registering) {
  elements.registerFields.classList.toggle("hidden", !registering);
  elements.authName.required = registering;
  elements.authPassword.autocomplete = registering ? "new-password" : "current-password";
  elements.authTitle.textContent = registering ? "Create your account" : "Sign in to Campusly";
  elements.authSubtitle.textContent = registering ? "Start your next chapter here." : "Your campus is just a moment away.";
  elements.authEyebrow.textContent = registering ? "JOIN YOUR CAMPUS" : "WELCOME BACK";
  elements.authSwitchCopy.textContent = registering ? "Already have an account?" : "New to Campusly?";
  elements.authSwitch.textContent = registering ? "Sign in" : "Create an account";
  elements.authSubmit.innerHTML = registering ? 'Create account <span>→</span>' : 'Sign in <span>→</span>';
  elements.authName.disabled = !registering;
  elements.authStudentNumber.disabled = !registering;
  elements.authPassword.minLength = 10;
  elements.authForm.dataset.mode = registering ? "register" : "login";
}

function showApp(user) {
  state.user = user;
  state.entity = null;
  elements.authScreen.classList.add("hidden");
  elements.appShell.classList.remove("hidden");
  elements.profileName.textContent = user.full_name;
  elements.profileRole.textContent = user.role;
  elements.avatar.textContent = (user.full_name || "C").trim().charAt(0).toUpperCase();
  elements.todayLabel.textContent = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" }).format(new Date());
  buildNav();
  loadDashboard();
}

function buildNav() {
  elements.primaryNav.replaceChildren();
  const overview = makeNavButton("overview", "Overview");
  elements.primaryNav.append(overview);
  if (state.user.role === "student") {
    elements.primaryNav.append(makeNavButton("profile", "My profile"));
  }
  for (const entity of ROLE_NAV[state.user.role] || []) {
    elements.primaryNav.append(makeNavButton(entity, RESOURCE_CONFIG[entity].label));
  }
}

function makeNavButton(entity, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "nav-item";
  button.dataset.page = entity;
  const icon = document.createElement("span");
  icon.className = "nav-icon";
  icon.textContent = PAGE_ICONS[entity] || "·";
  const name = document.createElement("span");
  name.textContent = label;
  button.append(icon, name);
  button.addEventListener("click", () => {
    elements.sidebar.classList.remove("open");
    if (entity === "overview") loadDashboard();
    else if (entity === "profile") loadProfile();
    else loadResource(entity);
  });
  return button;
}

function setActiveNav(entity) {
  for (const button of elements.primaryNav.querySelectorAll(".nav-item")) {
    button.classList.toggle("active", button.dataset.page === entity);
  }
}

async function loadDashboard() {
  clearTimeout(state.searchTimer);
  state.entity = "notices";
  state.search = "";
  state.filter = null;
  elements.searchInput.value = "";
  setActiveNav("overview");
  elements.dashboardSummary.classList.remove("hidden");
  elements.profileCard.classList.add("hidden");
  elements.contentCard.classList.remove("hidden");
  elements.searchInput.disabled = false;
  elements.currentPage.textContent = "Overview";
  elements.pageHeading.replaceChildren();
  const greeting = document.createElement("div");
  greeting.className = "greeting-label";
  greeting.textContent = `GOOD DAY, ${(state.user.full_name.split(" ")[0] || "THERE").toUpperCase()}`;
  const title = document.createElement("h1");
  title.textContent = "Your campus at a glance";
  const subtitle = document.createElement("p");
  subtitle.textContent = "Here’s what’s happening across your college.";
  elements.pageHeading.append(greeting, title, subtitle);
  elements.listTitle.textContent = "Recent announcements";
  elements.listDescription.textContent = "The latest from your campus community.";
  elements.addRecord.classList.add("hidden");
  elements.searchInput.placeholder = "Search announcements...";
  configureFilters("notices");
  elements.searchInput.value = "";
  elements.tableContainer.innerHTML = '<div class="empty-state"><span>◉</span>Loading your campus overview...</div>';
  elements.pagination.replaceChildren();
  try {
    const [dashboard, notices] = await Promise.all([
      request("/dashboard"),
      request("/notices?per_page=5"),
    ]);
    renderSummary(dashboard.data.summary);
    renderTable("notices", notices.data, false);
  } catch (error) {
    elements.dashboardSummary.replaceChildren();
    elements.tableContainer.replaceChildren(makeEmpty(error.message, "⚠"));
    toast(error.message, true);
  }
}

async function loadProfile() {
  clearTimeout(state.searchTimer);
  state.entity = null;
  setActiveNav("profile");
  elements.currentPage.textContent = "My profile";
  elements.pageHeading.replaceChildren();
  const greeting = document.createElement("div");
  greeting.className = "greeting-label";
  greeting.textContent = "YOUR CAMPUS ID";
  const title = document.createElement("h1");
  title.textContent = "My profile";
  const subtitle = document.createElement("p");
  subtitle.textContent = "Your student information and account details.";
  elements.pageHeading.append(greeting, title, subtitle);
  elements.dashboardSummary.classList.add("hidden");
  elements.contentCard.classList.add("hidden");
  elements.profileCard.classList.remove("hidden");
  elements.profileCard.replaceChildren(makeEmpty("Loading your profile...", "♙"));
  elements.searchInput.disabled = true;
  elements.filterField.disabled = true;
  try {
    const response = await request("/auth/me");
    const user = response.data;
    let departmentName = "Not assigned";
    if (user.department_id) {
      const departments = await loadOptions("departments");
      departmentName = departments.find((department) => department.id === user.department_id)?.name || departmentName;
    }
    const details = [
      ["Full name", user.full_name],
      ["College email", user.email],
      ["Role", user.role],
      ["Student number", user.student_number || "Not assigned"],
      ["Department", departmentName],
      ["Member since", user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"],
    ];
    elements.profileCard.replaceChildren();
    for (const [label, value] of details) {
      const item = document.createElement("article");
      item.className = "profile-detail";
      const name = document.createElement("span");
      name.textContent = label;
      const content = document.createElement("strong");
      content.textContent = value;
      item.append(name, content);
      elements.profileCard.append(item);
    }
  } catch (error) {
    elements.profileCard.replaceChildren(makeEmpty(error.message, "⚠"));
    toast(error.message, true);
  }
}

function renderSummary(summary) {
  elements.dashboardSummary.replaceChildren();
  const cards = Object.entries(summary);
  const icons = ["♙", "▤", "◷", "↗", "▦"];
  const label = (key) => key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  cards.forEach(([key, value], index) => {
    const card = document.createElement("article");
    card.className = "summary-card";
    const top = document.createElement("div");
    top.className = "summary-top";
    const name = document.createElement("span");
    name.textContent = label(key);
    const icon = document.createElement("span");
    icon.className = "summary-icon";
    icon.textContent = icons[index % icons.length];
    top.append(name, icon);
    const number = document.createElement("div");
    number.className = "summary-value";
    number.textContent = key.includes("percentage") ? `${value}%` : String(value);
    const foot = document.createElement("span");
    foot.className = "summary-foot";
    foot.textContent = "Updated just now";
    card.append(top, number, foot);
    elements.dashboardSummary.append(card);
  });
}

function configureFilters(entity) {
  const config = RESOURCE_CONFIG[entity];
  elements.filterField.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = config.filters.length ? "Filter" : "No filters";
  elements.filterField.append(placeholder);
  elements.filterField.disabled = !config.filters.length;
  elements.filterValue.classList.add("hidden");
  elements.applyFilter.classList.add("hidden");
  for (const [field, label] of config.filters) {
    const option = document.createElement("option");
    option.value = field;
    option.textContent = label;
    elements.filterField.append(option);
  }
}

async function loadResource(entity) {
  clearTimeout(state.searchTimer);
  state.entity = entity;
  state.page = 1;
  state.search = "";
  state.filter = null;
  elements.searchInput.value = "";
  elements.filterValue.value = "";
  setActiveNav(entity);
  elements.dashboardSummary.classList.add("hidden");
  elements.profileCard.classList.add("hidden");
  elements.contentCard.classList.remove("hidden");
  elements.searchInput.disabled = false;
  const config = RESOURCE_CONFIG[entity];
  elements.currentPage.textContent = config.label;
  elements.pageHeading.replaceChildren();
  const greeting = document.createElement("div");
  greeting.className = "greeting-label";
  greeting.textContent = "CAMPUS DIRECTORY";
  const title = document.createElement("h1");
  title.textContent = config.label;
  const subtitle = document.createElement("p");
  subtitle.textContent = config.description;
  elements.pageHeading.append(greeting, title, subtitle);
  elements.listTitle.textContent = config.label;
  elements.listDescription.textContent = config.description;
  elements.searchInput.placeholder = `Search ${config.label.toLowerCase()}...`;
  configureFilters(entity);
  elements.addRecord.classList.toggle("hidden", !canCreate(entity));
  await refreshResource();
}

function canCreate(entity) {
  if (state.user.role === "admin") return true;
  if (state.user.role === "student" && entity === "enrollments") return true;
  return state.user.role === "faculty" && ["attendance", "examinations", "results"].includes(entity);
}

function canEdit(entity) {
  if (state.user.role === "admin") return true;
  return state.user.role === "faculty" && ["courses", "attendance", "examinations", "results"].includes(entity);
}

async function refreshResource() {
  const entity = state.entity;
  if (!entity) return;
  const config = RESOURCE_CONFIG[entity];
  elements.tableContainer.innerHTML = '<div class="empty-state"><span>✳</span>Loading records...</div>';
  elements.pagination.replaceChildren();
  try {
    const params = new URLSearchParams({ page: String(state.page), per_page: "20" });
    if (state.search) params.set("q", state.search);
    if (state.filter) params.set(state.filter.field, state.filter.value);
    const response = await request(`/${entity}?${params}`);
    state.totalPages = response.meta.pages;
    renderTable(entity, response.data, true);
    renderPagination(response.meta);
  } catch (error) {
    elements.tableContainer.replaceChildren(makeEmpty(error.message, "⚠"));
    toast(error.message, true);
  }
}

function renderTable(entity, rows, actions) {
  const config = RESOURCE_CONFIG[entity];
  if (!rows.length) {
    elements.tableContainer.replaceChildren(makeEmpty("Nothing to show just yet."));
    return;
  }
  const table = document.createElement("table");
  table.className = "data-table";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const [, label] of config.columns) {
    const th = document.createElement("th");
    th.textContent = label;
    headRow.append(th);
  }
  if (actions && (canEdit(entity) || state.user.role === "admin")) {
    const th = document.createElement("th");
    th.textContent = "Actions";
    headRow.append(th);
  }
  head.append(headRow);
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const [field] of config.columns) {
      const td = document.createElement("td");
      const value = row[field];
      td.textContent = formatValue(field, value);
      if (field === "status") {
        const pill = document.createElement("span");
        pill.className = `status-pill ${String(value || "").replace(/[^a-z0-9-]/gi, "")}`;
        pill.textContent = formatValue(field, value);
        td.replaceChildren(pill);
      }
      tr.append(td);
    }
    if (actions && (canEdit(entity) || state.user.role === "admin")) {
      const td = document.createElement("td");
      const actionWrap = document.createElement("div");
      actionWrap.className = "table-actions";
      if (canEdit(entity)) {
        const edit = document.createElement("button");
        edit.className = "table-action";
        edit.type = "button";
        edit.textContent = "Edit";
        edit.addEventListener("click", () => {
          openRecordDialog(entity, row).catch((error) => toast(error.message, true));
        });
        actionWrap.append(edit);
      }
      if (state.user.role === "admin" || state.user.role === "faculty") {
        const remove = document.createElement("button");
        remove.className = "table-action delete";
        remove.type = "button";
        remove.textContent = "Delete";
        remove.addEventListener("click", () => deleteRecord(entity, row));
        actionWrap.append(remove);
      }
      td.append(actionWrap);
      tr.append(td);
    }
    body.append(tr);
  }
  table.append(head, body);
  elements.tableContainer.replaceChildren(table);
}

function formatValue(field, value) {
  if (value === null || value === undefined || value === "") return "—";
  if (field === "created_at") {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString();
  }
  return String(value);
}

function makeEmpty(message, icon = "✧") {
  const stateEl = document.createElement("div");
  stateEl.className = "empty-state";
  const symbol = document.createElement("span");
  symbol.textContent = icon;
  const text = document.createElement("p");
  text.textContent = message;
  stateEl.append(symbol, text);
  return stateEl;
}

function renderPagination(meta) {
  elements.pagination.replaceChildren();
  if (meta.total === 0) return;
  const label = document.createElement("span");
  label.textContent = `Page ${meta.page} of ${Math.max(1, meta.pages)} · ${meta.total} records`;
  const previous = document.createElement("button");
  previous.type = "button";
  previous.textContent = "←";
  previous.disabled = meta.page <= 1;
  previous.addEventListener("click", () => { state.page -= 1; refreshResource(); });
  const next = document.createElement("button");
  next.type = "button";
  next.textContent = "→";
  next.disabled = meta.page >= meta.pages;
  next.addEventListener("click", () => { state.page += 1; refreshResource(); });
  elements.pagination.append(label, previous, next);
}

async function loadOptions(resource, role) {
  const query = role ? `?role=${encodeURIComponent(role)}&per_page=100` : "?per_page=100";
  const response = await request(`/${resource}${query}`);
  return response.data;
}

async function openRecordDialog(entity, record = null) {
  state.editing = record;
  const config = RESOURCE_CONFIG[entity];
  elements.dialogTitle.textContent = record ? `Edit ${config.label.toLowerCase().replace(/s$/, "")}` : `Add ${config.label.toLowerCase().replace(/s$/, "")}`;
  elements.dialogSave.textContent = record ? "Save changes" : "Save record";
  elements.recordFields.replaceChildren();
  for (const [field, label, type, choices, role] of config.fields) {
    if (state.user.role === "faculty" && entity === "courses" && !["title", "description"].includes(field)) continue;
    if (state.user.role === "student" && entity === "enrollments" && field === "student_id") continue;
    if (state.user.role === "student" && entity === "enrollments" && field === "status") continue;
    const wrapper = document.createElement("div");
    if (type === "textarea") wrapper.className = "field-wide";
    const labelEl = document.createElement("label");
    const inputId = `record-${field}`;
    labelEl.htmlFor = inputId;
    labelEl.textContent = label;
    let input;
    if (type === "select" || type === "resource") {
      input = document.createElement("select");
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "Choose...";
      input.append(empty);
      const options = type === "resource" ? await loadOptions(choices, role) : choices;
      for (const option of options) {
        const optionEl = document.createElement("option");
        if (type === "resource") {
          optionEl.value = String(option.id);
          optionEl.textContent = option.full_name || option.title || option.name || option.code;
        } else {
          [optionEl.value, optionEl.textContent] = option;
        }
        input.append(optionEl);
      }
    } else {
      input = document.createElement(type === "textarea" ? "textarea" : "input");
      if (type !== "textarea") input.type = type;
      if (type === "number") input.step = "any";
      if (type === "password") input.minLength = 10;
    }
    input.id = inputId;
    input.name = field;
    if (record && field !== "password" && record[field] !== null && record[field] !== undefined) {
      input.value = String(record[field]);
    }
    if (!record && ["credits", "total_marks"].includes(field)) input.value = field === "credits" ? "3" : "";
    if (record && field === "password") input.required = false;
    wrapper.append(labelEl, input);
    elements.recordFields.append(wrapper);
  }
  elements.recordDialog.classList.remove("hidden");
}

async function saveRecord(event) {
  event.preventDefault();
  const entity = state.entity;
  const payload = {};
  for (const input of elements.recordForm.elements) {
    if (!input.name || input.value === "") continue;
    if (input.type === "number" || ["department_id", "faculty_id", "student_id", "course_id", "enrollment_id", "examination_id"].includes(input.name)) {
      payload[input.name] = Number(input.value);
    } else payload[input.name] = input.value;
  }
  const id = state.editing && state.editing.id;
  try {
    await request(`/${entity}${id ? `/${id}` : ""}`, {
      method: id ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    closeDialog();
    toast(id ? "Changes saved." : "Record added.");
    refreshResource();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteRecord(entity, record) {
  const label = record.full_name || record.title || record.name || record.code || "this record";
  if (!window.confirm(`Delete ${label}? This action cannot be undone.`)) return;
  try {
    await request(`/${entity}/${record.id}`, { method: "DELETE" });
    toast("Record deleted.");
    refreshResource();
  } catch (error) {
    toast(error.message, true);
  }
}

function closeDialog() {
  elements.recordDialog.classList.add("hidden");
  elements.recordForm.reset();
  elements.recordFields.replaceChildren();
  state.editing = null;
}

function setupEvents() {
  elements.authSwitch.addEventListener("click", () => {
    setAuthMode(elements.authForm.dataset.mode !== "register");
    elements.authNotice.classList.add("hidden");
  });
  elements.authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const registering = elements.authForm.dataset.mode === "register";
    const payload = {
      email: elements.authEmail.value.trim(),
      password: elements.authPassword.value,
    };
    if (registering) {
      payload.full_name = elements.authName.value.trim();
      if (elements.authStudentNumber.value.trim()) payload.student_number = elements.authStudentNumber.value.trim();
    }
    elements.authSubmit.disabled = true;
    elements.authSubmit.textContent = registering ? "Creating account..." : "Signing in...";
    try {
      const response = await request(`/auth/${registering ? "register" : "login"}`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (registering) {
        elements.authPassword.value = "";
        setAuthMode(false);
        elements.authNotice.textContent = "Account created. Sign in to continue.";
        elements.authNotice.classList.remove("hidden");
      } else {
        showApp(response.data.user);
      }
    } catch (error) {
      elements.authNotice.textContent = error.message;
      elements.authNotice.classList.remove("hidden");
    } finally {
      elements.authSubmit.disabled = false;
      elements.authSubmit.innerHTML = elements.authForm.dataset.mode === "register" ? 'Create account <span>→</span>' : 'Sign in <span>→</span>';
    }
  });
  elements.logoutButton.addEventListener("click", async () => {
    try {
      await request("/auth/logout", { method: "POST", body: "{}" });
      displayAuth("You have signed out.");
    } catch (error) {
      toast(error.message, true);
    }
  });
  elements.addRecord.addEventListener("click", () => {
    openRecordDialog(state.entity).catch((error) => toast(error.message, true));
  });
  elements.recordForm.addEventListener("submit", saveRecord);
  elements.dialogClose.addEventListener("click", closeDialog);
  elements.dialogCancel.addEventListener("click", closeDialog);
  elements.recordDialog.addEventListener("click", (event) => {
    if (event.target === elements.recordDialog) closeDialog();
  });
  elements.menuButton.addEventListener("click", () => elements.sidebar.classList.toggle("open"));
  elements.notificationButton.addEventListener("click", () => loadResource("notices"));
  elements.searchInput.addEventListener("input", () => {
    state.search = elements.searchInput.value.trim();
    state.page = 1;
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => {
      if (state.entity) refreshResource();
      else if (state.user) loadDashboard();
    }, 250);
  });
  elements.filterField.addEventListener("change", async () => {
    const selected = elements.filterField.value;
    const config = RESOURCE_CONFIG[state.entity];
    const filter = config.filters.find((item) => item[0] === selected);
    elements.filterValue.replaceChildren();
    if (!filter) {
      elements.filterValue.classList.add("hidden");
      elements.applyFilter.classList.add("hidden");
      return;
    }
    elements.filterValue.classList.remove("hidden");
    elements.applyFilter.classList.remove("hidden");
    if (Array.isArray(filter[2])) {
      elements.filterValue.type = "text";
      elements.filterValue.placeholder = "Value";
      elements.filterValue.replaceChildren();
      const select = document.createElement("select");
      select.className = "filter-input";
      select.id = "filter-choice";
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "Choose...";
      select.append(empty);
      for (const [value, label] of filter[2]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.append(option);
      }
      elements.filterValue.replaceWith(select);
      elements.filterValue = select;
    } else if (typeof filter[2] === "string") {
      try {
        const options = await loadOptions(filter[2], filter[3]);
        const select = document.createElement("select");
        select.className = "filter-input";
        select.id = "filter-value";
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = "Choose...";
        select.append(empty);
        for (const option of options) {
          const item = document.createElement("option");
          item.value = String(option.id);
          item.textContent = option.full_name || option.title || option.name || option.code;
          select.append(item);
        }
        elements.filterValue.replaceWith(select);
        elements.filterValue = select;
      } catch (error) {
        toast(error.message, true);
      }
    } else {
      const input = document.createElement("input");
      input.id = "filter-value";
      input.className = "filter-input";
      input.placeholder = `Enter ${filter[1].toLowerCase()}`;
      if (filter[0] === "date") input.type = "date";
      elements.filterValue.replaceWith(input);
      elements.filterValue = input;
    }
  });
  elements.applyFilter.addEventListener("click", () => {
    const field = elements.filterField.value;
    const value = elements.filterValue.value.trim();
    if (!field || !value) {
      state.filter = null;
    } else {
      state.filter = { field, value };
    }
    state.page = 1;
    refreshResource();
  });
}

async function initialize() {
  setupEvents();
  try {
    const response = await request("/auth/me");
    showApp(response.data);
  } catch (error) {
    displayAuth(error.status === 401 ? "" : error.message);
  }
}

initialize();
