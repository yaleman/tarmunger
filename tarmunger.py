#!/usr/bin/env python3

from time import time
import tarfile
#import gzip
import os
import os.path
import pickle
#from subprocess import Popen, PIPE
import subprocess

import sys
import zipfile

from loguru import logger
import click
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import checkboxlist_dialog, radiolist_dialog, message_dialog, yes_no_dialog

ACCEPTED_EXTENSIONS = [
    '.tar.gz',
    '.tar.bz2',
    '.tar',
]

def pickle_open(filename):
    """ looks for a pickle file and uses it, or returns false if can't find it """
    picklefile = f"{filename}.pickle"
    if not os.path.exists(picklefile):
        return (False, False)
    with open(picklefile, 'rb') as picklefile_handle:
        filedata = pickle.load(picklefile_handle)
    return ("pickle", filedata)



class AlltheData():


    def __init__(self, filename: str, dir: bool=False):
        """ loads the file, starts working on some things """
        self.MENU_ITEMS = {
            'open_archive' : self.open_archive_from_dir,
            'prompt_top50' : self.prompt_top50,
            'move_stripped_over_original' : self.move_stripped_over_original,
            'show_file_filters' : self.show_file_filters,
            'write_file' : self.write_archive,
        }

        self.filename = filename
        self.archive_written = False
        
        if not os.path.exists(self.filename):
            logger.error(f"Unable to find file {self.filename}, quitting")
            sys.exit(1)
        logger.info(f"Using file: {self.filename}, trying to open it...")

        if dir:
            self.open_archive_from_dir(filename)
        else:
            self.filetype, self.archivedata = self.load_archive(self.filename)
            
        logger.debug("Successfully loaded archive.")
        
        self.get_filedata()
        self.regex_filters = []
        self.file_filters = []
    
    def load_archive(self, filename: str):
        """ handles the various file types """
        if filename.endswith('.tar.gz') or filename.endswith('.tar.bz2') or filename.endswith('.tar'):
            try:
                tardata = tarfile.open(filename)
                return ('tar', tardata)
            except tarfile.TarError as error_message:
                logger.error(f"tarfile.TarError: {error_message}")
                sys.exit(1)
        else:
            try:
                filedata = zipfile.ZipFile(filename)
            except zipfile.BadZipFile as error_message:
                logger.error(f"zipfile.BadZipFile raised: {error_message}")
                sys.exit(1)
            return ("zipfile", filedata)

    def get_filedata(self):
        """ generates the dict of filedata from the archive file """
        logger.debug("Generating filedata")
        self.filedata = {}
        if self.filetype == 'tar':
            logger.debug("getting a list of files...")
            try:
                files = self.archivedata.getmembers()
            except Exception as error_message:
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

    def sorted_files(self):
        """ greturns a sorted list of files """
        for file in sorted(self.filedata, key=self.filedata.__getitem__, reverse=True):
            yield (self.filedata[file], file)

    def get_top50(self):
        """ returns a list of the top 50 filenames by size """
        for file in sorted(self.filedata, key=self.filedata.__getitem__, reverse=True)[:50]:
            yield (self.filedata[file], file)

    def prompt_top50(self):
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

    def show_file_filters(self):
        """ shows the user a list of the files selected """
        if not self.file_filters:
            message_dialog(
                title='No files selected!',
                text='Please return to the main menu\nAnd select some files.',
            ).run()
        else:
            for file in self.file_filters:
                print(file)

            text = prompt('Hit enter to continue')#, lexer=PygmentsLexer(HtmlLexer),style=our_style)
        return True

    def get_stripped_filename(self):
        """ returns a filename with -stripped in the end """
        if self.filename.endswith('.tar.gz'):
            return self.filename.replace(".tar.gz", '-stripped.tar.gz')

    def prompt_write_archive(self):
        """ prompts to write the archive file """
        result = yes_no_dialog(
            title='Action confirmation',
            text='Do you want to write the archive file?').run()
        if result:
            self.write_archive()


    def write_archive(self):
        """ writes out the stripped archive """
        self.archive_written = True
        if self.filetype == 'tar':
            destination_file = self.get_stripped_filename()
            if os.path.exists(destination_file):
                result = yes_no_dialog(
                    title="Action confirmation",
                    text=f"File exists: {destination_file}\nDo you want to overwrite it?").run()
                if not result:
                    return False
            archive_command = [ 'tar',
                                '--options', 'gzip:compression-level=9', 
                                '-czf', destination_file,
                                
        # --exclude='*wp-content/uploads/2*' \
        # --exclude '*backup*.tar.gz' \
        # --exclude '*public_html/video/*' \
        # --exclude '*.wpress' 
            ]
            for filename in self.file_filters:
                archive_command += [ '--exclude', f"'{filename}'", ]
            archive_command.append( f"@{self.filename}")
            
            string_command = " ".join(archive_command)
            
            logger.warning(f"I'm running this:")
            logger.warning(string_command)

            start_time = time()
            old_file_size = self.get_file_size()
            logger.info("Running tar command...")
            subprocess.run(" ".join(archive_command), shell=True)
            #logger.info("Done!")
            new_file_size = human_file_size(os.path.getsize(destination_file))
            total_time = round(time()-start_time, 2)
            logger.info(f"")
            message_dialog(
                title='Archive munging complete',
                text=f"It took: {total_time} seconds.\nOld file size: {old_file_size}\nNew file size: {new_file_size}").run()
        else:
            raise NotImplementedError("Uh, not done yet!")
        self.move_stripped_over_original()        

    def move_stripped_over_original(self):
        """ moves the *-stripped* file over the original """
        if os.path.exists(self.get_stripped_filename()):
            stripped_size = human_file_size(os.path.getsize(self.get_stripped_filename()))
            original_size = human_file_size(os.path.getsize(self.filename))

            result = yes_no_dialog(
                title='Action confirmation',
                text=f"""Do you want to move the stripped file over the original?
                
Stripped: ({stripped_size}) {self.get_stripped_filename()}
Original: ({original_size}) {self.filename} """).run()
            if not result:
                return False
            logger.debug(f"Moving {self.get_stripped_filename()} to {self.filename}")
            os.rename(self.get_stripped_filename(), self.filename)
            self.__init__(self.filename)
            return True
        return False

    def get_file_size(self):
        """ return a human interpretable file size of the current interst file """
        return human_file_size(os.path.getsize(self.filename))

    def open_archive_from_dir(self, filename: str):
        """ opens another archive in the same dir that the original one was in """
        self.filename = filename
        dirname = os.path.dirname(self.filename)
        if not dirname:
            return False
        else:
            if not os.path.exists(dirname):
                raise ValueError(f"Path {dirname} has gone missing while you were running this program.")
            filenames = []
            files = os.listdir(dirname)
            for filename in sorted(files):
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
                return False
            logger.debug(f"opening {result}")
            return self.__init__(result)

def main_menu(data_object: AlltheData):
    """ prompts for the main menu """
    result = radiolist_dialog(
        title="TARMunger",
        text=f"What do you want to do?\n\nCurrent file: {data_object.filename}\nSize: {data_object.get_file_size()}",
        cancel_text="Quit",
        values=[
            
            ("prompt_top50", "Select from the Top50"),
            ("show_file_filters", "Show the list of files selected"),
            ("regex_filter", "Add a regex filter"),
            ("show_regexes", "Show the regex filters"),
            ("write_file", "Write archive"),
            ("move_stripped_over_original", "Move stripped archive over original and reload"),
            ("open_archive", "Open another archive"),
        ]
    ).run()
    return result

def human_file_size(number: int):
    """ returns a string value of a human-readable filesize """
    MIN_STRING_LENGTH = 10
    if number < 1024:
        return str(number).rjust(MIN_STRING_LENGTH)
    elif number <= pow(1024, 2):
        return f"{round(number/1024,2)}K".rjust(MIN_STRING_LENGTH)
    elif number <= pow(1024,3):
        return f"{round(number/pow(1024,2),2)}M".rjust(MIN_STRING_LENGTH)
    elif number <= pow(1024,4):
        return f"{round(number/pow(1024,3),2)}G".rjust(MIN_STRING_LENGTH)
    else:
        return str(number).rjust(MIN_STRING_LENGTH)


@click.command()
@click.argument('filename')
def main(filename):
    """ main loop """
    if os.path.isdir(filename):
        allthedata = AlltheData(filename, dir=True)
    else:
        allthedata = AlltheData(filename)
    while True:
        menu_selection = main_menu(allthedata)
        if not menu_selection or menu_selection == "quit":
            if not allthedata.archive_written and allthedata.file_filters + allthedata.regex_filters:
                allthedata.prompt_write_archive()
            break
        if menu_selection in allthedata.MENU_ITEMS:
            allthedata.MENU_ITEMS[menu_selection]()



if __name__ == '__main__':
    main()

