from kidcut.cli import _get_output_path


def test_get_output_path_adds_kidcut_suffix():
    assert _get_output_path("/path/movie.mkv").endswith("-kidcut.mkv")
    assert "movie-kidcut" in _get_output_path("/path/movie.mkv")
