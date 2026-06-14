import trainer_server as server


def test_firmware_template_specs_load_from_bundled_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "FIRMWARE_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(server, "FIRMWARE_PROFILE_FILE", tmp_path / "profiles.json")

    keys = {spec["key"] for spec in server.FIRMWARE_TEMPLATE_SPECS}
    assert keys == {
        "voicepe",
        "satellite1",
        "koala",
        "respeaker_lite",
        "respeaker_xvf3800",
    }

    for spec in server.FIRMWARE_TEMPLATE_SPECS:
        ctx = server._load_firmware_template_context(spec["key"])
        assert ctx["source_label"].startswith(str(server.FIRMWARE_LOCAL_REPO_DIR))
        assert ctx["substitutions"]


def test_rendered_firmware_config_uses_local_packages_and_components(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "FIRMWARE_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(server, "FIRMWARE_PROFILE_FILE", tmp_path / "profiles.json")

    config_path, normalized, _ = server._render_firmware_config(
        "satellite1",
        {
            "wifi_ssid": "test-wifi",
            "wifi_password": "test-password",
            "wake_word_model_url": "http://127.0.0.1:8789/api/trained_wake_words/computer.json",
        },
        "192.0.2.10",
        "test-session",
    )

    assert normalized["ha_voice_ip"] == "192.0.2.10"
    rendered = config_path.read_text(encoding="utf-8")
    assert "!include" in rendered
    assert "https://github.com/Gabriel-Lewis/microWakeWords" not in rendered

    parsed = server.yaml.load(rendered, Loader=server._FirmwareYamlLoader)
    external_source = parsed["external_components"][0]["source"]
    assert external_source["type"] == "local"
    assert external_source["path"].endswith("firmware/microWakeWords/sat1/components")

    package_files = sorted((config_path.parent / "packages").rglob("*.yaml"))
    assert package_files
    package_text = "\n".join(path.read_text(encoding="utf-8") for path in package_files)
    assert "https://github.com/Gabriel-Lewis/microWakeWords" not in package_text
    assert "type: local" in package_text
