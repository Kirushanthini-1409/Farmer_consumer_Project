// ---- Fill these in after creating your free accounts (see README) ----

// Firebase web app config (Firebase console → Project settings → Your apps).
// This is PUBLIC by design; Firestore rules protect the data.
const firebaseConfig = {
  apiKey: "AIzaSyBKD_v2ZYQlCzEjJyu5x0oz95VdmFdn4L4",
  authDomain: "farmconnect-v2-2026.firebaseapp.com",
  projectId: "farmconnect-v2-2026",
  appId: "1:266774948308:web:50c740ac425cf91a508e41",
};

// Production: false. For local dev against the emulator suite set true and use
// projectId "demo-farmconnect" (see README).
const USE_EMULATOR = false;

// Flask backend base URL: http://localhost:8000 in dev, your Render URL in prod.
const API_BASE = "https://farmer-consumer-project.onrender.com";

// Cloudinary unsigned upload preset (images only, size-capped — configure in Cloudinary).
const CLOUDINARY_CLOUD = "YOUR_CLOUD_NAME";
const CLOUDINARY_PRESET = "farmconnect_unsigned";
