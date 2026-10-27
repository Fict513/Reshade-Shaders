// Validation helper for FakeHDR_Advanced.fx (Windows only).
//   fhdra_validate compile <file.hlsl> <entry> <profile>
//   fhdra_validate math <FakeHDR_Advanced.fx>
// "compile" runs D3DCompile (DXBC generation; no GPU driver involved).
// "math" extracts the shader's pure color functions verbatim, compiles them as a
// compute shader and executes them on the D3D11 WARP software device.
#define WIN32_LEAN_AND_MEAN
#include <d3d11.h>
#include <d3dcompiler.h>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

static std::string ReadFile(const char *path)
{
	std::ifstream f(path, std::ios::binary);
	std::stringstream ss;
	ss << f.rdbuf();
	return ss.str();
}

static ID3DBlob *Compile(const std::string &src, const char *entry, const char *profile)
{
	ID3DBlob *code = nullptr, *err = nullptr;
	HRESULT hr = D3DCompile(src.data(), src.size(), "shader", nullptr, nullptr, entry, profile, D3DCOMPILE_OPTIMIZATION_LEVEL1, 0, &code, &err);
	if (err && err->GetBufferSize())
		fwrite(err->GetBufferPointer(), 1, err->GetBufferSize(), stderr);
	if (FAILED(hr)) return nullptr;
	return code;
}

static int CompileMode(int argc, char **argv)
{
	if (argc < 5) return 1;
	ID3DBlob *code = Compile(ReadFile(argv[2]), argv[3], argv[4]);
	if (!code) { printf("FAIL %s %s\n", argv[3], argv[4]); return 2; }
	printf("OK   %s %s (%zu bytes DXBC)\n", argv[3], argv[4], (size_t)code->GetBufferSize());
	return 0;
}

struct Params { float Contrast, Brilliance, ShadowProtection, Vibrance, NoiseFloor, pad0, pad1, pad2; };

static int failures = 0;
static void Check(bool ok, const char *what, const char *detail)
{
	if (!ok) { ++failures; printf("FAIL %s %s\n", what, detail); }
}

static int MathMode(int argc, char **argv)
{
	if (argc < 3) return 1;
	std::string fx = ReadFile(argv[2]);
	size_t a = fx.find("float Decode(");
	size_t b = fx.find("void VS(");
	if (a == std::string::npos || b == std::string::npos) { printf("FAIL extraction markers\n"); return 2; }
	std::string cleaned;
	std::istringstream lines(fx.substr(a, b - a));
	for (std::string l; std::getline(lines, l);)
		if (l.rfind("float LogLuma(", 0) != 0) cleaned += l + "\n";

	std::string hlsl =
		"cbuffer C : register(b0) { float Contrast; float Brilliance; float ShadowProtection; float Vibrance; float NoiseFloor; float3 pad; };\n" + cleaned +
		"StructuredBuffer<float4> In : register(t0);\n"
		"RWStructuredBuffer<float4> Out : register(u0);\n"
		"[numthreads(64,1,1)] void main(uint3 id : SV_DispatchThreadID)\n"
		"{\n"
		" float4 v = In[id.x];\n"
		" float comp;\n"
		" float y = Luma(v.rgb);\n"
		" float3 g = ColorReconstruct(v.rgb, y, v.a, comp);\n"
		" Out[id.x * 3 + 0] = float4(Tone(v.r), BoundedExposure(v.r, v.a * 4.0 - 2.0), Gate(v.r - 0.5), SoftLimit(v.r * 8.0 - 4.0, 0.65));\n"
		" Out[id.x * 3 + 1] = float4(g, comp);\n"
		" Out[id.x * 3 + 2] = float4(Luma(g), y, 0, 0);\n"
		"}\n";
	ID3DBlob *cs = Compile(hlsl, "main", "cs_5_0");
	if (!cs) { printf("FAIL math compute shader compile\n"); return 2; }

	ID3D11Device *dev; ID3D11DeviceContext *ctx;
	if (FAILED(D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_WARP, nullptr, 0, nullptr, 0, D3D11_SDK_VERSION, &dev, nullptr, &ctx)))
	{ printf("FAIL WARP device\n"); return 2; }
	ID3D11ComputeShader *shader;
	dev->CreateComputeShader(cs->GetBufferPointer(), cs->GetBufferSize(), nullptr, &shader);

	struct Preset { const char *name; Params p; };
	const Preset presets[] = {
		{ "defaults", { 0.4f, 0.18f, 0.85f, 0.06f, 0.025f } },
		{ "max sliders", { 0.75f, 0.4f, 1.0f, 0.3f, 0.15f } },
		{ "min sliders", { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f } },
		{ "no shadow protection", { 0.75f, 0.4f, 0.0f, 0.3f, 0.0f } },
	};

	for (const Preset &pr : presets)
	{
		std::vector<float> in;
		const int toneCount = 257;
		for (int i = 0; i < toneCount; ++i) { float x = i / 256.0f; in.insert(in.end(), { x, x, x, x }); }
		const float levels[] = { 0, 1e-6f, 1e-4f, 0.002f, 0.01f, 0.05f, 0.18f, 0.5f, 0.8f, 0.95f, 1.0f };
		const float targets[] = { 0, 1e-7f, 1e-5f, 0.001f, 0.05f, 0.2f, 0.5f, 0.9f, 0.999f, 1.0f };
		for (float r : levels) for (float g : levels) for (float bl : levels) for (float t : targets)
			in.insert(in.end(), { r, g, bl, t });
		size_t count = in.size() / 4, padded = (count + 63) / 64 * 64;
		in.resize(padded * 4, 0.0f);

		D3D11_BUFFER_DESC bd = {};
		bd.ByteWidth = (UINT)(in.size() * 4); bd.Usage = D3D11_USAGE_DEFAULT; bd.BindFlags = D3D11_BIND_SHADER_RESOURCE;
		bd.MiscFlags = D3D11_RESOURCE_MISC_BUFFER_STRUCTURED; bd.StructureByteStride = 16;
		D3D11_SUBRESOURCE_DATA sd = { in.data() };
		ID3D11Buffer *inBuf; dev->CreateBuffer(&bd, &sd, &inBuf);
		D3D11_SHADER_RESOURCE_VIEW_DESC sv = {}; sv.Format = DXGI_FORMAT_UNKNOWN; sv.ViewDimension = D3D11_SRV_DIMENSION_BUFFER; sv.Buffer.NumElements = (UINT)padded;
		ID3D11ShaderResourceView *srv; dev->CreateShaderResourceView(inBuf, &sv, &srv);
		bd.ByteWidth = (UINT)(padded * 3 * 16); bd.BindFlags = D3D11_BIND_UNORDERED_ACCESS;
		ID3D11Buffer *outBuf; dev->CreateBuffer(&bd, nullptr, &outBuf);
		D3D11_UNORDERED_ACCESS_VIEW_DESC uv = {}; uv.Format = DXGI_FORMAT_UNKNOWN; uv.ViewDimension = D3D11_UAV_DIMENSION_BUFFER; uv.Buffer.NumElements = (UINT)(padded * 3);
		ID3D11UnorderedAccessView *uav; dev->CreateUnorderedAccessView(outBuf, &uv, &uav);
		D3D11_BUFFER_DESC cb = {}; cb.ByteWidth = sizeof(Params); cb.BindFlags = D3D11_BIND_CONSTANT_BUFFER;
		D3D11_SUBRESOURCE_DATA cd = { &pr.p };
		ID3D11Buffer *cbuf; dev->CreateBuffer(&cb, &cd, &cbuf);
		bd.Usage = D3D11_USAGE_STAGING; bd.BindFlags = 0; bd.MiscFlags = 0; bd.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
		ID3D11Buffer *stage; dev->CreateBuffer(&bd, nullptr, &stage);

		ctx->CSSetShader(shader, nullptr, 0);
		ctx->CSSetConstantBuffers(0, 1, &cbuf);
		ctx->CSSetShaderResources(0, 1, &srv);
		ctx->CSSetUnorderedAccessViews(0, 1, &uav, nullptr);
		ctx->Dispatch((UINT)(padded / 64), 1, 1);
		ctx->CopyResource(stage, outBuf);
		D3D11_MAPPED_SUBRESOURCE m;
		ctx->Map(stage, 0, D3D11_MAP_READ, 0, &m);
		const float *o = (const float *)m.pData;

		int nonFinite = 0, oob = 0, lumaBad = 0, neutralBad = 0, exposureBad = 0;
		float worstLuma = 0;
		for (size_t i = 0; i < count; ++i)
		{
			const float *t = o + i * 12;
			for (int k = 0; k < 12; ++k) if (!std::isfinite(t[k])) ++nonFinite;
			if (i < (size_t)toneCount) continue;
			const float *x = &in[i * 4];
			const float *c = t + 4;
			for (int k = 0; k < 4; ++k) if (c[k] < 0.0f || c[k] > 1.0f) ++oob;
			float y = t[9], highIn = fmaxf(x[0], fmaxf(x[1], x[2]));
			float target = fminf(x[3], y / fmaxf(highIn, 1e-6f)), lumaOut = t[8];
			if (y > 1e-7f && target > 1e-4f && target < 0.9999f)
			{
				float err = fabsf(lumaOut - target);
				if (err > 0.0015f) ++lumaBad;
				if (err > worstLuma) worstLuma = err;
			}
			if (x[0] == x[1] && x[1] == x[2] && (fabsf(c[0] - c[1]) > 1e-4f || fabsf(c[1] - c[2]) > 1e-4f)) ++neutralBad;
		}

		float prev = -1.0f, prevExp = -1.0f; int nonMono = 0, toneRange = 0;
		for (int i = 0; i < toneCount; ++i)
		{
			float tone = o[i * 12];
			if (tone < prev - 1e-6f) ++nonMono;
			if (tone < 0.0f || tone > 1.0f) ++toneRange;
			prev = tone;
			// Exposure at stops = x*4-2 is checked for range only (the gain varies with the sample).
			float e = o[i * 12 + 1];
			if (e < 0.0f || e > 1.0f || !std::isfinite(e)) ++exposureBad;
			(void)prevExp;
		}
		float lift = 0;
		for (int i = 0; i <= 8; ++i) lift = fmaxf(lift, o[i * 12] - i / 256.0f);

		char tag[96];
		snprintf(tag, sizeof tag, "[%s]", pr.name);
		Check(nonFinite == 0, "non-finite output", tag);
		Check(oob == 0, "ColorReconstruct output outside [0,1]", tag);
		Check(lumaBad == 0, "luminance not preserved by ColorReconstruct", tag);
		Check(neutralBad == 0, "neutral input became coloured", tag);
		Check(o[0] == 0.0f, "Tone(0) != 0", tag);
		Check(fabsf(o[256 * 12] - 1.0f) < 1e-6f, "Tone(1) != 1", tag);
		Check(nonMono == 0, "Tone not monotonic", tag);
		Check(toneRange == 0, "Tone outside [0,1]", tag);
		Check(exposureBad == 0, "BoundedExposure outside [0,1]", tag);
		Check(o[1] == 0.0f, "BoundedExposure(0) != 0", tag);
		int compressedCases = 0, lumaChecked = 0;
		for (size_t i = toneCount; i < count; ++i)
		{
			const float *t = o + i * 12;
			if (t[7] > 0.001f) ++compressedCases;
			if (t[9] > 1e-7f && in[i * 4 + 3] > 1e-4f && in[i * 4 + 3] < 0.9999f) ++lumaChecked;
		}
		printf("%-22s cases=%zu luma-checked=%d gamut-compressed=%d Tone(.25/.5/.75)=%.4f/%.4f/%.4f max low-end lift=%.5f worst luma err=%.6f\n",
			pr.name, count, lumaChecked, compressedCases, o[64 * 12], o[128 * 12], o[192 * 12], lift, worstLuma);
		ctx->Unmap(stage, 0);
	}
	printf(failures ? "MATH FAILED (%d)\n" : "MATH OK\n", failures);
	return failures ? 3 : 0;
}

// ---------------------------------------------------------------------------
// Full pipeline on WARP: executes the ReShade-generated HLSL passes on synthetic images.
// ---------------------------------------------------------------------------
#include <map>
#include <regex>

struct Pipeline
{
	ID3D11Device *dev = nullptr; ID3D11DeviceContext *ctx = nullptr;
	std::string hlsl;
	std::vector<std::string> cbNames, cbTypes;
	std::map<std::string, float> defaults;
	ID3D11VertexShader *vs = nullptr;
	std::vector<ID3D11PixelShader *> chain; // 6 filter passes (empty in HDR bypass)
	ID3D11PixelShader *finish = nullptr;
	ID3D11SamplerState *sampler = nullptr;
	int w = 0, h = 0;
	ID3D11Texture2D *tex[7] = {}; ID3D11ShaderResourceView *srv[7] = {}; ID3D11RenderTargetView *rtv[7] = {};
	ID3D11Texture2D *outTex = nullptr, *outStage = nullptr; ID3D11RenderTargetView *outRtv = nullptr;

	template <class T> T *Create(ID3DBlob *b, HRESULT (STDMETHODCALLTYPE ID3D11Device::*fn)(const void *, SIZE_T, ID3D11ClassLinkage *, T **))
	{
		T *r = nullptr; (dev->*fn)(b->GetBufferPointer(), b->GetBufferSize(), nullptr, &r); return r;
	}

	bool Init(const char *hlslPath, const char *fxPath, int width, int height)
	{
		w = width; h = height;
		hlsl = ReadFile(hlslPath);
		if (FAILED(D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_WARP, nullptr, 0, nullptr, 0, D3D11_SDK_VERSION, &dev, nullptr, &ctx))) return false;
		std::smatch m;
		std::regex cbRe("cbuffer _Globals \\{([^}]*)\\}");
		if (std::regex_search(hlsl, m, cbRe))
		{
			std::string body = m[1];
			std::regex fieldRe("(float|int|uint|bool)\\s+V__FHDRA__(\\w+);");
			for (auto it = std::sregex_iterator(body.begin(), body.end(), fieldRe); it != std::sregex_iterator(); ++it)
			{ cbTypes.push_back((*it)[1]); cbNames.push_back((*it)[2]); }
		}
		std::string fx = ReadFile(fxPath);
		std::regex uRe("uniform\\s+(?:float|int|bool)\\s+(\\w+)[\\s\\S]*?>\\s*=\\s*([^;]+);");
		for (auto it = std::sregex_iterator(fx.begin(), fx.end(), uRe); it != std::sregex_iterator(); ++it)
		{
			std::string v = (*it)[2];
			defaults[(*it)[1]] = v.find("true") != std::string::npos ? 1.0f : (float)atof(v.c_str());
		}
		ID3DBlob *vb = Compile(hlsl, "F__FHDRA__VS", "vs_5_0");
		if (!vb) return false;
		vs = Create<ID3D11VertexShader>(vb, &ID3D11Device::CreateVertexShader);
		const char *names[6] = { "FineHorizontal", "FineVertical", "MidHorizontal", "MidVertical", "BroadHorizontal", "BroadVertical" };
		if (hlsl.find("F__FHDRA__FineHorizontal") != std::string::npos)
			for (const char *n : names)
			{
				ID3DBlob *pb = Compile(hlsl, (std::string("F__FHDRA__") + n).c_str(), "ps_5_0");
				if (!pb) return false;
				chain.push_back(Create<ID3D11PixelShader>(pb, &ID3D11Device::CreatePixelShader));
			}
		ID3DBlob *fb = Compile(hlsl, "F__FHDRA__Composite", "ps_5_0");
		if (!fb) return false;
		finish = Create<ID3D11PixelShader>(fb, &ID3D11Device::CreatePixelShader);
		D3D11_SAMPLER_DESC sd = {};
		sd.Filter = D3D11_FILTER_MIN_MAG_LINEAR_MIP_POINT; sd.AddressU = sd.AddressV = sd.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP; sd.MaxLOD = D3D11_FLOAT32_MAX;
		dev->CreateSamplerState(&sd, &sampler);
		D3D11_RASTERIZER_DESC rd = {}; rd.FillMode = D3D11_FILL_SOLID; rd.CullMode = D3D11_CULL_NONE; rd.DepthClipEnable = TRUE;
		ID3D11RasterizerState *rs; dev->CreateRasterizerState(&rd, &rs); ctx->RSSetState(rs);
		D3D11_TEXTURE2D_DESC td = {};
		td.Width = w; td.Height = h; td.MipLevels = td.ArraySize = 1; td.SampleDesc.Count = 1; td.Usage = D3D11_USAGE_DEFAULT;
		td.BindFlags = D3D11_BIND_SHADER_RESOURCE | D3D11_BIND_RENDER_TARGET;
		td.Format = DXGI_FORMAT_R32G32_FLOAT;
		for (int i = 1; i < 7; ++i)
		{
			dev->CreateTexture2D(&td, nullptr, &tex[i]);
			dev->CreateShaderResourceView(tex[i], nullptr, &srv[i]);
			dev->CreateRenderTargetView(tex[i], nullptr, &rtv[i]);
		}
		td.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
		dev->CreateTexture2D(&td, nullptr, &outTex);
		dev->CreateRenderTargetView(outTex, nullptr, &outRtv);
		td.Usage = D3D11_USAGE_STAGING; td.BindFlags = 0; td.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
		dev->CreateTexture2D(&td, nullptr, &outStage);
		return true;
	}

	// rgba8: w*h*4 bytes. Returns w*h*4 floats.
	std::vector<float> Run(const std::vector<unsigned char> &rgba8, const std::map<std::string, float> &overrides, bool hdrRange = false)
	{
		D3D11_TEXTURE2D_DESC td = {};
		td.Width = w; td.Height = h; td.MipLevels = td.ArraySize = 1; td.SampleDesc.Count = 1; td.Usage = D3D11_USAGE_DEFAULT;
		td.BindFlags = D3D11_BIND_SHADER_RESOURCE;
		std::vector<float> hdrInput;
		if (hdrRange)
		{
			hdrInput.resize(rgba8.size());
			for (size_t i = 0; i < rgba8.size(); ++i) hdrInput[i] = rgba8[i] / 255.0f;
			hdrInput[0] = -0.5f; hdrInput[1] = 2.0f; hdrInput[2] = 7.5f;
		}
		td.Format = hdrRange ? DXGI_FORMAT_R32G32B32A32_FLOAT : DXGI_FORMAT_R8G8B8A8_UNORM;
		D3D11_SUBRESOURCE_DATA sd = { hdrRange ? static_cast<const void *>(hdrInput.data()) : static_cast<const void *>(rgba8.data()), (UINT)(w * (hdrRange ? 16 : 4)) };
		ID3D11Texture2D *in; dev->CreateTexture2D(&td, &sd, &in);
		ID3D11ShaderResourceView *inSrv; dev->CreateShaderResourceView(in, nullptr, &inSrv);
		std::vector<float> cb(cbNames.size() + 4, 0.0f);
		for (size_t i = 0; i < cbNames.size(); ++i)
		{
			float v = overrides.count(cbNames[i]) ? overrides.at(cbNames[i]) : defaults[cbNames[i]];
			if (cbTypes[i] == "float") cb[i] = v; else { int iv = (int)v; memcpy(&cb[i], &iv, 4); }
		}
		D3D11_BUFFER_DESC bd = {}; bd.ByteWidth = (UINT)((cb.size() * 4 + 15) / 16 * 16); bd.BindFlags = D3D11_BIND_CONSTANT_BUFFER;
		D3D11_SUBRESOURCE_DATA cd = { cb.data() };
		ID3D11Buffer *cbuf; dev->CreateBuffer(&bd, &cd, &cbuf);
		D3D11_VIEWPORT vp = { 0, 0, (float)w, (float)h, 0, 1 };
		ctx->RSSetViewports(1, &vp);
		ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
		ctx->VSSetShader(vs, nullptr, 0);
		ctx->VSSetConstantBuffers(0, 1, &cbuf); ctx->PSSetConstantBuffers(0, 1, &cbuf);
		ctx->PSSetSamplers(0, 1, &sampler);
		for (size_t p = 0; p <= chain.size(); ++p)
		{
			ID3D11ShaderResourceView *none[7] = {};
			ctx->PSSetShaderResources(0, 7, none);
			ID3D11ShaderResourceView *bound[7] = {}; bound[0] = inSrv;
			for (size_t t = 1; t <= p && t <= chain.size(); ++t) bound[t] = srv[t];
			if (p < chain.size()) { ctx->OMSetRenderTargets(1, &rtv[p + 1], nullptr); bound[p + 1] = nullptr; ctx->PSSetShader(chain[p], nullptr, 0); }
			else { ctx->OMSetRenderTargets(1, &outRtv, nullptr); ctx->PSSetShader(finish, nullptr, 0); }
			ctx->PSSetShaderResources(0, 7, bound);
			ctx->Draw(3, 0);
		}
		ctx->CopyResource(outStage, outTex);
		D3D11_MAPPED_SUBRESOURCE m; ctx->Map(outStage, 0, D3D11_MAP_READ, 0, &m);
		std::vector<float> out(w * h * 4);
		for (int y = 0; y < h; ++y) memcpy(&out[y * w * 4], (char *)m.pData + y * m.RowPitch, w * 16);
		ctx->Unmap(outStage, 0);
		return out;
	}
};

static int PipelineMode(int argc, char **argv)
{
	if (argc < 4) return 1;
	const int W = 640, H = 360;
	Pipeline pl;
	if (!pl.Init(argv[2], argv[3], W, H)) { printf("FAIL pipeline init (compile/device)\n"); return 2; }
	const bool hdr = pl.chain.empty();
	printf("passes: %zu (%s)\n", pl.chain.size() + 1, hdr ? "HDR bypass" : "SDR");

	// Synthetic scene: ramp, black, white, primaries, hard edge, noise, flat midtone.
	std::vector<unsigned char> img(W * H * 4, 0);
	auto set = [&](int x, int y, int r, int g, int b) { unsigned char *p = &img[(y * W + x) * 4]; p[0] = r; p[1] = g; p[2] = b; p[3] = 200; };
	unsigned seed = 12345;
	auto rnd = [&]() { seed = seed * 1664525u + 1013904223u; return (int)(seed >> 24); };
	for (int y = 0; y < H; ++y)
		for (int x = 0; x < W; ++x)
		{
			int r, g, b;
			if (y < 60) { r = g = b = x * 255 / (W - 1); }                       // gray ramp
			else if (y < 120) { int s = x / 80; static const int c[8][3] = { {0,0,0},{255,255,255},{255,0,0},{0,255,0},{0,0,255},{255,255,0},{0,255,255},{255,0,255} }; r = c[s][0]; g = c[s][1]; b = c[s][2]; }
			else if (y < 180) { r = g = b = (x < W / 2) ? 4 : 250; }              // hard edge, near-black vs near-white
			else if (y < 240) { r = g = b = 40 + (rnd() % 24); }                   // noisy dark region
			else if (y < 300) { r = 200 + (x % 40); g = 120; b = 40 + (x / 4) % 60; } // saturated warm gradient
			else { r = g = b = 118; }                                              // flat midtone
			set(x, y, r, g, b);
		}

	auto stats = [&](const std::vector<float> &o, const char *tag, bool strictFinite = true)
	{
		int bad = 0, oob = 0;
		for (float v : o) { if (!std::isfinite(v)) ++bad; else if (v < -1e-5f || v > 1.0f + 1e-5f) ++oob; }
		if (strictFinite) { Check(bad == 0, "non-finite pixels", tag); Check(oob == 0, "pixels outside [0,1]", tag); }
	};
	auto maxDiff = [&](const std::vector<float> &o, int x0, int x1, int y0, int y1)
	{
		float d = 0;
		for (int y = y0; y < y1; ++y) for (int x = x0; x < x1; ++x) for (int c = 0; c < 3; ++c)
			d = fmaxf(d, fabsf(o[(y * W + x) * 4 + c] - img[(y * W + x) * 4 + c] / 255.0f));
		return d;
	};
	auto meanDiff = [&](const std::vector<float> &o)
	{
		double d = 0; for (int i = 0; i < W * H; ++i) for (int c = 0; c < 3; ++c) d += fabs(o[i * 4 + c] - img[i * 4 + c] / 255.0f);
		return d / (W * H * 3.0);
	};

	std::vector<float> def = pl.Run(img, {});
	stats(def, "[defaults]");
	std::vector<float> again = pl.Run(img, {});
	Check(def == again, "output not deterministic across runs", "[defaults]");
	int alphaBad = 0;
	for (int i = 0; i < W * H; ++i) if (fabsf(def[i * 4 + 3] - 200 / 255.0f) > 1e-5f) ++alphaBad;
	Check(alphaBad == 0, "alpha not preserved", "[defaults]");
	printf("defaults: mean |delta| = %.5f, max |delta| = %.5f\n", meanDiff(def), maxDiff(def, 0, W, 0, H));
	{
		float best = 0; int bx = 0, by = 0;
		for (int y = 0; y < H; ++y) for (int x = 0; x < W; ++x) for (int c = 0; c < 3; ++c)
		{ float d = fabsf(def[(y * W + x) * 4 + c] - img[(y * W + x) * 4 + c] / 255.0f); if (d > best) { best = d; bx = x; by = y; } }
		printf("defaults: largest delta at (%d,%d) src=(%d,%d,%d) out=(%.3f,%.3f,%.3f)\n", bx, by, img[(by * W + bx) * 4], img[(by * W + bx) * 4 + 1], img[(by * W + bx) * 4 + 2],
			def[(by * W + bx) * 4], def[(by * W + bx) * 4 + 1], def[(by * W + bx) * 4 + 2]);
	}

	if (hdr)
	{
		Check(maxDiff(def, 0, W, 0, H) == 0.0f, "HDR bypass modified the image", "[hdr]");
		std::vector<float> range = pl.Run(img, {}, true);
		Check(range[0] == -0.5f && range[1] == 2.0f && range[2] == 7.5f && range[3] == 200 / 255.0f,
			"HDR bypass modified extended-range input", "[hdr]");
	}
	else
	{
		// Exact black / white primaries pixels (row 60..120, columns 0..80 black, 80..160 white).
		Check(maxDiff(def, 10, 70, 70, 110) <= 1e-6f, "pure black patch changed", "[defaults]");
		Check(maxDiff(def, 90, 150, 70, 110) <= 1e-6f, "pure white patch changed", "[defaults]");
		Check(def[(90 * W + 450) * 4 + 2] < 1.0f / 255.0f, "saturated yellow washed out", "[defaults]");
		float lift = 0;
		for (int x = 0; x < 12; ++x) for (int y = 5; y < 55; ++y) lift = fmaxf(lift, def[(y * W + x) * 4] - img[(y * W + x) * 4] / 255.0f);
		printf("ramp: max lift of first 12 columns (inputs <= ~5/255) = %.5f (%.2f 8-bit steps)\n", lift, lift * 255.0f);
		Check(lift <= 2.0f / 255.0f, "near-black ramp lifted by more than 2/255", "[defaults]");
		// Ramp luma inversions.
		int inv = 0; float worst = 0;
		for (int x = 1; x < W; ++x) { float d = def[(30 * W + x - 1) * 4 + 1] - def[(30 * W + x) * 4 + 1]; if (d > 2.0f / 255.0f) ++inv; worst = fmaxf(worst, d); }
		printf("ramp: columns with >2/255 inversion vs left neighbour: %d (worst %.5f)\n", inv, worst);
		// Strength 0 / split view / alternate views / extremes.
		std::vector<float> s0 = pl.Run(img, { { "Strength", 0.0f } });
		Check(maxDiff(s0, 0, W, 0, H) == 0.0f, "Strength=0 not identity", "[strength0]");
		std::vector<float> sp = pl.Run(img, { { "SplitView", 1.0f }, { "SplitPosition", 0.5f } });
		Check(maxDiff(sp, 0, W / 2 - 1, 0, H) == 0.0f, "split-view left half not original", "[split]");
		stats(sp, "[split]");
		for (int v = 1; v <= 2; ++v) { char t[32]; snprintf(t, sizeof t, "[view %d]", v); stats(pl.Run(img, { { "View", (float)v } }), t); }
		std::vector<float> nod = pl.Run(img, { { "Dither", 0.0f } });
		double ditherDelta = [&] { double d = 0; for (size_t i = 0; i < def.size(); ++i) d += fabs(def[i] - nod[i]); return d / def.size(); }();
		printf("dither effect: mean |delta| defaults vs Dither=0: %.6f\n", ditherDelta);
		Check(ditherDelta > 0.0, "dither setting had no effect", "[defaults]");
		std::map<std::string, float> mx = { { "Contrast", 0.75f }, { "Brilliance", 0.4f }, { "Brightness", 0.5f }, { "ShadowProtection", 0.0f }, { "Fine", 0.5f }, { "Medium", 0.6f },
			{ "Broad", 0.5f }, { "Adaptation", 0.25f }, { "Radius", 6.0f }, { "EdgeProtection", 0.0f }, { "HaloProtection", 0.0f }, { "HighlightProtection", 0.0f },
			{ "NoiseFloor", 0.0f }, { "Sharpen", 0.3f }, { "Vibrance", 0.3f }, { "Dither", 1.0f } };
		std::vector<float> ext = pl.Run(img, mx);
		stats(ext, "[max sliders]");
		Check(maxDiff(ext, 10, 70, 70, 110) <= 1.0f / 255.0f, "black patch changed beyond 1/255 at max sliders (Brightness 0.5)", "[max sliders]");
		std::map<std::string, float> mn = { { "Contrast", 0.0f }, { "Brilliance", 0.0f }, { "Fine", 0.0f }, { "Medium", 0.0f }, { "Broad", 0.0f }, { "Adaptation", 0.0f },
			{ "Sharpen", 0.0f }, { "Vibrance", 0.0f }, { "Dither", 0.0f }, { "Radius", 2.0f }, { "EdgeProtection", 1.0f } };
		std::vector<float> zero = pl.Run(img, mn);
		stats(zero, "[all-zero amounts]");
		printf("all amounts zero: max |delta| = %.6f (expect ~0)\n", maxDiff(zero, 0, W, 0, H));
		Check(maxDiff(zero, 0, W, 0, H) < 1.5f / 255.0f, "all-zero settings do not return the source", "[all-zero amounts]");
	}
	printf(failures ? "PIPELINE FAILED (%d)\n" : "PIPELINE OK\n", failures);
	return failures ? 3 : 0;
}

int main(int argc, char **argv)
{
	if (argc >= 2 && std::string(argv[1]) == "pipeline") return PipelineMode(argc, argv);
	if (argc >= 2 && std::string(argv[1]) == "compile") return CompileMode(argc, argv);
	if (argc >= 2 && std::string(argv[1]) == "math") return MathMode(argc, argv);
	fprintf(stderr, "usage: fhdra_validate compile <hlsl> <entry> <profile> | math <fx>\n");
	return 1;
}
