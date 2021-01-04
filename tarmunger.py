#!/usr/bin/env python3

from time import time
import tarfile
#import gzip
import os
import pickle
from subprocess import Popen, PIPE

import sys
import zipfile

from loguru import logger
import click
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import checkboxlist_dialog, radiolist_dialog, message_dialog, yes_no_dialog


def pickle_open(filename):
    """ looks for a pickle file and uses it, or returns false if can't find it """
    picklefile = f"{filename}.pickle"
    if not os.path.exists(picklefile):
        return (False, False)
    with open(picklefile, 'rb') as picklefile_handle:
        filedata = pickle.load(picklefile_handle)
    return ("pickle", filedata)

def open_archive(filename: str):
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

class AlltheData():
    def __init__(self ,filename):
        """ loads the file, starts working on some things """
        self.filename = filename
        self.archive_written = False
        if not os.path.exists(self.filename):
            logger.error(f"Unable to find file {self.filename}, quitting")
            sys.exit(1)
        logger.info(f"Using file: {self.filename}, trying to open it...")
        # for debugging/testing, use a pickled representation of the zipinfo object to save parsing the file over and over
        self.filetype, self.archivedata = pickle_open(self.filename)
        if not self.archivedata:
            self.filetype, self.archivedata = open_archive(self.filename)
            # TODO: store pickled data
            #with open(f"{self.filename}.pickle", 'wb') as pickle_handle:
            #    pickle.dump(self.archivedata, pickle_handle)
            #    logger.info(f"Wrote pickle data to {self.filename}.pickle")
        logger.debug("Successfully loaded archive.")
        
        self.get_filedata()
        self.regex_filters = []
        self.file_filters = []
        
    def get_filedata(self):
        """ generates the dict of filedata from the archive file """
        logger.debug("Generating filedata")
        self.filedata = {}
        if self.filetype == 'tar':
            logger.debug("getting a list of files...")
            files = self.archivedata.getmembers()
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

    def write_archive(self):
        """ writes out the stripped archive """
        self.archive_written = True
        if self.filetype == 'tar':
            destination_file = self.filename.replace(".tar.gz", '-stripped.tar.gz')
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
            logger.warning(f"I'm going to run this:")
            logger.warning(string_command)
            prompt('Hit enter to continue')
            start_time = time()
            logger.info("Running tar command...")
            process = Popen(archive_command, stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()
            logger.info("Done!")
            total_time = time()-start_time
            logger.info(f"It took: {total_time} seconds")
            
            if stderr:
                logger.error(stderr)
            if stdout:
                logger.info(stdout)
            prompt('Task completed...Hit enter to continue')
            
        else:
            raise NotImplementedError("Uh, not done yet!")

    def prompt_write_archive(self):
        """ prompts to write the archive file """
        result = yes_no_dialog(
            title='Action confirmation',
            text='Do you want to write out the stripped file?').run()
        if result:
            self.write_archive()

def main_menu(data_object: AlltheData):
    """ prompts for the main menu """
    result = radiolist_dialog(
        title="TARMunger",
        text="What do you want to do?",
        cancel_text="Quit",
        values=[
            ("top50", "Select from the Top50"),
            ("show_files", "Show the list of files selected"),
            ("regex_filter", "Add a regex filter"),
            ("show_regexes", "Show the regex filters"),
            ("write_file", "Write archive"),
            ("reload_archive", "Reload archive"),
        ]
    ).run()
    return result

def human_file_size(number: int):
    """ returns a string value of a human-readable filesize """
    if number < 1024:
        return number
    elif number <= pow(1024, 2):
        return f"{round(number/1024,2)}K"
    elif number <= pow(1024,3):
        return f"{round(number/pow(1024,2),2)}M"
    elif number <= pow(1024,4):
        return f"{round(number/pow(1024,3),2)}G"
    else:
        return number

@click.command()
@click.argument('filename')
def main(filename):
    """ main loop """
    allthedata = AlltheData(filename)
    while True:
        menu_selection = main_menu(allthedata)
        if menu_selection == "top50":
            top50 = allthedata.prompt_top50()
        elif menu_selection == "show_files":
            #top50 = allthedata.prompt_top50()
            allthedata.show_file_filters()
        elif menu_selection == 'write_file':
            result = allthedata.prompt_write_archive()
        elif not menu_selection or menu_selection == "quit":
            if not allthedata.archive_written:
                allthedata.prompt_write_archive()
            break


if __name__ == '__main__':
    main()