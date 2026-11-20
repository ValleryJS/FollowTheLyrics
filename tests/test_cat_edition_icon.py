from importlib.resources import files


def test_cat_edition_icon_is_bundled():
    icon = files("followthelyrics").joinpath("assets", "cat_edition.png")
    with icon.open("rb") as image:
        assert image.read(8) == b"\x89PNG\r\n\x1a\n"
