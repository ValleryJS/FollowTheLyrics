#include "ReShade.fxh"

uniform float PositionX < ui_type = "drag"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.001; > = 0.5;
uniform float PositionY < ui_type = "drag"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.001; > = 0.7;
uniform float LetterSize < ui_type = "drag"; ui_min = 0.01; ui_max = 0.08; ui_step = 0.002; > = 0.035;
uniform float LineHeight < ui_type = "drag"; ui_min = 0.02; ui_max = 0.3; ui_step = 0.005; > = 0.1;
uniform float PerspectiveTilt < ui_type = "drag"; ui_min = -0.7; ui_max = 0.7; ui_step = 0.01; > = 0.0;
uniform float Opacity < ui_type = "drag"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.01; > = 0.95;
uniform float3 LyricColor < ui_type = "color"; > = float3(1.0, 1.0, 1.0);

// Updated by FTLReShade.addon64, not by the desktop UI directly.
uniform int FTL_Count = 0;
uniform int FTL_Codes[64] = {
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0
};

texture FTLFont < source = "FTL_FontAtlas.png"; >
{
    Width = 1024;
    Height = 384;
    Format = RGBA8;
};
sampler FTLFontSampler { Texture = FTLFont; AddressU = CLAMP; AddressV = CLAMP; };

float4 FTLRender(float4 pos : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    float4 scene = tex2D(ReShade::BackBuffer, uv);
    if (FTL_Count <= 0)
        return scene;

    int count = min(FTL_Count, 64);
    float width = min(0.95, LetterSize * count);
    float2 local = (uv - float2(PositionX, PositionY)) / float2(width, LineHeight) + 0.5;
    local.x += (local.y - 0.5) * PerspectiveTilt;
    if (local.x < 0.0 || local.x > 1.0 || local.y < 0.0 || local.y > 1.0)
        return scene;

    float charPos = local.x * count;
    int index = min(count - 1, int(floor(charPos)));
    int code = FTL_Codes[index];
    if (code < 32 || code > 127)
        return scene;

    int glyph = code - 32;
    float2 glyphUV = float2(frac(charPos), local.y);
    float2 atlasUV = (float2(glyph % 16, glyph / 16) + glyphUV) / float2(16.0, 6.0);
    float alpha = tex2D(FTLFontSampler, atlasUV).a * Opacity;
    return float4(lerp(scene.rgb, LyricColor, alpha), scene.a);
}

technique FTL_Live < ui_label = "FollowTheLyrics Live (Experimental)"; >
{
    pass
    {
        VertexShader = PostProcessVS;
        PixelShader = FTLRender;
    }
}
