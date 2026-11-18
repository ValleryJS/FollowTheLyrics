from followthelyrics.system.renderers import RendererGate


def test_desktop_remains_visible_without_renderer_ack():
    gate = RendererGate(timeout=2.0)
    gate.mode = "fivem"
    assert not gate.route_to_external(now=10.0)


def test_renderer_takes_over_only_after_ack():
    gate = RendererGate(timeout=2.0)
    gate.mode = "fivem"
    gate.acknowledge("fivem-reshade", now=10.0)
    assert gate.route_to_external(now=11.0)


def test_desktop_returns_on_timeout():
    gate = RendererGate(timeout=2.0)
    gate.mode = "fivem"
    gate.acknowledge("fivem-reshade", now=10.0)
    assert not gate.route_to_external(now=12.01)


def test_other_addon_cannot_take_over():
    gate = RendererGate(timeout=2.0)
    gate.mode = "fivem"
    gate.acknowledge("random-addon", now=10.0)
    assert not gate.route_to_external(now=10.1)


def test_desktop_mode_always_shows_desktop():
    gate = RendererGate(timeout=2.0)
    gate.acknowledge("fivem-reshade", now=10.0)
    assert not gate.route_to_external(now=10.1)
