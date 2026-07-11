/**
 * LUMINA Vision Node — Frontend Application
 */

// Gunakan relative URL — frontend diserve dari server yang sama
const API_BASE_URL = "";

/* =========================================================
   DOM REFERENCES
   ========================================================= */

const $ = (selector) => document.querySelector(selector);

const dom = {
  // Status
  statusBadge: $("#statusBadge"),
  statusDot: $("#statusDot"),
  statusLabel: $("#statusLabel"),
  cameraStatus: $("#cameraStatus"),
  headerTime: $("#headerTime"),

  // Camera
  mjpegStream: $("#mjpegStream"),
  cameraPlaceholder: $("#cameraPlaceholder"),
  btnStart: $("#btnStartMonitor"),
  btnStop: $("#btnStopMonitor"),

  // Upload
  uploadForm: $("#uploadForm"),
  dropZone: $("#dropZone"),
  fileInput: $("#fileInput"),
  uploadPreview: $("#uploadPreview"),
  btnUpload: $("#btnUpload"),
  uploadStatus: $("#uploadStatus"),
  referenceGallery: $("#referenceGallery"),

  // Logs
  logsEmpty: $("#logsEmpty"),
  logTableWrapper: $("#logTableWrapper"),
  logTableBody: $("#logTableBody"),
  logCount: $("#logCount"),
  btnRefresh: $("#btnRefreshLogs"),

  // Modal
  detailModal: $("#detailModal"),
  modalTitle: $("#modalTitle"),
  modalBody: $("#modalBody"),
  btnModalClose: $("#btnModalClose"),

  // Toast
  toastContainer: $("#toastContainer"),

  // Patient Config
  patientName: $("#patientName"),
  patientStage: $("#patientStage"),
  emotionBadge: $("#emotionBadge"),
  emotionIndicator: $("#emotionIndicator"),
  emotionLabel: $("#emotionLabel"),
  btnRefreshEmotion: $("#btnRefreshEmotion"),
  btnSaveConfig: $("#btnSaveConfig"),
  configStatus: $("#configStatus"),

  // Camera Config
  cameraConfigForm: $("#cameraConfigForm"),
  cameraUrl: $("#cameraUrl"),
  cameraUsername: $("#cameraUsername"),
  cameraPassword: $("#cameraPassword"),
  btnSaveCamera: $("#btnSaveCamera"),
  cameraConfigStatus: $("#cameraConfigStatus"),

  // Memories (TASK 3)
  memoryForm: $("#memoryForm"),
  memoryName: $("#memoryName"),
  memoryRelation: $("#memoryRelation"),
  memoryPhoto: $("#memoryPhoto"),
  btnUploadMemory: $("#btnUploadMemory"),
  memoryStatus: $("#memoryStatus"),
  memoriesGallery: $("#memoriesGallery"),
  memoriesEmpty: $("#memoriesEmpty"),
};

/* =========================================================
   APPLICATION STATE
   ========================================================= */

let backendOnline = false;
let monitoringActive = false;
let selectedFile = null;
let logsRefreshInterval = null;
let statusRefreshInterval = null;

/* =========================================================
   UTILITIES
   ========================================================= */

function refreshIcons() {
  if (typeof lucide !== "undefined") {
    lucide.createIcons();
  }
}

function formatTime(date) {
  const parsedDate = new Date(date);

  if (Number.isNaN(parsedDate.getTime())) {
    return "--:--:--";
  }

  const hours = String(parsedDate.getHours()).padStart(2, "0");
  const minutes = String(parsedDate.getMinutes()).padStart(2, "0");
  const seconds = String(parsedDate.getSeconds()).padStart(2, "0");

  return `${hours}:${minutes}:${seconds}`;
}

function formatDate(date) {
  const parsedDate = new Date(date);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Unknown date";
  }

  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];

  return `${parsedDate.getDate()} ${
    months[parsedDate.getMonth()]
  } ${parsedDate.getFullYear()}`;
}

function formatDateTime(date) {
  return `${formatDate(date)}, ${formatTime(date)}`;
}

function statusLabel(status) {
  const map = {
    Safe: "Safe",
    Aman: "Safe",

    Attention: "Attention",
    Perhatian: "Attention",

    Emergency: "Emergency",
    Darurat: "Emergency",

    Error: "Error",
  };

  return map[status] || status || "Unknown";
}

function badgeClass(status) {
  const map = {
    Safe: "badge-safe",
    Aman: "badge-safe",

    Attention: "badge-attention",
    Perhatian: "badge-attention",

    Emergency: "badge-emergency",
    Darurat: "badge-emergency",

    Error: "badge-emergency",
  };

  return map[status] || "badge-attention";
}

function showToast(message, type = "info") {
  if (!dom.toastContainer) {
    console.log(`[${type}] ${message}`);
    return;
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  dom.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("toast-removing");

    toast.addEventListener("animationend", () => {
      toast.remove();
    });

    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, 1000);
  }, 3500);
}

function updateClock() {
  if (!dom.headerTime) {
    return;
  }

  const now = new Date();

  dom.headerTime.textContent = now.toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function normalizeBackendUrl(url) {
  if (!url) {
    return "";
  }

  if (
    url.startsWith("http://") ||
    url.startsWith("https://") ||
    url.startsWith("data:")
  ) {
    return url;
  }

  if (url.startsWith("/")) {
    return `${API_BASE_URL}${url}`;
  }

  return `${API_BASE_URL}/${url}`;
}

/* =========================================================
   GENERIC API REQUEST
   ========================================================= */

async function apiRequest(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
    },
  });

  let data = {};

  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    const message =
      data.detail ||
      data.message ||
      `Request failed with HTTP ${response.status}`;

    throw new Error(message);
  }

  return data;
}

/* =========================================================
   API CALLS
   ========================================================= */

async function apiGetStatus() {
  try {
    return await apiRequest("/api/status");
  } catch (error) {
    console.error("[LUMINA] Status fetch error:", error);
    return null;
  }
}

async function apiStartMonitoring() {
  try {
    return await apiRequest("/api/start-monitoring", {
      method: "POST",
    });
  } catch (error) {
    console.error("[LUMINA] Start monitoring error:", error);

    return {
      success: false,
      message:
        error.message ||
        "Cannot connect to backend. Please make sure the server is running.",
    };
  }
}

async function apiStopMonitoring() {
  try {
    return await apiRequest("/api/stop-monitoring", {
      method: "POST",
    });
  } catch (error) {
    console.error("[LUMINA] Stop monitoring error:", error);

    return {
      success: false,
      message: error.message || "Cannot connect to backend.",
    };
  }
}

async function apiGetLogs() {
  try {
    return await apiRequest("/api/logs?limit=100");
  } catch (error) {
    console.error("[LUMINA] Logs fetch error:", error);

    return {
      logs: [],
    };
  }
}

async function apiDeleteLog(id) {
  try {
    return await apiRequest(`/api/logs/${id}`, { method: "DELETE" });
  } catch (error) {
    console.error("[LUMINA] Delete log error:", error);
    return { success: false, detail: error.message };
  }
}

async function apiDeleteAllLogs() {
  try {
    return await apiRequest("/api/logs", { method: "DELETE" });
  } catch (error) {
    console.error("[LUMINA] Delete all logs error:", error);
    return { success: false, detail: error.message };
  }
}

async function apiUploadReference(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);

    return await apiRequest("/api/upload-reference", {
      method: "POST",
      body: formData,
    });
  } catch (error) {
    console.error("[LUMINA] Upload error:", error);

    return {
      success: false,
      detail: error.message || "Cannot connect to backend.",
    };
  }
}

async function apiGetReferencePhotos() {
  try {
    return await apiRequest("/api/reference-photos");
  } catch (error) {
    console.error("[LUMINA] Reference photos fetch error:", error);

    return {
      photos: [],
    };
  }
}

async function apiDeleteReferencePhoto(id) {
  try {
    return await apiRequest(`/api/reference-photos/${id}`, {
      method: "DELETE",
    });
  } catch (error) {
    console.error("[LUMINA] Delete photo error:", error);

    return {
      success: false,
      detail: error.message,
    };
  }
}

async function apiGetPatientConfig() {
  try {
    return await apiRequest("/api/patient-config");
  } catch (error) {
    console.error("[LUMINA] Get patient config error:", error);
    return null;
  }
}

async function apiUpdatePatientConfig(payload) {
  try {
    return await apiRequest("/api/patient-config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    console.error("[LUMINA] Update patient config error:", error);
    return {
      success: false,
      message: error.message || "Cannot connect to backend.",
    };
  }
}

/* =========================================================
   CAMERA CONFIG API
   ========================================================= */

async function apiGetCameraConfig() {
  try {
    return await apiRequest("/api/camera-config");
  } catch (error) {
    console.error("[LUMINA] Get camera config error:", error);
    return null;
  }
}

async function apiUpdateCameraConfig(payload) {
  try {
    return await apiRequest("/api/camera-config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    console.error("[LUMINA] Update camera config error:", error);
    return {
      success: false,
      message: error.message || "Cannot connect to backend.",
    };
  }
}

/* =========================================================
   MEMORIES API (TASK 3)
   ========================================================= */

async function apiUploadMemory(file, personName, relationship) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("person_name", personName);
    formData.append("relationship", relationship);

    return await apiRequest("/api/memories", {
      method: "POST",
      body: formData,
    });
  } catch (error) {
    console.error("[LUMINA] Memory upload error:", error);
    return {
      success: false,
      detail: error.message || "Cannot connect to backend.",
    };
  }
}

async function apiGetMemories() {
  try {
    return await apiRequest("/api/memories?limit=20");
  } catch (error) {
    console.error("[LUMINA] Memories fetch error:", error);
    return { memories: [] };
  }
}

async function apiDeleteMemory(id) {
  try {
    return await apiRequest(`/api/memories/${id}`, { method: "DELETE" });
  } catch (error) {
    console.error("[LUMINA] Memory delete error:", error);
    return { success: false, detail: error.message };
  }
}

/* =========================================================
   CAMERA CONFIG UI
   ========================================================= */

async function loadCameraConfig() {
  const data = await apiGetCameraConfig();
  if (!data) return;

  if (dom.cameraUrl) {
    dom.cameraUrl.value = data.camera_url || "";
  }
  if (dom.cameraUsername) {
    dom.cameraUsername.value = data.camera_username || "";
  }
  if (dom.cameraPassword) {
    // Don't pre-fill password — user must re-enter
    dom.cameraPassword.value = "";
    dom.cameraPassword.placeholder = data.has_password
      ? "•••••• (enter new to change)"
      : "Camera password";
  }
}

async function saveCameraConfig() {
  if (!dom.cameraUrl || !dom.cameraUrl.value.trim()) {
    showToast("Camera URL is required.", "error");
    return;
  }

  if (!dom.btnSaveCamera) return;

  dom.btnSaveCamera.disabled = true;
  dom.btnSaveCamera.innerHTML =
    '<i data-lucide="loader-2" class="icon-sm icon-spin"></i> Saving...';

  if (dom.cameraConfigStatus) {
    dom.cameraConfigStatus.textContent = "";
    dom.cameraConfigStatus.className = "config-status";
  }

  const url = dom.cameraUrl.value.trim();
  const username = dom.cameraUsername?.value.trim() || "";
  const password = dom.cameraPassword?.value || "";

  const result = await apiUpdateCameraConfig({
    camera_url: url,
    camera_username: username,
    camera_password: password,
  });

  if (result.success !== false) {
    if (dom.cameraConfigStatus) {
      dom.cameraConfigStatus.textContent =
        "Camera config saved! Restart monitoring to apply.";
      dom.cameraConfigStatus.className = "config-status success";
    }
    showToast("Camera configuration saved.", "success");
  } else {
    if (dom.cameraConfigStatus) {
      dom.cameraConfigStatus.textContent =
        result.message || "Failed to save camera config.";
      dom.cameraConfigStatus.className = "config-status error";
    }
    showToast(result.message || "Failed to save camera config.", "error");
  }

  dom.btnSaveCamera.disabled = false;
  dom.btnSaveCamera.innerHTML =
    '<i data-lucide="save" class="icon-sm"></i> Save Camera Config';
  refreshIcons();
}

/* =========================================================
   PATIENT CONFIG UI — Stage Adaptation & Emotion Agent
   ========================================================= */

function getEmotionStyle(emotion) {
  const map = {
    calm: { color: "#22c55e", label: "Calm", icon: "●" },
    anxious: { color: "#f59e0b", label: "Anxious", icon: "●" },
    confused: { color: "#a855f7", label: "Confused", icon: "●" },
  };
  return (
    map[emotion] || { color: "#94a3b8", label: emotion || "Unknown", icon: "●" }
  );
}

async function loadPatientConfig() {
  const data = await apiGetPatientConfig();
  if (!data || !data.config) {
    return;
  }

  const config = data.config;
  const autoEmotion = data.auto_detected_emotion || "calm";

  if (dom.patientName) {
    dom.patientName.value = config.patient_name || "";
  }
  if (dom.patientStage) {
    dom.patientStage.value = config.patient_stage || 1;
  }

  updateEmotionDisplay(autoEmotion);
}

function updateEmotionDisplay(emotion) {
  const style = getEmotionStyle(emotion);

  if (dom.emotionBadge) {
    dom.emotionBadge.textContent = style.label.toUpperCase();
    dom.emotionBadge.style.color = style.color;
  }
  if (dom.emotionIndicator) {
    dom.emotionIndicator.textContent = style.icon;
    dom.emotionIndicator.style.color = style.color;
  }
  if (dom.emotionLabel) {
    dom.emotionLabel.textContent = style.label;
    dom.emotionLabel.style.color = style.color;
  }
}

async function savePatientConfig() {
  if (!dom.btnSaveConfig) {
    return;
  }

  dom.btnSaveConfig.disabled = true;
  dom.btnSaveConfig.innerHTML =
    '<i data-lucide="loader-2" class="icon-sm icon-spin"></i> Saving...';

  if (dom.configStatus) {
    dom.configStatus.textContent = "";
    dom.configStatus.className = "config-status";
  }

  const payload = {};

  if (dom.patientName && dom.patientName.value.trim()) {
    payload.patient_name = dom.patientName.value.trim();
  }
  if (dom.patientStage) {
    payload.patient_stage = parseInt(dom.patientStage.value, 10);
  }

  const result = await apiUpdatePatientConfig(payload);

  if (result.success !== false) {
    if (dom.configStatus) {
      dom.configStatus.textContent = "Saved!";
      dom.configStatus.className = "config-status success";
    }
    showToast("Patient profile updated successfully.", "success");

    // Re-fetch to refresh auto-detected emotion
    await loadPatientConfig();
  } else {
    if (dom.configStatus) {
      dom.configStatus.textContent = result.message || "Save failed.";
      dom.configStatus.className = "config-status error";
    }
    showToast(result.message || "Failed to save config.", "error");
  }

  dom.btnSaveConfig.disabled = false;
  dom.btnSaveConfig.innerHTML =
    '<i data-lucide="save" class="icon-sm"></i> Save Profile';

  refreshIcons();
}

async function refreshEmotion() {
  if (!dom.btnRefreshEmotion) {
    return;
  }

  dom.btnRefreshEmotion.disabled = true;

  const data = await apiGetPatientConfig();

  if (data && data.auto_detected_emotion) {
    updateEmotionDisplay(data.auto_detected_emotion);
  }

  dom.btnRefreshEmotion.disabled = false;
  refreshIcons();
}

/* =========================================================
   CONNECTION AND MONITORING UI
   ========================================================= */

function updateMonitoringUI() {
  if (!backendOnline) {
    dom.statusBadge?.classList.add("badge-offline");
    dom.statusDot?.classList.remove("active");
    dom.statusDot?.classList.add("warning");

    if (dom.statusLabel) {
      dom.statusLabel.textContent = "OFFLINE";
    }

    if (dom.cameraStatus) {
      dom.cameraStatus.textContent = "Offline";
      dom.cameraStatus.classList.remove("live");
    }

    dom.cameraPlaceholder?.classList.remove("hidden");
    dom.btnStart?.classList.remove("hidden");
    dom.btnStop?.classList.add("hidden");

    return;
  }

  dom.statusBadge?.classList.remove("badge-offline");
  dom.statusDot?.classList.remove("warning");

  if (monitoringActive) {
    dom.btnStart?.classList.add("hidden");
    dom.btnStop?.classList.remove("hidden");

    dom.statusDot?.classList.add("active");

    if (dom.statusLabel) {
      dom.statusLabel.textContent = "ACTIVE";
    }

    if (dom.cameraStatus) {
      dom.cameraStatus.textContent = "Live";
      dom.cameraStatus.classList.add("live");
    }

    dom.cameraPlaceholder?.classList.add("hidden");
  } else {
    dom.btnStart?.classList.remove("hidden");
    dom.btnStop?.classList.add("hidden");

    dom.statusDot?.classList.remove("active");

    if (dom.statusLabel) {
      dom.statusLabel.textContent = "IDLE";
    }

    if (dom.cameraStatus) {
      dom.cameraStatus.textContent = "Offline";
      dom.cameraStatus.classList.remove("live");
    }

    dom.cameraPlaceholder?.classList.remove("hidden");
  }
}

function applyStreamUrl(streamUrl) {
  if (!dom.mjpegStream || !streamUrl) {
    return;
  }

  dom.mjpegStream.src = normalizeBackendUrl(streamUrl);
}

function fixExistingStreamUrl() {
  if (!dom.mjpegStream) {
    return;
  }

  const originalSrc = dom.mjpegStream.getAttribute("src");

  if (originalSrc && originalSrc.startsWith("/")) {
    dom.mjpegStream.src = `${API_BASE_URL}${originalSrc}`;
  }
}

/* =========================================================
   MONITORING CONTROL
   ========================================================= */

async function startMonitoring() {
  if (!dom.btnStart) {
    return;
  }

  dom.btnStart.disabled = true;
  dom.btnStart.textContent = "Starting...";

  const result = await apiStartMonitoring();

  dom.btnStart.disabled = false;

  const success = result && result.success !== false;

  if (success) {
    backendOnline = true;
    monitoringActive = true;

    const streamUrl =
      result.stream_url || result.video_url || result.camera_stream_url || null;

    if (streamUrl) {
      applyStreamUrl(streamUrl);
    }

    updateMonitoringUI();

    showToast("Monitoring started. System searching for patient...", "success");

    await refreshLogs();
  } else {
    showToast(result?.message || "Failed to start monitoring.", "error");

    dom.btnStart.innerHTML =
      '<i data-lucide="play" class="icon-sm"></i> Start Monitoring';

    refreshIcons();
  }
}

async function stopMonitoring() {
  if (!dom.btnStop) {
    return;
  }

  dom.btnStop.disabled = true;
  dom.btnStop.textContent = "Stopping...";

  const result = await apiStopMonitoring();

  dom.btnStop.disabled = false;

  const success = result && result.success !== false;

  if (success) {
    backendOnline = true;
    monitoringActive = false;

    updateMonitoringUI();

    showToast("Monitoring stopped.", "info");
  } else {
    showToast(result?.message || "Failed to stop monitoring.", "error");

    dom.btnStop.innerHTML = '<i data-lucide="square" class="icon-sm"></i> Stop';

    refreshIcons();
  }
}

async function pollStatus() {
  const status = await apiGetStatus();

  if (!status) {
    backendOnline = false;
    monitoringActive = false;

    updateMonitoringUI();
    return;
  }

  backendOnline = true;

  monitoringActive = Boolean(
    status.monitoring_active ?? status.active ?? status.is_monitoring ?? false,
  );

  updateMonitoringUI();

  if (monitoringActive && dom.statusLabel) {
    const mode = String(status.mode || "").toUpperCase();

    if (mode === "TRACKING") {
      dom.statusLabel.textContent = "TRACKING";
    } else if (mode === "SEARCHING") {
      dom.statusLabel.textContent = "SEARCHING";
    } else {
      dom.statusLabel.textContent = "ACTIVE";
    }
  }

  const streamUrl =
    status.stream_url || status.video_url || status.camera_stream_url || null;

  if (streamUrl) {
    applyStreamUrl(streamUrl);
  }
}

/* =========================================================
   LOG DISPLAY
   ========================================================= */

async function refreshLogs() {
  const data = await apiGetLogs();

  let logs = [];

  if (Array.isArray(data)) {
    logs = data;
  } else if (Array.isArray(data.logs)) {
    logs = data.logs;
  }

  renderLogs(logs);
}

function renderLogs(logs) {
  if (!Array.isArray(logs)) {
    logs = [];
  }

  if (dom.logCount) {
    dom.logCount.textContent = `${logs.length} entries`;
  }

  if (dom.logTableBody) {
    dom.logTableBody.innerHTML = "";
  }

  if (logs.length === 0) {
    dom.logsEmpty?.classList.remove("hidden");
    dom.logTableWrapper?.classList.add("hidden");
    return;
  }

  dom.logsEmpty?.classList.add("hidden");
  dom.logTableWrapper?.classList.remove("hidden");

  logs.forEach((log) => {
    const row = document.createElement("tr");

    row.setAttribute("role", "button");
    row.setAttribute("tabindex", "0");
    row.setAttribute(
      "aria-label",
      `Log ${formatDateTime(log.timestamp)} — ${statusLabel(log.alert_status)}`,
    );

    const timeCell = document.createElement("td");

    timeCell.innerHTML = `
      <div style="font-weight: 500;">
        ${formatTime(log.timestamp)}
      </div>
      <div style="font-size: 0.6875rem; color: #94A3B8;">
        ${formatDate(log.timestamp)}
      </div>
    `;

    const statusCell = document.createElement("td");

    const statusBadge = document.createElement("span");
    statusBadge.className = `badge ${badgeClass(log.alert_status)}`;
    statusBadge.textContent = statusLabel(log.alert_status);

    statusCell.appendChild(statusBadge);

    const activityCell = document.createElement("td");

    activityCell.style.maxWidth = "180px";
    activityCell.style.overflow = "hidden";
    activityCell.style.textOverflow = "ellipsis";
    activityCell.style.whiteSpace = "nowrap";

    activityCell.textContent = log.activity_description || log.activity || "—";

    const snapshotCell = document.createElement("td");

    if (log.snapshot_base64) {
      const image = document.createElement("img");

      image.className = "snapshot-thumb";
      image.src = `data:image/jpeg;base64,${log.snapshot_base64}`;
      image.alt = `Snapshot ${formatDateTime(log.timestamp)}`;
      image.loading = "lazy";

      snapshotCell.appendChild(image);
    } else if (log.snapshot_url || log.snapshot_path) {
      const image = document.createElement("img");

      image.className = "snapshot-thumb";
      image.src = normalizeBackendUrl(log.snapshot_url || log.snapshot_path);
      image.alt = `Snapshot ${formatDateTime(log.timestamp)}`;
      image.loading = "lazy";

      snapshotCell.appendChild(image);
    } else {
      snapshotCell.textContent = "—";
      snapshotCell.style.color = "#64748B";
    }

    // Actions cell with delete button
    const actionsCell = document.createElement("td");
    actionsCell.className = "td-actions";

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-ghost btn-sm btn-delete-log";
    deleteBtn.setAttribute("aria-label", "Delete this log");
    deleteBtn.title = "Delete this log";
    deleteBtn.innerHTML = '<i data-lucide="trash-2" class="icon-sm"></i>';

    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteLogEntry(log.id, row);
    });

    actionsCell.appendChild(deleteBtn);

    row.append(timeCell, statusCell, activityCell, snapshotCell, actionsCell);

    row.addEventListener("click", () => {
      openDetailModal(log);
    });

    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDetailModal(log);
      }
    });

    dom.logTableBody?.appendChild(row);
  });

  refreshIcons();
}

async function deleteLogEntry(logId, rowElement) {
  const result = await apiDeleteLog(logId);
  if (result.success !== false) {
    showToast("Log deleted.", "success");
    if (rowElement) {
      rowElement.style.opacity = "0";
      rowElement.style.transition = "opacity 0.3s";
      setTimeout(() => {
        rowElement.remove();
        // Update count
        const remaining = dom.logTableBody?.querySelectorAll("tr").length || 0;
        if (dom.logCount) {
          dom.logCount.textContent = `${remaining} entries`;
        }
        if (remaining === 0) {
          dom.logsEmpty?.classList.remove("hidden");
          dom.logTableWrapper?.classList.add("hidden");
        }
      }, 300);
    }
  } else {
    showToast(result.detail || "Failed to delete log.", "error");
  }
}

async function deleteAllLogs() {
  if (
    !confirm(
      "Are you sure you want to delete ALL analysis history? This cannot be undone.",
    )
  ) {
    return;
  }

  const result = await apiDeleteAllLogs();
  if (result.success !== false) {
    showToast(result.message || "All logs deleted.", "success");
    await refreshLogs();
  } else {
    showToast(result.detail || "Failed to delete logs.", "error");
  }
}

/* =========================================================
   DETAIL MODAL
   ========================================================= */

function openDetailModal(log) {
  if (!dom.detailModal || !dom.modalBody || !dom.modalTitle) {
    return;
  }

  dom.modalTitle.textContent = `Analysis — ${formatDateTime(log.timestamp)}`;

  dom.modalBody.innerHTML = "";

  if (log.snapshot_base64) {
    const image = document.createElement("img");

    image.src = `data:image/jpeg;base64,${log.snapshot_base64}`;
    image.alt = "Snapshot";

    dom.modalBody.appendChild(image);
  } else if (log.snapshot_url || log.snapshot_path) {
    const image = document.createElement("img");

    image.src = normalizeBackendUrl(log.snapshot_url || log.snapshot_path);

    image.alt = "Snapshot";

    dom.modalBody.appendChild(image);
  }

  const statusRow = document.createElement("div");
  statusRow.className = "detail-row";

  const statusTitle = document.createElement("div");
  statusTitle.className = "detail-label";
  statusTitle.textContent = "Status";

  const statusValue = document.createElement("div");
  statusValue.className = "detail-value";

  const badge = document.createElement("span");
  badge.className = `badge ${badgeClass(log.alert_status)}`;
  badge.textContent = statusLabel(log.alert_status);

  statusValue.appendChild(badge);
  statusRow.append(statusTitle, statusValue);

  const activityRow = document.createElement("div");
  activityRow.className = "detail-row";

  const activityTitle = document.createElement("div");
  activityTitle.className = "detail-label";
  activityTitle.textContent = "Activity Description";

  const activityValue = document.createElement("div");
  activityValue.className = "detail-value";
  activityValue.textContent =
    log.activity_description || log.activity || "No description.";

  activityRow.append(activityTitle, activityValue);

  const reportRow = document.createElement("div");
  reportRow.className = "detail-row";

  const reportTitle = document.createElement("div");
  reportTitle.className = "detail-label";
  reportTitle.textContent = "AI Narrative Report";

  const reportValue = document.createElement("div");
  reportValue.className = "detail-value";
  reportValue.textContent = log.narrative_report || "No report available.";

  reportRow.append(reportTitle, reportValue);

  dom.modalBody.append(statusRow, activityRow, reportRow);

  dom.detailModal.classList.remove("hidden");

  dom.btnModalClose?.focus();

  dom.detailModal.addEventListener("keydown", handleModalKeydown);
}

function closeDetailModal() {
  if (!dom.detailModal) {
    return;
  }

  dom.detailModal.classList.add("hidden");

  dom.detailModal.removeEventListener("keydown", handleModalKeydown);
}

function handleModalKeydown(event) {
  if (event.key === "Escape") {
    closeDetailModal();
  }
}

/* =========================================================
   REFERENCE PHOTO UPLOAD
   ========================================================= */

function handleFileSelect(file) {
  if (!file) {
    return;
  }

  const allowedFormats = ["image/jpeg", "image/png", "image/bmp"];

  if (!allowedFormats.includes(file.type)) {
    showToast("Unsupported file format. Please use JPG, PNG, or BMP.", "error");

    return;
  }

  if (file.size > 10 * 1024 * 1024) {
    showToast("File size too large. Maximum 10 MB.", "error");

    return;
  }

  selectedFile = file;

  if (dom.btnUpload) {
    dom.btnUpload.disabled = false;
  }

  if (dom.uploadStatus) {
    dom.uploadStatus.textContent = "";
    dom.uploadStatus.className = "upload-status";
  }

  const reader = new FileReader();

  reader.onload = (event) => {
    if (dom.uploadPreview) {
      dom.uploadPreview.src = event.target.result;
      dom.uploadPreview.classList.remove("hidden");
    }

    const dropzoneContent = dom.dropZone?.querySelector(".dropzone-content");

    if (dropzoneContent) {
      dropzoneContent.style.opacity = "0";
    }
  };

  reader.readAsDataURL(file);
}

async function uploadReference() {
  if (!selectedFile || !dom.btnUpload) {
    return;
  }

  dom.btnUpload.disabled = true;
  dom.btnUpload.innerHTML =
    '<i data-lucide="loader-2" class="icon-sm icon-spin"></i> Uploading...';

  if (dom.uploadStatus) {
    dom.uploadStatus.textContent = "";
    dom.uploadStatus.className = "upload-status";
  }

  const result = await apiUploadReference(selectedFile);

  if (result.success !== false) {
    backendOnline = true;

    // Reload patient data in the engine (new photo → fingerprint + face encoding)
    try {
      await apiRequest("/api/reload-patient-data", { method: "POST" });
    } catch (e) {
      // Non-critical — the engine will pick up the new photo on next restart
      console.warn("[LUMINA] Engine reload skipped:", e.message);
    }

    if (dom.uploadStatus) {
      dom.uploadStatus.textContent = "Upload successful!";
      dom.uploadStatus.className = "upload-status success";
    }

    showToast("Reference photo uploaded successfully.", "success");

    resetUploadForm();
    await loadReferencePhotos();
  } else {
    const errorMessage = result.detail || result.message || "Upload failed.";

    if (dom.uploadStatus) {
      dom.uploadStatus.textContent = errorMessage;
      dom.uploadStatus.className = "upload-status error";
    }

    showToast(errorMessage, "error");
  }

  dom.btnUpload.disabled = selectedFile === null;

  dom.btnUpload.innerHTML =
    '<i data-lucide="check" class="icon-sm"></i> Upload Photo';

  refreshIcons();
}

function resetUploadForm() {
  selectedFile = null;

  if (dom.fileInput) {
    dom.fileInput.value = "";
  }

  dom.uploadPreview?.classList.add("hidden");

  const dropzoneContent = dom.dropZone?.querySelector(".dropzone-content");

  if (dropzoneContent) {
    dropzoneContent.style.opacity = "1";
  }

  if (dom.btnUpload) {
    dom.btnUpload.disabled = true;
  }
}

/* =========================================================
   REFERENCE PHOTO GALLERY
   ========================================================= */

async function loadReferencePhotos() {
  const data = await apiGetReferencePhotos();

  let photos = [];

  if (Array.isArray(data)) {
    photos = data;
  } else if (Array.isArray(data.photos)) {
    photos = data.photos;
  }

  renderReferenceGallery(photos);
}

function renderReferenceGallery(photos) {
  if (!dom.referenceGallery) {
    return;
  }

  dom.referenceGallery.innerHTML = "";

  if (!photos || photos.length === 0) {
    dom.referenceGallery.innerHTML =
      '<div class="reference-gallery-empty">' +
      "No reference photos yet. Upload a patient photo above." +
      "</div>";

    return;
  }

  photos.forEach((photo) => {
    const card = document.createElement("div");
    card.className = "ref-photo-card";

    const image = document.createElement("img");

    const photoUrl =
      photo.url ||
      photo.file_url ||
      photo.path ||
      `/patient_photos/${encodeURIComponent(photo.filename)}`;

    image.src = normalizeBackendUrl(photoUrl);

    image.alt = `Reference photo: ${photo.filename || "patient"}`;

    image.loading = "lazy";

    image.onerror = () => {
      card.remove();
    };

    const deleteButton = document.createElement("button");

    deleteButton.className = "ref-delete";
    deleteButton.innerHTML = "&times;";

    deleteButton.setAttribute(
      "aria-label",
      `Delete ${photo.filename || "photo"}`,
    );

    deleteButton.addEventListener("click", async (event) => {
      event.stopPropagation();

      const confirmed = confirm(
        `Delete reference photo "${photo.filename || "foto ini"}"?`,
      );

      if (!confirmed) {
        return;
      }

      const result = await apiDeleteReferencePhoto(photo.id);

      if (result.success === false) {
        showToast(
          result.detail || "Failed to delete the reference photo.",
          "error",
        );

        return;
      }

      showToast("Reference photo deleted.", "info");

      await loadReferencePhotos();
    });

    card.append(image, deleteButton);
    dom.referenceGallery.appendChild(card);
  });
}

/* =========================================================
   MEMORIES (TASK 3)
   ========================================================= */

async function loadMemories() {
  const data = await apiGetMemories();
  const memories = data?.memories || [];
  renderMemoriesGallery(memories);
}

function renderMemoriesGallery(memories) {
  if (!dom.memoriesGallery) return;

  dom.memoriesGallery.innerHTML = "";

  if (!memories || memories.length === 0) {
    if (dom.memoriesEmpty) {
      dom.memoriesEmpty.style.display = "block";
      dom.memoriesGallery.appendChild(dom.memoriesEmpty);
    }
    return;
  }

  if (dom.memoriesEmpty) dom.memoriesEmpty.style.display = "none";

  memories.forEach((mem) => {
    const card = document.createElement("div");
    card.className = "memory-card";

    if (mem.photo_base64) {
      const img = document.createElement("img");
      img.src = `data:image/jpeg;base64,${mem.photo_base64}`;
      img.alt = `Photo of ${mem.person_name}`;
      img.className = "memory-photo";
      img.loading = "lazy";
      card.appendChild(img);
    }

    const info = document.createElement("div");
    info.className = "memory-info";

    const nameEl = document.createElement("div");
    nameEl.className = "memory-name";
    nameEl.textContent = mem.person_name || "Unknown";

    const relEl = document.createElement("div");
    relEl.className = "memory-relation";
    relEl.textContent = mem.relationship || "";

    const delBtn = document.createElement("button");
    delBtn.className = "memory-delete";
    delBtn.innerHTML = "&times;";
    delBtn.title = "Delete this memory";
    delBtn.setAttribute("aria-label", `Delete memory of ${mem.person_name}`);
    delBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (confirm(`Delete memory of "${mem.person_name}"?`)) {
        await apiDeleteMemory(mem.id);
        await loadMemories();
      }
    });

    info.appendChild(nameEl);
    info.appendChild(relEl);
    card.appendChild(info);
    card.appendChild(delBtn);
    dom.memoriesGallery.appendChild(card);
  });
}

async function uploadMemory() {
  const nameInput = dom.memoryName;
  const relInput = dom.memoryRelation;
  const photoInput = dom.memoryPhoto;
  const statusEl = dom.memoryStatus;

  if (!nameInput || !relInput || !photoInput) return;

  const personName = nameInput.value.trim();
  const relationship = relInput.value.trim();
  const file = photoInput.files?.[0];

  if (!personName || !relationship || !file) {
    if (statusEl) {
      statusEl.textContent = "Please fill in all fields and select a photo.";
      statusEl.className = "memory-status error";
    }
    return;
  }

  if (dom.btnUploadMemory) {
    dom.btnUploadMemory.disabled = true;
    dom.btnUploadMemory.textContent = "Uploading...";
  }

  const result = await apiUploadMemory(file, personName, relationship);

  if (result.success) {
    if (statusEl) {
      statusEl.textContent = "Memory uploaded successfully!";
      statusEl.className = "memory-status success";
    }
    nameInput.value = "";
    relInput.value = "";
    photoInput.value = "";
    await loadMemories();
  } else {
    if (statusEl) {
      statusEl.textContent = result.detail || "Upload failed.";
      statusEl.className = "memory-status error";
    }
  }

  if (dom.btnUploadMemory) {
    dom.btnUploadMemory.disabled = false;
    dom.btnUploadMemory.textContent = "Upload Memory";
  }
}

async function clearAllMemories() {
  const data = await apiGetMemories();
  const memories = data?.memories || [];
  if (memories.length === 0) {
    showToast("No memories to clear.", "info");
    return;
  }
  if (
    !confirm(`Delete all ${memories.length} memories? This cannot be undone.`)
  )
    return;

  let deleted = 0;
  for (const mem of memories) {
    const ok = await apiDeleteMemory(mem.id);
    if (ok) deleted++;
  }
  showToast(`${deleted} memories deleted.`, "info");
  await loadMemories();
}

/* =========================================================
   EVENT LISTENERS
   ========================================================= */

dom.btnStart?.addEventListener("click", startMonitoring);
dom.btnStop?.addEventListener("click", stopMonitoring);

dom.dropZone?.addEventListener("click", () => {
  dom.fileInput?.click();
});

dom.fileInput?.addEventListener("change", (event) => {
  const files = event.target.files;

  if (files && files.length > 0) {
    handleFileSelect(files[0]);
  }
});

dom.dropZone?.addEventListener("dragover", (event) => {
  event.preventDefault();
  dom.dropZone.classList.add("drag-over");
});

dom.dropZone?.addEventListener("dragleave", () => {
  dom.dropZone.classList.remove("drag-over");
});

dom.dropZone?.addEventListener("drop", (event) => {
  event.preventDefault();

  dom.dropZone.classList.remove("drag-over");

  const files = event.dataTransfer.files;

  if (files && files.length > 0) {
    handleFileSelect(files[0]);
  }
});

dom.uploadForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  uploadReference();
});

dom.btnRefresh?.addEventListener("click", refreshLogs);

const btnClearLogs = document.getElementById("btnClearLogs");
btnClearLogs?.addEventListener("click", deleteAllLogs);

dom.btnModalClose?.addEventListener("click", closeDetailModal);

dom.detailModal?.addEventListener("click", (event) => {
  if (event.target === dom.detailModal) {
    closeDetailModal();
  }
});

// ── Camera Config Events ──────────────────────────────────────────────
dom.cameraConfigForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  saveCameraConfig();
});

// ── Patient Config Events ─────────────────────────────────────────────
dom.btnSaveConfig?.addEventListener("click", savePatientConfig);
dom.btnRefreshEmotion?.addEventListener("click", refreshEmotion);

// ── Memories Events ───────────────────────────────────────────────────
dom.memoryForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  uploadMemory();
});

const btnClearMemories = document.getElementById("btnClearMemories");
btnClearMemories?.addEventListener("click", clearAllMemories);

/* =========================================================
   INITIALIZATION
   ========================================================= */

async function init() {
  refreshIcons();

  updateClock();
  setInterval(updateClock, 1000);

  fixExistingStreamUrl();

  const status = await apiGetStatus();

  if (status) {
    backendOnline = true;

    monitoringActive = Boolean(
      status.monitoring_active ??
      status.active ??
      status.is_monitoring ??
      false,
    );

    const streamUrl =
      status.stream_url || status.video_url || status.camera_stream_url || null;

    if (streamUrl) {
      applyStreamUrl(streamUrl);
    }
  } else {
    backendOnline = false;
    monitoringActive = false;

    showToast(
      "Backend is unreachable — make sure the server is running.",
      "error",
    );
  }

  updateMonitoringUI();

  await refreshLogs();
  await loadReferencePhotos();
  await loadPatientConfig();
  await loadCameraConfig();
  await loadMemories();

  logsRefreshInterval = setInterval(refreshLogs, 10000);

  statusRefreshInterval = setInterval(pollStatus, 5000);
}

init();
