# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Splunk Uploader class."""
from pathlib import Path

from tqdm.notebook import tqdm
import pandas as pd
from pandas.io.parsers import ParserError

from .uploader_base import UploaderBase
from ..._version import VERSION
from ..drivers.splunk_driver import SplunkDriver
from ...common.exceptions import MsticpyConnectionError, MsticpyUserError

__version__ = VERSION
__author__ = "Pete Bryan"


class SplunkUploader(UploaderBase):
    """Uploader class for Splunk."""

    def __init__(self, username: str, host: str, password: str, **kwargs):
        """Initialize a Splunk Uploader instance."""
        super().__init__()
        self._kwargs = kwargs
        self.workspace = host
        self.workspace_secret = password
        self.user = username
        self.driver = SplunkDriver()
        self.port = kwargs.get("port", 8089)
        self._debug = kwargs.get("debug", False)
        self._connect = kwargs.get("connect", True)
        self.connected = False
        if self._connect:
            self.connect()

    def connect(self):
        """Connect to Splunk host."""
        self.driver.connect(
            host=self.workspace,
            username=self.user,
            password=self.workspace_secret,
            port=self.port,
        )
        self.connected = True

    def _post_data(
        self,
        data: pd.DataFrame,
        index_name: str,
        table_name: str,
        host: str = None,
        **kwargs,
    ):
        """
        Write data to the Splunk instance connected to.

        Parameters
        ----------
        data : pd.DataFrame
            Data to upload.
        index_name : str
            Name of the Splunk Index to add data to, if it doesn't exist it will be created.
        table_name : str
            The souretype in Splunk data will be uploaded to.
        host : str, optional
            The hostname associated with the uploaded data, by default "Upload".

        """
        if not self.connected:
            raise MsticpyConnectionError(
                "Splunk host not connected, please call .connect before proceding.",
                title="Splunk host not connected",
            )
        if not host:
            host = "Upload"
        create_idx = kwargs.get("create_index", "False")
        index = self._load_index(index_name, create_idx)
        progress = tqdm(total=len(data.index), desc="Rows", position=0)
        for row in data.iterrows():
            data = row[1].to_csv()
            try:
                data.encode(encoding="latin-1")
            except UnicodeEncodeError:
                data = data.encode(encoding="utf-8")
            index.submit(data, sourcetype=table_name, host=host)
            progress.update(1)
        progress.close()
        if self._debug is True:
            print("Upload complete")

    def upload_df(  # pylint: disable=arguments-differ
        self, data: pd.DataFrame, table_name: str, index_name: str, **kwargs,
    ):
        """
        Upload a Pandas DataFrame to Splunk.

        Parameters
        ----------
        data : pd.DataFrame
            Data to upload.
        table_name : str
            The souretype in Splunk data will be uploaded to.
        index_name : str
            Name of the Splunk Index to add data to, if it doesn't exist it will be created.
        host : str, optional
            Host name to upload data with, default will be 'Upload'

        """
        host = kwargs.get("host", None)
        create_idx = kwargs.get("create_index", "False")
        if not isinstance(data, pd.DataFrame):
            raise MsticpyUserError(
                "Data must be in Pandas DataFrame format.",
                title="incorrect data format",
            )
        self._post_data(
            data=data,
            table_name=table_name,
            index_name=index_name,
            create_index=create_idx,
            host=host,
        )

    def upload_file(  # pylint: disable=arguments-differ
        self,
        file_path: str,
        index_name: str,
        table_name: str = None,
        delim: str = ",",
        **kwargs,
    ):
        """
        Upload a seperated value file to Splunk.

        Parameters
        ----------
        file_path : str
            Path to the file to upload.
        index_name : str
            Name of the Splunk Index to add data to, if it doesn't exist it will be created.
        table_name : str, optional
            The souretype in Splunk data will be uploaded to, if not set the file name will be used.
        delim : str, optional
            Seperator value in file, by default ","
        host : str, optional
            Host name to upload data with, default will be 'Upload'

        """
        host = kwargs.get("host", None)
        create_idx = kwargs.get("create_index", "False")
        path = Path(file_path)
        try:
            data = pd.read_csv(path, delimiter=delim)
        except (ParserError, UnicodeDecodeError):
            raise MsticpyUserError(
                "The file specified is not a seperated value file.",
                "Incorrect file type.",
            )

        if not table_name:
            table_name = str(path).split("\\")[-1].split(".")[0]
        self._post_data(
            data=data,
            table_name=table_name,
            index_name=index_name,
            host=host,
            create_index=create_idx,
        )

    def upload_folder(  # pylint: disable=arguments-differ
        self,
        folder_path: str,
        index_name: str,
        table_name: str = None,
        delim: str = ",",
        **kwargs,
    ):
        """
        Upload all files in a folder to Splunk.

        Parameters
        ----------
        folder_path : str
            Path to folder to upload.
        index_name : str
            Name of the Splunk Index to add data to, if it doesn't exist it will be created.
        table_name : str, optional
            The souretype in Splunk data will be uploaded to, if not set the file name will be used.
        delim : str, optional
            Seperator value in files, by default ","
        host : str, optional
            Host name to upload data with, default will be 'Upload'

        """
        host = kwargs.get("host", None)
        create_idx = kwargs.get("create_index", "False")
        if delim != ",":
            ext = "*"
        else:
            ext = "*.csv"
        t_name = bool(table_name)
        input_files = Path(folder_path).glob(ext)
        input_files = [
            path for path in input_files  # pylint: disable=unnecessary-comprehension
        ]
        f_progress = tqdm(total=len(input_files), desc="Files", position=0)
        for path in input_files:
            try:
                data = pd.read_csv(path, delimiter=delim)
            except (ParserError, UnicodeDecodeError):
                raise MsticpyUserError(
                    "The file specified is not a seperated value file.",
                    title="Incorrect file type.",
                )
            if t_name is False:
                table_name = str(path).split("\\")[-1].split(".")[0]
            self._post_data(
                data=data,
                table_name=table_name,
                index_name=index_name,
                host=host,
                create_index=create_idx,
            )
            f_progress.update(1)
            if self._debug is True:
                print(f"{str(path)} uploaded to {table_name}")
        f_progress.close()

    def _check_index(self, index_name: str):
        """Check if index exists in Splunk host."""
        service_list = [item.name for item in self.driver.service.indexes]
        if index_name in service_list:
            return True
        return False

    def _load_index(self, index_name, create: bool = True):
        """Load specified Index or create if it doesn't exist."""
        if self._check_index(index_name):
            return self.driver.service.indexes[index_name]
        if not self._check_index(index_name) and create:
            return self.driver.service.indexes.create(index_name)

        raise MsticpyConnectionError("Index not present in Splunk host.")
