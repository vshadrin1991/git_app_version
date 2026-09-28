from git_version_tagger.tagger import TagPlan, find_marker_tags, markers_in_tags, printable, tag_name

TEMPLATE = "{marker}-#{hash}"


def make_plan(**overrides) -> TagPlan:
    values = dict(
        branch="trunk",
        marker="3.25",
        commit="a1b2c3d" + "0" * 33,
        short_hash="a1b2c3d",
        subject="Fix login",
        new_tag="3.25-#a1b2c3d",
        old_tags=("3.25-#0000fff",),
        already_tagged=False,
    )
    values.update(overrides)
    return TagPlan(**values)


def test_tag_name_uses_template():
    assert tag_name(TEMPLATE, "3.25", "a1b2c3d") == "3.25-#a1b2c3d"
    assert tag_name(TEMPLATE, "alt-1.55", "abcdef1") == "alt-1.55-#abcdef1"


def test_find_marker_tags_matches_only_exact_marker():
    tags = [
        "3.25-#a1b2c3d",
        "3.2-#0000fff",
        "alt-1.55-#abcdef1",
        "1.55-#1234567",
        "3.25-rc",
        "v3.25-#a1b2c3d",
        "3.25-#nothex",
    ]
    assert find_marker_tags(tags, TEMPLATE, "3.25") == ["3.25-#a1b2c3d"]
    assert find_marker_tags(tags, TEMPLATE, "3.2") == ["3.2-#0000fff"]
    assert find_marker_tags(tags, TEMPLATE, "1.55") == ["1.55-#1234567"]
    assert find_marker_tags(tags, TEMPLATE, "alt-1.55") == ["alt-1.55-#abcdef1"]


def test_dot_in_marker_is_not_a_wildcard():
    assert find_marker_tags(["3x25-#a1b2c3d"], TEMPLATE, "3.25") == []


def test_custom_template_with_regex_characters():
    assert find_marker_tags(["v3.25+a1b2c3d", "v3.25-a1b2c3d"], "v{marker}+{hash}", "3.25") == ["v3.25+a1b2c3d"]


def test_find_marker_tags_returns_sorted_duplicates():
    assert find_marker_tags(["3.25-#0000002", "3.25-#0000001"], TEMPLATE, "3.25") == ["3.25-#0000001", "3.25-#0000002"]


def test_describe_lists_what_will_happen():
    text = make_plan().describe()
    assert "trunk is at a1b2c3d: Fix login" in text
    assert "delete 3.25-#0000fff" in text
    assert "create 3.25-#a1b2c3d" in text


def test_up_to_date_only_when_tagged_and_nothing_to_delete():
    assert make_plan(already_tagged=True, old_tags=()).up_to_date
    assert not make_plan(already_tagged=True).up_to_date
    assert not make_plan(already_tagged=False, old_tags=()).up_to_date
    assert "create" not in make_plan(already_tagged=True).describe()


def test_markers_in_tags_extracts_markers_highest_version_first():
    tags = ["3.24-#a1b2c3d", "3.25-#1234567", "3.9-#abcdef0", "alt-1.55-#0badf00d", "v1.0", "3.0-react-#abc1234"]
    assert markers_in_tags(tags, TEMPLATE) == ["alt-1.55", "3.25", "3.24", "3.9", "3.0-react"]


def test_markers_in_tags_deduplicates_and_skips_tags_in_other_formats():
    tags = ["3.25-#a1b2c3d", "3.25-#1234567", "3.25-#zzz", "release-3.25", "-#a1b2c3d", "3..25-#a1b2c3d"]
    assert markers_in_tags(tags, TEMPLATE) == ["3.25"]


def test_markers_in_tags_follows_a_custom_template():
    assert markers_in_tags(["v3.25+abc1234", "3.24-#abc1234"], "v{marker}+{hash}") == ["3.25"]


def test_markers_in_tags_with_the_marker_twice_in_the_template():
    tags = ["3.25/3.25-abc1234", "3.25/3.24-abc1234"]
    assert markers_in_tags(tags, "{marker}/{marker}-{hash}") == ["3.25"]


def test_printable_replaces_terminal_controls_and_bidi_overrides():
    assert printable("Fix \x1b]0;PWNED\x07 \x1b[2J done") == "Fix ?]0;PWNED? ?[2J done"
    assert printable("report‮gpj.exe") == "report?gpj.exe"
    assert printable("line\rover") == "line?over"
    assert printable("a\nb") == "a?b"
    assert printable("a\nb", keep_newlines=True) == "a\nb"
    assert printable("Релиз 3.26 ✓ → trunk") == "Релиз 3.26 ✓ → trunk"
