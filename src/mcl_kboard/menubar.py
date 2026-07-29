"""菜单栏：音量、声源风格、启停。"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

from .pack_loader import list_pack_infos
from .paths import MENUBAR_PID_PATH, ensure_support_dir, menubar_icon_path, repo_root
from .state import load_state, save_state

log = logging.getLogger("mcl_kboard.menubar")

VOLUME_PRESETS = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)


def _ensure_agent(enabled: bool) -> None:
    from .cli import _pid_alive, _read_pid, _python
    from .paths import AGENT_PID_PATH, SUPPORT_DIR

    pid = _read_pid(AGENT_PID_PATH)
    running = bool(pid and _pid_alive(pid))
    if enabled and not running:
        log_path = SUPPORT_DIR / "agent.log"
        subprocess.Popen(
            [_python(), "-m", "mcl_kboard.agent"],
            stdout=open(log_path, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(repo_root()),
        )
    elif not enabled and running and pid:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def _safe_clear(menu_item) -> None:
    """rumps: clear() crashes if NSMenu not yet created."""
    try:
        if getattr(menu_item, "_menu", None) is not None:
            menu_item.clear()
    except Exception:
        pass


def main() -> None:
    try:
        import rumps
    except ImportError:
        print("rumps is required for the menu bar. pip install rumps", file=sys.stderr)
        raise SystemExit(1)

    ensure_support_dir()
    MENUBAR_PID_PATH.write_text(str(os.getpid()), encoding="utf-8")

    class KboardApp(rumps.App):
        def __init__(self) -> None:
            icon = menubar_icon_path()
            # name 用于通知等；title="" 只显示自定义奔马图标
            kwargs = {
                "name": "键音",
                "title": " ",
                "quit_button": None,
            }
            if icon.is_file():
                kwargs["icon"] = str(icon)
                kwargs["template"] = True
                kwargs["title"] = ""
            super().__init__(**kwargs)
            self.state = load_state()

            self.enable_item = rumps.MenuItem("启用音效", callback=self.toggle_enabled)
            self.enable_item.state = bool(self.state.enabled)

            self.notify_item = rumps.MenuItem("桌面通知", callback=self.toggle_notifications)
            self.notify_item.state = bool(self.state.show_notifications)

            self.volume_menu = rumps.MenuItem("音量调节")
            self.style_menu = rumps.MenuItem("切换音效 / 声源")
            self.sens_menu = rumps.MenuItem("力度灵敏度")

            # 先挂到 self.menu，再填充子菜单（避免 clear 崩溃）
            self.menu = [
                self.enable_item,
                self.notify_item,
                None,
                self.volume_menu,
                rumps.MenuItem("音量 +10%", callback=self.vol_up),
                rumps.MenuItem("音量 −10%", callback=self.vol_down),
                None,
                self.style_menu,
                None,
                self.sens_menu,
                rumps.MenuItem("灵敏度 +", callback=self.sens_up),
                rumps.MenuItem("灵敏度 −", callback=self.sens_down),
                None,
                rumps.MenuItem("试听当前音效", callback=self.test_sound),
                rumps.MenuItem("刷新菜单", callback=self.reload),
                rumps.MenuItem("退出键音", callback=self.quit_app),
            ]
            self._rebuild_all_submenus()
            rumps.notifications(self._on_notification)
            if self.state.enabled:
                _ensure_agent(True)

        def _notify(self, title: str, subtitle: str, message: str, *, force: bool = False) -> None:
            if not force and not self.state.show_notifications:
                return
            try:
                rumps.notification(
                    title,
                    subtitle,
                    message,
                    sound=False,
                    action_button="不再提示",
                    data={"kind": "status"},
                )
            except Exception as e:
                log.debug("notification failed: %s", e)

        def _on_notification(self, info) -> None:
            # 点击通知上的「不再提示」按钮
            if getattr(info, "activation_type", None) != "action_button_clicked":
                return
            self.state.show_notifications = False
            self.notify_item.state = False
            self._persist()
            log.info("desktop notifications disabled by user")

        def _vol_label_prefix(self) -> str:
            return f"音量调节（当前 {int(round(self.state.volume * 100))}%）"

        def _rebuild_all_submenus(self) -> None:
            self._rebuild_volume_menu()
            self._rebuild_style_menu()
            self._rebuild_sens_menu()

        def _rebuild_volume_menu(self) -> None:
            _safe_clear(self.volume_menu)
            self.volume_menu.title = self._vol_label_prefix()
            for v in VOLUME_PRESETS:
                pct = int(v * 100)
                item = rumps.MenuItem(f"设为 {pct}%", callback=self.select_volume)
                if abs(self.state.volume - v) < 0.06:
                    item.state = True
                self.volume_menu.add(item)

        def _rebuild_style_menu(self) -> None:
            _safe_clear(self.style_menu)
            infos = list_pack_infos()
            current = next((i for i in infos if i.id == self.state.pack), None)
            if current:
                self.style_menu.title = f"切换音效 / 声源（{current.display_name}）"
            else:
                self.style_menu.title = "切换音效 / 声源"

            if not infos:
                self.style_menu.add(rumps.MenuItem("(无可用音色包)"))
                return
            for info in infos:
                item = rumps.MenuItem(
                    f"{info.display_name}  ·  {info.id}",
                    callback=self.select_pack,
                )
                if info.id == self.state.pack:
                    item.state = True
                self.style_menu.add(item)

        def _rebuild_sens_menu(self) -> None:
            _safe_clear(self.sens_menu)
            self.sens_menu.title = f"力度灵敏度（当前 {self.state.sensitivity:.1f}）"
            for s in (0.8, 1.0, 1.3, 1.6, 2.0, 2.5):
                item = rumps.MenuItem(f"设为 {s:.1f}", callback=self.select_sens)
                if abs(self.state.sensitivity - s) < 0.05:
                    item.state = True
                self.sens_menu.add(item)

        def _persist(self) -> None:
            save_state(self.state)
            self._rebuild_all_submenus()

        def toggle_enabled(self, sender: rumps.MenuItem) -> None:
            sender.state = not sender.state
            self.state.enabled = bool(sender.state)
            self._persist()
            _ensure_agent(self.state.enabled)
            self._notify(
                "键音 mcl-kboard",
                "",
                "音效已开启" if self.state.enabled else "音效已关闭",
            )

        def toggle_notifications(self, sender: rumps.MenuItem) -> None:
            sender.state = not sender.state
            self.state.show_notifications = bool(sender.state)
            self._persist()
            if self.state.show_notifications:
                self._notify("键音", "", "已重新开启桌面通知", force=True)

        def vol_up(self, _sender: rumps.MenuItem) -> None:
            self.state.volume = min(2.0, round(self.state.volume + 0.1, 2))
            self._persist()
            self._notify("键音", "音量", f"{int(self.state.volume * 100)}%")

        def vol_down(self, _sender: rumps.MenuItem) -> None:
            self.state.volume = max(0.0, round(self.state.volume - 0.1, 2))
            self._persist()
            self._notify("键音", "音量", f"{int(self.state.volume * 100)}%")

        def select_volume(self, sender: rumps.MenuItem) -> None:
            # "设为 80%"
            try:
                pct = int("".join(ch for ch in sender.title if ch.isdigit()))
                self.state.volume = max(0.0, min(2.0, pct / 100.0))
                self._persist()
                self._notify("键音", "音量", f"{pct}%")
            except ValueError:
                pass

        def select_sens(self, sender: rumps.MenuItem) -> None:
            try:
                val = float(sender.title.replace("设为", "").strip())
                self.state.sensitivity = max(0.2, min(4.0, val))
                self._persist()
            except ValueError:
                pass

        def sens_up(self, _sender: rumps.MenuItem) -> None:
            self.state.sensitivity = min(4.0, round(self.state.sensitivity + 0.1, 2))
            self._persist()

        def sens_down(self, _sender: rumps.MenuItem) -> None:
            self.state.sensitivity = max(0.2, round(self.state.sensitivity - 0.1, 2))
            self._persist()

        def select_pack(self, sender: rumps.MenuItem) -> None:
            title = sender.title
            pack_id = title.split("·")[-1].strip() if "·" in title else title
            self.state.pack = pack_id
            self._persist()
            self._notify("键音", "音效已切换", pack_id)
            from .audio_engine import preview_pack_async

            preview_pack_async(pack_id, volume=self.state.volume)

        def test_sound(self, _sender: rumps.MenuItem) -> None:
            try:
                from .audio_engine import preview_pack

                preview_pack(self.state.pack, volume=self.state.volume)
            except Exception as e:
                self._notify("键音", "试听失败", str(e), force=True)

        def reload(self, _sender: rumps.MenuItem) -> None:
            self.state = load_state()
            self.enable_item.state = bool(self.state.enabled)
            self.notify_item.state = bool(self.state.show_notifications)
            self._persist()
            self._notify("键音", "", "菜单已刷新")

        def quit_app(self, _sender: rumps.MenuItem) -> None:
            try:
                if MENUBAR_PID_PATH.exists():
                    MENUBAR_PID_PATH.unlink()
            except OSError:
                pass
            rumps.quit_application()

    print(
        "菜单栏已启动：请看屏幕右上角奔马图标（深浅色自动适配），点击可调节音量与音效。",
        flush=True,
    )
    KboardApp().run()


if __name__ == "__main__":
    main()
