#!/usr/bin/env bash
set -euo pipefail
# Pass an official ReShade checkout; no native ReShade add-on required by shader.
repo="${1:?Pass the path to a ReShade source checkout}"
here="$(cd "$(dirname "$0")" && pwd)"
g++ -std=c++17 -O2 -I"$repo/source" "$here/fx_frontend.cpp" \
 "$repo/source/effect_lexer.cpp" "$repo/source/effect_preprocessor.cpp" \
 "$repo/source/effect_expression.cpp" "$repo/source/effect_symbol_table.cpp" \
 "$repo/source/effect_parser_exp.cpp" "$repo/source/effect_parser_stmt.cpp" \
 "$repo/source/effect_codegen_hlsl.cpp" "$repo/source/effect_codegen_glsl.cpp" \
 -o "$here/fx_frontend"
