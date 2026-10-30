// Build against crosire/reshade's effect compiler sources. See Tests/README.md.
#include "effect_preprocessor.hpp"
#include "effect_parser.hpp"
#include "effect_codegen.hpp"
#include <array>
#include <iostream>
#include <memory>
#include <stdexcept>

static void check(const char *path,int quality,int masks,int dither,int space,
                  int depth,int width,int height,bool glsl)
{
    reshadefx::preprocessor pp;
    pp.add_macro_definition("BUFFER_WIDTH",std::to_string(width));
    pp.add_macro_definition("BUFFER_HEIGHT",std::to_string(height));
    pp.add_macro_definition("BUFFER_RCP_WIDTH","(1.0 / "+std::to_string(width)+".0)");
    pp.add_macro_definition("BUFFER_RCP_HEIGHT","(1.0 / "+std::to_string(height)+".0)");
    if (space>=0) pp.add_macro_definition("BUFFER_COLOR_SPACE",std::to_string(space));
    pp.add_macro_definition("BUFFER_COLOR_BIT_DEPTH",std::to_string(depth));
    pp.add_macro_definition("SDB_QUALITY",std::to_string(quality));
    pp.add_macro_definition("SDB_HUD_MASKS",std::to_string(masks));
    pp.add_macro_definition("SDB_DITHER",std::to_string(dither));
    if (!pp.append_file(path)) throw std::runtime_error(pp.errors());
    std::unique_ptr<reshadefx::codegen> cg(glsl ? reshadefx::create_codegen_glsl(true,false,false) :
                                                       reshadefx::create_codegen_hlsl(50,false,false));
    reshadefx::parser parser;
    if (!parser.parse(pp.output(),cg.get())) throw std::runtime_error(parser.errors());
    if (!parser.errors().empty()) throw std::runtime_error("Unexpected warning: "+parser.errors());
    const auto &m=cg->module();
    if (m.techniques.size()!=1 || m.techniques[0].passes.size()!=1)
        throw std::runtime_error("Expected one technique and one pass");
    for (const auto &texture : m.textures)
        if (texture.semantic.empty()) throw std::runtime_error("Unexpected intermediate texture");
    if (cg->finalize_code().empty()) throw std::runtime_error("Empty generated module");
    for (const auto &e : m.entry_points) {
        std::string code,assembly,errors;
        if (!cg->assemble_code_for_entry_point(e.first,code,assembly,errors) || code.empty())
            throw std::runtime_error("Entry-point generation failed: "+errors);
    }
}
int main(int argc,char **argv)
{
    if (argc!=2) { std::cerr<<"Usage: check_fx /absolute/path/Selective_Deband.fx\n";return 1; }
    int count=0;
    try {
        for (bool glsl : {false,true}) {
            for (int q=0;q<=2;++q)
                for (int masks=0;masks<=1;++masks)
                    for (int space=0;space<=4;++space) {
                        check(argv[1],q,masks,1,space,8,3440,1440,glsl);++count;
                    }
            for (int q=0;q<=2;++q) {
                check(argv[1],q,1,0,1,8,3440,1440,glsl);++count;
                for (int depth : {10,16}) {
                    check(argv[1],q,1,1,1,depth,3440,1440,glsl);++count;
                }
                for (auto size : {std::array<int,2>{1,1},{5,3},{3441,1441}}) {
                    check(argv[1],q,1,1,1,8,size[0],size[1],glsl);++count;
                }
            }
            check(argv[1],1,1,1,-1,8,3440,1440,glsl);++count;
        }
        std::cout<<"PASS "<<count<<" FX parse/module/entry-point generation configurations (HLSL SM5 + GLSL Vulkan semantics).\n";
        std::cout<<"One pass, no intermediate textures in every tested configuration.\n";
        std::cout<<"Not Windows GPU-driver compilation or GPU runtime execution.\n";
    } catch (const std::exception &e) { std::cerr<<e.what()<<'\n';return 2; }
}
