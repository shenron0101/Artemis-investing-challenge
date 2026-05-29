"""Handle NaN-heavy return matrices for PCA.

Methods:
1. Pairwise covariance: Compute cov(i,j) using overlapping weeks only.
   Require >= min_shared_weeks. If not PSD -> Higham nearest-PSD projection.
2. KNN imputation (fallback): sklearn.impute.KNNImputer(n_neighbors=5)
"""

from __future__ import annotations

import numpy as np
from sklearn.impute import KNNImputer


def pairwise_covariance(
    returns: np.ndarray,
    min_shared: int = 8,
) -> np.ndarray:
    """Compute pairwise covariance using overlapping (non-NaN) observations only.

    Parameters
    ----------
    returns : np.ndarray
        Returns matrix of shape (T, N) with NaN for missing values.
    min_shared : int
        Minimum number of shared non-NaN observations required for a pair.

    Returns
    -------
    np.ndarray
        Covariance matrix of shape (N, N).
    """
    n = returns.shape[1]
    cov = np.zeros((n, n))

    for i in range(n):
        for j in range(i, n):
            mask = ~np.isnan(returns[:, i]) & ~np.isnan(returns[:, j])
            n_shared = int(np.sum(mask))
            if n_shared < min_shared:
                cov[i, j] = np.nan
                cov[j, i] = np.nan
            else:
                ri = returns[mask, i]
                rj = returns[mask, j]
                cov[i, j] = np.cov(ri, rj, ddof=1)[0, 1]
                cov[j, i] = cov[i, j]

    np.fill_diagonal(cov, np.nanvar(returns, axis=0, ddof=1))
    return cov


def nearest_psd_matrix(a: np.ndarray, niters: int = 100) -> np.ndarray:
    """Project a symmetric matrix to the nearest positive semi-definite matrix.

    Uses the Higham (2002) algorithm.

    Parameters
    ----------
    a : np.ndarray
        Symmetric matrix of shape (N, N).
    niters : int
        Maximum number of iterations.

    Returns
    -------
    np.ndarray
        Nearest PSD matrix of shape (N, N).
    """
    if _is_psd(a):
        return a

    n = a.shape[0]
    w = np.ones(n) / n

    y = a.copy()
    ds = np.zeros_like(a)

    for _ in range(niters):
        r = y - ds
        x = _nearest_spd(r)
        ds = x - r
        y_new = x.copy()

        d, v = np.linalg.eigh(y_new)
        d = np.maximum(d, 0)
        y_new = v @ np.diag(d) @ v.T

        if np.allclose(y, y_new, atol=1e-8):
            y = y_new
            break
        y = y_new

    return y


def _is_psd(a: np.ndarray) -> bool:
    try:
        eigenvalues = np.linalg.eigvalsh(a)
        return bool(np.all(eigenvalues >= -1e-10))
    except np.linalg.LinAlgError:
        return False


def _nearest_spd(a: np.ndarray) -> np.ndarray:
    """Compute the nearest symmetric positive definite matrix."""
    b = (a + a.T) / 2
    _, s, vh = np.linalg.svd(b)
    h = vh.T @ np.diag(s) @ vh
    a2 = (b + h) / 2
    a3 = (a2 + a2.T) / 2

    if _is_psd(a3):
        return a3

    spacing = np.spacing(np.linalg.norm(a))
    eye = np.eye(a.shape[0])
    k = 1
    while not _is_psd(a3):
        min_eig = np.min(np.real(np.linalg.eigvals(a3)))
        a3 += eye * (-min_eig * k ** 2 + spacing)
        k += 1
        if k > 100:
            break

    return a3


def knn_impute(
    returns: np.ndarray,
    n_neighbors: int = 5,
) -> np.ndarray:
    """Impute missing values using KNN.

    Parameters
    ----------
    returns : np.ndarray
        Returns matrix of shape (T, N) with NaN for missing values.
    n_neighbors : int
        Number of nearest neighbors.

    Returns
    -------
    np.ndarray
        Imputed returns matrix of shape (T, N).
    """
    imputer = KNNImputer(n_neighbors=n_neighbors)
    return imputer.fit_transform(returns)


def get_psd_covariance(
    returns: np.ndarray,
    min_shared: int = 8,
    fallback_to_knn: bool = True,
) -> np.ndarray:
    """Get a PSD covariance matrix from a NaN-heavy returns matrix.

    Uses pairwise covariance, then projects to nearest PSD.
    If all-NaN columns exist, falls back to KNN imputation.

    Parameters
    ----------
    returns : np.ndarray
        Returns matrix of shape (T, N) with NaN for missing values.
    min_shared : int
        Minimum shared observations for pairwise cov.
    fallback_to_knn : bool
        Whether to use KNN imputation if pairwise cov has NaN entries.

    Returns
    -------
    np.ndarray
        PSD covariance matrix of shape (N, N).
    """
    cov = pairwise_covariance(returns, min_shared=min_shared)

    nan_mask = np.isnan(cov)
    if np.any(nan_mask):
        if fallback_to_knn:
            imputed = knn_impute(returns)
            cov = np.cov(imputed, rowvar=False, ddof=1)
        else:
            cov = np.nan_to_num(cov, nan=0.0)

    if not _is_psd(cov):
        cov = nearest_psd_matrix(cov)

    return cov