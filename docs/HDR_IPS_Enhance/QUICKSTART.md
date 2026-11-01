# Start here

1. Copy `Shaders/HDR_IPS_Enhance.fx` **and** `Shaders/HDRIPS_Math.fxh` to your game's `reshade-shaders/Shaders` folder.
2. Load `Presets/Natural_HDR.ini` in ReShade. It safely starts bypassed.
3. Confirm the encoding of ReShade's sampled final buffer using the procedure in README.md. Then choose explicit **HDR10 PQ / BT.2020** or **Linear scRGB**. Alternatively, use Auto with its verification checkbox after confirming the normal final-buffer contract. Your NVIDIA 10 bpc setting alone cannot decide this.
4. Keep default **High** quality. Begin with other color/HDR filters off. Calibrate the game's HDR with the effect bypassed, then restore it.
5. Use split view. Try `IPS_Depth_HDR.ini` for more depth or `Rich_Color_HDR.ini` for more color, reselecting your verified input contract after loading a supplied preset. Save your game-specific preset afterward.

To remove local contrast and its memory/pass cost, set `HDRIPS_ENABLE_LOCAL=0` in ReShade's preprocessor definitions and reload.

The effect cannot lower the panel's physical black level, remove IPS glow or create local dimming. It does not add a 400-nit limiter or replace the game's tone mapping.

Numerical tests and ReShade FX parsing/code generation were performed. GPU driver compilation, in-game visual testing and your game's sampled-buffer contract remain to be checked on your computer. See VALIDATION.md.
