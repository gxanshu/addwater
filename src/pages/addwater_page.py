# addwater_page.py
# TODO once this is working properly turn this class into a generic parent class and spin off Firefox and Thunderbird Pages into their own subclasses
# TODO make app_path and profile_path class properties that can be edited easily

import logging, json, os.path, shutil, requests
from configparser import ConfigParser
from gi.repository import Gtk, Adw, Gio, GLib, GObject
from ..utils import install, paths

log = logging.getLogger(__name__)


@Gtk.Template(resource_path="/dev/qwery/AddWater/pages/addwater-page.ui")
class AddwaterPage(Adw.Bin):
    """ ViewStackPage"""
    __gtype_name__ = "AddwaterPage"

    # Firefox Attributes

    # Widget controls
    toast_overlay = Gtk.Template.Child()
    preferences_page = Gtk.Template.Child()
    change_confirm_bar = Gtk.Template.Child()

    enable_button = Gtk.Template.Child()
    profile_switcher = Gtk.Template.Child()
    profile_list = Gtk.Template.Child()



    def __init__(self, app_path, app_options, app_name, theme_url):
        self.app_path = app_path
        self.app_options = app_options
        self.app_name = app_name
        self.theme_url = theme_url

    # GUI and Backend
        super().__init__()
        self.settings = Gio.Settings(schema_id=f"dev.qwery.AddWater.{self.app_name}")
        self.settings.delay()
        self.init_prefs(app_options)

        # Change Confirmation bar
        # TODO make sure this doesn't cause issues. If it does, then add an ActionGroup to this class or just workaround actions altogether and connect the signal directly
        self.install_action(
            "water.apply-changes",
            None,
            self.apply_changes
            )
        self.install_action(
            "water.discard-changes",
            None,
            self.discard_changes
        )

        self.settings.bind_property(
            "has-unapplied",
            self.change_confirm_bar,
            "revealed",
            GObject.BindingFlags.SYNC_CREATE
        )

    # Find Firefox Attributes
        self.installed_version = self.settings.get_int("installed-version")
        self.find_profiles(moz_path=self.app_path)

    # Look for updates
        self.check_for_updates()
    #     if self.update_version > self.installed_version:
    #         msg = f"Theme updated (v{self.update_version})"
            # TODO set has unapplied to True and ask to install if theme is installed, or automatically install
    #     else:
    #         msg = "No update available"

    #     self.toast_overlay.add_toast(
    #         Adw.Toast(
    #             title=msg,
    #             timeout=2
    #         )
    #     )


    def init_prefs(self, OPTIONS_LIST):
        # TODO When a button is switched from its previous position, add a dot next to the switch to show it's been changed. Set all to hidden when settings are applied.
        # App options
        self.settings.bind(
            "theme-enabled",
            self.enable_button,
            "active",
            Gio.SettingsBindFlags.DEFAULT
        )

        # Theme options
        for each in OPTIONS_LIST:
            group = Adw.PreferencesGroup(title=each["group_name"])

            for option in each["options"]:
                button = Adw.SwitchRow(
                    title=option["summary"],
                    tooltip_text=option["description"]
                )
                self.settings.bind(
                    option["key"],
                    button,
                    "active",
                    Gio.SettingsBindFlags.DEFAULT
                )
                # Disables theme-specific options if theme isn't enabled.
                self.enable_button.bind_property(
                    "active",
                    button,
                    "sensitive",
                    GObject.BindingFlags.SYNC_CREATE
                )

                group.add(button)
            self.preferences_page.add(group)



    def apply_changes(self, one, action, three):
        self.settings.set_int("installed-version", self.update_version)
        self.settings.apply()
        selected_profile_name = self.profile_switcher.get_selected_item().get_string()
        for each in self.profiles:
            if each["name"] == selected_profile_name:
                profile_id = each["id"]
                break

        # TODO Turn the install and uninstall into bespoke methods separate from each other
        if self.settings.get_boolean("theme-enabled") is True:
            msg = self.install_theme(profile_id=profile_id)
        else:
            msg = self.uninstall_theme(profile_id=profile_id)

        toast = Adw.Toast(
            title=msg,
            timeout=5,
            priority=Adw.ToastPriority.HIGH
        )
        self.toast_overlay.add_toast(toast)



    def discard_changes(self, one, action, three):
        self.settings.revert()

        # FIXME Toasts don't disappear unless another window is in focus. Why?
        toast = Adw.Toast(
            title="Changes reverted",
            timeout=3,
            priority=Adw.ToastPriority.NORMAL
        )
        self.toast_overlay.add_toast(toast)


    def install_theme(self, profile_id, OPTIONS):
        selected_profile_name = self.profile_switcher.get_selected_item().get_string()
        for each in self.profiles:
            if each["name"] == selected_profile_name:
                profile_id = each["id"]
                break

        user_js = os.path.join(self.app_path, profile_id, "user.js")
        # Run install script
        install.install_firefox(
            app_path=self.app_path,
            profile=profile_id,
            version=self.update_version
        )

        # Set all user.js options according to gsettings
        with open(file=user_js, mode="r") as file:
            lines = file.readlines()

        with open(file=user_js, mode="w") as file:
            for group in OPTIONS:
                for option in group["options"]:
                    js_key = option["js_key"]
                    value = str(self.settings.get_boolean(option["key"])).lower()
                    pref_name = f"gnomeTheme.{js_key}"
                    full_line = f"""user_pref("{pref_name}", {value});\n"""

                    found = False
                    for i in range(len(lines)):
                        if pref_name in lines[i]:
                            lines[i] = full_line
                            found = True
                            break
                    if found == False:
                        lines.append(full_line)

            file.writelines(lines)

        log.info("Theme installed successfully.")
        return "Firefox theme installed. Restart Firefox to see changes."


    def uninstall_theme(self, profile_id):
        # Delete Chrome folder
        chrome_path = os.path.join(self.app_path, profile_id, "chrome")
        shutil.rmtree(chrome_path)

        # Set all user_prefs to false
        user_js = os.path.join(self.app_path, profile_id, "user.js")
        try:
            with open(file=user_js, mode="r") as file:
                lines = file.readlines()
        except FileNotFoundError:
            pass

        with open(file=user_js, mode="w") as file:
            # TODO Cleaner way to do this? A basic for each doesn't let you replace the item in the list
            for i in range(len(lines)):
                if "gnomeTheme" in lines[i]:
                    lines[i] = lines[i].replace("true", "false")

            file.writelines(lines)

        log.info("Theme uninstalled successfully.")
        return "Firefox theme uninstalled. Restart Firefox to see changes."


    def check_for_updates(self):
        """Check theme github for new releases


        Returns:
            None = No new release to update to
            Int = Next release version to update to
        """

        DL_CACHE = paths.DOWNLOAD_DIR
        check_url = self.theme_url
        # TODO add checks to ensure this doesn't exceed GitHub API limit and add error logs
        # FIXME Thunderbird has no releases. Must clone git
        try:
            latest_release = requests.get(("meme")).json()[0]
        except json.JSONDecodeError as err:
            log.error(f"Update json parsing failed: {err}")
            return False
        except requests.RequestException as err:
            log.error(f"Update request failed: {err}")
            return False

        self.update_version = int(latest_release["tag_name"].lstrip("v"))

        if self.update_version > self.installed_version:
            download_release(
                tarball_url=latest_release["tarball_url"],
                version=self.update_version
            )
        else:
            log.info("No update available.")


    # TODO how to make download asynchronous? Is that even worthwhile?
    def download_release(self, tarball_url, version):
        log.info(f"Update available ({self.installed_version} → {self.update_version}). Downloading now...")
        response = requests.get(tarball_url) # ASYNC use stream flag
        if response.status_code != 200:
            log.error(f"Github download request gave bad response [{response.status_code}]")

        p = os.path.join(DL_CACHE, f"{app}-{version}.tar.gz")
        with open(file=p, mode="wb") as file:
            file.write(response.content)

        log.info("Github download SUCCESS!")


    def find_profiles(self, moz_path):
        """Reads the app configuration files to adds all of them in a list.

        ARGS:
        moz_path : The path to where the app stores its profiles and the profiles.ini files

        RETURN:
        A list of dicts with all profiles. Each dict includes the full ID of the profile, and a display name to present in the UI without the randomized prefix string.
        The first in the list is always the user's selected default profile.

        """
        install_file = os.path.join(moz_path, "installs.ini")
        profiles_file = os.path.join(moz_path, "profiles.ini")

        cfg = ConfigParser()
        defaults = []
        profiles = []

        try:
            # Preferred
            if len(cfg.read(install_file)) == 0:
                raise FileNotFoundError(install_file)

            # TODO Test that this works with multiple default profiles
            for each in cfg.sections():
                default_profile = cfg[each]["Default"]
                defaults.append(default_profile)
                profiles.append({"id" : default_profile,
                                "name" : default_profile.partition(".")[2] + " (Preferred)"})
                log.debug(f"User's default profile is {default_profile}")

            # All
            if len(cfg.read(profiles_file)) == 0:
                raise FileNotFoundError(profiles_file)

            for each in cfg.sections():
                try:
                    s = cfg[each]["path"]
                    if s not in defaults:
                        profiles.append({"id" : s,
                                        "name" : s.partition(".")[2]})
                except KeyError:
                    pass
        except FileNotFoundError as err:
            log.error(f"Reading INI failed: {err}")
            return

        # NOTE: The user's preferred profile must always be the first option in the list
        self.profiles = profiles
        for each in self.profiles:
            self.profile_list.append(each["name"])
