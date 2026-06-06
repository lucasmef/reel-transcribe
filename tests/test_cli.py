from reel_transcribe import cli


def test_cli_fails_before_download_without_api_key(monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    code = cli.main(["https://instagram.com/reel/ABC/"])
    assert code == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err


def test_help_is_available(capsys):
    try:
        cli.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "reel-transcribe" in capsys.readouterr().out


def test_default_model_is_gemini_35_flash():
    args = cli.build_parser().parse_args(["https://instagram.com/reel/ABC/"])
    assert args.model == "gemini-3.5-flash"


def test_default_output_is_google_drive_model_folder():
    args = cli.build_parser().parse_args(["https://instagram.com/reel/ABC/"])
    assert args.output.parts[-5:] == (
        "lucas",
        "Transmissão no Google Drive",
        "Meu Drive",
        "VIDEOS",
        "MODEL",
    )
