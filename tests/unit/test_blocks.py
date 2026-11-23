import pytest
from yardmaster.blocks import BlockError, replace_block

MD_B, MD_E = "<!-- yardmaster:begin v1 -->", "<!-- yardmaster:end -->"
H_B, H_E = "# yardmaster:begin v1", "# yardmaster:end"


def test_block_append_to_existing_text():
    out = replace_block("# Title\nhello\n", "route A", style="md")
    assert out == f"# Title\nhello\n\n{MD_B}\nroute A\n{MD_E}\n"


def test_block_append_to_empty_and_unterminated_text():
    assert replace_block("", "x", style="md") == f"{MD_B}\nx\n{MD_E}\n"
    out = replace_block("no newline at end", "x", style="hash")
    assert out.startswith("no newline at end") and out.endswith(f"{H_B}\nx\n{H_E}\n")


def test_block_replace_preserves_outside():
    before, after = "# top\nuser text\n\n", "\nmore user text\n"
    text = f"{before}{MD_B}\nold\nold2\n{MD_E}\n{after}"
    out = replace_block(text, "new body", style="md")
    assert out == f"{before}{MD_B}\nnew body\n{MD_E}\n{after}"
    assert out.startswith(before) and out.endswith(f"{MD_E}\n{after}")


def test_block_is_idempotent():
    once = replace_block("x\n", "body\nline2", style="md")
    assert replace_block(once, "body\nline2", style="md") == once


def test_block_hash_style_and_toml_comment():
    out = replace_block('model = "x"\n', '[profiles.a]\nmodel = "y"', style="hash")
    assert out == f'model = "x"\n\n{H_B}\n[profiles.a]\nmodel = "y"\n{H_E}\n'


def test_block_preserves_crlf_files():
    text = f"a\r\n{MD_B}\r\nold\r\n{MD_E}\r\nz\r\n"
    out = replace_block(text, "new\nbody", style="md")
    assert out == f"a\r\n{MD_B}\r\nnew\r\nbody\r\n{MD_E}\r\nz\r\n"


@pytest.mark.parametrize(
    "text",
    [f"{MD_B}\na\n{MD_E}\n{MD_B}\nb\n{MD_E}\n",  # duplicate pair
     f"{MD_B}\na\n",  # begin without end
     f"a\n{MD_E}\n",  # end without begin
     f"{MD_E}\na\n{MD_B}\n",  # reversed
     f"{MD_B}\n{MD_B}\na\n{MD_E}\n"],  # two begins
)
def test_block_duplicate_markers_abort(text):
    with pytest.raises(BlockError):
        replace_block(text, "new", style="md")


def test_marker_mentioned_inside_prose_is_not_a_marker():
    text = f"Docs: wrap content in {MD_B} and {MD_E} lines.\n"
    out = replace_block(text, "b", style="md")
    assert out.startswith(text) and out.count(f"\n{MD_B}\n") == 1


def test_body_containing_a_marker_line_aborts():
    with pytest.raises(BlockError):
        replace_block("x\n", f"ok\n{MD_E}\nevil", style="md")
    with pytest.raises(BlockError):
        replace_block("x\n", f"ok\n  {H_B}  \nevil", style="hash")


def test_unknown_style():
    with pytest.raises(ValueError):
        replace_block("x", "y", style="xml")
