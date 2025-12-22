"""Build and analyze implied-volatility surfaces from options data."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator, RegularGridInterpolator
from scipy.optimize import least_squares

LOGGER = logging.getLogger(__name__)


def _svi_total_variance(params: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Compute SVI total variance.

    Args:
        params: SVI parameters [a, b, rho, m, sigma].
        k: Log-moneyness values.

    Returns:
        Total variance values.
    """
    a, b, rho, m, sigma = params
    return a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma**2))


def fit_svi_slice(k: np.ndarray, t: float, iv: np.ndarray) -> Optional[np.ndarray]:
    """Fit an SVI smile for a single maturity.

    Args:
        k: Log-moneyness values.
        t: Time to maturity in years.
        iv: Implied volatility values.

    Returns:
        Fitted SVI parameters [a, b, rho, m, sigma] or None if fitting fails.
    """
    if len(k) < 5 or t <= 0:
        return None

    total_variance = (iv**2) * t

    def residuals(params: np.ndarray) -> np.ndarray:
        a, b, rho, m, sigma = params
        if b <= 0 or sigma <= 0 or not (-0.999 < rho < 0.999):
            return 1e6 * np.ones_like(total_variance)
        model_w = _svi_total_variance(params, k)
        if np.any(model_w <= 0):
            return 1e6 * np.ones_like(total_variance)
        model_iv = np.sqrt(model_w / t)
        return model_iv - iv

    initial = np.array([
        max(np.min(total_variance) * 0.5, 1e-4),
        0.1,
        0.0,
        float(np.mean(k)),
        0.1,
    ])
    bounds = (
        np.array([1e-8, 1e-6, -0.999, -np.inf, 1e-6]),
        np.array([1.0, 5.0, 0.999, np.inf, 5.0]),
    )

    result = least_squares(residuals, initial, bounds=bounds, max_nfev=2000)
    if not result.success:
        return None
    return result.x


def build_iv_surface(
    df: pd.DataFrame,
    *,
    strike_points: int = 40,
    maturity_points: int = 40,
    smoothing: str = "svi",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Construct a regularized implied-volatility surface.

    Args:
        df: Options DataFrame with 'moneyness', 'maturity_days', 'log_moneyness', 'implied_vol'.
        strike_points: Number of strike grid points.
        maturity_points: Number of maturity grid points.
        smoothing: Smoothing method ('svi' or 'spline').

    Returns:
        Tuple of (strike_grid, maturity_grid, iv_surface, skew_surface, term_surface).
        strike_grid and maturity_grid are 2D arrays (meshgrid) expressed in
        strike/spot and maturity days respectively.

    Raises:
        ValueError: If DataFrame is empty.
    """
    if df.empty:
        raise ValueError("Option dataframe is empty.")

    strike_min = df["moneyness"].quantile(0.05)
    strike_max = df["moneyness"].quantile(0.95)
    if not np.isfinite(strike_min) or not np.isfinite(strike_max) or strike_min <= 0:
        strike_min = df["moneyness"].min()
        strike_max = df["moneyness"].max()

    maturity_min = df["maturity_days"].min()
    maturity_max = df["maturity_days"].max()

    strike_axis = np.linspace(strike_min, strike_max, strike_points)
    maturity_axis = np.linspace(maturity_min, maturity_max, maturity_points)
    strike_grid, maturity_grid = np.meshgrid(strike_axis, maturity_axis, indexing="ij")
    log_strike_axis = np.log(strike_axis)
    maturity_years_axis = maturity_axis / 365.0

    iv_matrix = np.full_like(strike_grid, np.nan, dtype=float)
    fitted_maturities: list[float] = []
    fitted_curves: list[np.ndarray] = []

    grouped = df.groupby("maturity_days")
    for maturity_days, bucket in grouped:
        t_years = maturity_days / 365.0
        if t_years <= 0:
            continue

        k = bucket["log_moneyness"].to_numpy()
        iv = bucket["implied_vol"].to_numpy()
        params = fit_svi_slice(k, t_years, iv) if smoothing.lower() == "svi" else None

        if params is not None:
            slice_iv = np.sqrt(
                np.clip(_svi_total_variance(params, log_strike_axis), 1e-8, None) / t_years
            )
        else:
            # Fall back to monotone spline interpolation
            sorter = np.argsort(k)
            unique_idx = np.unique(k[sorter], return_index=True)[1]
            k_sorted = k[sorter][unique_idx]
            iv_sorted = iv[sorter][unique_idx]
            interpolator = PchipInterpolator(k_sorted, iv_sorted, extrapolate=True)
            slice_iv = interpolator(log_strike_axis)

        fitted_maturities.append(t_years)
        fitted_curves.append(slice_iv)

    if not fitted_curves:
        raise RuntimeError("Unable to fit any SVI slices; not enough data points per maturity.")

    fitted_maturities_arr = np.array(fitted_maturities)
    fitted_curves_arr = np.vstack(fitted_curves)  # shape (num_maturities, strike_points)

    for strike_idx in range(strike_points):
        iv_along_maturity = fitted_curves_arr[:, strike_idx]
        interpolator = PchipInterpolator(fitted_maturities_arr, iv_along_maturity, extrapolate=True)
        iv_matrix[strike_idx, :] = interpolator(maturity_years_axis)

    skew_matrix = np.gradient(iv_matrix, strike_axis, axis=0)
    term_matrix = np.gradient(iv_matrix, maturity_axis, axis=1)

    return strike_grid, maturity_grid, iv_matrix, skew_matrix, term_matrix


def detect_anomalies(
    df: pd.DataFrame,
    strike_grid: np.ndarray,
    maturity_grid: np.ndarray,
    iv_grid: np.ndarray,
    threshold_sigma: float = 3.0,
) -> pd.DataFrame:
    """Compare raw IV quotes to the smoothed surface and highlight outliers.

    Args:
        df: Options DataFrame with 'moneyness', 'maturity_days', 'implied_vol'.
        strike_grid: Strike axis from build_iv_surface.
        maturity_grid: Maturity axis from build_iv_surface.
        iv_grid: IV surface grid from build_iv_surface.
        threshold_sigma: Standard deviation threshold for anomalies.

    Returns:
        DataFrame with detected anomalies, sorted by absolute residual.
    """
    strike_axis = strike_grid[:, 0]
    maturity_axis = maturity_grid[0, :]

    interpolator = RegularGridInterpolator(
        (strike_axis, maturity_axis),
        iv_grid,
        bounds_error=False,
        fill_value=np.nan,
    )

    df = df.copy()
    pts = np.column_stack([df["moneyness"].to_numpy(), df["maturity_days"].to_numpy()])
    df["surface_iv"] = interpolator(pts)
    df["iv_residual"] = df["implied_vol"] - df["surface_iv"]
    df["abs_residual"] = df["iv_residual"].abs()

    valid = df["surface_iv"].notna()
    if valid.sum() < 5:
        return df.iloc[0:0]

    threshold = threshold_sigma * df.loc[valid, "iv_residual"].std(ddof=1)
    anomalies = df[valid & (df["abs_residual"] > threshold)].sort_values(
        "abs_residual", ascending=False
    )

    return anomalies.head(20)


def plot_surface(
    strike_grid: np.ndarray,
    maturity_grid: np.ndarray,
    iv_grid: np.ndarray,
    *,
    title: str = "Implied Volatility Surface",
    save_path: Optional[str] = None,
) -> None:
    """Plot a 3D IV surface.

    Args:
        strike_grid: Strike axis (2D meshgrid).
        maturity_grid: Maturity axis (2D meshgrid).
        iv_grid: IV values (2D grid).
        title: Plot title.
        save_path: Optional path to save the figure.
    """
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(10, 6))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(
        strike_grid, maturity_grid, iv_grid,
        cmap="viridis", edgecolor="none", alpha=0.9
    )
    ax.set_xlabel("Strike / Spot")
    ax.set_ylabel("Maturity (days)")
    ax.set_zlabel("Implied Volatility")
    ax.set_title(title)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150)
        LOGGER.info(f"Surface saved to {save_path}")
    else:
        plt.show()
