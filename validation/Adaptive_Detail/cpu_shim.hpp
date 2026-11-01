#pragma once
#include <cmath>
#include <algorithm>
#include <vector>
using std::min; using std::max; using std::abs; using std::pow; using std::floor;
float saturate(float v){return min(max(v,0.0f),1.0f);}
float clamp(float v,float a,float b){return min(max(v,a),b);}
struct float2 {float x,y; float2(float a=0,float b=0):x(a),y(b){}};
float2 operator+(float2 a,float2 b){return {a.x+b.x,a.y+b.y};}
float2 operator+(float2 a,float b){return {a.x+b,a.y+b};}
float2 operator*(float2 a,float2 b){return {a.x*b.x,a.y*b.y};}
float2 operator*(float2 a,float b){return {a.x*b,a.y*b};}
float2 floor(float2 a){return {std::floor(a.x),std::floor(a.y)};}
struct float3 {float r,g,b;float3(float x=0,float y=0,float z=0):r(x),g(y),b(z){}};
float3 operator*(float3 a,float b){return {a.r*b,a.g*b,a.b*b};}
float3 lerp(float3 a,float3 b,float t){return {a.r+(b.r-a.r)*t,a.g+(b.g-a.g)*t,a.b+(b.b-a.b)*t};}
struct float4 {float r,g,b,a;float4(float x=0,float y=0,float z=0,float w=0):r(x),g(y),b(z),a(w){} float4(float3 x,float w):r(x.r),g(x.g),b(x.b),a(w){} float3 rgb(){return {r,g,b};}};
static int width,height,linear_bits;
#define BUFFER_WIDTH width
#define BUFFER_HEIGHT height
#define BUFFER_RCP_WIDTH (1.0f/width)
#define BUFFER_RCP_HEIGHT (1.0f/height)
#ifndef BUFFER_COLOR_FORMAT
#define BUFFER_COLOR_FORMAT 10
#endif
#ifndef ADAPTIVE_DETAIL_VERIFIED_CONTRACT
#define ADAPTIVE_DETAIL_VERIFIED_CONTRACT 0
#endif
static float AD_Master,AD_Fine,AD_Detail,AD_Edge,AD_Noise,AD_Split;
static int AD_Contract,AD_View;
static const float *input;
static std::vector<float> luma;
enum Sampler {AD_ColorSampler,AD_LumaPoint,AD_LumaLinear};
float load(int x,int y){return luma[std::clamp(y,0,height-1)*width+std::clamp(x,0,width-1)];}
float4 tex2D(Sampler s,float2 uv){
 if(s==AD_LumaLinear){
  float px=uv.x*width-0.5f,py=uv.y*height-0.5f;
  int x=(int)std::floor(px),y=(int)std::floor(py); float a=px-x,b=py-y;
  if(linear_bits>0){float q=(float)(1<<linear_bits);a=std::round(a*q)/q;b=std::round(b*q)/q;}
  float top=load(x,y)+(load(x+1,y)-load(x,y))*a;
  float bottom=load(x,y+1)+(load(x+1,y+1)-load(x,y+1))*a;
  return {top+(bottom-top)*b,0,0,1};
 }
 int x=std::clamp((int)std::floor(uv.x*width),0,width-1),y=std::clamp((int)std::floor(uv.y*height),0,height-1);
 if(s==AD_LumaPoint)return {load(x,y),0,0,1};
 const float *p=input+4*(y*width+x);return {p[0],p[1],p[2],p[3]};
}
