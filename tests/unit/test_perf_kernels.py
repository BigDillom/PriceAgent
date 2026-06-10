"""Unit tests for numba performance kernels (correctness)."""

from __future__ import annotations

import numpy as np

from derivkit.core.enums import QuadMethod
from derivkit.pricing.perf.mc_kernels import evolve_bs_log, simulate_gbm_terminal
from derivkit.pricing.perf.pde_kernels import fdm_evolve_step
from derivkit.pricing.perf.quad_fft import (
    fft_convolve,
    get_quad_vector,
    get_quad_vector_jit,
    step_backward_jit,
)


class TestMcKernels:
    def test_evolve_bs_log_matches_numpy(self):
        rng = np.random.default_rng(7)
        z = rng.standard_normal((200, 50))
        s0, drift, vol = 100.0, 0.0004, 0.012
        jit_paths = evolve_bs_log(s0, drift, vol, z)
        log_inc = drift + vol * z
        ref = s0 * np.exp(np.cumsum(log_inc, axis=1))
        ref = np.column_stack([np.full(200, s0), ref])
        np.testing.assert_allclose(jit_paths, ref, rtol=1e-10)

    def test_simulate_gbm_terminal_matches_numpy(self):
        rng = np.random.default_rng(3)
        z = rng.standard_normal(500)
        s0, drift, vol = 100.0, 0.02, 0.15
        jit = simulate_gbm_terminal(s0, drift, vol, z)
        ref = s0 * np.exp(drift + vol * z)
        np.testing.assert_allclose(jit, ref, rtol=1e-10)


class TestPdeKernels:
    def test_fdm_evolve_step_matches_scipy_reference(self):
        from scipy import sparse

        from derivkit.pricing.perf.numerical import tdma_jit

        i_vec = np.arange(1, 81, dtype=float)
        s_vec = i_vec * 2.5
        a = np.full(s_vec.size, 0.04)
        b = np.zeros(s_vec.size)
        c = np.full(s_vec.size, 0.05)
        dt = -0.01
        theta = 0.5
        yv = np.linspace(0, 10, s_vec.size)
        bound = (0.0, 0.0, 0.0, 0.0)

        diffusion_square = a * i_vec**2
        drift_coef = b * i_vec
        lower_coef = 0.5 * (diffusion_square - drift_coef)
        diag_coef = -diffusion_square - c
        upper_coef = 0.5 * (diffusion_square + drift_coef)
        eye = sparse.eye(s_vec.size)
        a_mat = (
            sparse.diags((lower_coef[1:], diag_coef, upper_coef[:-1]), (-1, 0, 1), format="csc")
            * dt
        )
        m1 = eye - theta * a_mat
        m2 = eye + (1 - theta) * a_mat
        v_vec = m2.dot(yv)
        v_vec[0] += (theta * bound[0] + (1 - theta) * bound[1]) * lower_coef[0] * dt
        v_vec[-1] += (theta * bound[2] + (1 - theta) * bound[3]) * upper_coef[-1] * dt
        ref = tdma_jit(
            m1.diagonal(-1).copy(),
            m1.diagonal(0).copy(),
            m1.diagonal(1).copy(),
            np.asarray(v_vec),
        )
        jit = fdm_evolve_step(i_vec, a, b, c, dt, theta, yv.copy(), *bound)
        np.testing.assert_allclose(jit, ref, rtol=1e-10, atol=1e-10)


class TestQuadKernels:
    def test_get_quad_vector_jit_matches_python(self):
        for method in (QuadMethod.SIMPSON, QuadMethod.TRAPEZOID):
            qv, qi = get_quad_vector(101, method)
            is_simpson = method == QuadMethod.SIMPSON
            qv_jit, qi_jit = get_quad_vector_jit(101, is_simpson)
            np.testing.assert_allclose(qv_jit, qv)
            assert qi_jit == qi

    def test_fft_convolve_matches_direct_numpy(self):
        rng = np.random.default_rng(1)
        v = rng.random(51)
        pdf = rng.random(101)
        qv, qi = get_quad_vector(51, QuadMethod.SIMPSON)
        t, r, ln_ds = 0.05, 0.03, 0.01
        len_v, len_pdf = v.size, pdf.size
        v_pad = np.hstack((v * qv, np.zeros(len_pdf - len_v)))
        ref = np.fft.ifft(np.fft.fft(v_pad) * np.fft.fft(pdf)).real
        ref = ref[len_v - 1 :] / qi * ln_ds * np.exp(-r * t)
        out = fft_convolve(v, pdf, t, r, ln_ds, qv, qi)
        np.testing.assert_allclose(out, ref, rtol=1e-10)

    def test_step_backward_jit_finite(self):
        x = np.linspace(80, 120, 41)
        y = np.linspace(70, 130, 61)
        v = np.maximum(x[0] - 100, 0.0) * np.ones(61)
        qv, qi = get_quad_vector_jit(61, True)
        out = step_backward_jit(x, y, v, 0.1, 0.05, 0.0, 0.2, qv, qi)
        assert out.shape == x.shape
        assert np.all(np.isfinite(out))
