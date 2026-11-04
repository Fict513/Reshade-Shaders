// SPDX-License-Identifier: MIT
// Scalar functions shared by production and the adapted C++ CPU validation.
#ifndef OUTPUT_DITHER_CORE_FXH
#define OUTPUT_DITHER_CORE_FXH
bool OD_ContractValid(int contract, int target)
{
    return (contract == 1 && (target == 0 || target == 1)) ||
           (contract == 2 && target == 2);
}
bool OD_InDomain(float x)
{
    // Ordered comparisons reject NaN and both infinities; do not repair them.
    return x >= 0.0f && x <= 1.0f;
}
float OD_Noise(float unorm_byte)
{
    // R8 is read as b/255. Reconstruct midpoint ranks, NOT endpoints b/255-0.5.
    return (unorm_byte * 255.0f + 0.5f) / 256.0f - 0.5f;
}
float OD_Channel(float x, float noise, float strength, float levels)
{
    // Preserve signed zero and exact normalized endpoints before arithmetic.
    if (x == 0.0f || x == 1.0f)
        return x;
    // Explicit endpoint clipping: pre-quantizer noise becomes biased here.
    // At strength <= 1, clipping does not change the ideal nearest UNORM code.
    return min(1.0f, max(0.0f, x + noise * (strength / levels)));
}
#endif
