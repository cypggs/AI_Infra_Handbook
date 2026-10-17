from openai_mini.router import list_models, pick_model


def test_pick_model_exact():
    assert pick_model("gpt-mini") == "gpt-mini"
    assert pick_model("gpt-large") == "gpt-large"


def test_pick_model_default():
    assert pick_model("gpt-any") == "gpt-mini"


def test_pick_model_unsupported():
    try:
        pick_model("unsupported")
        assert False
    except ValueError as e:
        assert "unsupported model" in str(e)


def test_list_models():
    models = list_models()
    ids = {m["id"] for m in models}
    assert ids == {"gpt-mini", "gpt-large"}


def test_pick_model_tier_alias():
    assert pick_model("gpt-6-luna") == "gpt-mini"
    assert pick_model("gpt-6-sol") == "gpt-large"
    assert pick_model("gpt-6-astra") == "gpt-large"


def test_pick_model_effort_routing():
    # Unknown gpt-* names default to the small backend...
    assert pick_model("gpt-any") == "gpt-mini"
    # ...unless the caller asks for high reasoning effort.
    assert pick_model("gpt-any", effort="high") == "gpt-large"
    # Explicit model names are never overridden by effort.
    assert pick_model("gpt-mini", effort="high") == "gpt-mini"
