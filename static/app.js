
"use strict";

// ==================================================
// Neural Nexus — Frontend Application
// ==================================================

const $ = (selector) => window.document.querySelector(selector);

const state = {
    sessionId: null,
    documentId: null,
    sending: false,
    uploading: false,
    authenticated: false,
    typingElement: null,
    toastTimer: null,
};

const sessionList = $("#session-list");
const documentList = $("#document-list");
const messages = $("#messages");
const welcomePanel = $("#welcome-panel");
const chatPanel = $("#chat-panel");
const loginPanel = $("#login-panel");
const messageInput = $("#message-input");
const sendButton = $("#send-btn");
const errorBanner = $("#error-banner");
const documentSelect = $("#document-select");

// ==================================================
// Theme
// ==================================================

function applyTheme(theme) {
    const selectedTheme = theme === "light" ? "light" : "dark";

    window.document.documentElement.dataset.theme = selectedTheme;
    window.document.documentElement.style.colorScheme = selectedTheme;

    const themeIcon = $("#theme-icon");
    const themeLabel = $("#theme-label");
    const themeToggle = $("#theme-toggle");

    if (themeIcon) {
        themeIcon.textContent = selectedTheme === "dark" ? "☀" : "☾";
    }

    if (themeLabel) {
        themeLabel.textContent =
            selectedTheme === "dark" ? "Light mode" : "Dark mode";
    }

    if (themeToggle) {
        themeToggle.setAttribute(
            "aria-label",
            selectedTheme === "dark"
                ? "Switch to light mode"
                : "Switch to dark mode"
        );
    }
}

function initializeTheme() {
    let savedTheme = "dark";

    try {
        savedTheme =
            window.localStorage.getItem("neural-nexus-theme") || "dark";
    } catch {
        // Continue with dark mode if browser storage is unavailable.
    }

    applyTheme(savedTheme);
}

$("#theme-toggle")?.addEventListener("click", () => {
    const nextTheme =
        window.document.documentElement.dataset.theme === "dark"
            ? "light"
            : "dark";

    applyTheme(nextTheme);

    try {
        window.localStorage.setItem("neural-nexus-theme", nextTheme);
    } catch {
        // The selected theme still applies to the current page.
    }
});

// ==================================================
// API helper
// ==================================================

async function api(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    const isFormData = options.body instanceof FormData;

    if (options.body !== undefined && !isFormData) {
        headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
        ...options,
        headers,
        credentials: "same-origin",
    });

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error(
            `Unexpected server response (HTTP ${response.status}).`
        );
    }

    if (!response.ok) {
        const error = new Error(
            data.error || `Request failed (HTTP ${response.status}).`
        );

        error.status = response.status;
        throw error;
    }

    return data;
}

// ==================================================
// UI helpers
// ==================================================

function showToast(message) {
    const toast = $("#toast");

    if (!toast) return;

    toast.textContent = message;
    toast.classList.remove("hidden");

    if (state.toastTimer !== null) {
        window.clearTimeout(state.toastTimer);
    }

    state.toastTimer = window.setTimeout(() => {
        toast.classList.add("hidden");
        state.toastTimer = null;
    }, 3000);
}

function showError(message) {
    if (!errorBanner) return;

    errorBanner.textContent = message;
    errorBanner.classList.remove("hidden");
}

function clearError() {
    if (!errorBanner) return;

    errorBanner.textContent = "";
    errorBanner.classList.add("hidden");
}

function showLogin() {
    state.authenticated = false;
    state.sessionId = null;
    state.documentId = null;
    window.document.body.classList.add("auth-screen");

    chatPanel.classList.add("hidden");
    loginPanel.classList.remove("hidden");

    $("#logout-btn")?.classList.add("hidden");

    $("#user-label").textContent = "Not signed in";
    $("#user-subtitle").textContent = "Personal workspace";

    sessionList.replaceChildren();
    documentList.replaceChildren();

    const sessionNote = window.document.createElement("p");
    sessionNote.className = "muted";
    sessionNote.textContent = "Sign in to view conversations.";
    sessionList.append(sessionNote);

    const documentNote = window.document.createElement("p");
    documentNote.className = "muted";
    documentNote.textContent = "Sign in to view your documents.";
    documentList.append(documentNote);

    resetChat();
}

function showChat(user = null) {
    state.authenticated = true;
    window.document.body.classList.remove("auth-screen");

    loginPanel.classList.add("hidden");
    chatPanel.classList.remove("hidden");

    $("#logout-btn")?.classList.remove("hidden");

    if (user) {
        $("#user-label").textContent =
            user.username || user.email || "Signed in";

        $("#user-subtitle").textContent =
            user.email || "Personal workspace";

        const initial = (user.username || user.email || "U")
            .trim()
            .charAt(0)
            .toUpperCase();

        const avatar = $(".user-avatar");

        if (avatar) {
            avatar.textContent = initial || "U";
        }
    }
}

function showAuthView(view) {
    const isRegister = view === "register";

    $("#login-view").classList.toggle("hidden", isRegister);
    $("#register-view").classList.toggle("hidden", !isRegister);

    $("#login-error").textContent = "";
    $("#register-error").textContent = "";
}

function setChatTitle(title) {
    $("#page-title").textContent =
        title || "Ask your documents anything.";
}

function selectedFileLabel(text) {
    const element = $("#selected-file");

    if (!element) return;

    element.textContent = text || "";
    element.classList.toggle("hidden", !text);
}

function resetChat() {
    state.sessionId = null;

    messages.replaceChildren();
    messages.classList.add("hidden");
    welcomePanel.classList.remove("hidden");

    messageInput.value = "";
    messageInput.style.height = "auto";

    if (documentSelect) {
        documentSelect.value = "";
    }

    state.documentId = null;
    selectedFileLabel("");
    clearError();

    renderActiveSession();
    renderActiveDocument();
    setChatTitle("Ask your documents anything.");
}

function renderActiveSession() {
    window.document.querySelectorAll(".session-item").forEach((button) => {
        button.classList.toggle(
            "active",
            state.sessionId !== null &&
            Number(button.dataset.sessionId) === Number(state.sessionId)
        );
    });
}

function renderActiveDocument() {
    window.document.querySelectorAll(".document-item").forEach((button) => {
        button.classList.toggle(
            "active",
            state.documentId !== null &&
            Number(button.dataset.documentId) === Number(state.documentId)
        );
    });
}

// ==================================================
// Message rendering
// ==================================================

function addMessage(role, content, sources = []) {
    const article = window.document.createElement("article");

    article.className =
        `message ${role === "user" ? "user" : "assistant"}`;

    const label = window.document.createElement("div");
    label.className = "message-role";
    label.textContent = role === "user" ? "YOU" : "NEURAL NEXUS";

    const bubble = window.document.createElement("div");
    bubble.className = "message-bubble";

    // Display model output as plain text, never executable HTML.
    bubble.textContent = String(content ?? "");

    article.append(label, bubble);

    if (
        role === "assistant" &&
        Array.isArray(sources) &&
        sources.length > 0
    ) {
        const details = window.document.createElement("details");
        details.className = "source-list";

        const summary = window.document.createElement("summary");
        summary.textContent = `View sources (${sources.length})`;
        details.append(summary);

        const list = window.document.createElement("ul");

        for (const source of sources) {
            const item = window.document.createElement("li");

            if (typeof source === "string") {
                item.textContent = source;
            } else if (source && typeof source === "object") {
                item.textContent =
                    source.filename ||
                    source.original_filename ||
                    source.document_name ||
                    source.content ||
                    source.text ||
                    source.title ||
                    JSON.stringify(source);
            } else {
                item.textContent = String(source);
            }

            list.append(item);
        }

        details.append(list);
        article.append(details);
    }

    messages.append(article);

    article.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
    });

    return article;
}

function showTyping() {
    removeTyping();

    const indicator = window.document.createElement("div");
    indicator.className = "typing-indicator";
    indicator.setAttribute("role", "status");

    const dots = window.document.createElement("span");
    dots.className = "typing-dots";

    for (let index = 0; index < 3; index += 1) {
        dots.append(window.document.createElement("span"));
    }

    indicator.append(
        dots,
        window.document.createTextNode("Thinking...")
    );

    messages.append(indicator);
    state.typingElement = indicator;

    indicator.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
    });
}

function removeTyping() {
    if (state.typingElement) {
        state.typingElement.remove();
        state.typingElement = null;
    }
}

// ==================================================
// Conversation history
// ==================================================

async function loadSessions() {
    const data = await api("/api/chat/sessions");
    const sessions = Array.isArray(data.sessions) ? data.sessions : [];

    sessionList.replaceChildren();

    if (sessions.length === 0) {
        const empty = window.document.createElement("p");
        empty.className = "muted";
        empty.textContent = "No conversations yet. Start a new chat.";
        sessionList.append(empty);
        return;
    }

    for (const chat of sessions) {
        const button = window.document.createElement("button");

        button.type = "button";
        button.className = "session-item";
        button.dataset.sessionId = String(chat.id);
        button.textContent = chat.title || "Untitled conversation";
        button.title = chat.title || "Untitled conversation";

        button.addEventListener("click", () => {
            openSession(chat.id);
        });

        sessionList.append(button);
    }

    renderActiveSession();
}

async function openSession(sessionId) {
    clearError();

    try {
        const data = await api(
            `/api/chat/sessions/${encodeURIComponent(sessionId)}/messages`
        );

        state.sessionId = data.session_id;
        messages.replaceChildren();

        for (const message of data.messages || []) {
            addMessage(message.role, message.content);
        }

        welcomePanel.classList.add("hidden");
        messages.classList.remove("hidden");

        setChatTitle("Your conversation");
        renderActiveSession();
        messageInput.focus();
    } catch (error) {
        if (error.status === 401) {
            showLogin();
            showAuthView("login");
            return;
        }

        showError(error.message);
    }
}

// ==================================================
// Uploaded documents
// ==================================================

function documentName(docItem) {
    return (
        docItem.original_filename ||
        docItem.filename ||
        docItem.name ||
        `Document ${docItem.id}`
    );
}

function documentTypeLabel(filename) {
    const extension = filename.split(".").pop().toLowerCase();

    if (extension === "pdf") return "PDF";
    if (extension === "docx") return "DOCX";
    if (extension === "txt") return "TXT";

    return extension.toUpperCase() || "FILE";
}

async function loadDocuments() {
    const data = await api("/api/documents");
    const documents = Array.isArray(data.documents) ? data.documents : [];

    documentList.replaceChildren();
    documentSelect.replaceChildren();

    const allOption = window.document.createElement("option");
    allOption.value = "";
    allOption.textContent = "All documents";
    documentSelect.append(allOption);

    if (documents.length === 0) {
        const empty = window.document.createElement("p");
        empty.className = "muted";
        empty.textContent = "No documents uploaded yet.";
        documentList.append(empty);
    }

    for (const docItem of documents) {
        if (docItem.id == null) continue;

        const name = documentName(docItem);

        const button = window.document.createElement("button");
        button.type = "button";
        button.className = "document-item";
        button.dataset.documentId = String(docItem.id);
        button.title = name;

        const icon = window.document.createElement("span");
        icon.className = "document-icon";
        icon.textContent = documentTypeLabel(name);

        const label = window.document.createElement("span");
        label.className = "document-name";
        label.textContent = name;

        button.append(icon, label);

        button.addEventListener("click", () => {
            state.documentId = Number(docItem.id);
            documentSelect.value = String(docItem.id);

            renderActiveDocument();
            selectedFileLabel(`Selected document: ${name}`);
            showToast("Questions will target this document.");
            messageInput.focus();
        });

        documentList.append(button);

        const option = window.document.createElement("option");
        option.value = String(docItem.id);
        option.textContent = name;
        documentSelect.append(option);
    }

    const selectionExists =
        state.documentId !== null &&
        documents.some(
            (docItem) => Number(docItem.id) === Number(state.documentId)
        );

    if (!selectionExists) {
        state.documentId = null;
    }

    documentSelect.value =
        state.documentId === null ? "" : String(state.documentId);

    renderActiveDocument();
}

documentSelect.addEventListener("change", () => {
    const value = documentSelect.value;

    state.documentId = value ? Number(value) : null;
    renderActiveDocument();

    if (state.documentId === null) {
        selectedFileLabel("");
    } else {
        const selectedOption =
            documentSelect.options[documentSelect.selectedIndex];

        selectedFileLabel(
            `Selected document: ${selectedOption.textContent}`
        );
    }
});

// ==================================================
// Upload PDF, DOCX, and TXT documents
// ==================================================

async function uploadDocument(file) {
    if (state.uploading || !file) return;

    clearError();

    const extension = file.name.split(".").pop().toLowerCase();
    const supportedExtensions = ["pdf", "docx", "txt"];

    if (!supportedExtensions.includes(extension)) {
        showError("Please choose a PDF, DOCX, or TXT file.");
        return;
    }

    if (file.size <= 0) {
        showError("The selected file is empty.");
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        showError("The file exceeds the 10 MB upload limit.");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    state.uploading = true;
    selectedFileLabel(`Uploading and processing ${file.name}...`);

    try {
        const data = await api("/api/documents/upload", {
            method: "POST",
            body: formData,
        });

        const uploadedDocument = data.document;

        if (!uploadedDocument || uploadedDocument.id == null) {
            throw new Error(
                "Upload succeeded, but the response did not include a document ID."
            );
        }

        state.documentId = Number(uploadedDocument.id);

        await loadDocuments();

        documentSelect.value = String(state.documentId);
        renderActiveDocument();

        selectedFileLabel(
            `Ready: ${documentName(uploadedDocument)} · ${data.chunk_count ?? "Processed"
            } chunks`
        );

        showToast("Document uploaded and processed successfully.");
    } catch (error) {
        if (error.status === 401) {
            showLogin();
            showAuthView("login");
            return;
        }

        selectedFileLabel("");
        showError(error.message);
    } finally {
        state.uploading = false;
    }
}

$("#sidebar-file-input").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];

    if (file) {
        await uploadDocument(file);
    }

    event.target.value = "";
});

$("#composer-file-input").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];

    if (file) {
        await uploadDocument(file);
    }

    event.target.value = "";
});

// ==================================================
// Chat
// ==================================================

async function sendMessage(text) {
    if (state.sending || !text.trim()) return;

    clearError();

    state.sending = true;
    sendButton.disabled = true;
    sendButton.textContent = "Thinking…";

    welcomePanel.classList.add("hidden");
    messages.classList.remove("hidden");

    addMessage("user", text.trim());
    showTyping();

    const payload = {
        message: text.trim(),
    };

    if (state.sessionId !== null) {
        payload.session_id = state.sessionId;
    }

    if (state.documentId !== null) {
        payload.document_id = state.documentId;
    }

    try {
        const data = await api("/api/chat", {
            method: "POST",
            body: JSON.stringify(payload),
        });

        state.sessionId = data.session_id;

        removeTyping();

        addMessage(
            "assistant",
            data.answer,
            data.sources || []
        );

        renderActiveSession();
        await loadSessions();
        showChat();
    } catch (error) {
        removeTyping();

        if (error.status === 401) {
            showLogin();
            showAuthView("login");
            return;
        }

        showError(error.message);
        showToast("The assistant could not answer this message.");
    } finally {
        state.sending = false;
        sendButton.disabled = false;
        sendButton.innerHTML = 'Send <span>↑</span>';
    }
}

$("#chat-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const text = messageInput.value.trim();

    if (!text || state.sending) return;

    messageInput.value = "";
    messageInput.style.height = "auto";

    await sendMessage(text);
});

messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";

    messageInput.style.height =
        `${Math.min(messageInput.scrollHeight, 180)}px`;
});

messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        $("#chat-form").requestSubmit();
    }
});

// ==================================================
// New conversation and prompt suggestions
// ==================================================

$("#new-chat-btn").addEventListener("click", () => {
    resetChat();
    messageInput.focus();
});

window.document.querySelectorAll(".suggestion").forEach((button) => {
    button.addEventListener("click", () => {
        messageInput.value = button.dataset.prompt || "";
        messageInput.focus();
        messageInput.dispatchEvent(new Event("input"));
    });
});

// ==================================================
// Authentication: sign in and create account
// ==================================================

$("#show-register").addEventListener("click", () => {
    showAuthView("register");
});

$("#show-login").addEventListener("click", () => {
    showAuthView("login");
});

$("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const errorBox = $("#login-error");
    errorBox.textContent = "";

    const identifier = $("#identifier").value.trim();
    const password = $("#password").value;

    try {
        const data = await api("/api/auth/login", {
            method: "POST",
            body: JSON.stringify({ identifier, password }),
        });

        showChat(data.user);
        resetChat();

        await Promise.all([
            loadSessions(),
            loadDocuments(),
        ]);

        showToast("Welcome back!");
    } catch (error) {
        errorBox.textContent = error.message;
    }
});

$("#register-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const errorBox = $("#register-error");
    errorBox.textContent = "";

    const username = $("#register-username").value.trim();
    const email = $("#register-email").value.trim();
    const password = $("#register-password").value;

    if (username.length < 3) {
        errorBox.textContent =
            "Username must contain at least 3 characters.";
        return;
    }

    if (password.length < 8) {
        errorBox.textContent =
            "Password must contain at least 8 characters.";
        return;
    }

    try {
        await api("/api/auth/register", {
            method: "POST",
            body: JSON.stringify({ username, email, password }),
        });

        // Sign in through the existing backend login endpoint.
        const data = await api("/api/auth/login", {
            method: "POST",
            body: JSON.stringify({
                identifier: email,
                password,
            }),
        });

        showChat(data.user);
        resetChat();

        await Promise.all([
            loadSessions(),
            loadDocuments(),
        ]);

        showToast("Account created successfully!");
    } catch (error) {
        errorBox.textContent = error.message;
    }
});

// ==================================================
// Logout
// ==================================================

$("#logout-btn").addEventListener("click", async () => {
    try {
        await api("/api/auth/logout", {
            method: "POST",
            body: JSON.stringify({}),
        });
    } catch {
        showToast("Could not confirm sign out. Please refresh the page.");
        return;
    }

    resetChat();
    showLogin();
    showAuthView("login");

    $("#login-form").reset();

    showToast("You have signed out.");
});

// ==================================================
// App initialization
// ==================================================

async function initialize() {
    initializeTheme();

    try {
        const data = await api("/api/auth/me");

        showChat(data.user);

        await Promise.all([
            loadSessions(),
            loadDocuments(),
        ]);
    } catch (error) {
        showLogin();
        showAuthView("login");

        if (error.status !== 401) {
            $("#login-error").textContent =
                `Unable to connect to the backend: ${error.message}`;
        }
    }
}

initialize();

