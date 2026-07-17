// ---- Fill these in after creating your free accounts (see README) ----

// Firebase web app config (Firebase console → Project settings → Your apps).
// This is PUBLIC by design; Firestore rules protect the data.
const firebaseConfig = {
  apiKey: "fake-api-key",            // any value works against the local emulator
  authDomain: "demo-farmconnect.firebaseapp.com",
  projectId: "demo-farmconnect",
  appId: "demo",
};

// Local demo: point the Firebase SDK at the emulator suite (auth :9099, firestore :8080).
// Set to false and fill in real firebaseConfig values for production.
const USE_EMULATOR = true;

// Flask backend base URL: http://localhost:8000 in dev, your Render URL in prod.
const API_BASE = "http://localhost:8000";

// Cloudinary unsigned upload preset (images only, size-capped — configure in Cloudinary).
const CLOUDINARY_CLOUD = "YOUR_CLOUD_NAME";
const CLOUDINARY_PRESET = "farmconnect_unsigned";
