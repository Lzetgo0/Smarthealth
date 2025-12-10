import joblib
import numpy as np
import pandas as pd
from collections import deque
import os

class ModelService:
    def __init__(self, pkl_path, roll_size=3):
        if not os.path.exists(pkl_path):
            raise FileNotFoundError(f"Model not found at {pkl_path}")
        self.model = joblib.load(pkl_path)
        # try to load scaler if present next to model
        scaler_path = os.path.join(os.path.dirname(pkl_path), "scaler.pkl")
        self.scaler = joblib.load(scaler_path) if os.path.exists(scaler_path) else None

        # keep per-device history for delta & rolling
        self.history = {}  # device -> deque of last values
        self.last = {}     # device -> last reading

        self.roll_size = roll_size

    def _ensure_device(self, device):
        if device not in self.history:
            self.history[device] = {"temp": deque(maxlen=self.roll_size),
                                    "hum": deque(maxlen=self.roll_size),
                                    "gas": deque(maxlen=self.roll_size)}
            self.last[device] = {"temp": None, "hum": None, "gas": None}

    def compute_features(self, device, temp, hum, gas, ts=None):
        """
        Returns raw feature array shaped (1, n_features)
        default feature order: temp, hum, gas, d_temp, d_hum, d_gas, r_temp, r_hum, r_gas
        Adjust if your training pipeline differs.
        """
        self._ensure_device(device)
        last = self.last[device]
        d_temp = 0.0 if last["temp"] is None else temp - last["temp"]
        d_hum  = 0.0 if last["hum"] is None else hum - last["hum"]
        d_gas  = 0.0 if last["gas"] is None else gas - last["gas"]

        # update history and rolling mean
        h = self.history[device]
        h["temp"].append(temp)
        h["hum"].append(hum)
        h["gas"].append(gas)

        r_temp = float(sum(h["temp"]) / len(h["temp"]))
        r_hum  = float(sum(h["hum"]) / len(h["hum"]))
        r_gas  = float(sum(h["gas"]) / len(h["gas"]))

        self.last[device] = {"temp": temp, "hum": hum, "gas": gas}

        features = np.array([[temp, hum, gas, d_temp, d_hum, d_gas, r_temp, r_hum, r_gas]])
        # return raw features; scaling and column naming handled in predict_from_features
        return features

    def predict_from_features(self, features):
        """
        Accepts numpy array or list-like of shape (1, n_features) or (n_samples, n_features).
        Converts to DataFrame with appropriate column names, applies scaler if present,
        and returns model prediction as string.
        """
        # ensure numpy array
        arr = np.asarray(features)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        # determine expected feature names
        default_names = ["temp","hum","gas","d_temp","d_hum","d_gas","r_temp","r_hum","r_gas"]
        model_feat = getattr(self.model, "feature_names_in_", None)
        feature_names = list(model_feat) if model_feat is not None else default_names

        # basic validation of shape vs feature names
        if arr.shape[1] != len(feature_names):
            raise ValueError(f"Feature dimension mismatch: got {arr.shape[1]} features but model expects {len(feature_names)}")

        # build DataFrame with correct column names
        X = pd.DataFrame(arr, columns=feature_names)

        # apply scaler if present (scale numeric values, keep as DataFrame so feature names persist)
        if self.scaler is not None:
            scaled = self.scaler.transform(X.values)
            X = pd.DataFrame(scaled, columns=feature_names)

        # ensure column order matches model if model has names
        if model_feat is not None:
            # reorder to model.feature_names_in_ (in case of different ordering)
            X = X[list(model_feat)]

        pred = self.model.predict(X)
        return str(pred[0])