// Build against crosire/reshade's effect compiler sources. See Tests/README.md.
#include "effect_preprocessor.hpp"
#include "effect_parser.hpp"
#include "effect_codegen.hpp"
#include <array>
#include <iostream>
#include <memory>
#include <stdexcept>

static void check(const char *path, int quality, int masks, int colorSpace,
                  int width, int height, bool glsl)
{
    reshadefx::preprocessor pp;
    pp.add_macro_definition("BUFFER_WIDTH", std::to_string(width));
    pp.add_macro_definition("BUFFER_HEIGHT", std::to_string(height));
    pp.add_macro_definition("BUFFER_RCP_WIDTH", "(1.0 / " + std::to_string(width) + ".0)");
    pp.add_macro_definition("BUFFER_RCP_HEIGHT", "(1.0 / " + std::to_string(height) + ".0)");
    if (colorSpace >= 0) pp.add_macro_definition("BUFFER_COLOR_SPACE", std::to_string(colorSpace));
    pp.add_macro_definition("AC_QUALITY", std::to_string(quality));
    pp.add_macro_definition("AC_HUD_MASKS", std::to_string(masks));
    if (!pp.append_file(path)) throw std::runtime_error(pp.errors());
    std::unique_ptr<reshadefx::codegen> cg(glsl ?
        reshadefx::create_codegen_glsl(true, false, false) :
        reshadefx::create_codegen_hlsl(50, false, false));
    reshadefx::parser parser;
    if (!parser.parse(pp.output(), cg.get())) throw std::runtime_error(parser.errors());
    if (!parser.errors().empty()) throw std::runtime_error("Unexpected warning: " + parser.errors());
    const auto &m = cg->module();
    const bool hdr = colorSpace > 1;
    const size_t expected = hdr ? 1 : 2;
    if (m.techniques.size()!=1 || m.techniques[0].passes.size()!=expected)
        throw std::runtime_error("Unexpected technique/pass count");
    size_t intermediateBytes = 0, targets = 0;
    for (const auto &t : m.textures) {
        if (!t.semantic.empty()) continue;
        if (hdr || t.format!=reshadefx::texture_format::r32f ||
            t.width!=unsigned(width) || t.height!=unsigned(height))
            throw std::runtime_error("Unexpected intermediate texture format/size");
        intermediateBytes += size_t(t.width)*t.height*4; ++targets;
    }
    if (targets!=(hdr ? 0 : 1)) throw std::runtime_error("Unexpected target allocation count");
    if (cg->finalize_code().empty()) throw std::runtime_error("Empty generated module");
    for (const auto &e : m.entry_points) {
        std::string code, assembly, errors;
        if (!cg->assemble_code_for_entry_point(e.first,code,assembly,errors) || code.empty())
            throw std::runtime_error("Entry-point generation failed: " + errors);
    }
    if (!glsl && width==3440 && height==1440 && colorSpace==1 && masks==1)
        std::cout << "QUALITY=" << quality << " passes=" << expected
                  << " intermediate_bytes=" << intermediateBytes << '\n';
}
int main(int argc, char **argv)
{
    if (argc!=2) { std::cerr << "Usage: check_fx /absolute/path/Adaptive_Clarity.fx\n"; return 1; }
    int checked=0;
    try {
        for (bool glsl : {false,true}) {
            for (int quality=0; quality<=2; ++quality)
                for (int masks=0; masks<=1; ++masks)
                    for (int space=0; space<=4; ++space) {
                        check(argv[1],quality,masks,space,3440,1440,glsl); ++checked;
                    }
            for (int quality=0; quality<=2; ++quality)
                for (auto size : {std::array<int,2>{1,1},{5,3},{3441,1441}}) {
                    check(argv[1],quality,1,1,size[0],size[1],glsl); ++checked;
                }
            check(argv[1],1,1,-1,3440,1440,glsl); ++checked;
        }
        std::cout << "PASS " << checked << " FX parse/module/entry-point generation configurations (HLSL SM5 + GLSL Vulkan semantics).\n";
        std::cout << "Not Windows GPU-driver compilation or runtime execution.\n";
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 2; }
}
