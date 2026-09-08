from remote_server.longcat_deploy.root.api_service.prompts import resolve_prompts


def test_character_template_and_default_negative_prompt() -> None:
    prompt, negative = resolve_prompts(" 哪吒   少年 ", "character", None, True)
    assert prompt.startswith("哪吒 少年")
    assert "piying_china_style" in prompt
    assert "full body strict side view" in prompt
    assert "stage photography" in negative
    assert "伪文字" in negative


def test_raw_prompt_is_not_modified() -> None:
    prompt, negative = resolve_prompts("raw prompt", "background", "raw negative", False)
    assert prompt == "raw prompt"
    assert negative == "raw negative"

