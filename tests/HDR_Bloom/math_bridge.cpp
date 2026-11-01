#include <cmath>
#include <algorithm>
using std::pow; using std::min; using std::max;
#include "../HDR_Bloom_Math.fxh"
extern "C" {
float pq_decode(float v){return HB_PQDecode(v);}
float pq_encode(float v){return HB_PQEncode(v);}
float srgb_decode(float v){return HB_SRGBDecode(v);}
float srgb_encode(float v){return HB_SRGBEncode(v);}
float fraction(float y,float t,float k){return HB_Fraction(y,t,k);}
float channel_limit(float s,float d,float c){return HB_ChannelLimit(s,d,c);}
}
