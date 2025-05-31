/**
 * NekoConf Configuration Editor
 * Refactored for new backend API requirements with clean architecture
 */

// API Configuration
const API_CONFIG = {
  BASE_URL: window.location.origin,
  ENDPOINTS: {
    CONFIG: (appName) => `/api/apps/${appName}/config`,
    CONFIG_PATH: (appName, path) => `/api/apps/${appName}/config/${path}`,
    VALIDATE: (appName) => `/api/apps/${appName}/validate`,
  },
  HEADERS: {
    "Content-Type": "application/json",
  },
};

// Utility Functions
const utils = {
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  },

  formatTime(timestamp) {
    if (!timestamp) return "Never";
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now - time;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return time.toLocaleDateString();
  },

  formatKeyName(key) {
    return key
      .replace(/([A-Z])/g, " $1")
      .replace(/^./, (str) => str.toUpperCase())
      .replace(/_/g, " ");
  },

  getNestedValue(obj, path) {
    return path.split(".").reduce((current, key) => current?.[key], obj);
  },

  setNestedValue(obj, path, value) {
    const keys = path.split(".");
    const lastKey = keys.pop();
    const target = keys.reduce((current, key) => {
      if (!(key in current)) current[key] = {};
      return current[key];
    }, obj);
    target[lastKey] = value;
  },

  deleteNestedValue(obj, path) {
    const keys = path.split(".");
    const lastKey = keys.pop();
    const target = keys.reduce((current, key) => current?.[key], obj);
    if (target && lastKey in target) {
      delete target[lastKey];
    }
  },

  async parseStringToFormat(data, format) {
    try {
      if (!data.trim()) return {};

      switch (format.toLowerCase()) {
        case "json":
          return JSON.parse(data);
        case "yaml":
          return jsyaml.load(data, { schema: jsyaml.DEFAULT_SAFE_SCHEMA });
        case "toml":
          // Use the external @iarna/toml library
          if (typeof window.TOML === "undefined") {
            throw new Error("TOML library not loaded");
          }
          return window.TOML.parse(data);
        default:
          throw new Error(`Unsupported format: ${format}`);
      }
    } catch (error) {
      throw new Error(`Invalid ${format.toUpperCase()} format: ${error.message}`);
    }
  },

  formatToString(data, format) {
    try {
      switch (format.toLowerCase()) {
        case "json":
          return JSON.stringify(data, null, 2);
        case "yaml":
          return jsyaml.dump(data, { indent: 2, lineWidth: 120 });
        case "toml":
          // Use the external @iarna/toml library
          if (typeof window.TOML === "undefined") {
            console.warn("TOML library not loaded, falling back to JSON");
            return JSON.stringify(data, null, 2);
          }
          return window.TOML.stringify(data);
        default:
          return "";
      }
    } catch (error) {
      console.error(`Error formatting ${format}:`, error);
      return "";
    }
  },
};

// API Service Layer aligned with backend requirements
class ConfigAPIService {
  constructor(appName) {
    this.appName = appName;
  }

  async getConfig() {
    const response = await fetch(API_CONFIG.ENDPOINTS.CONFIG(this.appName));
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  }

  async updateConfig(configData) {
    // Backend expects { data: string, format: string } structure
    const response = await fetch(API_CONFIG.ENDPOINTS.CONFIG(this.appName), {
      method: "PUT",
      headers: API_CONFIG.HEADERS,
      body: JSON.stringify({
        data: JSON.stringify(configData),
        format: "json",
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async updateConfigPath(path, value, type = "str") {
    const response = await fetch(API_CONFIG.ENDPOINTS.CONFIG_PATH(this.appName, path), {
      method: "PUT",
      headers: API_CONFIG.HEADERS,
      body: JSON.stringify({ value, type }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async deleteConfigPath(path) {
    const response = await fetch(API_CONFIG.ENDPOINTS.CONFIG_PATH(this.appName, path), {
      method: "DELETE",
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async validateConfig(data, format = "json") {
    const response = await fetch(API_CONFIG.ENDPOINTS.VALIDATE(this.appName), {
      method: "POST",
      headers: API_CONFIG.HEADERS,
      body: JSON.stringify({ data, format }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }
}

// Monaco Editor Utilities - Simplified and Clean
const MonacoEditor = {
  // Store editor instances directly
  editors: {},
  initialized: false,

  // Initialize Monaco using the loader script
  async init() {
    if (this.initialized) {
      return true;
    }

    try {
      // Check if Monaco is already available
      if (typeof monaco !== "undefined") {
        this.initialized = true;
        return true;
      }

      // Use the AMD loader that comes with Monaco
      if (typeof require !== "undefined") {
        return new Promise((resolve) => {
          require.config({
            paths: {
              vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs",
            },
          });

          require(["vs/editor/editor.main"], () => {
            this.initialized = true;
            console.log("Monaco Editor loaded successfully");
            resolve(true);
          });
        });
      }

      // Simple fallback - wait for Monaco to be available
      let attempts = 0;
      while (typeof monaco === "undefined" && attempts < 30) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        attempts++;
      }

      if (typeof monaco !== "undefined") {
        this.initialized = true;
        return true;
      }

      throw new Error("Monaco Editor not available");
    } catch (error) {
      console.error("Monaco initialization failed:", error);
      return false;
    }
  },

  // Create or get editor for a specific language
  async getOrCreateEditor(language, containerId, initialValue = "") {
    // Ensure Monaco is initialized
    if (!(await this.init())) {
      throw new Error("Monaco Editor not available");
    }

    // Return existing editor if available and valid
    if (this.editors[language] && !this.isEditorDisposed(language)) {
      return this.editors[language];
    }

    // Create new editor
    return this.createEditor(language, containerId, initialValue);
  },

  // Create a new Monaco editor instance
  createEditor(language, containerId, initialValue = "") {
    const container = document.getElementById(containerId);
    if (!container) {
      throw new Error(`Container not found: ${containerId}`);
    }

    // Clean up existing editor
    this.disposeEditor(language);

    try {
      const editor = monaco.editor.create(container, {
        value: initialValue,
        language: language === "toml" ? "ini" : language,
        theme: "vs-dark",
        automaticLayout: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 14,
        fontFamily: "JetBrains Mono, Monaco, Consolas, monospace",
        tabSize: 2,
        insertSpaces: true,
        wordWrap: "on",
        folding: true,
        lineNumbers: "on",
        renderWhitespace: "selection",
      });

      this.editors[language] = editor;
      return editor;
    } catch (error) {
      console.error(`Failed to create ${language} editor:`, error);
      throw error;
    }
  },

  // Get current value from editor
  getValue(language) {
    const editor = this.editors[language];
    if (!editor || this.isEditorDisposed(language)) {
      return "";
    }

    try {
      return editor.getValue();
    } catch (error) {
      console.error(`Error getting value for ${language}:`, error);
      return "";
    }
  },

  // Set value in editor
  setValue(language, value) {
    const editor = this.editors[language];
    if (!editor || this.isEditorDisposed(language)) {
      return false;
    }

    try {
      editor.setValue(value || "");
      return true;
    } catch (error) {
      console.error(`Error setting value for ${language}:`, error);
      return false;
    }
  },

  // Check if editor is disposed
  isEditorDisposed(language) {
    const editor = this.editors[language];
    if (!editor) return true;

    try {
      const model = editor.getModel();
      return !model || model.isDisposed();
    } catch (error) {
      return true;
    }
  },

  // Add change listener to editor
  addChangeListener(language, callback) {
    const editor = this.editors[language];
    if (!editor || this.isEditorDisposed(language)) {
      return null;
    }

    const debouncedCallback = utils.debounce(callback, 300);
    return editor.onDidChangeModelContent(debouncedCallback);
  },

  // Dispose specific editor
  disposeEditor(language) {
    const editor = this.editors[language];
    if (editor) {
      try {
        editor.dispose();
      } catch (error) {
        console.warn(`Error disposing ${language} editor:`, error);
      }
      delete this.editors[language];
    }
  },

  // Dispose all editors
  disposeAll() {
    Object.keys(this.editors).forEach((language) => {
      this.disposeEditor(language);
    });
  },

  // Format content in editor
  async formatEditor(language) {
    const editor = this.editors[language];
    if (!editor || this.isEditorDisposed(language)) {
      return false;
    }

    try {
      await editor.getAction("editor.action.formatDocument").run();
      return true;
    } catch (error) {
      console.warn(`Auto-format not available for ${language}`);
      return false;
    }
  },
};

// Main Alpine.js Component
function configApp() {
  return {
    // Core State
    configData: {},
    activeTab: "visual",
    loading: true,
    saving: false,
    validating: false,

    // App Context
    currentAppName: null,
    apiService: null,

    // UI State
    connectionStatus: "connected",
    lastSaved: null,
    hasUnsavedChanges: false,
    darkMode: localStorage.getItem("theme") === "dark" || (!localStorage.getItem("theme") && window.matchMedia("(prefers-color-scheme: dark)").matches),

    // Search functionality
    searchQuery: "",
    searchResults: [],

    // Notifications
    notifications: [],

    // Unified Modal System - Clean and consolidated
    fieldModal: {
      show: false,
      isSection: false,
      title: "",
      description: "",
      data: {
        name: "",
        type: "string",
        parentPath: "",
        initialValue: "",
      },
      typeOptions: {
        string: {
          icon: '<svg class="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16m-7 6h7"></path></svg>',
          label: "Text",
          description: "String value",
        },
        number: {
          icon: '<svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"></path></svg>',
          label: "Number",
          description: "Numeric value",
        },
        boolean: {
          icon: '<svg class="w-4 h-4 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><path d="M9,12l2,2 4,-4"></path></svg>',
          label: "Boolean",
          description: "True/False toggle",
        },
        array: {
          icon: '<svg class="w-4 h-4 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>',
          label: "Array",
          description: "List of items",
        },
        object: {
          icon: '<svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
          label: "Object",
          description: "Nested configuration",
        },
      },

      open(isSection = false, parentPath = "") {
        this.show = true;
        this.isSection = isSection;
        this.data.parentPath = parentPath;
        this.data.name = "";
        this.data.type = isSection ? "object" : "string";
        this.data.initialValue = "";

        if (isSection) {
          this.title = "Add New Section";
          this.description = "Create a new configuration section";
        } else {
          this.title = "Add New Field";
          this.description = parentPath ? `Add field to ${parentPath}` : "Add field to root level";
        }
      },

      close() {
        this.show = false;
        this.data = { name: "", type: "string", parentPath: "", initialValue: "" };
      },

      submit() {
        // This method will be replaced by submitFieldModal() in the main component
        console.warn("fieldModal.submit() called - this should use submitFieldModal() instead");
      },

      getPreviewValue() {
        switch (this.data.type) {
          case "string":
            return `"${this.data.initialValue || ""}"`;
          case "number":
            return this.data.initialValue || "0";
          case "boolean":
            return this.data.initialValue || "false";
          case "array":
            return "[]";
          case "object":
            return "{}";
          default:
            return '""';
        }
      },
    },

    // Editor tracking - simplified
    editorInstances: {},
    editorChangeListeners: {},

    // Computed Properties
    get visualEditorHtml() {
      return this.renderVisualEditor(this.configData);
    },

    // Initialization
    async init() {
      try {
        this.detectAppContext();
        this.initTheme();
        this.setupKeyboardShortcuts();

        // Initialize services
        this.apiService = new ConfigAPIService(this.currentAppName);

        await this.loadConfiguration();

        // Initialize Monaco editor
        await MonacoEditor.init();

        this.loading = false;
        this.showNotification("success", "Configuration editor ready! 🐱");
      } catch (error) {
        console.error("Initialization failed:", error);
        this.loading = false;
        this.showNotification("error", "Failed to initialize NekoConf");
      }
    },

    detectAppContext() {
      const path = window.location.pathname;
      const match = path.match(/^\/(?:app\/)?([^\/]+)$/);

      if (match && match[1] !== "api" && match[1] !== "static") {
        this.currentAppName = match[1];
        document.title = `NekoConf - ${this.currentAppName}`;
      }
    },

    // Configuration Management
    async loadConfiguration() {
      try {
        this.configData = await this.apiService.getConfig();
        this.hasUnsavedChanges = false;
        this.updateEditors();
      } catch (error) {
        console.error("Failed to load config:", error);
        this.showNotification("error", `Failed to load configuration: ${error.message}`);
        this.configData = {};
      }
    },

    async saveConfig() {
      if (this.saving) return;

      try {
        this.saving = true;
        let dataToSave = this.configData;

        // Get data from active editor if not in visual mode
        if (this.activeTab !== "visual") {
          const editorContent = this.getEditorValue(this.activeTab);
          if (editorContent.trim()) {
            dataToSave = await utils.parseStringToFormat(editorContent, this.activeTab);
          }
        }

        await this.apiService.updateConfig(dataToSave);
        this.configData = dataToSave;
        this.lastSaved = new Date();
        this.hasUnsavedChanges = false;
        this.updateEditors();

        this.showNotification("success", "Configuration saved! 💾");
      } catch (error) {
        console.error("Save failed:", error);
        this.showNotification("error", `Failed to save: ${error.message}`);
      } finally {
        this.saving = false;
      }
    },

    async validateConfig() {
      if (this.validating) return;

      try {
        this.validating = true;
        let configToValidate = this.configData;
        let format = "json";

        if (this.activeTab !== "visual") {
          const editorContent = this.getEditorValue(this.activeTab);
          if (editorContent.trim()) {
            configToValidate = await utils.parseStringToFormat(editorContent, this.activeTab);
            format = this.activeTab;
          }
        }

        const result = await this.apiService.validateConfig(JSON.stringify(configToValidate), format);

        if (result.valid) {
          this.showNotification("success", "Configuration is valid! ✅");
        } else {
          const errorMsg = result.errors?.join(", ") || "Unknown validation errors";
          this.showNotification("error", `Validation failed: ${errorMsg}`);
        }
      } catch (error) {
        console.error("Validation failed:", error);
        this.showNotification("error", `Validation failed: ${error.message}`);
      } finally {
        this.validating = false;
      }
    },

    // Editor Management - Simplified
    switchTab(tab) {
      this.activeTab = tab;
      if (tab !== "visual") {
        this.$nextTick(() => this.ensureEditorExists(tab));
      }
    },
    async ensureEditorExists(type) {
      if (this.editorInstances[type]) return;

      try {
        const containerId = `${type}-editor`;
        const container = document.getElementById(containerId);

        if (!container) {
          console.error(`Container not found: ${containerId}`);
          this.showNotification("error", `Editor container not found for ${type.toUpperCase()}`);
          return;
        }

        // Check if Monaco is available
        if (!(await MonacoEditor.init())) {
          console.error("Monaco not available, creating fallback textarea");
          this.createFallbackEditor(type, container);
          return;
        }

        const value = utils.formatToString(this.configData, type);
        const editor = await MonacoEditor.getOrCreateEditor(type, containerId, value);

        // Add focus out listener for better UX
        const changeListener = this.addEditorFocusOutListener(type, editor);

        this.editorInstances[type] = editor;
        this.editorChangeListeners[type] = changeListener;
      } catch (error) {
        console.error(`Failed to create ${type} editor:`, error);
        this.showNotification("warning", `Using fallback editor for ${type.toUpperCase()}`);

        // Create fallback textarea editor
        const container = document.getElementById(`${type}-editor`);
        if (container) {
          this.createFallbackEditor(type, container);
        }
      }
    },

    createFallbackEditor(type, container) {
      // Clear container
      container.innerHTML = "";

      // Create textarea fallback
      const textarea = document.createElement("textarea");
      textarea.className = "w-full h-96 p-4 font-mono text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-900 text-green-400 resize-none";
      textarea.value = utils.formatToString(this.configData, type);
      textarea.placeholder = `Enter ${type.toUpperCase()} configuration here...`;

      // Add change listener
      textarea.addEventListener(
        "input",
        utils.debounce(() => {
          this.hasUnsavedChanges = true;
          this.syncContentFromEditor(type);
        }, 300)
      );

      container.appendChild(textarea);

      // Store fallback editor
      this.editorInstances[type] = {
        isFallback: true,
        element: textarea,
        getValue: () => textarea.value,
        setValue: (value) => {
          textarea.value = value || "";
        },
        dispose: () => {
          textarea.remove();
        },
      };
    },

    // Add focus out listener for editor sync
    addEditorFocusOutListener(type, editor) {
      if (editor.isFallback) {
        editor.element.addEventListener("focusout", () => {
          this.hasUnsavedChanges = true;
          this.syncContentFromEditor(type);
        });
        return null;
      } else {
        return editor.onDidBlurEditorText(() => {
          this.hasUnsavedChanges = true;
          this.syncContentFromEditor(type);
        });
      }
    },

    updateEditors() {
      Object.keys(this.editorInstances).forEach((type) => {
        const value = utils.formatToString(this.configData, type);
        const editor = this.editorInstances[type];

        if (editor && editor.isFallback) {
          // Handle fallback textarea editors
          editor.setValue(value);
        } else {
          // Handle Monaco editors
          MonacoEditor.setValue(type, value);
        }
      });
    },

    // Helper method to get editor value (works with both Monaco and fallback)
    getEditorValue(type) {
      const editor = this.editorInstances[type];
      if (!editor) return "";

      if (editor.isFallback) {
        return editor.getValue();
      } else {
        return MonacoEditor.getValue(type);
      }
    },

    // Sync content across all tabs when any editor changes
    async syncContentFromEditor(sourceType) {
      try {
        const sourceContent = this.getEditorValue(sourceType);
        if (!sourceContent.trim()) return;

        // Parse the source content and update configData
        const parsedData = await utils.parseStringToFormat(sourceContent, sourceType);

        // Only update if data actually changed to prevent unnecessary re-renders
        const currentDataStr = JSON.stringify(this.configData);
        const newDataStr = JSON.stringify(parsedData);

        if (currentDataStr === newDataStr) return;

        this.configData = parsedData;

        // Update all other editors except the source
        Object.keys(this.editorInstances).forEach((type) => {
          if (type !== sourceType) {
            const formattedContent = utils.formatToString(this.configData, type);
            const editor = this.editorInstances[type];

            if (editor && editor.isFallback) {
              editor.setValue(formattedContent);
            } else {
              MonacoEditor.setValue(type, formattedContent);
            }
          }
        });

        // Mark as having unsaved changes
        this.hasUnsavedChanges = true;
      } catch (error) {
        console.error(`Error syncing content from ${sourceType}:`, error);
        this.showNotification("warning", `Invalid ${sourceType.toUpperCase()} format - sync skipped`);
      }
    },

    // Visual Editor Operations
    async updateConfigValue(path, value) {
      try {
        const convertedValue = this.convertValueType(value);

        if (this.apiService && path) {
          const valueType = this.getValueType(convertedValue);
          await this.apiService.updateConfigPath(path, convertedValue, valueType);
        }

        utils.setNestedValue(this.configData, path, convertedValue);
        this.hasUnsavedChanges = true;

        // Update all editor tabs when visual editor changes
        this.updateEditors();
        this.showNotification("success", "Configuration updated!");
      } catch (error) {
        console.error("Failed to update config:", error);
        this.showNotification("error", `Failed to update: ${error.message}`);
      }
    },

    async deleteConfigPath(path) {
      if (!confirm(`Delete "${path}"? This cannot be undone.`)) return;

      try {
        if (this.apiService && path) {
          await this.apiService.deleteConfigPath(path);
        }

        utils.deleteNestedValue(this.configData, path);
        this.updateEditors();
        this.showNotification("success", `Deleted: ${path}`);
      } catch (error) {
        console.error("Failed to delete config:", error);
        this.showNotification("error", `Failed to delete: ${error.message}`);
      }
    },

    getValueType(value) {
      if (typeof value === "boolean") return "bool";
      if (typeof value === "number") return Number.isInteger(value) ? "int" : "float";
      if (Array.isArray(value)) return "list";
      if (value && typeof value === "object") return "dict";
      return "str";
    },

    convertValueType(value) {
      // Smart type conversion
      if (typeof value === "string") {
        if (value === "true") return true;
        if (value === "false") return false;
        if (!isNaN(value) && !isNaN(parseFloat(value))) return parseFloat(value);
      }
      return value;
    },

    // Array Operations with API integration
    async addArrayItem(path) {
      try {
        const currentArray = utils.getNestedValue(this.configData, path) || [];
        const newArray = [...currentArray, ""];
        await this.updateConfigValue(path, newArray);
      } catch (error) {
        console.error("Failed to add array item:", error);
        this.showNotification("error", "Failed to add array item");
      }
    },

    async removeArrayItem(path, index) {
      try {
        const currentArray = utils.getNestedValue(this.configData, path) || [];
        const newArray = currentArray.filter((_, i) => i !== index);
        await this.updateConfigValue(path, newArray);
      } catch (error) {
        console.error("Failed to remove array item:", error);
        this.showNotification("error", "Failed to remove array item");
      }
    },

    async updateArrayItem(path, index, value) {
      try {
        const currentArray = utils.getNestedValue(this.configData, path) || [];
        const newArray = [...currentArray];

        // Try to preserve the original type if possible
        const originalValue = currentArray[index];
        let convertedValue = this.convertValueType(value);

        // If the original was a specific type, try to maintain it
        if (typeof originalValue === "number" && !isNaN(parseFloat(value))) {
          convertedValue = parseFloat(value);
        } else if (typeof originalValue === "boolean") {
          if (value === "true" || value === true) convertedValue = true;
          else if (value === "false" || value === false) convertedValue = false;
        } else if (typeof originalValue === "object" && originalValue !== null) {
          try {
            convertedValue = JSON.parse(value);
          } catch (e) {
            // If parsing fails, keep as string
            convertedValue = value;
          }
        }

        newArray[index] = convertedValue;
        await this.updateConfigValue(path, newArray);
      } catch (error) {
        console.error("Failed to update array item:", error);
        this.showNotification("error", "Failed to update array item");
      }
    },

    async updateObjectValue(path, jsonString, targetElement) {
      try {
        const value = JSON.parse(jsonString);
        await this.updateConfigValue(path, value);
        // Remove error styling if successful
        targetElement.classList.remove("border-red-500");
      } catch (error) {
        // Add error styling for invalid JSON
        targetElement.classList.add("border-red-500");
        this.showNotification("warning", "Invalid JSON format");
      }
    },

    // Theme Management
    initTheme() {
      this.updateTheme();
    },

    toggleTheme() {
      this.darkMode = !this.darkMode;
      localStorage.setItem("theme", this.darkMode ? "dark" : "light");
      this.updateTheme();
      this.showNotification("info", `Switched to ${this.darkMode ? "dark" : "light"} mode`);
    },

    updateTheme() {
      document.documentElement.classList.toggle("dark", this.darkMode);
    },

    // Utility Operations
    async reloadConfig() {
      try {
        this.loading = true;
        await this.loadConfiguration();
        this.showNotification("success", "Configuration reloaded!");
      } catch (error) {
        console.error("Reload failed:", error);
        this.showNotification("error", "Failed to reload configuration");
      } finally {
        this.loading = false;
      }
    },

    exportConfig() {
      const dataStr = JSON.stringify(this.configData, null, 2);
      const dataBlob = new Blob([dataStr], { type: "application/json" });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${this.currentAppName || "config"}.json`;
      link.click();
      URL.revokeObjectURL(url);
      this.showNotification("success", "Configuration exported!");
    },

    importConfig() {
      document.getElementById("file-input").click();
    },

    handleFileImport(event) {
      const file = event.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          const content = e.target.result;
          const format = file.name.split(".").pop();
          const importedConfig = await utils.parseStringToFormat(content, format);

          this.configData = importedConfig;
          this.hasUnsavedChanges = true;
          this.updateEditors();
          this.showNotification("success", "Configuration imported!");
        } catch (error) {
          this.showNotification("error", `Import failed: ${error.message}`);
        }
      };
      reader.readAsText(file);
    },

    // Editor Specific Operations - Removed unused format and validate methods

    // Search & Navigation
    searchConfig() {
      if (!this.searchQuery.trim()) {
        this.searchResults = [];
        return;
      }

      const results = [];
      const searchTerm = this.searchQuery.toLowerCase();

      const searchObject = (obj, path = "") => {
        for (const [key, value] of Object.entries(obj)) {
          const currentPath = path ? `${path}.${key}` : key;

          if (key.toLowerCase().includes(searchTerm)) {
            results.push({
              key: utils.formatKeyName(key),
              path: currentPath,
              value: value,
            });
          }

          if (value && typeof value === "object" && !Array.isArray(value)) {
            searchObject(value, currentPath);
          }
        }
      };

      searchObject(this.configData);
      this.searchResults = results.slice(0, 10);
    },

    navigateToConfigPath(path) {
      // Scroll to the section in visual editor
      this.activeTab = "visual";
      this.$nextTick(() => {
        const fieldId = `field-${path.replace(/\./g, "-")}`;
        const element = document.getElementById(fieldId) || document.querySelector(`[data-path="${path}"]`) || document.querySelector(`h3:contains("${path.split(".").pop()}")`);

        if (element) {
          element.scrollIntoView({ behavior: "smooth", block: "center" });
          // Highlight the element briefly
          element.classList.add("highlight-config-item");
          setTimeout(() => {
            element.classList.remove("highlight-config-item");
          }, 2000);
        }
      });
    },

    applyTemplate(template) {
      // Removed - templates functionality simplified
    },

    addNewSection() {
      this.fieldModal.open(true);
    },

    addNestedField(parentPath = "") {
      this.fieldModal.open(false, parentPath);
    },

    submitFieldModal() {
      if (!this.fieldModal.data.name.trim()) {
        this.showNotification("warning", "Name is required!");
        return;
      }

      const fullPath = this.fieldModal.data.parentPath ? `${this.fieldModal.data.parentPath}.${this.fieldModal.data.name}` : this.fieldModal.data.name;

      // Check if already exists
      if (utils.getNestedValue(this.configData, fullPath) !== undefined) {
        this.showNotification("warning", "Field already exists!");
        return;
      }

      let initialValue;
      switch (this.fieldModal.data.type) {
        case "string":
          initialValue = this.fieldModal.data.initialValue || "";
          break;
        case "number":
          initialValue = parseFloat(this.fieldModal.data.initialValue) || 0;
          break;
        case "boolean":
          initialValue = this.fieldModal.data.initialValue === "true" || this.fieldModal.data.initialValue === true;
          break;
        case "array":
          initialValue = [];
          break;
        case "object":
          initialValue = {};
          break;
        default:
          initialValue = "";
      }

      utils.setNestedValue(this.configData, fullPath, initialValue);
      this.hasUnsavedChanges = true;
      this.updateEditors();
      this.showNotification("success", `Added ${this.fieldModal.isSection ? "section" : "field"}: ${fullPath}`);
      this.fieldModal.close();
    },

    // Statistics
    getTotalKeys() {
      const countKeys = (obj) => {
        let count = 0;
        for (const [key, value] of Object.entries(obj)) {
          count++;
          if (value && typeof value === "object" && !Array.isArray(value)) {
            count += countKeys(value);
          }
        }
        return count;
      };
      return countKeys(this.configData);
    },

    getDataTypes() {
      const types = new Set();
      const analyzeTypes = (obj) => {
        for (const [key, value] of Object.entries(obj)) {
          if (Array.isArray(value)) {
            types.add("array");
          } else if (value === null) {
            types.add("null");
          } else {
            types.add(typeof value);
          }

          if (value && typeof value === "object" && !Array.isArray(value)) {
            analyzeTypes(value);
          }
        }
      };
      analyzeTypes(this.configData);
      return types.size;
    },

    // Notifications
    showNotification(type, message, duration = 5000) {
      const id = Date.now() + Math.random();
      const notification = {
        id,
        type,
        message,
        show: true,
        timestamp: new Date().toLocaleTimeString(),
      };

      this.notifications.push(notification);

      if (duration > 0) {
        setTimeout(() => this.removeNotification(id), duration);
      }

      console.log(`[${type.toUpperCase()}] ${message}`);
      return id;
    },

    removeNotification(id) {
      const index = this.notifications.findIndex((n) => n.id === id);
      if (index > -1) {
        this.notifications[index].show = false;
        setTimeout(() => {
          this.notifications.splice(index, 1);
        }, 300);
      }
    },

    // Keyboard Shortcuts
    setupKeyboardShortcuts() {
      document.addEventListener("keydown", (e) => {
        if (e.ctrlKey || e.metaKey) {
          if (this.isInInputField(e.target)) return;

          switch (e.key) {
            case "s":
              e.preventDefault();
              this.saveConfig();
              break;
            case "e":
              e.preventDefault();
              this.exportConfig();
              break;
            case "i":
              e.preventDefault();
              this.importConfig();
              break;
            case "r":
              e.preventDefault();
              this.reloadConfig();
              break;
            case "1":
              e.preventDefault();
              this.switchTab("visual");
              break;
            case "2":
              e.preventDefault();
              this.switchTab("json");
              break;
            case "3":
              e.preventDefault();
              this.switchTab("yaml");
              break;
            case "4":
              e.preventDefault();
              this.switchTab("toml");
              break;
          }
        }
      });
    },

    isInInputField(element) {
      return element.tagName === "INPUT" || element.tagName === "TEXTAREA" || element.closest(".monaco-editor");
    },

    // Visual Editor Rendering (keeping existing rendering logic)
    renderVisualEditor(data) {
      if (!data || typeof data !== "object" || Object.keys(data).length === 0) {
        return this.renderEmptyState();
      }

      let html = '<div class="space-y-6">';
      for (const [key, value] of Object.entries(data)) {
        html += this.renderSection(key, value, key);
      }
      html += "</div>";
      return html;
    },

    renderEmptyState() {
      return `
        <div class="text-center py-16">
          <div class="text-8xl mb-6">📝</div>
          <h3 class="text-2xl font-bold text-gray-900 dark:text-white mb-4">No Configuration Data</h3>
          <p class="text-gray-600 dark:text-gray-400 mb-8">
            Start by adding some configuration data using the JSON or YAML editor, or create a new configuration entry.
          </p>
          <button @click="addNewSection()" class="inline-flex items-center px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-700 hover:to-primary-600 text-white font-medium rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-105">
            <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
            </svg>
            Add Configuration Entry
          </button>
        </div>
      `;
    },

    renderSection(key, value, path) {
      const formattedKey = utils.formatKeyName(key);
      let html = `
        <div class="gradient-border animate-slide-up" data-path="${path}">
          <div class="p-6">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">${formattedKey}</h3>
              <div class="flex items-center space-x-2">
                <button @click="addNestedField('${path}')" class="text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 transition-colors duration-200" title="Add nested field">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
                  </svg>
                </button>
                <button @click="deleteConfigPath('${path}')" class="text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 transition-colors duration-200" title="Delete this section">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                  </svg>
                </button>
              </div>
            </div>
      `;

      if (Array.isArray(value)) {
        html += this.renderArrayField(value, path);
      } else if (value && typeof value === "object") {
        html += '<div class="space-y-4">';
        for (const [subKey, subValue] of Object.entries(value)) {
          const subPath = `${path}.${subKey}`;
          html += this.renderField(subKey, subValue, subPath);
        }
        html += "</div>";
      } else {
        html += this.renderField(key, value, path);
      }

      html += "</div></div>";
      return html;
    },

    renderField(key, value, path) {
      const formattedKey = utils.formatKeyName(key);
      const fieldId = `field-${path.replace(/\./g, "-")}`;

      // Handle arrays using the dedicated array field renderer
      if (Array.isArray(value)) {
        return this.renderArrayFieldWrapper(key, value, path);
      }

      // Wrapper with controls for nested fields
      let fieldHtml = "";
      if (typeof value === "boolean") {
        fieldHtml = this.renderBooleanField(fieldId, formattedKey, value, path);
      } else if (typeof value === "number") {
        fieldHtml = this.renderNumberField(fieldId, formattedKey, value, path);
      } else if (typeof value === "string") {
        fieldHtml = this.renderStringField(fieldId, formattedKey, value, path, key);
      } else if (value && typeof value === "object" && !Array.isArray(value)) {
        return this.renderNestedObjectField(key, value, path);
      } else {
        fieldHtml = this.renderObjectField(fieldId, formattedKey, value, path);
      }

      // Add controls for simple fields
      return `
        <div class="relative group">
          ${fieldHtml}
          <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <button @click="deleteConfigPath('${path}')" class="text-red-500 hover:text-red-600 p-1 rounded bg-white dark:bg-gray-800 shadow-sm" title="Delete field">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
              </svg>
            </button>
          </div>
        </div>
      `;
    },

    renderArrayFieldWrapper(key, value, path) {
      const formattedKey = utils.formatKeyName(key);
      return `
        <div class="relative group">
          <div class="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-800/20">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center space-x-2">
                <div class="w-2 h-2 rounded-full bg-orange-400 animate-pulse"></div>
                <h4 class="text-md font-medium text-gray-900 dark:text-gray-100">${formattedKey}</h4>
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gradient-to-r from-orange-100 to-orange-200 text-orange-800 dark:from-orange-900 dark:to-orange-800 dark:text-orange-200 shadow-sm">
                  <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>
                  </svg>
                  Array[${value.length}]
                </span>
              </div>
              <div class="flex items-center space-x-2">
                <button @click="addArrayItem('${path}')" class="text-orange-600 hover:text-orange-700 dark:text-orange-400 dark:hover:text-orange-300 p-1" title="Add array item">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
                  </svg>
                </button>
                <button @click="deleteConfigPath('${path}')" class="text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 p-1" title="Delete array">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                  </svg>
                </button>
              </div>
            </div>
            ${this.renderArrayField(value, path)}
          </div>
        </div>
      `;
    },

    renderNestedObjectField(key, value, path) {
      const formattedKey = utils.formatKeyName(key);
      let html = `
        <div class="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-800/50">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-md font-medium text-gray-900 dark:text-gray-100">${formattedKey}</h4>
            <div class="flex items-center space-x-2">
              <button @click="addNestedField('${path}')" class="text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 p-1" title="Add nested field">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
                </svg>
              </button>
              <button @click="deleteConfigPath('${path}')" class="text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 p-1" title="Delete object">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
              </button>
            </div>
          </div>
          <div class="space-y-3">
      `;

      if (Object.keys(value).length === 0) {
        html += `
          <div class="text-center py-4 text-gray-500 dark:text-gray-400 text-sm">
            No fields yet. Click the + button to add one.
          </div>
        `;
      } else {
        for (const [subKey, subValue] of Object.entries(value)) {
          const subPath = `${path}.${subKey}`;
          html += this.renderField(subKey, subValue, subPath);
        }
      }

      html += "</div></div>";
      return html;
    },

    renderBooleanField(fieldId, formattedKey, value, path) {
      return `
        <div class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl border border-gray-200 dark:border-gray-600 hover:border-primary-300 dark:hover:border-primary-600 transition-all duration-200 config-field group">
          <div class="flex items-center space-x-3">
            <div class="w-2 h-2 rounded-full ${value ? "bg-green-400" : "bg-gray-400"} animate-pulse"></div>
            <label for="${fieldId}" class="text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors duration-200">${formattedKey}</label>
          </div>
          <div class="relative">
            <input type="checkbox" id="${fieldId}" ${value ? "checked" : ""} 
                   @change="updateConfigValue('${path}', $event.target.checked)"
                   class="sr-only">
            <label for="${fieldId}" class="flex items-center cursor-pointer">
              <div class="relative">
                <div class="w-12 h-6 rounded-full shadow-inner transition-all duration-300 ease-in-out ${
                  value ? "bg-gradient-to-r from-green-500 to-green-600 shadow-green-200 dark:shadow-green-800" : "bg-gray-200 dark:bg-gray-600 hover:bg-gray-300 dark:hover:bg-gray-500"
                }"></div>
                <div class="absolute w-5 h-5 bg-white rounded-full shadow-lg top-0.5 transition-all duration-300 ease-in-out transform ${value ? "translate-x-6 bg-white shadow-lg" : "translate-x-0.5 bg-white"}">
                  <div class="w-full h-full rounded-full ${value ? "bg-gradient-to-br from-white to-gray-100" : "bg-gradient-to-br from-white to-gray-50"}"></div>
                </div>
              </div>
              <span class="ml-3 text-xs font-medium ${value ? "text-green-600 dark:text-green-400" : "text-gray-500 dark:text-gray-400"} transition-colors duration-200">
                ${value ? "ON" : "OFF"}
              </span>
            </label>
          </div>
        </div>
      `;
    },

    renderNumberField(fieldId, formattedKey, value, path) {
      return `
        <div class="space-y-3 config-field group">
          <div class="flex items-center space-x-2">
            <div class="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></div>
            <label for="${fieldId}" class="block text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors duration-200">${formattedKey}</label>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 dark:from-blue-900 dark:to-blue-800 dark:text-blue-200 shadow-sm">
              <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"></path>
              </svg>
              Number
            </span>
          </div>
          <div class="relative">
            <input type="number" id="${fieldId}" value="${value}" 
                   @change="updateConfigValue('${path}', parseFloat($event.target.value) || 0)"
                   @focus="$event.target.select()"
                   class="block w-full px-4 py-3 border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all duration-200 hover:border-gray-300 dark:hover:border-gray-600 shadow-sm hover:shadow-md focus:shadow-lg">
            <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
              <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
              </svg>
            </div>
          </div>
        </div>
      `;
    },

    renderStringField(fieldId, formattedKey, value, path, key) {
      const isPassword = key.toLowerCase().includes("password") || key.toLowerCase().includes("secret");
      const isMultiline = value.length > 100 || value.includes("\n");
      const isUrl = key.toLowerCase().includes("url") || (typeof value === "string" && value.startsWith("http"));
      const isEmail = key.toLowerCase().includes("email") || (typeof value === "string" && value.includes("@"));

      if (isMultiline) {
        return `
          <div class="space-y-3 config-field group">
            <div class="flex items-center space-x-2">
              <div class="w-2 h-2 rounded-full bg-yellow-400 animate-pulse"></div>
              <label for="${fieldId}" class="block text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors duration-200">${formattedKey}</label>
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gradient-to-r from-yellow-100 to-yellow-200 text-yellow-800 dark:from-yellow-900 dark:to-yellow-800 dark:text-yellow-200 shadow-sm">
                <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"></path>
                </svg>
                Multiline
              </span>
            </div>
            <div class="relative">
              <textarea id="${fieldId}" rows="4" 
                        @change="updateConfigValue('${path}', $event.target.value)"
                        @focus="$event.target.select()"
                        class="block w-full px-4 py-3 border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all duration-200 resize-y hover:border-gray-300 dark:hover:border-gray-600 shadow-sm hover:shadow-md focus:shadow-lg"
                        placeholder="Enter ${formattedKey.toLowerCase()}...">${value}</textarea>
              <div class="absolute bottom-3 right-3 pointer-events-none">
                <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"></path>
                </svg>
              </div>
            </div>
          </div>
        `;
      }

      const inputType = isPassword ? "password" : isEmail ? "email" : isUrl ? "url" : "text";
      const iconSvg = isPassword
        ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>'
        : isEmail
        ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>'
        : isUrl
        ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path>'
        : '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16m-7 6h7"></path>';

      const typeLabel = isPassword ? "Password" : isEmail ? "Email" : isUrl ? "URL" : "Text";
      const typeColor = isPassword ? "red" : isEmail ? "green" : isUrl ? "purple" : "gray";

      return `
        <div class="space-y-3 config-field group">
          <div class="flex items-center space-x-2">
            <div class="w-2 h-2 rounded-full bg-${typeColor}-400 animate-pulse"></div>
            <label for="${fieldId}" class="block text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors duration-200">${formattedKey}</label>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gradient-to-r from-${typeColor}-100 to-${typeColor}-200 text-${typeColor}-800 dark:from-${typeColor}-900 dark:to-${typeColor}-800 dark:text-${typeColor}-200 shadow-sm">
              <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                ${iconSvg}
              </svg>
              ${typeLabel}
            </span>
          </div>
          <div class="relative">
            <input type="${inputType}" id="${fieldId}" value="${value}" 
                   @change="updateConfigValue('${path}', $event.target.value)"
                   @focus="$event.target.select()"
                   class="block w-full px-4 py-3 pr-10 border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all duration-200 hover:border-gray-300 dark:hover:border-gray-600 shadow-sm hover:shadow-md focus:shadow-lg"
                   placeholder="Enter ${formattedKey.toLowerCase()}...">
            <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
              <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                ${iconSvg}
              </svg>
            </div>
          </div>
        </div>
      `;
    },

    renderObjectField(fieldId, formattedKey, value, path) {
      return `
        <div class="space-y-3 config-field">
          <label for="${fieldId}" class="block text-sm font-medium text-gray-700 dark:text-gray-300">${formattedKey}</label>
          <input type="text" id="${fieldId}" value="${JSON.stringify(value).replace(/"/g, "&quot;")}" 
                 @change="updateObjectValue('${path}', $event.target.value, $event.target)"
                 class="block w-full px-4 py-3 border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all duration-200 font-mono text-sm"
                 placeholder="Enter JSON value...">
        </div>
      `;
    },

    renderArrayField(value, path) {
      let html = `
        <div class="space-y-4 config-field">
      `;

      if (value.length === 0) {
        html += `
          <div class="text-center py-8 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl">
            <div class="text-4xl mb-2">📝</div>
            <p class="text-sm text-gray-500 dark:text-gray-400">No items yet</p>
            <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Click "Add Item" to get started</p>
          </div>
        `;
      } else {
        html += '<div class="space-y-3">';
        value.forEach((item, index) => {
          html += this.renderArrayItem(item, index, path);
        });
        html += "</div>";
      }

      html += "</div>";
      return html;
    },

    renderArrayItem(item, index, path) {
      const itemPath = `${path}[${index}]`;

      if (Array.isArray(item)) {
        // Nested array - reuse renderArrayField for consistency
        return `
          <div class="border border-orange-200 dark:border-orange-800 rounded-lg p-4 bg-gradient-to-br from-orange-25 to-orange-50 dark:from-orange-950/50 dark:to-orange-900/30">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center space-x-2">
                <span class="text-sm font-medium text-gray-600 dark:text-gray-300">${index + 1}.</span>
                <span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-800 dark:text-orange-200">
                  <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>
                  </svg>
                  Nested Array[${item.length}]
                </span>
              </div>
              <div class="flex items-center space-x-2">
                <button @click="addArrayItem('${itemPath}')" class="text-orange-600 hover:text-orange-700 dark:text-orange-400 dark:hover:text-orange-300 p-1 rounded transition-colors duration-200" title="Add item to nested array">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
                  </svg>
                </button>
                <button @click="removeArrayItem('${path}', ${index})" 
                        class="text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 p-1 rounded transition-colors duration-200" title="Remove this array">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                  </svg>
                </button>
              </div>
            </div>
            ${this.renderArrayField(item, itemPath)}
          </div>
        `;
      } else if (item && typeof item === "object") {
        // Nested object - render as a larger, well-structured config field
        return `
          <div class="border-2 border-blue-200 dark:border-blue-700 rounded-xl p-6 bg-gradient-to-br from-blue-25 via-blue-50 to-blue-75 dark:from-blue-950/30 dark:via-blue-900/20 dark:to-blue-950/30 shadow-lg">
            <div class="flex items-center justify-between mb-6">
              <div class="flex items-center space-x-3">
                <div class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold text-sm shadow-md">
                  ${index + 1}
                </div>
                <div>
                  <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-gradient-to-r from-blue-100 to-blue-200 text-blue-900 dark:from-blue-800 dark:to-blue-700 dark:text-blue-100 shadow-sm">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    Configuration Object
                  </span>
                  <div class="text-xs text-blue-600 dark:text-blue-300 mt-1 font-medium">
                    ${Object.keys(item).length} field${Object.keys(item).length !== 1 ? "s" : ""}
                  </div>
                </div>
              </div>
              <div class="flex items-center space-x-2">
                <button @click="addNestedField('${itemPath}')" 
                        class="inline-flex items-center px-3 py-1.5 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white text-xs font-medium rounded-lg shadow-md hover:shadow-lg transition-all duration-200 transform hover:scale-105" 
                        title="Add field to this object">
                  <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
                  </svg>
                  Add Field
                </button>
                <button @click="removeArrayItem('${path}', ${index})" 
                        class="inline-flex items-center px-3 py-1.5 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white text-xs font-medium rounded-lg shadow-md hover:shadow-lg transition-all duration-200 transform hover:scale-105" 
                        title="Remove this object">
                  <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                  </svg>
                  Remove
                </button>
              </div>
            </div>
            <div class="bg-white dark:bg-gray-800/50 rounded-lg p-4 border border-blue-100 dark:border-blue-800">
              ${this.renderObjectFields(item, itemPath)}
            </div>
          </div>
        `;
      } else {
        // Simple value (string, number, boolean)
        const valueType = typeof item;
        const typeIcon = this.getTypeIcon(valueType);
        const typeColor = this.getTypeColor(valueType);

        return `
          <div class="flex items-center space-x-3 p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-gray-300 dark:hover:border-gray-600 transition-all duration-200 group">
            <div class="flex items-center space-x-2 min-w-0 flex-shrink-0">
              <span class="text-sm font-medium text-gray-500 dark:text-gray-400">${index + 1}.</span>
              <span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-${typeColor}-100 text-${typeColor}-800 dark:bg-${typeColor}-800 dark:text-${typeColor}-200">
                ${typeIcon}
                ${valueType}
              </span>
            </div>
            ${this.renderArrayItemInput(item, valueType, path, index)}
            <button @click="removeArrayItem('${path}', ${index})" 
                    class="flex-shrink-0 text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 p-1 rounded opacity-0 group-hover:opacity-100 transition-all duration-200" title="Remove this item">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        `;
      }
    },

    renderObjectFields(obj, basePath) {
      if (Object.keys(obj).length === 0) {
        return `
          <div class="text-center py-4 text-gray-500 dark:text-gray-400 text-sm">
            <div class="text-2xl mb-2">🔧</div>
            <p>No fields yet</p>
            <p class="text-xs mt-1">Click the + button to add fields</p>
          </div>
        `;
      }

      let html = '<div class="space-y-3">';
      for (const [key, value] of Object.entries(obj)) {
        const fieldPath = `${basePath}.${key}`;
        html += this.renderField(key, value, fieldPath);
      }
      html += "</div>";
      return html;
    },

    renderArrayItemInput(item, valueType, path, index) {
      switch (valueType) {
        case "boolean":
          return `
            <div class="flex-1 flex items-center justify-center">
              <label class="flex items-center cursor-pointer">
                <div class="relative">
                  <input type="checkbox" ${item ? "checked" : ""} 
                         @change="updateArrayItem('${path}', ${index}, $event.target.checked)"
                         class="sr-only">
                  <div class="w-10 h-6 rounded-full shadow-inner transition-all duration-200 ${item ? "bg-green-500" : "bg-gray-300 dark:bg-gray-600"}"></div>
                  <div class="absolute w-4 h-4 bg-white rounded-full shadow-md top-1 transition-all duration-200 transform ${item ? "translate-x-5" : "translate-x-1"}"></div>
                </div>
                <span class="ml-2 text-sm ${item ? "text-green-600 dark:text-green-400" : "text-gray-500 dark:text-gray-400"}">
                  ${item ? "True" : "False"}
                </span>
              </label>
            </div>
          `;
        case "number":
          return `
            <input type="number" value="${item}" 
                   @change="updateArrayItem('${path}', ${index}, parseFloat($event.target.value))"
                   @focus="$event.target.select()"
                   class="flex-1 px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200">
          `;
        default: // string and others
          const isLongText = typeof item === "string" && (item.length > 50 || item.includes("\n"));
          if (isLongText) {
            return `
              <textarea rows="3" 
                        @change="updateArrayItem('${path}', ${index}, $event.target.value)"
                        @focus="$event.target.select()"
                        class="flex-1 px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-700 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200">${item}</textarea>
            `;
          } else {
            return `
              <input type="text" value="${typeof item === "object" ? JSON.stringify(item).replace(/"/g, "&quot;") : item}" 
                     @change="updateArrayItem('${path}', ${index}, $event.target.value)"
                     @focus="$event.target.select()"
                     class="flex-1 px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200">
            `;
          }
      }
    },

    getTypeIcon(type) {
      const icons = {
        string: '<svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16m-7 6h7"></path></svg>',
        number: '<svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"></path></svg>',
        boolean: '<svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><path d="M9,12l2,2 4,-4"></path></svg>',
        object:
          '<svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
      };
      return icons[type] || icons.string;
    },

    getTypeColor(type) {
      const colors = {
        string: "gray",
        number: "green",
        boolean: "purple",
        object: "blue",
      };
      return colors[type] || "gray";
    },

    // Cleanup
    cleanup() {
      MonacoEditor.disposeAll();
      this.notifications = [];
      this.editorInstances = {};
      this.editorChangeListeners = {};
    },

    destroy() {
      this.cleanup();
    },
  };
}

// Global exports
window.configApp = configApp;

if (typeof module !== "undefined" && module.exports) {
  module.exports = { configApp, utils, ConfigAPIService, MonacoEditor };
}
