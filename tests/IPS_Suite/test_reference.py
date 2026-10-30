"""Integration tests for the CPU chain model, not the GPU shader."""
import unittest
from itertools import product

import numpy as np
from scipy.ndimage import gaussian_filter

from reference import ac, ips, process, sdb


def rgba(gray):
    rgb = np.repeat(np.asarray(gray)[..., None], 3, axis=-1)
    alpha = np.linspace(.1, .9, gray.shape[1])[None, :, None]
    return np.concatenate([rgb, np.broadcast_to(alpha, (*gray.shape, 1))], axis=-1)


class SuiteTests(unittest.TestCase):
    def test_combinations_identity_and_hdr(self):
        image = np.random.default_rng(42).uniform(-.2, 1.3, (5, 7, 4))
        for quality, stages, dither in product(range(3), product([False, True], repeat=3), [False, True]):
            out, _ = process(image, quality, stages, dither, contrast={"Strength": 0},
                             deband={"Strength": 0}, clarity={"Strength": 0})
            np.testing.assert_array_equal(out, image)
            for space in (2, 3, 4):
                out, _ = process(image, quality, stages, dither, color_space=space)
                np.testing.assert_array_equal(out, image)

    def test_standalone_chain_agreement_and_stage_freshness(self):
        yy, xx = np.indices((19, 53))
        gray = np.round((.25 + .22 * xx / 52 + .012 * np.sin(yy / 3)) * 255) / 255
        image = rgba(gray)
        for quality, stages in product(range(3), product([False, True], repeat=3)):
            expected = image.copy()
            if stages[0]:
                expected[..., :3], _, _ = ips.process(expected[..., :3], quality)
            if stages[1]:
                expected, _ = sdb.process(expected, quality, enable_dither=False, hud_masks=False)
            if stages[2]:
                expected, _ = ac.process(expected, quality, hud_masks=False)
            actual, _ = process(image, quality, stages, dither=False)
            np.testing.assert_allclose(actual, expected, atol=3e-7, rtol=0)
            np.testing.assert_array_equal(actual[..., 3], image[..., 3])
        # A stale clarity guide/result from the input must not match this chain.
        together, _ = process(image, stages=(True, True, True), dither=False)
        original_clarity, _ = ac.process(image)
        self.assertGreater(np.max(np.abs(together[..., :3] - original_clarity[..., :3])), .005)

    def test_constant_fields_gradients_tiny_and_odd_sizes(self):
        for shape, value, quality in product([(1, 1), (3, 5), (9, 17)], [0, .01, .3, .8, 1], range(3)):
            image = rgba(np.full(shape, value))
            out, info = process(image, quality)
            self.assertTrue(np.isfinite(out).all())
            np.testing.assert_allclose(out[..., 0], out[..., 1], atol=1e-12)
            np.testing.assert_allclose(out[..., 1], out[..., 2], atol=1e-12)
            np.testing.assert_array_equal(out[..., 3], image[..., 3])
            self.assertLess(np.max(np.abs(info["deband"]["delta"])), 1e-7)
            self.assertLess(np.max(np.abs(info["clarity"]["correction"])), 1e-7)
        image = rgba(np.tile(np.linspace(0, 1, 257), (9, 1)))
        for quality in range(3):
            out, _ = process(image, quality, dither=False)
            self.assertGreater(np.diff(out[..., 0], axis=1).min(), 0)
            np.testing.assert_allclose(out[:, [0, -1], :3], image[:, [0, -1], :3], atol=1e-7)

    def test_edges_lines_texture_bounds_and_alpha(self):
        yy, xx = np.indices((25, 65))
        p = .25 + .06 * np.sin(xx * np.pi / 4) * np.sin(yy * np.pi / 4)
        p = gaussian_filter(p, .6)
        p[:, 32:] += .45
        p[:, 12] = .8
        image = rgba(p)
        for quality in range(3):
            out, diag = process(image, quality, dither=False, crop_height=1080)
            self.assertTrue(np.isfinite(out).all())
            self.assertGreaterEqual(out[..., :3].min(), 0)
            self.assertLessEqual(out[..., :3].max(), 1)
            self.assertLessEqual(np.abs(diag["deband"]["delta"]).max(), .85 / 255 + 1e-12)
            self.assertLessEqual(np.abs(diag["clarity"]["correction"]).max(), .75 * .025 + 1e-12)
            self.assertGreater(out[:, 12, 0].mean(), out[:, 11, 0].mean() + .35)
            np.testing.assert_array_equal(out[..., 3], image[..., 3])
        rng = np.random.default_rng(5)
        color = rng.random((13, 23, 4))
        out, _ = process(color, 2)
        self.assertGreaterEqual(out[..., :3].min(), 0)
        self.assertLessEqual(out[..., :3].max(), 1)
        np.testing.assert_array_equal(out[..., 3], color[..., 3])

    def test_final_dither_quantization_and_clarity_revealing_bands(self):
        width, height = 513, 25
        truth = np.tile(np.linspace(.2, .8, width), (height, 1))
        banded = np.round(truth * 255) / 255
        image = rgba(banded)
        for quality in range(3):
            smoothed, _ = process(image, quality, stages=(False, True, False), dither=False)
            sharpened, diag = process(image, quality, stages=(False, True, True), dither=False)
            dithered, _ = process(image, quality, stages=(False, True, True), dither=True)
            quantized = np.round(dithered[..., 0] * 255) / 255
            self.assertGreater(np.count_nonzero(quantized != banded), 0)
            self.assertLess(np.abs(diag["clarity"]["correction"]).max(), 1e-7)
            # Inspect both band error and step energy after output quantization;
            # this characterizes this fixture, not a universal quality claim.
            area = np.s_[4:-4, 16:-16]
            mean_before = np.mean(banded[area], axis=0)
            mean_smoothed = np.mean(smoothed[area][..., 0], axis=0)
            mean_sharp = np.mean(sharpened[area][..., 0], axis=0)
            mean_final = np.mean(quantized[area], axis=0)
            mse = lambda x: np.mean((x - truth[area].mean(axis=0)) ** 2)
            step = lambda x: np.mean(np.abs(np.diff(x)))
            print(f"quality={quality} band MSE input/smooth/clarity/final: "
                  f"{mse(mean_before):.8g}/{mse(mean_smoothed):.8g}/"
                  f"{mse(mean_sharp):.8g}/{mse(mean_final):.8g}; "
                  f"step energy smooth/clarity: {step(mean_smoothed):.8g}/{step(mean_sharp):.8g}")
            self.assertLess(mse(mean_smoothed), mse(mean_before))
            self.assertLessEqual(np.abs(diag["clarity"]["correction"]).max(), .75 * .025)
            for depth in (0, 12, 16):
                other, _ = process(image, quality, stages=(False, True, True), bit_depth=depth)
                np.testing.assert_array_equal(other, sharpened)
            again, _ = process(image, quality, stages=(False, True, True))
            np.testing.assert_array_equal(again, dithered)
            aggressive, aggressive_diag = process(
                image, quality, stages=(False, True, True), dither=False,
                clarity={"NoiseThreshold": 0, "NoiseProtection": 0, "Strength": 1,
                         "TextureStrength": 1, "EdgeStrength": .75})
            change = np.max(np.abs(aggressive_diag["clarity"]["correction"]))
            self.assertGreater(change, 1e-8)
            print(f"quality={quality} clarity correction max default/aggressive: "
                  f"{np.max(np.abs(diag['clarity']['correction'])):.8g}/{change:.8g}; "
                  f"aggressive changed quantized pixels: "
                  f"{np.count_nonzero(np.round(aggressive[..., 0]*255) != np.round(smoothed[..., 0]*255))}")
            coarse = rgba(np.round(truth * 127) / 127)
            coarse_smooth, _ = process(coarse, quality, stages=(False, True, False), dither=False)
            coarse_sharp, _ = process(
                coarse, quality, stages=(False, True, True), dither=False,
                clarity={"NoiseThreshold": 0, "NoiseProtection": 0, "Strength": 1,
                         "TextureStrength": 1, "EdgeStrength": .75})
            base = np.round(coarse_smooth[..., 0] * 255)
            sharp = np.round(coarse_sharp[..., 0] * 255)
            base_steps = np.sum(np.abs(np.diff(base, axis=1)))
            sharp_steps = np.sum(np.abs(np.diff(sharp, axis=1)))
            self.assertGreater(sharp_steps, base_steps)
            print(f"quality={quality} coarse-band quantized step energy smooth/strong clarity: "
                  f"{base_steps:.0f}/{sharp_steps:.0f}")

    def test_masks_feather_split_and_boundary_contamination(self):
        yy, xx = np.indices((25, 65))
        image = rgba(np.round((.35 + xx * .001) * 255) / 255)
        image[8:17, 26:39, :3] = .8
        rect = (26 / 65, 8 / 25, 39 / 65, 17 / 25)
        plain, _ = process(image, dither=False)
        for feather in (0, 3):
            out, diag = process(image, dither=False, masks=[rect], feather=feather)
            inside = diag["protection"] == 1
            np.testing.assert_array_equal(out[inside], image[inside])
            partial = (diag["protection"] > 0) & (diag["protection"] < 1)
            if feather:
                self.assertTrue(partial.any())
                np.testing.assert_allclose(out[partial, :3],
                    image[partial, :3] * diag["protection"][partial, None]
                    + plain[partial, :3] * (1 - diag["protection"][partial, None]), atol=1e-15)
        split, _ = process(image, split=.5)
        np.testing.assert_array_equal(split[:, :32], image[:, :32])
        # Protection restores pixels, but cannot undo sampling by nearby pixels.
        altered = image.copy()
        altered[8:17, 26:39, :3] = .2
        masked_a, diag = process(image, dither=False, masks=[rect])
        masked_b, _ = process(altered, dither=False, masks=[rect])
        outside = diag["protection"] == 0
        self.assertGreater(np.max(np.abs(masked_a[outside] - masked_b[outside])), 1e-8)

    def test_dither_bit_depth_amplitude_and_eligibility(self):
        image = rgba(np.tile(np.round(np.linspace(.25, .75, 257) * 255) / 255, (17, 1)))
        base, _ = process(image, stages=(False, True, True), dither=False)
        eight, e = process(image, stages=(False, True, True), bit_depth=8)
        ten, t = process(image, stages=(False, True, True), bit_depth=10)
        self.assertGreater(np.max(np.abs(e["dither"])), 0)
        self.assertLessEqual(np.max(np.abs(e["dither"])), .8 / 255)
        self.assertLessEqual(np.max(np.abs(t["dither"])), .8 / 1023)
        np.testing.assert_allclose(e["dither"] * 255, t["dither"] * 1023, atol=1e-15)
        np.testing.assert_allclose(eight[..., 0] - base[..., 0], e["dither"], atol=1e-15)
        np.testing.assert_allclose(ten[..., 0] - base[..., 0], t["dither"], atol=1e-15)
        unchanged, _ = process(image, stages=(False, False, True), dither=True)
        undithered, _ = process(image, stages=(False, False, True), dither=False)
        np.testing.assert_array_equal(unchanged, undithered)

    def test_standalone_dither_agrees_when_placement_matches(self):
        image = rgba(np.tile(np.round(np.linspace(.2, .8, 257) * 255) / 255, (17, 1)))
        for quality, depth in product(range(3), (8, 10)):
            standalone, _ = sdb.process(image, quality, bit_depth=depth, hud_masks=False)
            suite, _ = process(image, quality, stages=(False, True, False), bit_depth=depth)
            np.testing.assert_allclose(suite, standalone, atol=1e-15, rtol=0)

    def test_intermediate_precision_on_gradients_and_shadows(self):
        for low, high in ((0, .08), (.2, .8), (.92, 1)):
            image = rgba(np.tile(np.linspace(low, high, 257), (9, 1)))
            full, _ = process(image, dither=False, target_dtype=np.float64)
            chosen, _ = process(image, dither=False, target_dtype=np.float32)
            half, _ = process(image, dither=False, target_dtype=np.float16)
            err32 = np.max(np.abs(chosen[..., :3] - full[..., :3]))
            err16 = np.max(np.abs(half[..., :3] - full[..., :3]))
            print(f"gradient {low}-{high}: max accumulated output error vs float64 "
                  f"RGBA32F={err32:.8g}, RGBA16F={err16:.8g}")
            self.assertLess(err32, 1e-6)
            self.assertGreater(err16, err32 * 100)

    def test_subtle_texture_can_be_smoothed(self):
        y, x = np.indices((33, 65))
        p = gaussian_filter(.5 + .006 * np.sin(x * np.pi / 4) * np.sin(y * np.pi / 4), .6)
        image = rgba(p)
        area = np.s_[4:-4, 4:-4]
        for quality in range(3):
            out, diag = process(image, quality, stages=(False, True, True), dither=False)
            ratio = np.std(out[area][..., 0]) / np.std(p[area])
            self.assertGreater(ratio, .25)
            self.assertLess(ratio, .8)
            self.assertLessEqual(np.abs(diag["deband"]["delta"]).max(), .85 / 255 + 1e-12)
            print(f"quality={quality} subtle texture standard-deviation ratio after suite: {ratio:.4f}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
