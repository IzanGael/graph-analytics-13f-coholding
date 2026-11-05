"""Checks for the chance model in src/gutils.py. Run: python tests/test_gutils.py (or pytest tests/)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import gutils  # noqa: E402


def random_bipartite(n_stocks=40, n_managers=300, seed=0):
    rng = np.random.default_rng(seed)
    pop = rng.uniform(0.05, 0.9, n_stocks)[:, None]
    size = rng.uniform(0.05, 0.9, n_managers)[None, :]
    B = (rng.random((n_stocks, n_managers)) < pop * size).astype(float)
    B[:, B.sum(axis=0) == 0] = 0
    keep_m = (B.sum(axis=0) > 0) & (B.sum(axis=0) < n_stocks)
    B = B[:, keep_m]
    return B[B.sum(axis=1) > 0]


def reference_solver(k, n, iters=50000, tol=1e-12):
    """Plain version over every manager, as first written; used only to check the grouped solver."""
    E = k.sum()
    x, y = k / np.sqrt(E), n / np.sqrt(E)
    for _ in range(iters):
        D = 1.0 + np.outer(x, y)
        x_new = k / (y[None, :] / D).sum(axis=1)
        y_new = n / (x[:, None] / D).sum(axis=0)
        gap = max(np.abs(x_new / x - 1).max(), np.abs(y_new / y - 1).max())
        x, y = x_new, y_new
        if gap < tol:
            break
    P = np.outer(x, y)
    return P / (1.0 + P)


def test_grouped_solver_matches_reference():
    B = random_bipartite()
    k, n = B.sum(axis=1), B.sum(axis=0)
    P, _, err_k, err_n = gutils.solve_bicm(k, n)
    assert np.abs(P - reference_solver(k, n)).max() < 1e-6
    assert err_k < 1e-6 and err_n < 1e-6


def test_expected_degrees_equal_observed():
    B = random_bipartite(seed=3)
    k, n = B.sum(axis=1), B.sum(axis=0)
    P, *_ = gutils.solve_bicm(k, n)
    assert np.allclose(P.sum(axis=1), k, rtol=1e-6)
    assert np.allclose(P.sum(axis=0), n, rtol=1e-6)


def test_zero_degree_is_rejected():
    try:
        gutils.solve_bicm(np.array([3.0, 0.0]), np.array([1.0, 2.0]))
    except ValueError:
        return
    raise AssertionError("zero-degree stock should raise")


def test_z_scores_are_roughly_standard_on_data_from_the_model():
    """Draw a graph from the fitted model itself: z-scores should have spread near 1."""
    B = random_bipartite(n_stocks=60, n_managers=1500, seed=5)
    k, n = B.sum(axis=1), B.sum(axis=0)
    P, *_ = gutils.solve_bicm(k, n)
    E = P @ P.T
    var = np.maximum(E - (P * P) @ (P * P).T, 1e-9)
    rng = np.random.default_rng(11)
    Xs = (rng.random(P.shape) < P).astype(float)
    z = (Xs @ Xs.T - E) / np.sqrt(var)
    iu = np.triu_indices(len(P), 1)
    assert 0.85 < z[iu].std() < 1.15


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("passed:", name)
    print("all tests passed")
