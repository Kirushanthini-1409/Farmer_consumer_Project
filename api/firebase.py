"""Firebase Admin SDK initialisation. The backend is the ONLY writer to Firestore."""
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

import config

_app = None


def init_app():
    global _app
    if _app is not None:
        return _app
    if config.SERVICE_ACCOUNT_JSON:
        cred = credentials.Certificate(json.loads(config.SERVICE_ACCOUNT_JSON))
    elif config.SERVICE_ACCOUNT_FILE:
        cred = credentials.Certificate(config.SERVICE_ACCOUNT_FILE)
    elif os.environ.get("FIRESTORE_EMULATOR_HOST") or os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):
        # Emulator mode: no real credentials needed or checked.
        import google.auth.credentials

        class _EmulatorCredential(credentials.Base):
            def get_credential(self):
                return google.auth.credentials.AnonymousCredentials()

        cred = _EmulatorCredential()
    else:
        cred = None  # Application Default Credentials (gcloud)
    options = {"projectId": os.environ.get("GCLOUD_PROJECT", "demo-farmconnect")}
    _app = firebase_admin.initialize_app(cred, options)
    return _app


def db():
    init_app()
    return firestore.client()
