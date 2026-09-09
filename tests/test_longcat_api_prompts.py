from remote_server.longcat_deploy.root.api_service.prompts import resolve_prompts


def test_character_template_and_default_negative_prompt() -> None:
    prompt, negative = resolve_prompts(" 哪吒   少年 ", "character", None, True)
    assert prompt.startswith("哪吒 少年")
    assert "piying_china_style" in prompt
    assert "full body strict 90-degree side profile" in prompt
    assert "stage photography" in negative
    assert "伪文字" in negative


def test_raw_prompt_is_not_modified() -> None:
    prompt, negative = resolve_prompts("raw prompt", "background", "raw negative", False)
    assert prompt == "raw prompt"
    assert negative == "raw negative"


def test_custom_negative_is_merged_with_style_safety_terms() -> None:
    prompt, negative = resolve_prompts(
        "江南水乡",
        "background",
        "现代建筑，人物",
        True,
    )
    assert "scenery backdrop only" in prompt
    assert negative.startswith("现代建筑，人物")
    assert "stage photography" in negative
    assert "pseudo-text" in negative


def test_style_trigger_alone_does_not_skip_constraints() -> None:
    prompt, _negative = resolve_prompts(
        "piying_china_style 哪吒",
        "character",
        None,
        True,
    )
    assert "full body strict 90-degree side profile" in prompt
