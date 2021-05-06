# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""File Browser class."""
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

import ipywidgets as widgets

from .._version import VERSION
from .comp_edit import CompEditDisplayMixin

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=too-many-instance-attributes
class FileBrowser(CompEditDisplayMixin):
    """File system browser control."""

    PARENT = ".."

    def __init__(self, path: str = ".", select_cb: Callable[[str], Any] = None):
        """
        Initialize the class for path and with optional callback.

        Parameters
        ----------
        path : str, optional
            Path to open at, by default "."
        select_cb : Callable[[str], Any], optional
            Callback function, by default None. This is executed
            when the user hits the "Select File" button. The function
            is passed the path of the selected file.

        """
        self.current_folder = Path(path).resolve()
        self.file: Optional[str] = None
        self.action = select_cb

        file_layout = widgets.Layout(height="200px", width="45%")
        self.select_file = widgets.Select(description="Files", layout=file_layout)
        folder_layout = widgets.Layout(height="150px", width="99%")
        self.select_folder = widgets.Select(description="Folders", layout=folder_layout)

        self.btn_open = widgets.Button(description="Select File")
        self.btn_f_nav = widgets.Button(description="Open folder")
        self.txt_path = widgets.Text(
            description="Path",
            value=str(self.current_folder),
            layout=widgets.Layout(width="75%"),
        )

        style_indent = {"description_width": "150px"}
        self.select_search = widgets.Select(
            description="Results",
            layout=self.no_border_layout("75%"),
            style=style_indent,
        )
        self.select_search.observe(self._select_search_file, names="value")
        self.lbl_search = widgets.Label(value="Search for file in current path")

        self.txt_search = widgets.Text(
            description="Search pattern",
            layout=widgets.Layout(width="50%"),
            style=style_indent,
            continuous_update=False,
        )
        self.txt_search.observe(self._search, "value")
        self.btn_search = widgets.Button(description="Search")
        self.btn_search.on_click(self._search)
        hb_search = widgets.HBox([self.txt_search, self.btn_search])
        vb_search = widgets.VBox([self.lbl_search, hb_search, self.select_search])
        self.accd_search = widgets.Accordion(children=[vb_search])
        self.accd_search.set_title(0, "Search")
        self.accd_search.selected_index = None

        self.txt_path.continuous_update = False
        self.txt_path.observe(self._enter_folder, "value")
        self.btn_open.on_click(self._return_file)
        self.btn_f_nav.on_click(self._open_folder)
        self.select_file.observe(self._select_file, names="value")

        self._open_folder(tgt_folder=self.current_folder)

        vb_folder_nav = widgets.VBox(
            [self.select_folder, self.btn_f_nav], layout=widgets.Layout(width="30%")
        )
        hb_files_folders = widgets.HBox(
            [vb_folder_nav, self.select_file], layout=self.border_layout("98%")
        )

        hb_search = widgets.HBox([self.txt_search, self.btn_search])
        vb_search = widgets.VBox([self.lbl_search, hb_search, self.select_search])

        self.layout = widgets.VBox(
            [self.txt_path, hb_files_folders, self.accd_search, self.btn_open],
            layout=self.border_layout("98%"),
        )

    def _enter_folder(self, event):
        """Handle event from folder text box when pressing ENTER."""
        del event
        if Path(self.txt_path.value).is_dir():
            self._open_folder(tgt_folder=self.txt_path.value)

    def _open_folder(self, btn=None, tgt_folder=None):
        """Handle event from Open Folder button - change directory."""
        del btn
        if not tgt_folder:
            tgt_folder = self.select_folder.value
        if tgt_folder == self.PARENT:
            tgt_folder = self.current_folder.parent
        if tgt_folder:
            self.current_folder = (
                Path(self.current_folder).joinpath(tgt_folder).resolve()
            )
            self.txt_path.value = str(self.current_folder)
            folders, files = self.read_folder(self.current_folder)
            self.select_folder.options = self.get_folder_list(folders)
            self.select_file.options = files

    def _select_file(self, change):
        """Handle event from select file button."""
        selected_file = change.get("new")
        self.file = str(Path(self.current_folder).joinpath(selected_file).resolve())

    def _select_search_file(self, change):
        """Handle event for selection of file from search UI."""
        self.file = change.get("new")

    def _return_file(self, btn):
        """Execute callback on selected file if one is defined."""
        del btn
        if self.action:
            self.action(self.file)

    @staticmethod
    def read_folder(folder: str) -> Tuple[List[str], List[str]]:
        """
        Return folder contents.

        Parameters
        ----------
        folder : str
            Folder path.

        Returns
        -------
        Tuple[List[str], List[str]]
            List of folders and files in the folder.

        """
        contents = list(Path(folder).glob("*"))
        files = [file.parts[-1] for file in contents if file.is_file()]
        folders = [fld.parts[-1] for fld in contents if fld.is_dir()]
        return folders, files

    def get_folder_list(self, folders: List[str]) -> List[str]:
        """Return sorted list of folders with '..' inserted if not root."""
        if self.current_folder != Path(self.current_folder.parts[0]):
            return [self.PARENT, *(sorted(folders))]
        return sorted(folders)

    def _search(self, btn):
        """Handle event for search button."""
        del btn
        if self.txt_search.value:
            found_files: Optional[List[Path]] = None
            while found_files is None:
                try:
                    found_files = list(self.current_folder.rglob(self.txt_search.value))
                except FileNotFoundError:
                    pass
            self.select_search.options = [
                str(file) for file in found_files if file.exists()
            ]
