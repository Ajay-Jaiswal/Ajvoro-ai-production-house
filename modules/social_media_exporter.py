    test_input = TEMP_DIR / "test_input.mp4"
    test_input.parent.mkdir(parents=True, exist_ok=True)
    test_input.write_bytes(b"test")

    try:
        command = build_ffmpeg_command(
            test_input,
            TEMP_DIR / "test_output.mp4",
            get_preset("YouTube Shorts"),
        )
        assert command[0] == "ffmpeg"
        assert "libx264" in command
        assert "1080:1920" in command[command.index("-vf") + 1]
    finally:
        test_input.unlink(missing_ok=True)