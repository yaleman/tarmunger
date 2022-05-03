""" Mangling tarfiles since 20something """
from pathlib import Path
from time import time
import tarfile
import os
import os.path
import pickle
import shutil
import subprocess
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import sys
import zipfile

from loguru import logger
import click
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import checkboxlist_dialog, radiolist_dialog, message_dialog, yes_no_dialog

MIN_STRING_LENGTH = 10


ACCEPTED_EXTENSIONS = [
    '.tar.gz',
    '.tar.bz2',
    '.tar',
]

def pickle_open(filename: Path) -> Any:
    """ looks for a pickle file and uses it, or returns false if can't find it """
    picklefile = f"{filename}.pickle"
    if not os.path.exists(picklefile):
        return (False, False)
    with open(picklefile, 'rb') as picklefile_handle:
        filedata = pickle.load(picklefile_handle)
    return ("pickle", filedata)


class NeedsReload(Exception):
    """ tell the menu to reload the file """


class AlltheData():
    """ Mangling tarfiles since 20xx """
    def __init__(self, filepath: Path):
        """ loads the file, starts working on some things """

        self.menu_items = {
            'open_archive' : self.open_archive_from_dir,
            'prompt_top50' : self.prompt_top50,
            'move_stripped_over_original' : self.move_stripped_over_original,
            'show_file_filters' : self.show_file_filters,
            'write_file' : self.write_archive,
        }

        self.filepath = filepath
        self.archive_written = False

        if not filepath.exists():
            logger.error(f"Unable to find file {self.filepath}, quitting")
            sys.exit(1)
        logger.info(f"Using file: {self.filepath}, trying to open it...")

        if filepath.is_dir():
            self.open_archive_from_dir(filepath)
        else:
            self.filetype, self.archivedata = self.load_archive(self.filepath)

        logger.debug("Successfully loaded archive.")

        self.get_filedata()
        #self.regex_filters : List[str] = []
        self.file_filters: List[str] = []

    @classmethod
    def load_archive(cls, filename: Path) -> Tuple[str,Union[tarfile.TarFile, zipfile.ZipFile]]:
        """ handles the various file types """
        if filename.name.endswith('.tar.gz') or filename.name.endswith('.tar.bz2') or filename.name.endswith('.tar'):
            try:
                return ('tar', tarfile.open(filename)) # pylint: disable=consider-using-with
            except tarfile.TarError as error_message:
                logger.error(f"tarfile.TarError: {error_message}")
                sys.exit(1)
        else:
            try:
                filedata = zipfile.ZipFile(filename) # pylint: disable=consider-using-with
            except zipfile.BadZipFile as error_message:
                logger.error(f"zipfile.BadZipFile raised: {error_message}")
                sys.exit(1)
            return ("zipfile", filedata)

    def get_filedata(self) -> Dict[str, int]:
        """ generates the dict of filedata from the archive file """
        logger.debug("Generating filedata")
        self.filedata = {}
        if isinstance(self.archivedata, tarfile.TarFile):
            logger.debug("getting a list of files...")
            try:
                files = self.archivedata.getmembers()
            except Exception as error_message: # pylint: disable=broad-except
                logger.error(f"error raised getting file contents: {error_message} - {type(error_message)}")
                sys.exit(1)
            logger.debug("done getting a list of files...")
            for fileinfo in files:
                if fileinfo.isfile():
                    #print(fileinfo.name, fileinfo.size)
                    self.filedata[fileinfo.name] = fileinfo.size
        else:
            logger.error("currently haven't done anything but tar files... oops?")
            raise NotImplementedError("currently haven't done anything but tar files... oops?")
        logger.debug("Done generating filedata")
        return self.filedata

    def sorted_files(self) -> Generator[Tuple[int, Any], None, None]:
        """ greturns a sorted list of files """
        for file in sorted(self.filedata, key=self.filedata.__getitem__, reverse=True):
            yield (self.filedata[file], file)

    def get_top50(self)-> Generator[Tuple[int, Any], None, None]:
        """ returns a list of the top 50 filenames by size """
        for file in sorted(self.filedata, key=self.filedata.__getitem__, reverse=True)[:50]:
            yield (self.filedata[file], file)

    def prompt_top50(self) -> List[str]:
        """ prompts with a list of the top 50 files by size so the user can select to strip them """
        dialogue_top50 = []
        for filesize, filename in self.get_top50():
            dialogue_top50.append((filename, f"{human_file_size(filesize)} - {filename}"))

        #dialogue_top50 = [ (filename, f"{filesize}\\t{filename}") for filesize, filename in allthedata.get_top50() ]
        results = checkboxlist_dialog(
            title="Select some files to strip",
            text="Here are the top 50 files",
            values = dialogue_top50,
        ).run()
        print(results)
        if results:
            for file in results:
                if file not in self.file_filters:
                    self.file_filters.append(file)
        # if you're changing the filter list, prompt again for writeout
        self.archive_written = False
        return results

    def show_file_filters(self) -> None:
        """ shows the user a list of the files selected """
        if not self.file_filters:
            message_dialog(
                title='No files selected!',
                text='Please return to the main menu\nAnd select some files.',
            ).run()
        else:
            for file in self.file_filters:
                print(file)
            prompt('Please press enter to continue')

    def get_stripped_filename(self) -> Optional[Path]:
        """ returns a filepath with -stripped in the end """
        if self.filepath.name.endswith('.tar.gz'):
            #new_path = self.filepath.parent
            new_filename = self.filepath.name.replace(".tar.gz", '-stripped.tar.gz')
            result = self.filepath.with_name(new_filename)
        elif self.filepath.name.endswith('.tar'):
            #new_path = self.filepath.parent
            new_filename = self.filepath.name.replace(".tar", '-stripped.tar')
            result = self.filepath.with_name(new_filename)
        else:
            logger.debug("Not a .tar.gz file!")
            return None
        logger.debug(result)
        return result


    def prompt_write_archive(self) -> None:
        """ prompts to write the archive file """
        result = yes_no_dialog(
            title='Action confirmation',
            text='Do you want to write the archive file?').run()
        if result:
            self.write_archive()

    def write_archive(self) -> bool:
        """ writes out the stripped archive """
        self.archive_written = True
        if self.filetype == 'tar':
            destination_file = self.get_stripped_filename()
            if destination_file is None:
                raise NotImplementedError("Uh... can't deal with a file that doesn't end with .tar or .tar.gz?")
            if destination_file.exists():
                result = yes_no_dialog(
                    title="Action confirmation",
                    text=f"File exists: {destination_file}\nDo you want to overwrite it?").run()
                if not result:
                    return False
            tar_command = shutil.which("tar")
            if tar_command is None:
                logger.error("Couldn't find tar in your path, bailing")
                sys.exit(1)
            archive_command = [ tar_command,
                                '--options', 'gzip:compression-level=9',
                                '-czf', str(destination_file),

        # --exclude='*wp-content/uploads/2*' \
        # --exclude '*backup*.tar.gz' \
        # --exclude '*public_html/video/*' \
        # --exclude '*.wpress'
            ]
            for filename in self.file_filters:
                archive_command += [ '--exclude', f"'{filename}'", ]
            archive_command.append( f"@{self.filepath}")

            string_command = " ".join(archive_command)

            logger.warning("I'm running this:\n{}",string_command)

            start_time = time()
            old_file_size = self.get_file_size()
            logger.info("Running tar command...")
            subprocess.run(archive_command, check=True)
            new_file_size = human_file_size(os.path.getsize(destination_file))
            total_time = round(time()-start_time, 2)
            logger.info("")
            message_dialog(
                title='Archive munging complete',
                text=f"It took: {total_time} seconds.\nOld file size: {old_file_size}\nNew file size: {new_file_size}").run()
        else:
            raise NotImplementedError("Uh, not done yet!")
        self.move_stripped_over_original()
        return True

    def move_stripped_over_original(self) -> bool:
        """ moves the *-stripped* file over the original """
        stripped_filename = self.get_stripped_filename()
        if stripped_filename is None:
            raise ValueError("Uh.. can't deal with this")
        if stripped_filename.exists():
            stripped_size = human_file_size(stripped_filename.stat().st_size)
            original_size = human_file_size(self.filepath.stat().st_size)

            result = yes_no_dialog(
                title='Action confirmation',
                text=f"""Do you want to move the stripped file over the original?


Stripped: ({stripped_size}) {stripped_filename}
Original: ({original_size}) {self.filepath} """).run()
            if not result:
                return False
            logger.debug(f"Moving {stripped_filename} to {self.filepath}")
            stripped_filename.rename(self.filepath)
            raise NeedsReload(self.filepath)
        return False

    def get_file_size(self) -> str:
        """ return a human interpretable file size of the current file """
        return human_file_size(self.filepath.stat().st_size)

    def open_archive_from_dir(self, filepath: Path) -> None:
        """ opens another archive in the same dir that the original one was in """
        self.filepath = filepath
        dirname = filepath.parent
        if not dirname.exists():
            raise ValueError(f"Path {dirname} has gone missing while you were running this program.")
        filenames = []
        for filename in sorted(list(dirname.iterdir())):
            fullpath = os.path.join(dirname, filename)
            if os.path.exists(fullpath) and os.path.isfile(fullpath):
                display_size = human_file_size(os.path.getsize(fullpath))
                display_name = f"{display_size} {filename}"
                filenames.append((fullpath, display_name))

        result = radiolist_dialog(
            title="Select a new archive to open...",
            #text="What do you want to do?",
            cancel_text="Cancel",
            values=filenames,
        ).run()
        if not result:
            logger.debug("No option selected")
            return None
        logger.debug(f"opening {result}")
        raise NeedsReload(Path(result).expanduser().resolve())

def main_menu(data_object: AlltheData) -> str:
    """ prompts for the main menu """
    result = radiolist_dialog(
        title="TARMunger",
        text=f"What do you want to do?\n\nCurrent file: {data_object.filepath}\nSize: {data_object.get_file_size()}",
        cancel_text="Quit",
        values=[

            ("prompt_top50", "Select from the Top 50 files (by size)"),
            ("show_file_filters", "Show the list of files selected for removal"),
            ("regex_filter", "Add a regex filter"),
            ("show_regexes", "Show the regex filters"),
            ("write_file", "Write archive"),
            ("move_stripped_over_original", "Move stripped archive over original and reload"),
            ("open_archive", "Open another archive"),
        ]
    ).run()
    return result

def human_file_size(number: int) -> str:
    """ returns a string value of a human-readable filesize """
    if number < 1024:
        return f"{str(number).rjust(MIN_STRING_LENGTH)} bytes"
    if number <= pow(1024, 2):
        return f"{round(number/1024,2)}K".rjust(MIN_STRING_LENGTH)
    if number <= pow(1024,3):
        return f"{round(number/pow(1024,2),2)}M".rjust(MIN_STRING_LENGTH)
    if number <= pow(1024,4):
        return f"{round(number/pow(1024,3),2)}G".rjust(MIN_STRING_LENGTH)
    return str(number).rjust(MIN_STRING_LENGTH)


@click.command()
@click.argument('filename')
def cli(filename: Optional[str]=None) -> None:
    """ A terrible utility for mangling tarfiles  """
    if filename is None:
        logger.error("please specify a filename")
        return
    filepath = Path(filename).expanduser().resolve()

    if filepath.is_dir():
        data = AlltheData(filepath)
    else:
        data = AlltheData(filepath)
    while True:
        menu_selection = main_menu(data)
        if not menu_selection or menu_selection == "quit":
            if not data.archive_written and data.file_filters:# + data.regex_filters:
                data.prompt_write_archive()
            break
        if menu_selection in data.menu_items:
            try:
                data.menu_items[menu_selection]() # type: ignore
            except NeedsReload as reload_data:
                data = AlltheData(reload_data.args[0])
