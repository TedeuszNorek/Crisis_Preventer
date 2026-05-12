"""Gaussian Mixture Model regime classification for crypto markets.

Replaces static threshold-based signals with adaptive, unsupervised
regime detection using GMM clustering on market features.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

LOGGER = logging.getLogger(__name__)

# Default regime names (will be assigned based on cluster characteristics)
REGIME_NAMES = {
    "high_leverage": "Overleveraged — high funding, rising OI",
    "normal": "Normal — balanced market conditions",
    "deleveraging": "Deleveraging — falling OI, negative funding",
    "accumulation": "Accumulation — rising OI, neutral funding",
}


@dataclass
class RegimeLabel:
    """A single regime classification result."""
    regime: str
    probability: float
    all_probabilities: Dict[str, float]
    features_used: Dict[str, float]


@dataclass
class RegimeClassifierResult:
    """Full result from regime classification."""
    current_regime: RegimeLabel
    regime_history: List[RegimeLabel]
    n_regimes: int
    regime_transitions: int  # Number of regime changes in history
    model_bic: float  # Model quality metric
    interpretation: str


class RegimeClassifier:
    """GMM-based regime classifier for crypto markets.
    
    Uses Gaussian Mixture Models to identify market regimes based on:
    - Funding rate (normalized)
    - OI change (normalized)
    - L/S ratio (normalized)
    - Price momentum (normalized)
    """
    
    def __init__(
        self,
        n_components: int = 3,
        min_samples: int = 50,
        random_state: int = 42,
    ):
        """Initialize the regime classifier.
        
        Args:
            n_components: Number of regimes to detect (3-4 recommended).
            min_samples: Minimum samples required for training.
            random_state: Random seed for reproducibility.
        """
        self.n_components = n_components
        self.min_samples = min_samples
        self.random_state = random_state
        
        self.gmm: Optional[GaussianMixture] = None
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.regime_labels: Dict[int, str] = {}
        self.feature_names = ["funding_rate", "oi_change", "ls_ratio", "momentum"]
    
    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract and normalize features from DataFrame."""
        features = []
        
        # Funding rate (or use 0 if not available)
        if "funding_rate" in df.columns:
            features.append(df["funding_rate"].fillna(0).values)
        else:
            features.append(np.zeros(len(df)))
        
        # OI change
        if "oi_change" in df.columns:
            features.append(df["oi_change"].fillna(0).values)
        elif "oi" in df.columns:
            features.append(df["oi"].pct_change().fillna(0).values)
        else:
            features.append(np.zeros(len(df)))
        
        # L/S ratio (convert to log scale for normalization)
        if "ls_ratio" in df.columns:
            ls = df["ls_ratio"].fillna(1).values
            features.append(np.log(np.clip(ls, 0.1, 10)))
        elif "long_ratio" in df.columns:
            lr = df["long_ratio"].fillna(0.5).values
            sr = df.get("short_ratio", 1 - lr).fillna(0.5).values
            ls = lr / np.clip(sr, 0.01, 1)
            features.append(np.log(np.clip(ls, 0.1, 10)))
        else:
            features.append(np.zeros(len(df)))
        
        # Price momentum
        if "momentum" in df.columns:
            features.append(df["momentum"].fillna(0).values)
        elif "close" in df.columns:
            features.append(df["close"].pct_change(6).fillna(0).values)
        elif "price" in df.columns:
            features.append(df["price"].pct_change(6).fillna(0).values)
        else:
            features.append(np.zeros(len(df)))
        
        X = np.column_stack(features)
        return X
    
    def fit(self, df: pd.DataFrame) -> "RegimeClassifier":
        """Fit the GMM on historical data.
        
        Args:
            df: DataFrame with columns for features.
        
        Returns:
            Self for chaining.
        """
        if len(df) < self.min_samples:
            LOGGER.warning(f"Insufficient data for training: {len(df)} < {self.min_samples}")
            return self
        
        X = self._prepare_features(df)
        
        # Remove NaN rows
        mask = ~np.isnan(X).any(axis=1)
        X = X[mask]
        
        if len(X) < self.min_samples:
            LOGGER.warning(f"Insufficient valid samples: {len(X)} < {self.min_samples}")
            return self
        
        # Normalize features
        X_scaled = self.scaler.fit_transform(X)
        
        # Fit GMM
        self.gmm = GaussianMixture(
            n_components=self.n_components,
            covariance_type="full",
            random_state=self.random_state,
            n_init=3,
        )
        self.gmm.fit(X_scaled)
        
        # Assign regime labels based on cluster means
        self._assign_regime_labels(X_scaled)
        
        self.is_fitted = True
        LOGGER.info(f"GMM fitted with {self.n_components} regimes, BIC={self.gmm.bic(X_scaled):.2f}")
        
        return self
    
    def _assign_regime_labels(self, X_scaled: np.ndarray) -> None:
        """Assign human-readable labels to regimes based on cluster characteristics."""
        if self.gmm is None:
            return
        
        means = self.gmm.means_
        
        # Feature indices: 0=funding, 1=oi_change, 2=ls_ratio, 3=momentum
        for i in range(self.n_components):
            funding_mean = means[i, 0]
            oi_mean = means[i, 1]
            ls_mean = means[i, 2]  # Log scale, >0 means more longs
            
            if funding_mean > 0.5 and oi_mean > 0.3:
                self.regime_labels[i] = "high_leverage"
            elif funding_mean < -0.3 or oi_mean < -0.5:
                self.regime_labels[i] = "deleveraging"
            elif oi_mean > 0.3 and abs(funding_mean) < 0.3:
                self.regime_labels[i] = "accumulation"
            else:
                self.regime_labels[i] = "normal"
    
    def predict(self, df: pd.DataFrame) -> List[RegimeLabel]:
        """Predict regime for each row in DataFrame.
        
        Args:
            df: DataFrame with feature columns.
        
        Returns:
            List of RegimeLabel for each row.
        """
        if not self.is_fitted or self.gmm is None:
            # Fallback to simple heuristics if not fitted
            return self._predict_heuristic(df)
        
        X = self._prepare_features(df)
        
        # Handle NaN
        valid_mask = ~np.isnan(X).any(axis=1)
        X_valid = X[valid_mask]
        
        results = []
        valid_idx = 0
        
        for i in range(len(df)):
            if not valid_mask[i]:
                results.append(RegimeLabel(
                    regime="unknown",
                    probability=0.0,
                    all_probabilities={},
                    features_used={},
                ))
                continue
            
            x = X_valid[valid_idx:valid_idx+1]
            x_scaled = self.scaler.transform(x)
            
            cluster = self.gmm.predict(x_scaled)[0]
            probs = self.gmm.predict_proba(x_scaled)[0]
            
            regime = self.regime_labels.get(cluster, "unknown")
            
            all_probs = {
                self.regime_labels.get(j, f"cluster_{j}"): float(probs[j])
                for j in range(self.n_components)
            }
            
            features = {
                name: float(x[0, j]) 
                for j, name in enumerate(self.feature_names)
            }
            
            results.append(RegimeLabel(
                regime=regime,
                probability=float(probs[cluster]),
                all_probabilities=all_probs,
                features_used=features,
            ))
            
            valid_idx += 1
        
        return results
    
    def _predict_heuristic(self, df: pd.DataFrame) -> List[RegimeLabel]:
        """Fallback heuristic prediction when GMM not fitted."""
        results = []
        
        for i, row in df.iterrows():
            funding = row.get("funding_rate", 0)
            oi_change = row.get("oi_change", 0)
            
            if funding > 0.0005 and oi_change > 0.05:
                regime = "high_leverage"
                prob = 0.7
            elif funding < -0.0003 or oi_change < -0.05:
                regime = "deleveraging"
                prob = 0.7
            elif oi_change > 0.03:
                regime = "accumulation"
                prob = 0.6
            else:
                regime = "normal"
                prob = 0.8
            
            results.append(RegimeLabel(
                regime=regime,
                probability=prob,
                all_probabilities={regime: prob},
                features_used={"funding_rate": funding, "oi_change": oi_change},
            ))
        
        return results
    
    def predict_single(
        self,
        funding_rate: float = 0.0,
        oi_change: float = 0.0,
        ls_ratio: float = 1.0,
        momentum: float = 0.0,
    ) -> RegimeLabel:
        """Predict regime for a single observation.
        
        Args:
            funding_rate: Current funding rate.
            oi_change: OI change (fractional).
            ls_ratio: Long/short ratio.
            momentum: Price momentum.
        
        Returns:
            RegimeLabel with prediction.
        """
        df = pd.DataFrame([{
            "funding_rate": funding_rate,
            "oi_change": oi_change,
            "ls_ratio": ls_ratio,
            "momentum": momentum,
        }])
        
        results = self.predict(df)
        return results[0] if results else RegimeLabel(
            regime="unknown",
            probability=0.0,
            all_probabilities={},
            features_used={},
        )


def analyze_regime(
    df: pd.DataFrame,
    n_regimes: int = 3,
    lookback: int = 168,  # 7 days at 1h
) -> RegimeClassifierResult:
    """Analyze market regime using GMM.
    
    Args:
        df: DataFrame with funding_rate, oi_change, ls_ratio, momentum columns.
        n_regimes: Number of regimes to detect.
        lookback: Number of periods for training window.
    
    Returns:
        RegimeClassifierResult with current and historical regimes.
    """
    if df.empty or len(df) < 20:
        return RegimeClassifierResult(
            current_regime=RegimeLabel(
                regime="unknown",
                probability=0.0,
                all_probabilities={},
                features_used={},
            ),
            regime_history=[],
            n_regimes=n_regimes,
            regime_transitions=0,
            model_bic=0.0,
            interpretation="Insufficient data for regime classification.",
        )
    
    # Use last lookback periods for training
    train_df = df.tail(lookback)
    
    # Fit classifier
    classifier = RegimeClassifier(n_components=n_regimes)
    classifier.fit(train_df)
    
    # Predict on all data
    labels = classifier.predict(df)
    
    # Count transitions
    transitions = 0
    for i in range(1, len(labels)):
        if labels[i].regime != labels[i-1].regime:
            transitions += 1
    
    # Current regime
    current = labels[-1] if labels else RegimeLabel(
        regime="unknown",
        probability=0.0,
        all_probabilities={},
        features_used={},
    )
    
    # Model quality
    bic = classifier.gmm.bic(classifier.scaler.transform(
        classifier._prepare_features(train_df)
    )) if classifier.is_fitted else 0.0
    
    interpretation = _generate_interpretation(current, transitions, len(df))
    
    return RegimeClassifierResult(
        current_regime=current,
        regime_history=labels[-24:],  # Last 24 periods
        n_regimes=n_regimes,
        regime_transitions=transitions,
        model_bic=bic,
        interpretation=interpretation,
    )


def _generate_interpretation(current: RegimeLabel, transitions: int, total: int) -> str:
    """Generate human-readable interpretation."""
    regime = current.regime
    prob = current.probability
    
    stability = "stable" if transitions / max(total, 1) < 0.1 else "volatile"
    
    if regime == "high_leverage":
        return f"🔴 HIGH LEVERAGE (p={prob:.0%}): Market overleveraged. Consider reducing long exposure or shorting. Regime {stability}."
    elif regime == "deleveraging":
        return f"🟡 DELEVERAGING (p={prob:.0%}): Leverage unwinding. Wait for stabilization. Regime {stability}."
    elif regime == "accumulation":
        return f"🟢 ACCUMULATION (p={prob:.0%}): OI building without funding extreme. Potential trend continuation. Regime {stability}."
    elif regime == "normal":
        return f"⚪ NORMAL (p={prob:.0%}): Balanced conditions. No strong directional bias. Regime {stability}."
    else:
        return f"❓ UNKNOWN: Insufficient data for classification."


def get_regime_summary(result: RegimeClassifierResult) -> Dict[str, Any]:
    """Get summary dict for reporting."""
    return {
        "current_regime": result.current_regime.regime,
        "confidence": round(result.current_regime.probability, 2),
        "all_probabilities": {
            k: round(v, 2) 
            for k, v in result.current_regime.all_probabilities.items()
        },
        "n_regimes": result.n_regimes,
        "transitions_24h": result.regime_transitions,
        "model_bic": round(result.model_bic, 2),
        "interpretation": result.interpretation,
    }
