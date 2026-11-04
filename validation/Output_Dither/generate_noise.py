"""Original implementation of Ulichney's toroidal void-and-cluster rank algorithm.
SPDX-License-Identifier: MIT. No downloaded texture or third-party source copied.
numpy 2.x, Pillow. Deterministic PCG64 seed; double precision energy updates.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
N = 128
SEED = 20261104
SIGMA = 1.5

def generate():
    rng = np.random.Generator(np.random.PCG64(SEED))
    dist = np.minimum(np.arange(N), N - np.arange(N))
    kernel = np.exp(-(dist[:, None]**2 + dist[None, :]**2) / (2*SIGMA**2))
    def footprint(index):
        return np.roll(kernel, (index // N, index % N), axis=(0, 1))
    def density(mask):
        return np.fft.ifft2(np.fft.fft2(mask) * np.fft.fft2(kernel)).real
    def cluster(mask, energy):
        return int(np.argmax(np.where(mask, energy, -np.inf)))
    def void(mask, energy):
        return int(np.argmin(np.where(mask, np.inf, energy)))
    count = N*N // 10
    mask = np.zeros((N, N), dtype=bool)
    mask.flat[rng.choice(N*N, count, replace=False)] = True
    energy = density(mask)
    # Relax initial 10% population: remove tightest cluster then fill largest void.
    for iteration in range(N*N*10):
        old = cluster(mask, energy)
        mask.flat[old] = False
        energy -= footprint(old)
        new = void(mask, energy)
        mask.flat[new] = True
        energy += footprint(new)
        if new == old:
            break
    else:
        raise RuntimeError("Initial pattern failed to converge")
    initial = mask.copy()
    ranks = np.full((N,N), -1, dtype=np.int32)
    # Phase 1: remove occupied clusters, assigning descending low ranks.
    for rank in range(count-1, -1, -1):
        index = cluster(mask, energy)
        ranks.flat[index] = rank
        mask.flat[index] = False
        energy -= footprint(index)
    # Phase 2: restore seed and fill voids up to 50%.
    mask = initial.copy()
    energy = density(mask)
    for rank in range(count, N*N//2):
        index = void(mask, energy)
        ranks.flat[index] = rank
        mask.flat[index] = True
        energy += footprint(index)
    # Phase 3: inverted pattern; remove clusters of zeros up to 100%.
    mask = ~mask
    energy = density(mask)
    for rank in range(N*N//2, N*N):
        index = cluster(mask, energy)
        ranks.flat[index] = rank
        mask.flat[index] = False
        energy -= footprint(index)
    assert np.array_equal(np.sort(ranks.ravel()), np.arange(N*N))
    data = (ranks // (N*N//256)).astype(np.uint8)
    return data, ranks, iteration + 1

if __name__ == '__main__':
    data, ranks, iterations = generate()
    dest = ROOT/'Textures'
    dest.mkdir(exist_ok=True)
    Image.fromarray(data).save(dest/'Output_Dither_BN128.png')
    meta = dict(algorithm='Ulichney three-phase void-and-cluster', size=N,
                sigma=SIGMA, seed=SEED, initial_count=N*N//10,
                relaxation_iterations=iterations,
                numpy=np.__version__, pixel_sha256=hashlib.sha256(data.tobytes()).hexdigest(),
                png_sha256=hashlib.sha256((dest/'Output_Dither_BN128.png').read_bytes()).hexdigest())
    (dest/'provenance.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(meta, indent=2))
