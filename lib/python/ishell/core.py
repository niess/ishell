# -*- coding: utf-8 -*-
#
#  Copyright (C) 2017 Université Clermont Auvergne, CNRS/IN2P3, LPC
#  Author: Valentin NIESS (niess@in2p3.fr)
#
#  Irods in a nutSHELL (ISHELL).
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>

import cmd
import fnmatch
import getopt
import os
import readline
import subprocess
import sys

from irods.exception import (CATALOG_ALREADY_HAS_ITEM_BY_THAT_NAME,
                             CAT_NAME_EXISTS_AS_COLLECTION,
                             CollectionDoesNotExist, DataObjectDoesNotExist,
                             USER_FILE_DOES_NOT_EXIST)
from irods.session import iRODSSession
from irods.data_object import irods_basename
from irods.keywords import FORCE_FLAG_KW


# Redefine the delimiters according to file name syntax. This is required
# for autocompletion of file names.
readline.set_completer_delims(" \t\n")


class IShell(cmd.Cmd, object):
    """Shell like client for managing iRods data
    """

    cursor = None

    interactive = False

    session = None

    class _IShellError(Exception):
        pass

    def default(self, line):
        """Handle unknown commands
        """
        args = shlex.split(line)
        self.println("... unknown command `{:}`", args[0])

    def completedefault(self, text, line, begidx, endidx):
        dirname, _, content = self.get_content(text + "*")
        completion = content.keys()
        if dirname:
            dirname = dirname.replace("/", r"/")
            completion = [r"/".join((dirname, c)) for c in completion]
        return completion

    def get_content(self, pattern, data=True, collections=True, base=None):
        """Get items within the collection that match the pattern
        """
        if base is None:
            base = self.cursor

        try:
            dirname, basename = pattern.rsplit("/", 1)
        except ValueError:
            dirname = None
        else:
            path = self.get_path(dirname, base)
            try:
                base = self.session.collections.get(path)
            except CollectionDoesNotExist:
                return []
            pattern = basename

        content = {}
        if collections:
            for c in base.subcollections:
                if fnmatch.fnmatch(c.name, pattern):
                    content[c.name] = c
        if data:
            for d in base.data_objects:
                if fnmatch.fnmatch(d.name, pattern):
                    content[d.name] = d
        return dirname, base, content

    def get_path(self, path, base=None):
        if path.startswith("/"):
            return path
        else:
            if base is None:
                base = self.cursor
            path = os.path.join(base.path, path)
            return os.path.normpath(path)

    def parse_command(self, command, options, noargs=False):
        """Parse a command line for arguments and options
        """
        args = self._command[1:]
        try:
            opts, args = getopt.getopt(args, options)
        except getopt.GetoptError as e:
            self.println("... {:}: {:}", command, e.msg)
            raise self._IShellError()

        if (not noargs) and (not args):
            self.println("... {:}: missing operand", command)
            raise self._IShellError()
        return opts, args

    def parse_line(self, line):
        """Parse a line and strip commands
        """
        cmds, cmd, arg = [], [], []
        quote, commented = None, False
        for c in line:
            if commented:
                if c in "\r\n":
                    commented = False
            elif quote is None:
                if c in "#;\r\n":
                    if arg:
                        cmd.append("".join(arg))
                        arg = []
                    if cmd:
                        cmds.append(cmd)
                        cmd = []
                    if c == "#":
                        commented = True
                elif c in " \t":
                    if arg:
                        cmd.append("".join(arg))
                        arg = []
                elif c in "'\"":
                    quote = c
                else:
                    arg.append(c)
            else:
                if c == quote:
                    quote = None
                else:
                    arg.append(c)
        if arg:
            cmd.append("".join(arg))
        if cmd:
            cmds.append(cmd)
        return cmds

    def println(self, text, *opts):
        self.printfmt(text, *opts)
        print

    def printfmt(self, text, *opts):
        if opts:
            text = text.format(*opts)
        else:
            text = str(text)
        if self.interactive:
            text = self.prompt + text
        print text,

    def ask_for_confirmation(self, text, *args):
        self.printfmt(text, *args)
        try:
            answer = raw_input()
        except EOFError:
            return False
        if answer in ("y", "Y", "yes", "Yes"):
            return True
        return False

    def do_cd(self, line):
        """Change the current irods collection
        """
        # Parse the new path
        try:
            opts, args = self.parse_command("cd", "", noargs=True)
        except self._IShellError:
            return
        if not args:
            path = self.home
        else:
            path = self.get_path(args[0])

        # Fetch the corresponding irods collection
        try:
            self.cursor = self.session.collections.get(path)
        except CollectionDoesNotExist:
            self.println("... path `{:}` does not exist", args[0])
        else:
            # Update the prompt
            current = irods_basename(self.cursor.path)
            self.prompt = "[{:} {:}]$ ".format(self.prompt_prefix, current)

    def do_ls(self, line):
        """List the objects inside the current irods collection
        """
        try:
            opts, args = self.parse_command("ls", "", noargs=True)
        except self._IShellError:
            return
        if not args:
            args = ("*",)

        for iteration, pattern in enumerate(args):
            # Find items that match the pattern
            dirname, base, content = self.get_content(pattern)

            # Print the result
            if iteration > 0:
                self.println("")
            if len(args) > 1:
                self.println("{:}:", pattern)
            self.println(sorted(content.keys()))

    def do_mkdir(self, line):
        try:
            opts, args = self.parse_command("mkdir", "")
        except self._IShellError:
            return

        for arg in args:
            path = self.get_path(arg)
            try:
                self.session.collections.create(path)
            except CATALOG_ALREADY_HAS_ITEM_BY_THAT_NAME:
                self.println("... mkdir: cannot create collection `{:}`:"
                             " Object exists", irods_basename(path))
                break

    def do_pwd(self, line):
        self.println(self.cursor.path)

    def do_rm(self, line):
        try:
            opts, args = self.parse_command("rm", "rfT")
        except self._IShellError:
            return

        protect_collections = True
        request_confirmation = True
        skip_trash = False
        for opt, param in opts:
            if opt == "-r":
                protect_collections = False
            elif opt == "-f":
                request_confirmation = False
            elif opt == "-T":
                skip_trash = True

        for arg in args:
            # Check that the object exist and what is its type
            path = self.get_path(arg)
            basename = irods_basename(path)
            try:
                target = self.session.data_objects.get(path)
            except DataObjectDoesNotExist:
                try:
                    target = self.session.collections.get(path)
                except CollectionDoesNotExist:
                    self.println("... rm: cannot remove object `{:}`:"
                                 "No such data or collection", basename)
                    return
                else:
                    itype = "collection"
            else:
                itype = "data object"

            # Check for the recursive mode
            if protect_collections and (itype == "collection"):
                self.println("... rm: cannot remove `{:}`: Is a collection",
                             basename)
                return

            # Check for a confirmation
            if request_confirmation:
                if not self.ask_for_confirmation(
                        "rm: remove {:} `{:}'?", itype, basename):
                    continue

            # Now we can remove the data
            try:
                if itype == "collection":
                    self.session.collections.remove(path)
                else:
                    self.session.data_objects.unlink(path, force=skip_trash)
            except USER_FILE_DOES_NOT_EXIST:
                self.println("... rm: cannot remove object `{:}`:"
                             "No such data or collection", basename)
                return

    def do_put(self, line):
        try:
            opts, args = self.parse_command("put", "rf")
        except self._IShellError:
            return

        recursive = False
        request_confirmation = True
        for opt, param in opts:
            if opt == "-r":
                recursive = True
            elif opt == "-f":
                request_confirmation = False

        # Parse the src(s) and the destination
        if len(args) == 1:
            srcs = args
            dst = self.cursor.path
        else:
            if len(args) == 2:
                srcs = (args[0],)
            else:
                srcs = args[:-1]
            dst = self.get_path(args[-1])

        # Check if the destination is an existing collection
        if self.session.collections.exists(dst):
            if not dst.endswith("/"):
                dst += "/"
        elif len(srcs) > 1:
            self.println("... put: target `{:}` is not a directory", basename)
            return

        # Upload the data
        def upload(srcs, dst):
            for src in srcs:
                basename = os.path.basename(src)
                if dst.endswith("/"):
                    target = dst + basename
                else:
                    target = dst

                if os.path.isdir(src):
                    if not recursive:
                        self.println("... put: omitting collection `{:}`",
                                     basename)
                        raise self._IShellError()
                    if not self.session.collections.exists(target):
                        self.session.collections.create(target)
                    children = [os.path.join(src, f) for f in os.listdir(src)]
                    upload(children, target + "/")
                else:
                    if self.session.data_objects.exists(target):
                        if request_confirmation:
                            if not self.ask_for_confirmation(
                                    "put: overwrite data object `{:}'?", basename):
                                continue
                    try:
                        self.session.data_objects.put(src, dst)
                    except CAT_NAME_EXISTS_AS_COLLECTION:
                        self.println("... put: `{:}` is an existing collection",
                                     basename)
                        raise self._IShellError()
        try:
            upload(srcs, dst)
        except self._IShellError:
            return

    def complete_put(self, text, line, begidx, endidx):
        self._command = self.parse_line(line)[0]
        try:
            opts, args = self.parse_command("put", "rf", noargs=True)
        except self._IShellError:
            return []
        nargs = len(args)
        if (nargs < 1) or ((nargs == 1) and (line[-1] != " ")):
            dirname = os.path.dirname(text)
            if not dirname:
                pattern = text + "*"
                return filter(lambda s: fnmatch.fnmatch(s, pattern),
                              os.listdir("."))
            else:
                pattern = os.path.basename(text) + "*"
                completion = filter(lambda s: fnmatch.fnmatch(s, pattern),
                                    os.listdir(dirname))
                completion = [os.path.join(dirname, c) for c in completion]
                return completion
        else:
            return self.completedefault(text, line, begidx, endidx)

    def do_get(self, line):
        try:
            opts, args = self.parse_command("get", "rf")
        except self._IShellError:
            return

        recursive = False
        request_confirmation = True
        for opt, param in opts:
            if opt == "-r":
                recursive = True
            elif opt == "-f":
                request_confirmation = False

        # Parse the src(s) and the destination
        if len(args) == 1:
            srcs = args
            dst = "."
        else:
            if len(args) == 2:
                srcs = (args[0],)
            else:
                srcs = args[:-1]
            dst = args[-1]

        # Check the consistency of the inputs
        if os.path.isdir(dst):
            isdir = True
        else:
            isdir = False
            if len(srcs) > 1:
                self.println("... get: target `{:}' is not a directory",
                             os.path.basename(dst))
                return

        # Download the data
        def download(srcs, dst, isdir):
            for src in srcs:
                basename = os.path.basename(src)
                if isdir:
                    target = os.path.join(dst, basename)
                else:
                    target = dst

                if self.session.collections.exists(src):
                    if not recursive:
                        self.println("... get: omitting collection `{:}`",
                                     irods_basename(src))
                        raise self._IShellError()

                    if os.path.exists(target):
                        if not os.path.isdir(target):
                            self.println("get: cannot overwrite non-directory "
                                         "`{:}'", target)
                            raise self._IShellError()
                    else:
                        os.makedirs(target)

                    base = self.session.collections.get(src)
                    _, _, content = self.get_content("*", base=base)
                    newsrcs = content.keys()
                    newsrcs = [self.get_path(src, base=base) for src in newsrcs]
                    download(newsrcs, target, True)
                else:
                    if not self.session.data_objects.exists(src):
                        self.println("... get: cannot stat `{:}`: No such data "
                                     "object of collection",
                                     irods_basename(src))
                        raise self._IShellError()

                    if os.path.exists(target) and request_confirmation:
                        if not self.ask_for_confirmation(
                                "get: overwrite file `{:}'?", basename):
                            continue

                    opts = {FORCE_FLAG_KW: True}
                    self.session.data_objects.get(src, target, **opts)

        srcs = [self.get_path(src) for src in srcs]
        try:
            download(srcs, dst, isdir)
        except self._IShellError:
            return

    def do_shell(self, line):
        args = shlex.split(line)
        if args and (args[0] == "cd"):
            os.chdir(args[1])
        else:
            p = subprocess.Popen(line, shell=True)
            p.communicate()

    def do_EOF(self, line):
        return True

    def onecmd(self, line):
        """Override the default command processing in order to strip commands
        """
        for self._command in self.parse_line(line):
            if super(IShell, self).onecmd(" ".join(self._command)):
                return True

    def cmdloop(self, intro=None):
        """Override the default command loop in order to catch Ctrl+C
        """
        # Initialise the session
        self.initialise()

        # Run the command loop
        self.interactive = True

        while True:
            try:
                super(IShell, self).cmdloop(intro="")
                break
            except KeyboardInterrupt:
                print("^C")
        print

        # Finalise the session
        self.finalise()

    def initialise(self):
        """Start an iRods session and initialise the environment
        """
        # Start the iRods session
        environment = os.path.expanduser("~/.irods/irods_environment.json")
        self.session = iRODSSession(irods_env_file=environment)

        # Fetch the environment
        env = self.session.get_irods_env(environment)
        self.home = env["irods_home"]
        self.user = env["irods_user_name"]
        self.host = env["irods_host"]
        self.prompt_prefix = "{:}@{:}".format(self.host.split(".", 1)[0],
                                                  self.user)

        # Go to the home directory
        self._command = ["cd"]
        self.do_cd("")

    def finalise(self):
        """Close the current iRods session
        """
        self.session.cleanup()
        self.session = None
