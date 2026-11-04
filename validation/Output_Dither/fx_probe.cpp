// SPDX-License-Identifier: MIT
// Front end to upstream ReShade FX parser and code generators.
// See build_tools.ps1 for the lexer-only libc++ portability substitution.
// Usage: fx_probe shader.fx width height enable hlsl|glsl output-file
#include "effect_parser.hpp"
#include "effect_preprocessor.hpp"
#include "effect_codegen.hpp"
#include <fstream>
#include <iostream>
#include <memory>
int main(int argc, char **argv) {
    if (argc != 7) return 1;
    reshadefx::preprocessor pp;
    pp.add_macro_definition("BUFFER_WIDTH", argv[2]);
    pp.add_macro_definition("BUFFER_HEIGHT", argv[3]);
    pp.add_macro_definition("OUTPUT_DITHER_ENABLE", argv[4]);
    pp.add_include_path(std::filesystem::path(argv[1]).parent_path());
    if (!pp.append_file(argv[1])) { std::cerr << pp.errors(); return 2; }
    bool glsl = std::string(argv[5]) == "glsl";
    std::unique_ptr<reshadefx::codegen> cg(glsl
        ? reshadefx::create_codegen_glsl(false, false, false, false, false)
        : reshadefx::create_codegen_hlsl(50, false, false));
    reshadefx::parser parser;
    if (!parser.parse(pp.output(), cg.get())) {
        std::cerr << pp.errors() << parser.errors(); return 3;
    }
    std::ofstream(argv[6]) << cg->finalize_code();
    const auto &m = cg->module();
    std::cout << "textures=" << m.textures.size() << " samplers=" << m.samplers.size()
              << " techniques=" << m.techniques.size() << '\n';
    for (const auto &t : m.textures)
        std::cout << "texture " << t.name << ' ' << t.width << 'x' << t.height << " semantic=" << t.semantic << '\n';
    for (const auto &t : m.techniques)
        for (const auto &p : t.passes)
            std::cout << "pass " << p.name << " srgb=" << p.srgb_write_enable
                      << " blend=" << p.blend_enable[0] << " viewport=" << p.viewport_width << 'x' << p.viewport_height << '\n';
    std::cout << pp.errors() << parser.errors();
}
