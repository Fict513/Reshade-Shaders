// Build against crosire/reshade effect compiler sources; see README.md.
#include "effect_preprocessor.hpp"
#include "effect_parser.hpp"
#include "effect_codegen.hpp"
#include <iostream>
#include <stdexcept>
#include <vector>
#include <array>
#include <memory>

static void check(const char *path, int quality, int local, int broad, int space,
                  int depth, int width, int height, bool glsl)
{
    reshadefx::preprocessor pp;
    pp.add_macro_definition("BUFFER_WIDTH", std::to_string(width));
    pp.add_macro_definition("BUFFER_HEIGHT", std::to_string(height));
    pp.add_macro_definition("BUFFER_RCP_WIDTH", "(1.0 / " + std::to_string(width) + ".0)");
    pp.add_macro_definition("BUFFER_RCP_HEIGHT", "(1.0 / " + std::to_string(height) + ".0)");
    pp.add_macro_definition("BUFFER_COLOR_SPACE", std::to_string(space));
    pp.add_macro_definition("BUFFER_COLOR_BIT_DEPTH", std::to_string(depth));
    pp.add_macro_definition("IPSD2_QUALITY", std::to_string(quality));
    pp.add_macro_definition("IPSD2_LOCAL", std::to_string(local));
    pp.add_macro_definition("IPSD2_BROAD", std::to_string(broad));
    if (!pp.append_file(path)) throw std::runtime_error(pp.errors());
    std::unique_ptr<reshadefx::codegen> cg(glsl ?
        reshadefx::create_codegen_glsl(true, false, false) :
        reshadefx::create_codegen_hlsl(50, false, false));
    reshadefx::parser parser;
    if (!parser.parse(pp.output(), cg.get())) throw std::runtime_error(parser.errors());
    if (!parser.errors().empty()) throw std::runtime_error("Unexpected warning: " + parser.errors());
    const auto &m = cg->module();
    const bool filtered = space <= 1 && local;
    const size_t expected_passes = !filtered ? 1 : broad ? 7 : 4;
    if (m.techniques.size() != 1 || m.techniques[0].passes.size() != expected_passes)
        throw std::runtime_error("Unexpected technique/pass count");
    size_t bytes = 0;
    for (const auto &t : m.textures) {
        if (!t.semantic.empty()) continue;
        if (!filtered) throw std::runtime_error("Bypass path allocated an intermediate texture");
        size_t bpp = t.format == reshadefx::texture_format::r16f ? 2 :
                     t.format == reshadefx::texture_format::rg16f ? 4 :
                     t.format == reshadefx::texture_format::rgba16f ? 8 : 0;
        if (!bpp || !t.width || !t.height) throw std::runtime_error("Unexpected texture format/size");
        bytes += size_t(t.width) * t.height * bpp;
    }
    if (cg->finalize_code().empty()) throw std::runtime_error("Empty generated module");
    for (const auto &e : m.entry_points) {
        std::string binary, assembly, errors;
        if (!cg->assemble_code_for_entry_point(e.first, binary, assembly, errors) || binary.empty())
            throw std::runtime_error("Entry point generation failed: " + errors);
    }
    if (!glsl && width == 3440 && height == 1440 && space == 1 && depth == 8 && local && broad)
        std::cout << "QUALITY=" << quality << " passes=" << expected_passes
                  << " intermediate_bytes=" << bytes << '\n';
}
int main(int argc, char **argv)
{
    if (argc != 2) { std::cerr << "Usage: check_fx /absolute/path/IPS_Depth_v2.fx\n"; return 1; }
    int checked = 0;
    try {
        for (bool glsl : {false, true}) {
            for (int q = 0; q <= 2; ++q)
                for (auto mode : {std::array<int,2>{0,0}, {1,0}, {1,1}})
                    for (int space = 0; space <= 4; ++space) {
                        check(argv[1], q, mode[0], mode[1], space, 8, 3440, 1440, glsl); ++checked;
                    }
            for (int q = 0; q <= 2; ++q) {
                for (int depth : {10,16}) {
                    check(argv[1], q, 1, 1, 1, depth, 3440, 1440, glsl); ++checked;
                }
                for (auto size : {std::array<int,2>{1,1}, {5,3}, {3441,1441}}) {
                    check(argv[1], q, 1, 1, 1, 8, size[0], size[1], glsl); ++checked;
                }
                check(argv[1], q, 0, 1, 1, 8, 3440, 1440, glsl); ++checked;
            }
        }
        std::cout << "PASS " << checked << " FX parse/module/entry-point generation configurations (HLSL SM5 + GLSL Vulkan semantics).\n";
        std::cout << "Not Windows GPU-driver compilation or runtime execution.\n";
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 2; }
}
