"""Random Matrix Theory covariance denoising (Marchenko-Pastur).

Given a correlation matrix C of shape (N, N) estimated from T observations:
1. Compute Marchenko-Pastur bounds: lambda_plus = (1 + sqrt(N/T))^2
2. Eigendecompose C
3. Replace eigenvalues below lambda_plus with their average (noise floor)
4. Reconstruct denoised correlation matrix
5. Convert back to covariance

This removes estimation noise from short windows, stabilising PCA.
"""

from __future__ import annotations

import numpy as np


def marchenko_pastur_bounds(n: int, t: int) -> tuple[float, float]:
    """Compute Marchenko-Pastur eigenvalue bounds.

    Parameters
    ----------
    n : int
        Number of variables (assets).
    t : int
        Number of observations (time periods).

    Returns
    -------
    tuple[float, float]
        (lambda_minus, lambda_plus) — the support bounds of the MP distribution.
    """
    q = n / t
    lambda_minus = (1.0 - np.sqrt(q)) ** 2
    lambda_plus = (1.0 + np.sqrt(q)) ** 2
    return lambda_minus, lambda_plus


def denoise_correlation(
    corr_matrix: np.ndarray,
    n_observations: int,
) -> np.ndarray:
    """Denoise a correlation matrix using Marchenko-Pastur filtering.

    Parameters
    ----------
    corr_matrix : np.ndarray
        Correlation matrix of shape (N, N).
    n_observations : int
        Number of time observations used to estimate the correlation.

    Returns
    -------
    np.ndarray
        Denoised correlation matrix of shape (N, N).
    """
    n = corr_matrix.shape[0]
    t = n_observations

    if n == 0 or t == 0:
        return corr_matrix

    eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix)

    lambda_minus, lambda_plus = marchenko_pastur_bounds(n, t)

    noise_mask = eigenvalues < lambda_plus
    n_signal = int(np.sum(~noise_mask))

    if n_signal == 0:
        return np.eye(n)

    noise_eigenvalues = eigenvalues[noise_mask]
    if len(noise_eigenvalues) > 0:
        noise_mean = np.mean(noise_eigenvalues)
    else:
        noise_mean = lambda_minus

    denoised_eigenvalues = eigenvalues.copy()
    denoised_eigenvalues[noise_mask] = noise_mean

    denoised_corr = eigenvectors @ np.diag(denoised_eigenvalues) @ eigenvectors.T

    d = np.sqrt(np.diag(denoised_corr))
    d[d == 0] = 1.0
    denoised_corr = denoised_corr / np.outer(d, d)

    np.fill_diagonal(denoised_corr, 1.0)

    return denoised_corr


def cov_to_corr(cov: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert covariance matrix to correlation matrix and standard deviations.

    Parameters
    ----------
    cov : np.ndarray
        Covariance matrix of shape (N, N).

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (correlation_matrix, std_deviations)
    """
    std = np.sqrt(np.diag(cov))
    std[std == 0] = 1.0
    corr = cov / np.outer(std, std)
    np.fill_diagonal(corr, 1.0)
    return corr, std


def corr_to_cov(corr: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Convert correlation matrix back to covariance matrix.

    Parameters
    ----------
    corr : np.ndarray
        Correlation matrix of shape (N, N).
    std : np.ndarray
        Standard deviations of shape (N,).

    Returns
    -------
    np.ndarray
        Covariance matrix of shape (N, N).
    """
    return corr * np.outer(std, std)


def denoise_covariance(
    cov_matrix: np.ndarray,
    n_observations: int,
) -> np.ndarray:
    """Denoise a covariance matrix via correlation-domain denoising.

    Converts cov → corr, applies Marchenko-Pastur denoising to corr,
    then converts back to cov.
    """
    corr, std = cov_to_corr(cov_matrix)
    denoised_corr = denoise_correlation(corr, n_observations)
    return corr_to_cov(denoised_corr, std)