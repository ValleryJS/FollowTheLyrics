from pathlib import Path


NATIVE = (
    Path(__file__).resolve().parents[1]
    / "integrations/fivem-reshade/native/FTLReShade.cpp"
)


def test_native_frame_callback_avoids_cpp_mutex_runtime():
    source = NATIVE.read_text(encoding="utf-8")
    assert "SRWLOCK g_mutex = SRWLOCK_INIT;" in source
    assert "std::lock_guard" not in source
    assert "std::mutex" not in source


def test_native_frame_callback_uses_windows_monotonic_clock():
    source = NATIVE.read_text(encoding="utf-8")
    assert "GetTickCount64()" in source
    assert "std::chrono::steady_clock" not in source
