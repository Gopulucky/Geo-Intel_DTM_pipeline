// frontend/src/api/client.js
const BASE_URL = import.meta.env.VITE_API_URL;

export const api = {
    upload: async (file, villageName, epsgCode, streamThreshold) => {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("village_name", villageName);
        if (epsgCode) {
            formData.append("epsg_code", epsgCode);
        }
        if (streamThreshold !== undefined && streamThreshold !== null) {
            formData.append("stream_threshold", streamThreshold);
        }
        const res = await fetch(`${BASE_URL}/upload`, { method: "POST", body: formData });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || "Upload failed");
        }
        return res.json();
    },

    runDemo: async (villageName = "DEMO_Village") => {
        const res = await fetch(`${BASE_URL}/demo?village_name=${encodeURIComponent(villageName)}`, { method: "POST" });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || "Demo start failed");
        }
        return res.json();
    },

    rerunHydrology: async (jobId, streamThreshold) => {
        const formData = new FormData();
        formData.append("stream_threshold", streamThreshold);
        const res = await fetch(`${BASE_URL}/rerun-hydrology/${jobId}`, { method: "POST", body: formData });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || "Re-run failed");
        }
        return res.json();
    },

    getStatus: async (jobId) => {
        const res = await fetch(`${BASE_URL}/status/${jobId}`);
        if (!res.ok) throw new Error("Job not found");
        return res.json();
    },

    getFiles: async (jobId) => {
        const res = await fetch(`${BASE_URL}/files/${jobId}`);
        if (!res.ok) throw new Error("Could not load files");
        return res.json();
    },

    getGeoJSON: async (jobId) => {
        const res = await fetch(`${BASE_URL}/geojson/${jobId}`);
        if (!res.ok) throw new Error("DrainageDesign GeoJSON not available yet");
        return res.json();
    },

    getFileUrl: (jobId, filename) =>
        `${BASE_URL}/download/${jobId}/${filename}`,

    getZipUrl: (jobId) =>
        `${BASE_URL}/download-all/${jobId}`,

    checkHealth: async () => {
        const res = await fetch(`${BASE_URL}/health`);
        if (!res.ok) throw new Error("Health check failed");
        return res.json();
    }
};

