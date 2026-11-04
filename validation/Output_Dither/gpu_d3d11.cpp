// SPDX-License-Identifier: MIT
// Offscreen D3D11 test harness. This does NOT run the ReShade runtime or present.
#include <d3d11.h>
#include <dxgi.h>
#include <cstring>
#include <cstdint>
template<class T> struct P {
    T *p=nullptr;
    ~P(){if(p)p->Release();}
    T *operator->(){return p;}
    T **put(){return &p;}
};
static P<ID3D11Device> dev;
static P<ID3D11DeviceContext> ctx;
static wchar_t adapter_name[128];
static D3D_FEATURE_LEVEL level;
#define TRY(x) do { HRESULT h=(x); if(FAILED(h)) return h; } while(0)
extern "C" __declspec(dllexport) const wchar_t *gpu_adapter(){return adapter_name;}
extern "C" __declspec(dllexport) HRESULT gpu_init(){
    if(dev.p)return S_OK;
    D3D_FEATURE_LEVEL levels[]={D3D_FEATURE_LEVEL_11_0};
    TRY(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,levels,1,D3D11_SDK_VERSION,dev.put(),&level,ctx.put()));
    P<IDXGIDevice> dxgi; P<IDXGIAdapter> adapter;
    TRY(dev->QueryInterface(__uuidof(IDXGIDevice),(void**)dxgi.put()));
    TRY(dxgi->GetAdapter(adapter.put()));
    DXGI_ADAPTER_DESC desc={}; TRY(adapter->GetDesc(&desc));
    std::memcpy(adapter_name,desc.Description,sizeof(adapter_name));
    return S_OK;
}
extern "C" __declspec(dllexport) HRESULT gpu_run(
    const void *input,void *output,const uint8_t *noise,int width,int height,
    int input_format,int output_format,int input_bpp,int output_bpp,
    const void *vs_data,size_t vs_size,const void *ps_data,size_t ps_size,
    int bypass,int contract,int target,float strength)
{
    TRY(gpu_init());
    P<ID3D11VertexShader> vs; P<ID3D11PixelShader> ps;
    TRY(dev->CreateVertexShader(vs_data,vs_size,nullptr,vs.put()));
    TRY(dev->CreatePixelShader(ps_data,ps_size,nullptr,ps.put()));
    D3D11_TEXTURE2D_DESC desc={};
    desc.Width=width; desc.Height=height; desc.MipLevels=1; desc.ArraySize=1;
    desc.Format=(DXGI_FORMAT)input_format; desc.SampleDesc.Count=1;
    desc.Usage=D3D11_USAGE_IMMUTABLE; desc.BindFlags=D3D11_BIND_SHADER_RESOURCE;
    D3D11_SUBRESOURCE_DATA initial={input,UINT(width*input_bpp),0};
    P<ID3D11Texture2D> src,mask,dst,staging;
    TRY(dev->CreateTexture2D(&desc,&initial,src.put()));
    P<ID3D11ShaderResourceView> src_view,mask_view;
    TRY(dev->CreateShaderResourceView(src.p,nullptr,src_view.put()));
    desc.Width=128; desc.Height=128; desc.Format=DXGI_FORMAT_R8_UNORM;
    initial={noise,128,0};
    TRY(dev->CreateTexture2D(&desc,&initial,mask.put()));
    TRY(dev->CreateShaderResourceView(mask.p,nullptr,mask_view.put()));
    desc.Width=width; desc.Height=height; desc.Format=(DXGI_FORMAT)output_format;
    desc.Usage=D3D11_USAGE_DEFAULT; desc.BindFlags=D3D11_BIND_RENDER_TARGET;
    TRY(dev->CreateTexture2D(&desc,nullptr,dst.put()));
    P<ID3D11RenderTargetView> rtv;
    TRY(dev->CreateRenderTargetView(dst.p,nullptr,rtv.put()));
    desc.Usage=D3D11_USAGE_STAGING; desc.BindFlags=0; desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    TRY(dev->CreateTexture2D(&desc,nullptr,staging.put()));
    struct {int bypass,contract,target; float strength;} uniforms={bypass,contract,target,strength};
    D3D11_BUFFER_DESC cb_desc={}; cb_desc.ByteWidth=16;
    cb_desc.Usage=D3D11_USAGE_IMMUTABLE; cb_desc.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
    D3D11_SUBRESOURCE_DATA cb_data={&uniforms,0,0};
    P<ID3D11Buffer> cb; TRY(dev->CreateBuffer(&cb_desc,&cb_data,cb.put()));
    D3D11_SAMPLER_DESC sd={}; sd.Filter=D3D11_FILTER_MIN_MAG_MIP_POINT;
    sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP; sd.MaxLOD=0;
    P<ID3D11SamplerState> color_sampler,noise_sampler;
    TRY(dev->CreateSamplerState(&sd,color_sampler.put()));
    sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_WRAP;
    TRY(dev->CreateSamplerState(&sd,noise_sampler.put()));
    D3D11_RASTERIZER_DESC rd={}; rd.FillMode=D3D11_FILL_SOLID; rd.CullMode=D3D11_CULL_NONE; rd.DepthClipEnable=TRUE;
    P<ID3D11RasterizerState> raster; TRY(dev->CreateRasterizerState(&rd,raster.put()));
    ctx->ClearState();
    ctx->RSSetState(raster.p);
    D3D11_VIEWPORT vp={0,0,float(width),float(height),0,1}; ctx->RSSetViewports(1,&vp);
    ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    ctx->VSSetShader(vs.p,nullptr,0); ctx->PSSetShader(ps.p,nullptr,0);
    ctx->PSSetConstantBuffers(0,1,&cb.p);
    ID3D11ShaderResourceView *views[]={src_view.p,mask_view.p};
    ID3D11SamplerState *samplers[]={color_sampler.p,noise_sampler.p};
    ctx->PSSetShaderResources(0,2,views); ctx->PSSetSamplers(0,2,samplers);
    ctx->OMSetRenderTargets(1,&rtv.p,nullptr);
    ctx->Draw(3,0);
    ctx->CopyResource(staging.p,dst.p);
    D3D11_MAPPED_SUBRESOURCE mapped={}; TRY(ctx->Map(staging.p,0,D3D11_MAP_READ,0,&mapped));
    for(int y=0;y<height;++y)
        std::memcpy((uint8_t*)output+size_t(y)*width*output_bpp,(uint8_t*)mapped.pData+size_t(y)*mapped.RowPitch,size_t(width)*output_bpp);
    ctx->Unmap(staging.p,0);
    ctx->ClearState();
    return dev->GetDeviceRemovedReason();
}
