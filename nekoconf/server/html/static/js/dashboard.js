/**
 * NekoConf Dashboard Application
 * Modern configuration management dashboard with real-time updates
 */

function dashboardApp() {
  return {
    // State Management
    darkMode: localStorage.getItem("theme") === "dark" || (!localStorage.getItem("theme") && window.matchMedia("(prefers-color-scheme: dark)").matches),
    loading: true,
    apps: [],
    filteredApps: [],
    searchQuery: "",

    // Modal States
    showCreateModal: false,
    showEditModal: false,
    showMobileSearch: false,
    showImportModal: false,
    showAboutModal: false,

    // Loading States
    creating: false,
    updating: false,

    // Notifications
    notifications: [],

    // Statistics
    stats: {
      totalApps: 0,
      activeConnections: 0,
      serverStatus: "Online",
    },

    // Form Data
    newApp: {
      name: "",
      description: "",
      format: "json",
      template: "empty",
    },

    editApp: {
      name: "",
      description: "",
      originalName: "",
    },

    // App Templates with enhanced metadata and default data
    templates: {
      empty: {
        name: "Empty Configuration",
        description: "Start with a blank configuration",
        icon: "📄",
        data: "{}",
        format: "json",
      },
      "web-app": {
        name: "Web Application",
        description: "Frontend application with server and API settings",
        icon: "🌐",
        data: JSON.stringify(
          {
            app: { name: "web-app", version: "1.0.0", port: 3000 },
            server: { host: "localhost", ssl: false },
            api: { baseUrl: "/api/v1", timeout: 5000 },
          },
          null,
          2
        ),
        format: "json",
      },
      "api-service": {
        name: "API Service",
        description: "Backend service with database and auth configuration",
        icon: "🔌",
        data: JSON.stringify(
          {
            service: { name: "api-service", version: "1.0.0", port: 8000 },
            database: { host: "localhost", port: 5432, name: "app_db" },
            auth: { jwt_secret: "your-secret-key", expires_in: "24h" },
          },
          null,
          2
        ),
        format: "json",
      },
      microservice: {
        name: "Microservice",
        description: "Containerized service with logging and metrics",
        icon: "🐳",
        data: JSON.stringify(
          {
            service: { name: "microservice", version: "1.0.0", port: 8080 },
            logging: { level: "info", format: "json" },
            metrics: { enabled: true, endpoint: "/metrics" },
            health: { endpoint: "/health", timeout: 30 },
          },
          null,
          2
        ),
        format: "json",
      },
    },

    // Initialization
    async init() {
      console.log("🐱 Initializing NekoConf Dashboard...");

      this.applyTheme();
      await this.loadApps();
      await this.updateStats();
      this.setupAutoRefresh();
      this.setupKeyboardShortcuts();
      this.setupResponsiveHandlers();
      console.log("✅ Dashboard initialized successfully");
    },

    // Theme Management
    toggleTheme() {
      this.darkMode = !this.darkMode;
      localStorage.setItem("theme", this.darkMode ? "dark" : "light");
      this.applyTheme();
      this.showNotification("info", `Switched to ${this.darkMode ? "dark" : "light"} mode`);
    },

    applyTheme() {
      if (this.darkMode) {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    },

    // API Methods
    async loadApps() {
      try {
        this.loading = true;
        const response = await fetch("/api/apps");

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();
        this.apps = Object.entries(result.data || {}).map(([name, data]) => ({
          name,
          ...data,
          configKeys: data.config_count || data.configKeys || 0,
          status: data.status || "online",
          connections: data.connections || 0,
          last_modified: data.last_modified || new Date().toISOString(),
        }));

        this.filterApps();
        this.updateStatsFromApps();

        if (this.apps.length === 0) {
          this.showNotification("info", "No apps found. Create your first app to get started! 🚀");
        }
      } catch (error) {
        console.error("Failed to load apps:", error);
        this.showNotification("error", `Failed to load apps: ${error.message}`);
        this.apps = [];
        this.filteredApps = [];
      } finally {
        this.loading = false;
      }
    },

    async createApp() {
      if (!this.validateAppForm(this.newApp)) {
        return;
      }

      try {
        this.creating = true;
        const template = this.templates[this.newApp.template];

        const requestBody = {
          name: this.newApp.name.trim(),
          description: this.newApp.description?.trim() || template?.description || "",
          data: template?.data || "{}",
          format: template?.format || "json",
        };

        const response = await this.apiRequest("/api/apps", {
          method: "POST",
          body: JSON.stringify(requestBody),
        });

        this.showNotification("success", `App "${this.newApp.name}" created successfully! 🎉`);
        this.showCreateModal = false;
        this.resetNewAppForm();
        await this.loadApps();

        // Auto-navigate to the new app after a short delay
        setTimeout(() => {
          this.navigateToApp(this.newApp.name);
        }, 1000);
      } catch (error) {
        this.handleApiError(error, "Failed to create app");
      } finally {
        this.creating = false;
      }
    },

    async duplicateApp(appName) {
      try {
        // Get the original app's configuration
        const configResponse = await this.apiRequest(`/api/apps/${appName}/config`);
        const config = await configResponse.json();

        // Get app info for description
        const appResponse = await this.apiRequest(`/api/apps/${appName}`);
        const appInfo = await appResponse.json();

        // Generate unique name
        const newName = this.generateUniqueName(`${appName}-copy`);

        // Create the duplicate app
        const requestBody = {
          name: newName,
          description: `Copy of ${appInfo.data?.description || appName}`,
          data: JSON.stringify(config, null, 2),
          format: "json",
        };

        await this.apiRequest("/api/apps", {
          method: "POST",
          body: JSON.stringify(requestBody),
        });

        this.showNotification("success", `App duplicated as "${newName}" 📋`);
        await this.loadApps();
      } catch (error) {
        this.handleApiError(error, "Failed to duplicate app");
      }
    },

    async deleteApp(appName) {
      // Enhanced confirmation dialog
      const confirmed = await this.showConfirmDialog("Delete App", `Are you sure you want to delete "${appName}"?`, "This action cannot be undone and will permanently remove all configuration data.", "Delete", "danger");

      if (!confirmed) return;

      try {
        await this.apiRequest(`/api/apps/${appName}`, {
          method: "DELETE",
        });

        this.showNotification("success", `App "${appName}" deleted successfully`);
        await this.loadApps();
      } catch (error) {
        this.handleApiError(error, "Failed to delete app");
      }
    },

    async editAppMetadata(appName) {
      const app = this.apps.find((a) => a.name === appName);
      if (!app) {
        this.showNotification("error", "App not found");
        return;
      }

      this.editApp = {
        name: app.name,
        description: app.description || "",
        originalName: app.name,
      };
      this.showEditModal = true;
    },

    async updateAppMetadata() {
      if (!this.validateAppForm(this.editApp)) {
        return;
      }

      try {
        this.updating = true;
        const requestBody = {};

        // Only include fields that have changed
        if (this.editApp.name !== this.editApp.originalName) {
          requestBody.name = this.editApp.name.trim();
        }

        if (this.editApp.description !== undefined) {
          requestBody.description = this.editApp.description.trim();
        }

        // Skip if no changes
        if (Object.keys(requestBody).length === 0) {
          this.showNotification("info", "No changes to save");
          this.showEditModal = false;
          return;
        }

        await this.apiRequest(`/api/apps/${this.editApp.originalName}/metadata`, {
          method: "PATCH",
          body: JSON.stringify(requestBody),
        });

        this.showNotification("success", "App metadata updated successfully! ✅");
        this.showEditModal = false;
        this.resetEditAppForm();
        await this.loadApps();
      } catch (error) {
        this.handleApiError(error, "Failed to update app metadata");
      } finally {
        this.updating = false;
      }
    },

    async refreshApps() {
      this.showNotification("info", "Refreshing apps... 🔄");
      await this.loadApps();
    },

    async updateStats() {
      try {
        const response = await fetch("/health");
        if (response.ok) {
          const health = await response.json();
          this.stats.serverStatus = health.status === "ok" ? "Online" : "Offline";
        } else {
          this.stats.serverStatus = "Offline";
        }
      } catch (error) {
        console.warn("Health check failed:", error);
        this.stats.serverStatus = "Offline";
      }
    },

    updateStatsFromApps() {
      this.stats.totalApps = this.apps.length;
      this.stats.activeConnections = this.apps.reduce((total, app) => total + (app.connections || 0), 0);
    },

    // UI Methods
    filterApps() {
      if (!this.searchQuery.trim()) {
        this.filteredApps = [...this.apps];
      } else {
        const query = this.searchQuery.toLowerCase();
        this.filteredApps = this.apps.filter((app) => app.name.toLowerCase().includes(query) || this.getAppDescription(app).toLowerCase().includes(query));
      }
    },

    navigateToApp(appName) {
      // Add loading state for better UX
      this.showNotification("info", `Opening ${appName}...`);
      window.location.href = `/${appName}`;
    },

    getAppDescription(app) {
      if (app.description && app.description.trim()) {
        return app.description;
      }

      if (!app.configKeys) {
        return "Empty configuration - ready to be configured";
      }

      const complexity = this.getComplexity(app);
      return `${complexity} configuration with ${app.configKeys} keys`;
    },

    getComplexity(app) {
      const keys = app.configKeys || 0;
      if (keys === 0) return "Empty";
      if (keys <= 5) return "Simple";
      if (keys <= 15) return "Medium";
      return "Complex";
    },

    getTemplateIcon(templateKey) {
      return this.templates[templateKey]?.icon || "📄";
    },

    resetNewAppForm() {
      this.newApp = {
        name: "",
        description: "",
        format: "json",
        template: "empty",
      };
    },

    resetEditAppForm() {
      this.editApp = {
        name: "",
        description: "",
        originalName: "",
      };
    },

    // API Helper Methods
    async apiRequest(url, options = {}) {
      const defaultHeaders = {
        "Content-Type": "application/json",
      };

      const config = {
        headers: { ...defaultHeaders, ...options.headers },
        ...options,
      };

      const response = await fetch(url, config);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      return response;
    },

    handleApiError(error, context = "Operation") {
      console.error(`${context} failed:`, error);
      this.showNotification("error", `${context} failed: ${error.message}`);
    },

    // Form Validation
    validateAppForm(formData) {
      if (!formData.name?.trim()) {
        this.showNotification("warning", "Please enter an app name");
        return false;
      }

      // Validate app name format
      const namePattern = /^[a-zA-Z0-9][a-zA-Z0-9_-]*$/;
      if (!namePattern.test(formData.name.trim())) {
        this.showNotification("error", "Invalid app name format. Must start with alphanumeric character and contain only letters, numbers, hyphens, and underscores.");
        return false;
      }

      // Check for duplicate names (only for new apps or name changes)
      if (formData.originalName !== formData.name && this.apps.some((app) => app.name === formData.name.trim())) {
        this.showNotification("error", `App "${formData.name}" already exists`);
        return false;
      }

      return true;
    },

    // Utility to generate unique names
    generateUniqueName(baseName) {
      let finalName = baseName;
      let counter = 1;

      while (this.apps.some((app) => app.name === finalName)) {
        finalName = `${baseName}-${counter}`;
        counter++;
      }

      return finalName;
    },

    // Enhanced Features
    async exportAllConfigs() {
      try {
        const allConfigs = {};

        for (const app of this.apps) {
          const response = await this.apiRequest(`/api/apps/${app.name}/config`);
          if (response.ok) {
            allConfigs[app.name] = await response.json();
          }
        }

        const dataStr = JSON.stringify(allConfigs, null, 2);
        const dataBlob = new Blob([dataStr], { type: "application/json" });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `nekoconf-export-${new Date().toISOString().split("T")[0]}.json`;
        link.click();
        URL.revokeObjectURL(url);

        this.showNotification("success", "All configurations exported! 📁");
      } catch (error) {
        console.error("Failed to export configs:", error);
        this.showNotification("error", "Failed to export configurations");
      }
    },

    // Enhanced Notification System
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

      // Auto-remove notification
      if (duration > 0) {
        setTimeout(() => this.removeNotification(id), duration);
      }

      // Log to console for debugging
      console.log(`[${type.toUpperCase()}] ${message}`);
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

    // Enhanced Confirmation Dialog
    async showConfirmDialog(title, message, details, confirmText = "Confirm", type = "warning") {
      return new Promise((resolve) => {
        // Create a more sophisticated confirmation dialog
        const confirmed = confirm(`${title}\n\n${message}\n\n${details}`);
        resolve(confirmed);
      });
    },

    // Auto-refresh functionality
    setupAutoRefresh() {
      // Refresh stats every 30 seconds
      setInterval(() => {
        this.updateStats();
      }, 30000);

      // Refresh apps every 2 minutes
      setInterval(() => {
        if (!this.loading) {
          this.loadApps();
        }
      }, 120000);
    },

    // Responsive Handlers
    setupResponsiveHandlers() {
      // Handle window resize
      window.addEventListener("resize", () => {
        if (window.innerWidth >= 768) {
          this.showMobileSearch = false;
        }
      });

      // Handle escape key for mobile search
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && this.showMobileSearch) {
          this.showMobileSearch = false;
        }
      });
    },

    // Keyboard Shortcuts
    setupKeyboardShortcuts() {
      document.addEventListener("keydown", (e) => {
        // Only handle shortcuts when not in input fields
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
          return;
        }

        if (e.ctrlKey || e.metaKey) {
          switch (e.key) {
            case "n":
              e.preventDefault();
              this.showCreateModal = true;
              break;
            case "r":
              e.preventDefault();
              this.refreshApps();
              break;
            case "k":
              e.preventDefault();
              // Focus search input
              const searchInput = document.querySelector('input[placeholder*="Search"]');
              if (searchInput) {
                searchInput.focus();
              } else {
                this.showMobileSearch = true;
              }
              break;
            case "/":
              e.preventDefault();
              const searchInput2 = document.querySelector('input[placeholder*="Search"]');
              if (searchInput2) {
                searchInput2.focus();
              } else {
                this.showMobileSearch = true;
              }
              break;
            case "e":
              e.preventDefault();
              this.exportAllConfigs();
              break;
          }
        }

        // Escape key to close modals
        if (e.key === "Escape") {
          this.showCreateModal = false;
          this.showEditModal = false;
          this.showImportModal = false;
          this.showAboutModal = false;
          this.showMobileSearch = false;
        }
      });
    },

    // Utility Methods
    formatDate(date) {
      if (!date) return "Never";
      return new Date(date).toLocaleDateString();
    },

    formatTime(date) {
      if (!date) return "Just now";
      const now = new Date();
      const then = new Date(date);
      const diffMs = now - then;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;
      return then.toLocaleDateString();
    },

    // Error Handling
    handleError(error, context = "Operation") {
      console.error(`${context} failed:`, error);
      this.showNotification("error", `${context} failed: ${error.message}`);
    },

    // Performance Monitoring
    measurePerformance(name, fn) {
      const start = performance.now();
      const result = fn();
      const end = performance.now();
      console.log(`⚡ ${name} took ${(end - start).toFixed(2)}ms`);
      return result;
    },

    // Advanced Search
    performAdvancedSearch(query) {
      const searchTerms = query
        .toLowerCase()
        .split(" ")
        .filter((term) => term.length > 0);

      return this.apps.filter((app) => {
        const searchableText = [app.name, this.getAppDescription(app), this.getComplexity(app), app.status].join(" ").toLowerCase();

        return searchTerms.every((term) => searchableText.includes(term));
      });
    },

    // Accessibility helpers
    announceToScreenReader(message) {
      const announcement = document.createElement("div");
      announcement.setAttribute("aria-live", "polite");
      announcement.setAttribute("aria-atomic", "true");
      announcement.className = "sr-only";
      announcement.textContent = message;
      document.body.appendChild(announcement);

      setTimeout(() => {
        document.body.removeChild(announcement);
      }, 1000);
    },
  };
}

// Export for potential module usage
if (typeof module !== "undefined" && module.exports) {
  module.exports = { dashboardApp };
}
