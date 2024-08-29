# backend.py
#
# Copyright 2024 Qwery
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import shutil
import requests

from enum import Enum
from os.path import join, exists
from typing import Optional, Callable

from gi.repository import Gio

from addwater import info
from addwater.components.online import OnlineManager
from addwater.components.install import InstallManager
from addwater.utils.paths import DOWNLOAD_DIR
from addwater.utils.tests.mocks import mock_online

log = logging.getLogger(__name__)

# FIXME if the theme files get lost, there is no way for the app to ever install until another update or the user resets the app
# It should attempt to re-download it every time but stop early if the files already exist

class AddWaterBackend():
    """The interface by which this app can complete important tasks like installing, updating, etc.
    Relies on injected components that manage those actual processes. This class
    just connects and abstracts those details into easy public methods that can be
    used anywhere.

    This class can live without a GUI frontend to allow for background updating.

    Args:
        app_details = object that stores and manages the state of important app details
                        such as the app's name, available profiles, data paths, and what
                        theme options are available. Will be passed into other managers
                        for convenience.
        install_manager = object that manages processes related to installing,
                            uninstalling, and setting user's theme preferences in
                            configuration files.
        online_manager = object that makes internet requests, processes http responses,
                            handles network errors, downloads theme releases, and preps
                            those releases to be installed.
    """

    app_details: callable
    online_manager: callable
    install_manager: callable

    def __init__(self, app_details, install_manager, online_manager):
        log.info("Backend is alive!")

        self.app_details = app_details
        self.install_manager = install_manager
        self.online_manager = online_manager



    """PUBLIC METHODS

    For these methods, it's often impossible to avoid modifying object states. So it's
    important for these methods to be readable and concise, and modify as little
    as possible.
    """

    # TODO Should the install manager make the decision on quick or full install?
    """Install actions"""
    def full_install(self, profile_id: str, color_palette: str="adwaita",) -> Enum:
        version = self.get_update_version()

        # TODO remove this GioSettings and add it to app_details or something
        app_name = self.app_details.get_name().title()
        gset = Gio.Settings(schema_id=f'dev.qwery.AddWater.{app_name}')

        install_status = self.install_manager.full_install(
            app_details=self.app_details,
            profile_id=profile_id,
            color_palette=color_palette,
            version=version,
            gset_reader=gset
        )
        if install_status.SUCCESS:
            self.app_details.set_installed_version(version)
        return install_status


    def quick_install(self, profile_id: str, color_palette: str="adwaita",) -> Enum:
        """Installs theme files but doesn't change any user preferences. This is
        useful for updating in the background."""
        version = self.get_update_version()

        install_status = self.install_manager.quick_install(
            app_details=self.app_details,
            profile_id=profile_id,
            color_palette=color_palette,
            version=version,
        )
        if install_status.SUCCESS:
            self.app_details.set_installed_version(version)
        return install_status


    def remove_theme(self, profile_id) -> Enum:
        app_path = self.app_details.get_data_path()
        folder_name = self.app_details.final_theme_name
        profile_path = join(app_path, profile_id)

        install_status = self.install_manager.uninstall(profile_path, folder_name)
        return install_status


    """Getters"""
    def get_app_options(self) -> list[dict[str,any]]:
        return self.app_details.get_options()

    def get_colors_list(self) -> list:
        return self.app_details.get_color_palettes()

    def get_update_version(self,):
        return self.online_manager.get_update_version()


    def get_updates(self) -> Enum:
        app_name = self.app_details.get_name()
        installed_version = self.app_details.get_installed_version()

        update_status = self.online_manager.get_updates_online(
            app_details=self.app_details
        )
        # TODO sloppy to do this assignment here. would prefer a cleaner, natural solution
        new_version = self.get_update_version()
        self.app_details.set_update_version(new_version)

        return update_status

    def get_profile_list(self):
        return self.app_details.get_profiles()


    """Setters"""
    def set_data_path(self, new_path: str) -> None:
        try:
            self.app_details.set_data_path(new_path)
        except AppDetailsException as err:
            raise InterfaceMisuseError(err)


    """Dangerous"""
    def reset_app(self,):
        app_name = self.app_details.get_name()
        log.warning(f'{app_name} is now being reset...')
        # self._uninstall_all_profiles()
        self.app_details._reset_settings()
        log.info(f'done. {app_name} has been reset to default state')



    """PRIVATE METHODS

    All private methods should ideally be static or at least not modify the object state;
    this helps avoid unexpected behavior and aid in testing these important methods.
    """

    def _uninstall_all_profiles(self):
        log.warning(f"uninstalling theme from all known profiles...")
        profiles = self.app_details.get_profiles()
        for each in profiles:
            profile_id = each["id"]
            self.remove_theme(profile_id)

        log.info('done. theme removed from all profiles')




# TODO should I inherit from Exception or is an Error object?
class InterfaceMisuseError(Exception):
    pass

class FatalInterfaceError(Exception):
    pass




class BackendFactory():

    @staticmethod
    def new_from_appdetails(app_details):

        install_method = app_details.installer
        install_manager = InstallManager(
            installer=install_method,
        )

        # TODO clean up mock selection and meson
        if info.PROFILE == 'developer':
            online_manager = mock_online.MockOnlineManager(2)
        elif info.PROFILE == 'user':
            theme_url = app_details.get_info_url()
            online_manager = OnlineManager(
                theme_url=theme_url,
            )

        firefox_backend = AddWaterBackend(
            app_details=app_details,
            install_manager=install_manager,
            online_manager=online_manager,
        )
        return firefox_backend


