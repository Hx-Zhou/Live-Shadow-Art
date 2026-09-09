from __future__ import annotations

from typing import Literal


SHARED_NEGATIVE_PROMPT = (
    "photorealistic, realistic person, stage photography, 3d render, glossy plastic, "
    "modern clothing, ordinary digital illustration, front view, front-facing pose, three-quarter "
    "view, symmetrical face, both eyes visible, cropped body, close-up, "
    "missing limb, extra limb, fused limbs, arms touching torso, overlapping legs, hidden hands, "
    "hidden feet, malformed anatomy, duplicate body, floating weapon, blurry edge, low contrast, "
    "busy background, central obstruction, text, letters, subtitle, logo, watermark, pseudo-text, "
    "写实人物，舞台摄影，现代服饰，普通插画，正面，三分之四侧脸，对称正脸，双眼同时可见，"
    "主体裁切，缺肢，多肢，四肢粘连，"
    "手臂贴躯干，腿部重叠，手脚遮挡，复杂背景，中央被遮挡，文字，伪文字，水印"
)

CHARACTER_SUFFIX = (
    "piying_china_style, 中国传统皮影人物，严格九十度纯侧身，仅一只眼睛可见，鼻梁和下巴形成"
    "清楚的侧面剪影，非正面，非三分之四侧脸，traditional Chinese shadow-puppet leather "
    "cutout, full body strict 90-degree side profile, exactly one eye visible, clear nose and chin "
    "silhouette, head-to-toe visible, arms and legs clearly separated from torso, visible movable joints, "
    "clean silhouette, perforated translucent leather, hand-cut engraved patterns, red gold black "
    "and muted teal palette, flat colors, plain warm ivory background, centered single character, "
    "no text"
)

BACKGROUND_SUFFIX = (
    "piying_china_style, traditional Chinese shadow-puppet stage background, layered paper-cut and "
    "translucent leather silhouettes, red gold black and muted teal palette, clear foreground "
    "middle-ground and background layers, central 35 percent open for character performance, no "
    "people, no text, flat graphic shapes, strong warm backlight"
)


def resolve_prompts(
    prompt: str,
    kind: Literal["character", "background"],
    negative_prompt: str | None,
    apply_style_template: bool,
) -> tuple[str, str]:
    cleaned = " ".join(prompt.split())
    if apply_style_template:
        suffix = CHARACTER_SUFFIX if kind == "character" else BACKGROUND_SUFFIX
        if "piying_china_style" not in cleaned:
            cleaned = f"{cleaned}. {suffix}"
    negative = " ".join((negative_prompt or SHARED_NEGATIVE_PROMPT).split())
    return cleaned, negative
