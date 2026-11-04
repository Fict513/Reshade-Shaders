// SPDX-License-Identifier: MIT
// The .fxh scalar arithmetic is compiled directly. The wrapper adapts vector I/O,
// guard/selection logic and texture reads from OD_PS to CPU array traversal.
#include <algorithm>
#include <cstdint>
using std::min;
using std::max;
#include "../../Shaders/Output_Dither_Core.fxh"
extern "C" __declspec(dllexport)
void od_run(const float *input, float *output, const uint8_t *asset,
            int width, int height, int bypass, int contract, int target, float strength) {
    for (int y=0; y<height; ++y) for (int x=0; x<width; ++x) {
        const int offset = 4*(y*width+x);
        for (int c=0;c<4;++c) output[offset+c]=input[offset+c];
        if (bypass || !OD_ContractValid(contract,target) || !(strength>0 && strength<=1)) continue;
        if (!(OD_InDomain(input[offset]) && OD_InDomain(input[offset+1]) && OD_InDomain(input[offset+2]))) continue;
        float n=OD_Noise(float(asset[(y%128)*128+x%128])/255.0f);
        float levels=target==0 ? 255.0f : 1023.0f;
        for (int c=0;c<3;++c) output[offset+c]=OD_Channel(input[offset+c],n,strength,levels);
    }
}
