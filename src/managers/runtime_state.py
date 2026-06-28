from platform import freedesktop_os_release, platform, system, win32_ver

import distro


class RuntimeState:
    def __init__(self):
        self.active_games: dict = {}

        self.invites: list = []
    
    def get_platform_info(self):
        platform_info = platform(aliased=True)
        system_info = system()
        if system_info == "Linux":
            try:
                os_rel = freedesktop_os_release()
                if os_rel and os_rel.get("ID") == "ubuntu":
                    platform_info = distro.name(pretty=True)
            except Exception:
                pass
        elif system_info == "Windows":
            platform_info = "Windows" + " ".join(list(win32_ver()))
        
        return platform_info
