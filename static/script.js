// Configuration state
let configData = {};
let editors = {
  json: null,
  yaml: null,
};
let ws;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// API service for interacting with the backend
const apiService = {
  // Get all configuration
  async fetchConfig() {
    const response = await fetch("/api/config");
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  },

  // Update multiple configuration values
  async updateConfig(config) {
    const response = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        `HTTP error! status: ${response.status}${
          errorData.detail ? ` - ${errorData.detail}` : ""
        }`
      );
    }

    return await response.json();
  },

  // Get a specific configuration path
  async getConfigPath(path) {
    const response = await fetch(`/api/config/${path}`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  },

  // Set a specific configuration path
  async setConfigPath(path, value) {
    const response = await fetch(`/api/config/${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  },

  // Delete a specific configuration path
  async deleteConfigPath(path) {
    const response = await fetch(`/api/config/${path}`, {
      method: "DELETE",
    });

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  },

  // Reload configuration from disk
  async reloadConfig() {
    const response = await fetch("/api/config/reload", {
      method: "POST",
    });

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  },

  // Validate configuration against schema
  async validateConfig() {
    const response = await fetch("/api/config/validate", {
      method: "POST",
    });

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  },
};

// Improved WebSocket service with better reconnection handling
const wsService = {
  init() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    if (ws?.readyState === WebSocket.OPEN) return;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected 😺");
      reconnectAttempts = 0;
      notify.success("Connected to server!");
    };

    ws.onmessage = ({ data }) => {
      try {
        const { type, data: configUpdate } = JSON.parse(data);
        if (type === "config") {
          configData = configUpdate;
          updateUIWithNewConfig();
          notify.success("Configuration updated 🐱");
        }
      } catch (error) {
        console.error("WebSocket message error:", error);
        notify.error("Failed to process server update 😿");
      }
    };

    ws.onclose = () => {
      if (reconnectAttempts++ < MAX_RECONNECT_ATTEMPTS) {
        notify.warning(
          `Connection lost, retrying... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}) 🔄`
        );
        setTimeout(
          wsService.init,
          Math.min(1000 * Math.pow(2, reconnectAttempts), 10000)
        );
      } else {
        notify.error("Connection lost! Please refresh the page 😿");
      }
    };

    ws.onerror = () => {
      notify.error("WebSocket error occurred 😿");
    };
  },
};

// Initialize the application
document.addEventListener("DOMContentLoaded", initializeApp);

// Main initialization function
async function initializeApp() {
  initializeTheme();
  setupTabs();
  setupEventListeners();
  await fetchInitialConfig();
}

// Update UI when config changes
function updateUIWithNewConfig() {
  updateEditors();
  renderVisualEditor();
}

// Set up all event listeners
function setupEventListeners() {
  document.getElementById("save-btn").addEventListener("click", saveConfig);
  document
    .getElementById("theme-toggle")
    .addEventListener("click", toggleTheme);
  document.getElementById("export-btn").addEventListener("click", exportConfig);
  document.getElementById("import-btn").addEventListener("click", importConfig);
  document.getElementById("reload-btn").addEventListener("click", reloadConfig);
  document
    .getElementById("validate-btn")
    .addEventListener("click", validateConfig);

  // Add input validation for the visual editor with debounce
  document
    .getElementById("visual-editor")
    .addEventListener("input", debounce(validateInput, 300));

  // Add keyboard shortcuts
  document.addEventListener("keydown", handleKeyboardShortcuts);
}

// Enhanced keyboard shortcuts with better feedback
function handleKeyboardShortcuts(e) {
  if (!e.ctrlKey && !e.metaKey) return;

  const shortcuts = {
    s: saveConfig,
    e: exportConfig,
    i: importConfig,
    r: reloadConfig,
    v: validateConfig,
  };

  const action = shortcuts[e.key.toLowerCase()];
  if (action) {
    e.preventDefault();
    action();
  }
}

// Set up tab switching functionality
function setupTabs() {
  const tabButtons = document.querySelectorAll(".tab-button");

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-target");

      // Remove active class from all buttons and panes
      document.querySelectorAll(".tab-button").forEach((btn) => {
        btn.classList.remove("active");
        btn.setAttribute("aria-selected", "false");
      });

      document.querySelectorAll(".tab-pane").forEach((pane) => {
        pane.classList.remove("active");
      });

      // Add active class to clicked button and corresponding pane
      button.classList.add("active");
      button.setAttribute("aria-selected", "true");
      document.getElementById(targetId).classList.add("active");
    });
  });
}

// Notification system
const notify = {
  create(type, message, duration = 5000) {
    // Create elements
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;
    notification.setAttribute("role", "alert");

    const content = document.createElement("div");
    content.className = "notification-content";
    content.textContent = message;

    const closeBtn = document.createElement("button");
    closeBtn.className = "close-btn";
    closeBtn.innerHTML = "&times;";
    closeBtn.setAttribute("aria-label", "Close notification");

    // Add event listener to close button
    closeBtn.addEventListener("click", () => {
      this.dismiss(notification);
    });

    // Append elements
    notification.appendChild(content);
    notification.appendChild(closeBtn);

    // Add to container
    const container = document.getElementById("notification-container");
    container.appendChild(notification);

    // Auto-dismiss
    if (duration) {
      setTimeout(() => this.dismiss(notification), duration);
    }

    return notification;
  },

  dismiss(notification) {
    if (!notification.parentNode) return;

    notification.style.opacity = "0";
    notification.style.transform = "translateX(20px)";
    setTimeout(() => notification.remove(), 300);
  },

  success: (message) => notify.create("success", message),
  error: (message) => notify.create("error", message),
  warning: (message) => notify.create("warning", message),
};

// Theme management
function initializeTheme() {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const savedTheme =
    localStorage.getItem("theme") || (prefersDark ? "dark" : "light");

  setTheme(savedTheme);

  // Listen for system theme changes
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", (e) => {
      if (!localStorage.getItem("theme")) {
        setTheme(e.matches ? "dark" : "light");
      }
    });
}

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  updateThemeToggleIcons(theme === "dark");
  updateEditorThemes(theme === "dark");
}

function updateThemeToggleIcons(isDark) {
  document.getElementById("moon-icon").style.display = isDark
    ? "none"
    : "block";
  document.getElementById("sun-icon").style.display = isDark ? "block" : "none";
}

function toggleTheme() {
  const currentTheme =
    document.documentElement.getAttribute("data-theme") || "light";
  const newTheme = currentTheme === "light" ? "dark" : "light";

  localStorage.setItem("theme", newTheme);
  setTheme(newTheme);
}

function updateEditorThemes(isDark) {
  if (editors.json) {
    editors.json.updateOptions({
      theme: isDark ? "nekoconf-dark" : "vs-light",
    });
  }
  if (editors.yaml) {
    editors.yaml.updateOptions({
      theme: isDark ? "nekoconf-dark" : "vs-light",
    });
  }
}

// Show/hide loading indicator
function toggleLoading(show) {
  const loader = document.querySelector(".tab-pane-loader");
  loader.hidden = !show;

  if (show) {
    document.body.classList.add("loading-neko");
  } else {
    document.body.classList.remove("loading-neko");
  }
}

// Data fetching
async function fetchInitialConfig() {
  toggleLoading(true);

  try {
    configData = await apiService.fetchConfig();
    initMonacoEditor();
    renderVisualEditor();
    wsService.init();
  } catch (error) {
    console.error("Error fetching configuration:", error);
    notify.error(
      "Failed to load configuration. Please try refreshing the page."
    );
  } finally {
    toggleLoading(false);
  }
}

// Monaco Editor initialization
function initMonacoEditor() {
  require.config({
    paths: {
      vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.33.0/min/vs",
    },
  });

  require(["vs/editor/editor.main"], function () {
    setupMonacoThemes();
    createJsonEditor();
    createYamlEditor();
  });
}

// Improved Monaco theme with better contrast and kawaii colors
function setupMonacoThemes() {
  monaco.editor.defineTheme("nekoconf-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "string", foreground: "#ffb3b3" }, // Soft pink for strings
      { token: "number", foreground: "#b3e6ff" }, // Soft blue for numbers
      { token: "keyword", foreground: "#ff99cc" }, // Pink for keywords
      { token: "comment", foreground: "#a6a6a6", fontStyle: "italic" },
    ],
    colors: {
      "editor.background": "#1a1a1a",
      "editor.foreground": "#f0f0f0",
      "editorCursor.foreground": "#ff99cc",
      "editor.lineHighlightBackground": "#ff99cc15",
      "editor.selectionBackground": "#ff99cc40",
      "editorLineNumber.foreground": "#666666",
      "editorLineNumber.activeForeground": "#ff99cc",
    },
  });
}

function createJsonEditor() {
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";

  editors.json = monaco.editor.create(document.getElementById("json-editor"), {
    value: JSON.stringify(configData, null, 2),
    language: "json",
    theme: isDark ? "nekoconf-dark" : "vs-light",
    automaticLayout: true,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    fontSize: 14,
    lineNumbers: "on",
    renderLineHighlight: "all",
    formatOnPaste: true,
    formatOnType: true,
    bracketPairColorization: { enabled: true },
  });

  // Add validation to JSON editor
  editors.json.onDidChangeModelContent(
    debounce(() => {
      try {
        JSON.parse(editors.json.getValue());
        monaco.editor.setModelMarkers(
          editors.json.getModel(),
          "json-validation",
          []
        );
      } catch (e) {
        // Mark the error in the editor
        const errorMatch = e.message.match(/at position (\d+)/);
        if (errorMatch) {
          const pos = parseInt(errorMatch[1]);
          const position = editors.json.getModel().getPositionAt(pos);
          monaco.editor.setModelMarkers(
            editors.json.getModel(),
            "json-validation",
            [
              {
                severity: monaco.MarkerSeverity.Error,
                message: e.message,
                startLineNumber: position.lineNumber,
                startColumn: position.column,
                endLineNumber: position.lineNumber,
                endColumn: position.column + 1,
              },
            ]
          );
        }
      }
    }, 300)
  );
}

function createYamlEditor() {
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";

  editors.yaml = monaco.editor.create(document.getElementById("yaml-editor"), {
    value: jsyaml.dump(configData),
    language: "yaml",
    theme: isDark ? "nekoconf-dark" : "vs-light",
    automaticLayout: true,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    fontSize: 14,
    lineNumbers: "on",
    renderLineHighlight: "all",
    bracketPairColorization: { enabled: true },
  });

  // Add validation to YAML editor
  editors.yaml.onDidChangeModelContent(
    debounce(() => {
      try {
        jsyaml.load(editors.yaml.getValue());
        monaco.editor.setModelMarkers(
          editors.yaml.getModel(),
          "yaml-validation",
          []
        );
      } catch (e) {
        if (e.mark) {
          monaco.editor.setModelMarkers(
            editors.yaml.getModel(),
            "yaml-validation",
            [
              {
                severity: monaco.MarkerSeverity.Error,
                message: e.reason,
                startLineNumber: e.mark.line + 1,
                startColumn: e.mark.column + 1,
                endLineNumber: e.mark.line + 1,
                endColumn: e.mark.column + 2,
              },
            ]
          );
        }
      }
    }, 300)
  );
}

// Update editors with current config data
function updateEditors() {
  if (editors.json) {
    editors.json.setValue(JSON.stringify(configData, null, 2));
  }
  if (editors.yaml) {
    editors.yaml.setValue(jsyaml.dump(configData));
  }
}

// Simplified visual editor rendering
function renderVisualEditor() {
  const container = document.getElementById("visual-editor");
  container.innerHTML = `
    <div class="form-header">
      <h3>Visual Configuration Editor</h3>
      <p>Edit your configuration with an intuitive interface 🐱</p>
    </div>
    <form class="form-container">
      ${renderConfigSections(configData)}
    </form>
  `;
}

function renderConfigSections(data, path = "") {
  return Object.entries(data)
    .map(([key, value]) => {
      const currentPath = path ? `${path}.${key}` : key;
      return isObject(value)
        ? renderSection(key, value, currentPath)
        : renderField(key, value, currentPath);
    })
    .join("");
}

function renderSection(key, value, path) {
  return `
    <fieldset data-path="${path}">
      <legend>${formatKeyName(key)}</legend>
      <div class="form-row">
        ${renderConfigSections(value, path)}
      </div>
    </fieldset>
  `;
}

function renderField(key, value, path) {
  const type = typeof value;
  const inputHtml =
    type === "boolean"
      ? renderBooleanField(value, path)
      : type === "number"
      ? renderNumberField(value, path)
      : Array.isArray(value)
      ? renderArrayField(value, path)
      : renderTextField(value, path);

  return `
    <div class="form-group">
      <label class="form-label" for="${path}">${formatKeyName(key)}</label>
      ${inputHtml}
    </div>
  `;
}

function renderBooleanField(value, path) {
  return `
    <div class="form-check">
      <input type="checkbox" class="form-check-input" id="${path}" ${
    value ? "checked" : ""
  } data-path="${path}" data-type="boolean">
      <label class="form-check-label" for="${path}">${
    value ? "Enabled" : "Disabled"
  }</label>
    </div>
  `;
}

function renderNumberField(value, path) {
  return `<input type="number" class="form-control" id="${path}" value="${value}" step="any" data-path="${path}" data-type="number">`;
}

function renderArrayField(value, path) {
  return `<textarea class="form-control" id="${path}" data-path="${path}" data-type="array" rows="${Math.min(
    value.length + 2,
    5
  )}">${JSON.stringify(value, null, 2)}</textarea>`;
}

function renderTextField(value, path) {
  return `<input type="text" class="form-control" id="${path}" value="${value}" data-path="${path}" data-type="string">`;
}

function isObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// Format key names for better readability
function formatKeyName(key) {
  return key
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}

// Validate input in the visual editor
function validateInput(event) {
  if (!event.target.matches("input, textarea")) return;

  const input = event.target;
  const type = input.getAttribute("data-type");

  if (type === "number") {
    const isValid = !isNaN(parseFloat(input.value));
    input.classList.toggle("is-invalid", !isValid);
  } else if (type === "array") {
    try {
      JSON.parse(input.value);
      input.classList.remove("is-invalid");
    } catch (e) {
      input.classList.add("is-invalid");
    }
  }
}

// Improved save functionality
async function saveConfig() {
  const saveBtn = document.getElementById("save-btn");
  saveBtn.disabled = true;

  try {
    const config = await getActiveTabConfig();
    await apiService.updateConfig(config);
    notify.success("Configuration saved successfully! 😺");
  } catch (error) {
    notify.error(`Failed to save: ${error.message} 😿`);
  } finally {
    saveBtn.disabled = false;
  }
}

async function getActiveTabConfig() {
  const activeTab = document.querySelector(".tab-button.active").dataset.target;

  switch (activeTab) {
    case "json":
      return validateAndParseJson();
    case "yaml":
      return validateAndParseYaml();
    default:
      return collectFormData();
  }
}

function validateAndParseJson() {
  try {
    return JSON.parse(editors.json.getValue());
  } catch (error) {
    throw new Error("Invalid JSON: " + error.message);
  }
}

function validateAndParseYaml() {
  try {
    return jsyaml.load(editors.yaml.getValue());
  } catch (error) {
    throw new Error("Invalid YAML: " + error.message);
  }
}

function collectFormData() {
  // Visual editor - collect values from form inputs
  const updatedConfig = structuredClone(configData);
  const inputs = document.querySelectorAll(
    "#visual-editor input, #visual-editor textarea"
  );
  let hasValidationErrors = false;

  inputs.forEach((input) => {
    const path = input.getAttribute("data-path");
    const type = input.getAttribute("data-type");
    if (!path) return;

    let value;

    if (type === "boolean") {
      value = input.checked;
    } else if (type === "number") {
      if (isNaN(parseFloat(input.value))) {
        input.classList.add("is-invalid");
        hasValidationErrors = true;
        return;
      }
      value = parseFloat(input.value);
    } else if (type === "array") {
      try {
        value = JSON.parse(input.value);
      } catch (e) {
        input.classList.add("is-invalid");
        hasValidationErrors = true;
        return;
      }
    } else {
      value = input.value;
    }

    // Set value in the config object
    setNestedValue(updatedConfig, path, value);
  });

  if (hasValidationErrors) {
    throw new Error("Please fix validation errors before saving");
  }

  return updatedConfig;
}

function setNestedValue(obj, path, value) {
  const pathParts = path.split(".");
  let current = obj;

  for (let i = 0; i < pathParts.length - 1; i++) {
    if (!current[pathParts[i]]) {
      current[pathParts[i]] = {};
    }
    current = current[pathParts[i]];
  }

  current[pathParts[pathParts.length - 1]] = value;
}

// Export configuration to file
function exportConfig() {
  const activeTabId = document
    .querySelector(".tab-button.active")
    .getAttribute("data-target");
  let content, filename, type;

  try {
    if (activeTabId === "json" || activeTabId === "visual") {
      content = JSON.stringify(
        activeTabId === "json"
          ? JSON.parse(editors.json.getValue())
          : configData,
        null,
        2
      );
      filename = "config.json";
      type = "application/json";
    } else if (activeTabId === "yaml") {
      content = editors.yaml.getValue();
      filename = "config.yaml";
      type = "text/yaml";
    }

    downloadFile(content, filename, type);
    notify.success(`Exported ${filename} successfully!`);
  } catch (error) {
    notify.error("Error exporting configuration: " + error.message);
  }
}

function downloadFile(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();

  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 0);
}

// Import configuration from file
function importConfig() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json,.yaml,.yml";

  input.onchange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        let newConfig;
        if (file.name.endsWith(".json")) {
          newConfig = JSON.parse(event.target.result);
        } else if (file.name.endsWith(".yaml") || file.name.endsWith(".yml")) {
          newConfig = jsyaml.load(event.target.result);
        }

        if (newConfig) {
          configData = newConfig;
          updateUIWithNewConfig();
          notify.success(`Imported ${file.name} successfully!`);
        }
      } catch (error) {
        console.error("Error parsing imported file:", error);
        notify.error(
          "Failed to import configuration. The file may be invalid."
        );
      }
    };

    reader.readAsText(file);
  };

  input.click();
}

// Reload config from server
async function reloadConfig() {
  try {
    toggleLoading(true);
    await apiService.reloadConfig();
    configData = await apiService.fetchConfig();
    updateUIWithNewConfig();
    notify.success("Configuration reloaded successfully!");
  } catch (error) {
    console.error("Error reloading configuration:", error);
    notify.error("Error reloading configuration: " + error.message);
  } finally {
    toggleLoading(false);
  }
}

// Improved validation feedback
async function validateConfig() {
  const validateBtn = document.getElementById("validate-btn");
  validateBtn.disabled = true;

  try {
    toggleLoading(true);
    const result = await apiService.validateConfig();

    if (result.valid) {
      notify.success("Configuration is purr-fect! 😺");
    } else {
      const errorsHtml = result.errors
        .map((err) => `<li>😿 ${err}</li>`)
        .join("");

      const notificationEl = notify.warning(
        `Validation found some issues:<ul class="validation-errors">${errorsHtml}</ul>`,
        15000
      );
      notificationEl.classList.add("notification-with-list");
    }
  } catch (error) {
    notify.error(`Validation failed: ${error.message} 😿`);
  } finally {
    toggleLoading(false);
    validateBtn.disabled = false;
  }
}

// Utility function for debouncing
function debounce(func, wait) {
  let timeout;
  return function (...args) {
    const context = this;
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(context, args), wait);
  };
}
