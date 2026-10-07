from reel_transcribe import cli
from reel_transcribe.app import Result


def test_cli_prints_images_without_api_key(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    image_output = tmp_path / "assets"
    image = image_output / "image.jpg"
    caption = image_output / "ABC-legenda.txt"

    def fake_process_reel(*args, **kwargs):
        assert kwargs["image_output_dir"] == image_output.resolve()
        return Result(image_paths=(image,), caption_path=caption)

    monkeypatch.setattr(cli, "process_reel", fake_process_reel)

    code = cli.main(
        [
            "https://instagram.com/p/ABC/",
            "--image-output",
            str(image_output),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "Imagem:" in captured.out
    assert str(image) in captured.out
    assert f"Legenda: {caption}" in captured.out
    assert captured.err == ""


def test_help_is_available(capsys):
    try:
        cli.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "reel-transcribe" in capsys.readouterr().out


def test_cookies_are_opt_in():
    parser = cli.build_parser()
    assert parser.parse_args(["https://instagram.com/reel/ABC/"]).cookies_from_browser is None
    assert parser.parse_args(["https://instagram.com/reel/ABC/", "--cookies-from-browser", "safari"]).cookies_from_browser == "safari"


def test_default_model_is_gemini_35_flash():
    args = cli.build_parser().parse_args(["https://instagram.com/reel/ABC/"])
    assert args.model == "gemini-3.5-flash"


def test_default_output_is_portable(monkeypatch):
    monkeypatch.delenv("REEL_TRANSCRIBE_OUTPUT", raising=False)
    args = cli.build_parser().parse_args(["https://instagram.com/reel/ABC/"])
    assert args.output == cli.Path.home() / "Videos" / "reel-transcribe"


def test_default_image_output_is_downloads_folder_on_macos():
    args = cli.build_parser().parse_args(["https://instagram.com/p/ABC/"])
    assert args.image_output == cli.Path.home() / "Downloads"
