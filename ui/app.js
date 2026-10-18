/**
 * Alpine.js component for the Repair AI form.
 *
 * Calls the same-origin API (POST /v1/repair-descriptions) with the API key
 * the user pasted; no secrets ship with this file.
 */

const API_KEY_STORAGE = "repair_ai_api_key";
const COLD_START_HINT_MS = 10000;

let nextRowKey = 1;

function emptyRows() {
  return {
    findings: () => ({ code: "", description: "" }),
    operations: () => ({ code: "", description: "", status: "proposed" }),
    materials: () => ({ material_id: "", description: "", quantity: 1, unit: "" }),
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("repairForm", () => ({
    apiKey: "",
    form: {
      repair_type: "component_replacement",
      language: "en",
      style: "professional_customer_facing",
      equipment: "",
      findings: [],
      operations: [],
      materials: [],
    },
    submitting: false,
    slowHint: false,
    result: null,
    error: null,
    _wakeTimer: null,

    init() {
      this.apiKey = localStorage.getItem(API_KEY_STORAGE) || "";
      this.$watch("apiKey", (value) => {
        localStorage.setItem(API_KEY_STORAGE, value);
      });
      this.addRow("findings");
      this.addRow("operations");
      this.addRow("materials");
    },

    addRow(listName) {
      const row = emptyRows()[listName]();
      row.key = nextRowKey++;
      this.form[listName].push(row);
    },

    removeRow(listName, key) {
      this.form[listName] = this.form[listName].filter((row) => row.key !== key);
    },

    buildPayload() {
      const trim = (value) => value.trim();
      const optional = (value) => trim(value) || null;
      const filled = (row) => trim(row.description) !== "";

      return {
        repair_type: this.form.repair_type,
        language: this.form.language,
        style: this.form.style,
        equipment: { type: trim(this.form.equipment) },
        findings: this.form.findings.filter(filled).map((row) => ({
          code: optional(row.code),
          description: trim(row.description),
        })),
        operations: this.form.operations.filter(filled).map((row) => ({
          code: optional(row.code),
          description: trim(row.description),
          status: row.status,
        })),
        materials: this.form.materials.filter(filled).map((row) => ({
          material_id: optional(row.material_id),
          description: trim(row.description),
          quantity: Number(row.quantity),
          unit: trim(row.unit),
        })),
      };
    },

    describeError(status, body) {
      const detail = body && body.detail;

      if (status === 401) {
        return { title: "Missing API key", message: "Enter your API key above and retry.", details: [] };
      }
      if (status === 403) {
        return { title: "Invalid API key", message: "The key was rejected. Check it and retry.", details: [] };
      }
      if (status === 422 && Array.isArray(detail)) {
        return {
          title: "Invalid request data",
          message: "The server rejected the following fields:",
          details: detail.map((item) => {
            const path = (item.loc || []).filter((part) => part !== "body").join(" → ");
            return path ? `${path}: ${item.msg}` : item.msg;
          }),
        };
      }

      const titles = {
        413: "Request too large",
        500: "Draft rejected by validation",
        502: "Generation temporarily unavailable",
        503: "Authentication not configured",
      };
      return {
        title: titles[status] || `Unexpected error (${status})`,
        message: typeof detail === "string" ? detail : "Please retry or use the manual fallback process.",
        details: [],
      };
    },

    async submit() {
      this.result = null;
      this.error = null;
      this.submitting = true;
      this.slowHint = false;
      this._wakeTimer = setTimeout(() => {
        this.slowHint = true;
      }, COLD_START_HINT_MS);

      try {
        const response = await fetch("/v1/repair-descriptions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": this.apiKey,
          },
          body: JSON.stringify(this.buildPayload()),
        });
        const body = await response.json().catch(() => null);

        if (response.ok) {
          this.result = body;
        } else {
          this.error = this.describeError(response.status, body);
        }
      } catch (e) {
        this.error = {
          title: "Network error",
          message: "The service could not be reached. It may be starting up — retry shortly.",
          details: [],
        };
      } finally {
        clearTimeout(this._wakeTimer);
        this.submitting = false;
        this.slowHint = false;
      }
    },
  }));
});
