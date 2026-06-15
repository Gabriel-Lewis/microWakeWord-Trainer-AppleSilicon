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


def test_rendered_firmware_config_applies_wake_engine_customizations(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "FIRMWARE_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(server, "FIRMWARE_PROFILE_FILE", tmp_path / "profiles.json")

    config_path, normalized, _ = server._render_firmware_config(
        "satellite1",
        {
            "wifi_ssid": "test-wifi",
            "wifi_password": "test-password",
            "wake_word_model_url": "http://127.0.0.1:8789/api/trained_wake_words/computer.json",
            "enabled_wake_engines": ["microwakeword", "openwakeword"],
            "default_wake_engine": "microwakeword",
        },
        "192.0.2.10",
        "test-session",
    )

    assert normalized["wake_engine"] == "microwakeword"
    assert normalized["__enabled_wake_engines"] == "microwakeword,openwakeword"

    package_docs = [
        server.yaml.load(path.read_text(encoding="utf-8"), Loader=server._FirmwareYamlLoader)
        for path in (config_path.parent / "packages").rglob("*.yaml")
    ]
    wake_engine_selects = [
        item
        for doc in package_docs
        for item in (doc.get("select") if isinstance(doc, dict) and isinstance(doc.get("select"), list) else [])
        if isinstance(item, dict) and item.get("id") == "wake_engine_select"
    ]
    assert wake_engine_selects
    assert all(item["options"] == ["microwakeword", "openwakeword"] for item in wake_engine_selects)
    assert all(item["initial_option"] == "microwakeword" for item in wake_engine_selects)


def test_rendered_firmware_config_prunes_single_micro_wake_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "FIRMWARE_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(server, "FIRMWARE_PROFILE_FILE", tmp_path / "profiles.json")

    config_path, _, _ = server._render_firmware_config(
        "satellite1",
        {
            "wifi_ssid": "test-wifi",
            "wifi_password": "test-password",
            "wake_word_model_url": "http://127.0.0.1:8789/api/trained_wake_words/computer.json",
            "enabled_wake_engines": ["microwakeword"],
            "default_wake_engine": "microwakeword",
        },
        "192.0.2.10",
        "test-session",
    )

    package_text = "\n".join(path.read_text(encoding="utf-8") for path in (config_path.parent / "packages").rglob("*.yaml"))
    assert "remote_wake_word:" not in package_text
    assert "remote_wake_word.start" not in package_text
    assert "remote_wake_word.stop" not in package_text
    assert "id: wake_engine_select" not in package_text
    assert "id: openwakeword_server_url" not in package_text
    assert "id: nanowakeword_server_url" not in package_text


def test_rendered_firmware_config_prunes_single_remote_wake_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "FIRMWARE_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(server, "FIRMWARE_PROFILE_FILE", tmp_path / "profiles.json")

    config_path, normalized, _ = server._render_firmware_config(
        "satellite1",
        {
            "wifi_ssid": "test-wifi",
            "wifi_password": "test-password",
            "wake_word_model_url": "http://127.0.0.1:8789/api/trained_wake_words/computer.json",
            "enabled_wake_engines": ["nanowakeword"],
            "default_wake_engine": "nanowakeword",
        },
        "192.0.2.10",
        "test-session",
    )

    package_text = "\n".join(path.read_text(encoding="utf-8") for path in (config_path.parent / "packages").rglob("*.yaml"))
    assert normalized["wake_engine"] == "nanowakeword"
    assert "micro_wake_word:" not in package_text
    assert "micro_wake_word.start" not in package_text
    assert "micro_wake_word.enable_model" not in package_text
    assert "id: wake_engine_select" not in package_text
    assert "stream_path: /api/nanowakeword/stream" in package_text
    assert "id: openwakeword_server_url" not in package_text
    assert "id: nanowakeword_server_url" in package_text


def test_rendered_firmware_config_adds_sat1_optional_packages(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "FIRMWARE_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(server, "FIRMWARE_PROFILE_FILE", tmp_path / "profiles.json")

    config_path, normalized, _ = server._render_firmware_config(
        "satellite1",
        {
            "wifi_ssid": "test-wifi",
            "wifi_password": "test-password",
            "wake_word_model_url": "http://127.0.0.1:8789/api/trained_wake_words/computer.json",
            "enabled_optional_packages": ["sat1/mmwave_ld2410.yaml", "sat1/debug.yaml"],
        },
        "192.0.2.10",
        "test-session",
    )

    package_paths = {path.relative_to(config_path.parent / "packages").as_posix() for path in (config_path.parent / "packages").rglob("*.yaml")}
    assert "sat1/mmwave_ld2410.yaml" in package_paths
    assert "sat1/debug.yaml" in package_paths
    assert normalized["__enabled_optional_packages"] == "sat1/mmwave_ld2410.yaml,sat1/debug.yaml"


def test_firmware_customizations_reject_both_mmwave_packages():
    try:
        server._normalize_firmware_customizations(
            "satellite1",
            {
                "enabled_optional_packages": [
                    "sat1/mmwave_ld2410.yaml",
                    "sat1/mmwave_ld2450.yaml",
                ]
            },
            {},
        )
    except ValueError as exc:
        assert "mmwave" in str(exc)
    else:
        raise AssertionError("Expected both mmWave packages to be rejected")
