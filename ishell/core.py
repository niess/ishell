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

# For 2/3 compatibility
from __future__ import absolute_import, division, print_function, with_statement

import os
import sys
try:
    import builtins
except ImportError:
    path = os.path.realpath(os.path.join(os.path.dirname(__file__),
                            "..", "..", "..", "deps", "future", "src"))
    sys.path.append(path)

from builtins import input
from builtins import str
from builtins import range

# Standard library imports
import argparse
import cmd
import fnmatch
import glob
import io
import math
import readline
import subprocess
import time

# iRODS imports
from irods.exception import (CATALOG_ALREADY_HAS_ITEM_BY_THAT_NAME,
                             CAT_NAME_EXISTS_AS_COLLECTION,
                             CollectionDoesNotExist, DataObjectDoesNotExist,
                             USER_FILE_DOES_NOT_EXIST)
from irods.session import iRODSSession
from irods.data_object import chunks, irods_basename
from irods.keywords import FORCE_FLAG_KW
try:
    from irods.manager.data_object_manager import (READ_BUFFER_SIZE,
                                                   WRITE_BUFFER_SIZE)
except ImportError:
    READ_BUFFER_SIZE = 1024 * io.DEFAULT_BUFFER_SIZE
    WRITE_BUFFER_SIZE = 1024 * io.DEFAULT_BUFFER_SIZE

__all__ = ["IShell"]


# Redefine the delimiters according to file name syntax. This is required
# for autocompletion of file names.
readline.set_completer_delims(" \t\n")


class IShell(cmd.Cmd, object):
    """Shell like client for managing iRODS data
    """

    cursor = None

    interactive = False

    parser = {}

    session = None

    class _IShellError(Exception):
        pass

    def default(self, line):
        """Handle unknown commands
        """
        args = line.split(None, 1)
        self.errorln("error: unknown command `{:}'", args[0])

    def completedefault(self, text, line, begidx, endidx):
        dirname, _, content = self.get_content(text + "*")
        completion = list(content.keys())
        if dirname:
            if dirname == "/":
                dirname = ""
            else: 
                dirname = dirname.replace("/", r"/")
            completion = [r"/".join((dirname, c)) for c in completion]
        return completion

    def get_content(self, pattern, data=True, collections=True, base=None):
        """Get items within the collection that match the pattern
        """
        if base is None:
            base = self.cursor
        if pattern.endswith("/"):
            pattern += "*"
        elif pattern.endswith(".."):
            pattern += "/*"
        elif pattern.endswith("/."):
            pattern = pattern[:-1] + "*"
        elif pattern == ".":
            pattern = "*"

        if pattern.startswith("~"):
            pattern = self.home + pattern[1:]

        try:
            dirname, basename = pattern.rsplit("/", 1)
        except ValueError:
            dirname = None
        else:
            if dirname == "":
                dirname = "/"
            path = self.get_path(dirname, base)
            try:
                base = self.session.collections.get(path)
            except CollectionDoesNotExist:
                return None, base, None
            pattern = basename

        content, n = {}, 0
        if collections:
            for c in base.subcollections:
                n += 1
                if c.name == "":
                    continue
                if fnmatch.fnmatch(c.name, pattern):
                    content[c.name] = (True, c)
        if data:
            for d in base.data_objects:
                n += 1
                if fnmatch.fnmatch(d.name, pattern):
                    content[d.name] = (False, d)

        if (n > 0) and not content:
            content = None
        return dirname, base, content

    def get_path(self, path, base=None):
        if path.startswith("/"):
            return os.path.normpath(path)
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
            opts = vars(self.parser[command].parse_args(args))
            try:
                args = opts.pop("args")
            except KeyError:
                arg = opts.pop("arg")
                if arg is None:
                    args = []
                else:
                    args = [arg]
        except SystemExit:
            raise self._IShellError()

        if (not noargs) and (not args):
            self.errorln("{:}: missing operand", command)
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

    def println(self, text, *opts, **kwopts):
        self.printfmt(text, *opts, **kwopts)
        print()

    def printfmt(self, text, *opts, **kwopts):
        if opts or kwopts:
            text = text.format(*opts, **kwopts)
        else:
            text = str(text)
        print(text, end="")

    def errorln(self, text, *opts, **kwopts):
        if opts or kwopts:
            text = text.format(*opts, **kwopts)
        else:
            text = str(text)
        if self.interactive:
            text = "\033[93m{:}\033[0m".format(text)
        print(text, file=sys.stderr)

    def ask_for_confirmation(self, text, *args):
        self.printfmt(text, *args)
        try:
            answer = input()
        except EOFError:
            return False
        if answer in ("y", "Y", "yes", "Yes"):
            return True
        return False

    def _register_cd(self):
        if "cd" not in self.parser:
            p = argparse.ArgumentParser(
                prog="cd",
                description="Change the iRODS collection to the given path. "
                "If no path is provided then get back to HOME ({:}).".format(
                    self.home))
            p.add_argument("arg", metavar="path", type=str, nargs="?",
                           help="the path to change the current collection to")
            self.parser["cd"] = p

    def help_cd(self):
        """Print a help message for the `cd' command
        """
        self._register_cd()
        self.println(self.parser["cd"].format_help())

    def do_cd(self, line):
        """Change the current iRODS collection
        """
        self._register_cd()
        try:
            opts, args = self.parse_command("cd", "", noargs=True)
        except self._IShellError:
            return
        if not args:
            path = self.home
        else:
            path = args[0]
            if path.startswith("~"):
                path = path.replace("~", self.home)
            path = self.get_path(path)

        # Fetch the corresponding iRODS collection
        try:
            self.cursor = self.session.collections.get(path)
        except CollectionDoesNotExist:
            self.errorln("cd: path `{:}' does not exist", args[0])
        else:
            # Update the prompt
            current = irods_basename(self.cursor.path)
            self.prompt = "[{:} \033[94m{:}\033[0m]$ ".format(
                self.prompt_prefix, current)

    def _register_ls(self):
        if "ls" not in self.parser:
            p = argparse.ArgumentParser(
                prog="ls",
                description="List the objects inside the given iRODS "
                "collection. If no path is provided then list the current "
                "collection.")
            p.add_argument("args", metavar="path", type=str, nargs="*",
                           help="the path(s) to list")
            self.parser["ls"] = p

    def help_ls(self):
        """Print a help message for the `ls' command
        """
        self._register_ls()
        self.println(self.parser["ls"].format_help())

    def do_ls(self, line):
        """List the objects inside the given iRODS collection
        """
        self._register_ls()
        try:
            opts, args = self.parse_command("ls", "", noargs=True)
        except self._IShellError:
            return
        list_subcol = True
        if not args:
            args = ("*",)

        for iteration, pattern in enumerate(args):
            # Find items that match the pattern
            if ((pattern == ".") or (pattern == "*") or (pattern == "/") or
                pattern.endswith("/.") or pattern.endswith("/*")):
                list_subcol = False

            dirname, base, content = self.get_content(pattern)
            if content is None:
               	self.errorln("ls: cannot access `{:}':"
                             " No such data object or collection",
                             pattern)
               	break
            elif len(content) == 0:
                break

            # Print the result
            if iteration > 0:
                self.println("")
            if len(args) > 1:
                self.println("{:}:", pattern)
            if (len(content) == 1) and list_subcol:
                pattern = list(content.keys())[0]
                if pattern[-1] == "/":
                    pattern += "*"
                else:
                    pattern += "/*"
                if dirname:
                    pattern = os.path.join(dirname, pattern)
                _, _, content = self.get_content(pattern)
            keys = sorted([str(s) for s in content.keys()], key=str.lower)

            if len(keys) == 0:
                continue

            if self.interactive:
                # Get the current terminal's width
                p = subprocess.Popen("stty size", shell=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                out, err = p.communicate()
                if err:
                    screen_width = 80
                else:
                    screen_width = int(out.split()[-1])

                # Compute the layout
                tokens = []
                for item in keys:
                    n = len(item) + 2
                    if content[item][0]:
                        item = "\033[94m{:}\033[0m".format(item)
                        extra = len(item) - n + 3
                    else:
                        extra = 1
                    tokens.append((n, item, extra))
                max_width = max(tokens)[0]
                n_columns = max(screen_width // max_width, 1)
                n_tokens = len(tokens)
                if n_columns >= n_tokens:
                    n_columns = n_tokens
                    n_rows = 1
                else:
                    n_rows = int(math.ceil(n_tokens / float(n_columns)))

                column_width = n_columns * [0]
                for i in range(n_columns):
                    w = 0
                    for j in range(n_rows):
                        index = i * n_rows + j
                        if index >= n_tokens:
                            continue
                        wj = tokens[index][0]
                        if wj > w:
                            w = wj
                    column_width[i] = w - 1

                # Print the result
                for i in range(n_rows):
                    for j in range(n_columns):
                        index = j * n_rows + i
                        if index >= n_tokens:
                            continue
                        self.printfmt("{:<{width}}", tokens[index][1],
                                      width=column_width[j] + tokens[index][2])
                    self.println("")
            else:
                self.println(os.linesep.join(keys))

    def _register_mkdir(self):
        if "mkdir" not in self.parser:
            p = argparse.ArgumentParser(
                prog="mkdir", description="Create new iRODS collection(s)")
            p.add_argument("args", metavar="path", type=str, nargs="+",
                           help="the path(s) of the new collection(s)")
            self.parser["mkdir"] = p

    def help_mkdir(self):
        """Print a help message for the `mkdir' command
        """
        self._register_mkdir()
        self.println(self.parser["mkdir"].format_help())

    def do_mkdir(self, line):
        """Create new iRODS collection(s)
        """
        self._register_mkdir()
        try:
            opts, args = self.parse_command("mkdir", "")
        except self._IShellError:
            return

        for arg in args:
            path = self.get_path(arg)
            try:
                self.session.collections.create(path)
            except CATALOG_ALREADY_HAS_ITEM_BY_THAT_NAME:
                self.errorln("mkdir: cannot create collection `{:}':"
                             " Object exists", irods_basename(path))
                break

    def _register_pwd(self):
        if "pwd" not in self.parser:
            p = argparse.ArgumentParser(
                prog="mkdir", description="Show the current iRODS collection.")
            self.parser["pwd"] = p

    def help_pwd(self):
        """Print a help message for the `pwd' command
        """
        self._register_pwd()
        self.println(self.parser["pwd"].format_help())

    def do_pwd(self, line):
        """Show the current iRODS collection
        """
        self._register_pwd()
        self.println(self.cursor.path)

    def _register_rm(self):
        if "rm" not in self.parser:
            p = argparse.ArgumentParser(
                prog="rm", description="Remove collection(s) or data object(s) "
                "from iRODS.")
            p.add_argument("args", metavar="path", type=str, nargs="+",
                           help="the path(s) of the object(s) to remove")
            p.add_argument("-f", "--force", action="store_true",
                           help="do not prompt before removal")
            p.add_argument("-r", "--recursive", action="store_true",
                           help="remove collections and their content "
                           "recursively")
            p.add_argument("-T", "--no-trash", action="store_true",
                           help="do not put the erased object in the trash."
                           " Remove them definitively")
            self.parser["rm"] = p

    def help_rm(self):
        """Print a help message for the `rm' command
        """
        self._register_rm()
        self.println(self.parser["rm"].format_help())

    def do_rm(self, line):
        """Remove collection(s) or data object(s) from iRODS
        """
        self._register_rm()
        try:
            opts, args = self.parse_command("rm", "rfT")
        except self._IShellError:
            return
        protect_collections = not opts["recursive"]
        request_confirmation = not opts["force"]
        skip_trash = opts["no_trash"]

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
                    self.errorln("rm: cannot remove object `{:}':"
                                 "No such data or collection", basename)
                    return
                else:
                    itype = "collection"
            else:
                itype = "data object"

            # Check for the recursive mode
            if protect_collections and (itype == "collection"):
                self.errorln("rm: cannot remove `{:}': Is a collection",
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
                self.errorln("rm: cannot remove object `{:}':"
                             "No such data or collection", basename)
                return

    def _register_put(self):
        if "put" not in self.parser:
            p = argparse.ArgumentParser(
                prog="put", description="Upload collection(s) or data "
                "object(s) to iRODS.")
            p.add_argument("args", metavar="path", type=str, nargs="+",
                           help="the local path(s) of the object(s) to "
                           "download. If more than one argument is given, the "
                           "last one specifies the iRODS destination path")
            p.add_argument("-f", "--force", action="store_true",
                           help="do not prompt before overwriting")
            p.add_argument("-r", "--recursive", action="store_true",
                           help="upload directories and their content "
                           "recursively")
            self.parser["put"] = p

    def help_put(self):
        """Print a help message for the `put' command
        """
        self._register_put()
        self.println(self.parser["put"].format_help())

    @staticmethod
    def _hrdb(x):
        """Format a number as human readable text
        """
        if x > 1125899906842624:
            return "{:.1f}P".format(x / 1125899906842624.)
        elif x == 0:
            return "0.0B"
        i = int(math.floor(math.log(x) / math.log(1024)))
        unit = ("B", "kB", "MB", "GB", "TB")
        return "{:.1f} {:}".format(x / 1024**i, unit[i])

    def do_put(self, line):
        """Upload collection(s) or data object(s) to iRODS
        """
        self._register_put()
        try:
            opts, args = self.parse_command("put", "rf")
        except self._IShellError:
            return
        recursive = opts["recursive"]
        request_confirmation = not opts["force"]

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

        # Expand the source(s)
        expanded = []
        for src in srcs:
            s = glob.glob(src)
            if not s:
                self.errorln("cannot access {:}: No such file or directory",
                             os.path.basename(src))
                return
            expanded += s
        srcs = expanded

        # Check if the destination is an existing collection
        if self.session.collections.exists(dst):
            if not dst.endswith("/"):
                dst += "/"
        elif len(srcs) > 1:
            self.errorln("put: target `{:}' is not a directory", basename)
            return

        # Upload the data
        def upload(srcs, dst):
            for src in srcs:
                basename = os.path.basename(src)
                if not os.path.exists(src):
                    self.errorln("cannot access {:}: No such file or directory",
                                 basename)
                    raise self._IShellError()
                if dst.endswith("/"):
                    target = dst + basename
                else:
                    target = dst

                if os.path.isdir(src):
                    if not recursive:
                        self.errorln("put: omitting collection `{:}'",
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

                    size = os.stat(src).st_size
                    done = 0
                    t0 = t1 = time.time()
                    if self.interactive:
                        red, blue, reset = "\033[91m", "\033[94m", "\033[0m"
                    else:
                        red, blue, reset = "", "", ""
                    self.printfmt("Uploading {:}{:}{:} ...",
                                  red, basename, reset),
                    sys.stdout.flush()
                    dmgr = self.session.data_objects
                    try:
                        with open(src, "rb") as f, dmgr.open(
                                target, "w", oprType=1) as o:
                            for chunk in chunks(f, WRITE_BUFFER_SIZE):
                                o.write(chunk)

                                n_chunk = len(chunk)
                                done += n_chunk
                                if done < size:
                                    status = int(100 * done / float(size))
                                    t2 = time.time()
                                    dt, t1 = t2 - t1, t2
                                    self.printfmt(
                                        "\rUploading {:}{:}{:} ({:2d}%), "
                                        "size={:}{:}{:}, speed={:}{:}/s{:}",
                                        red, basename, reset, status,
                                        blue, self._hrdb(done), reset,
                                        blue, self._hrdb(n_chunk / dt),
                                        reset),
                                    sys.stdout.flush()
                            dt = time.time() - t0
                            self.println(
                                "\rUploaded {:}{:}{:} as {:} ({:}{:}{:} at "
                                "{:}{:}/s{:})", red, basename, reset,
                                irods_basename(target), blue, self._hrdb(done),
                                reset, blue, self._hrdb(done / dt), reset)
                    except CAT_NAME_EXISTS_AS_COLLECTION:
                        self.errorln("put: `{:}' is an existing collection",
                                     basename)
                        raise self._IShellError()
                    except KeyboardInterrupt:
                        print("^C")
                        raise self._IShellError
                    except EOFError:
                        print("^D")
                        raise self._IShellError

        try:
            upload(srcs, dst)
        except self._IShellError:
            return

    def complete_put(self, text, line, begidx, endidx):
        self._register_put()
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
                return [s for s in os.listdir(".")
                        if fnmatch.fnmatch(s, pattern)]
            else:
                pattern = os.path.basename(text) + "*"
                completion = [os.path.join(dirname, s)
                              for s in os.listdir(dirname)
                              if fnmatch.fnmatch(s, pattern)]
                return completion
        else:
            return self.completedefault(text, line, begidx, endidx)

    def _register_get(self):
        if "get" not in self.parser:
            p = argparse.ArgumentParser(
                prog="get", description="Download collection(s) or data "
                "object(s) from iRODS.")
            p.add_argument("args", metavar="path", type=str, nargs="+",
                           help="the iRODS path(s) of the object(s) to "
                           "download. If more than one argument is given, the "
                           "last one specifies the local destination path")
            p.add_argument("-f", "--force", action="store_true",
                           help="do not prompt before overwriting")
            p.add_argument("-r", "--recursive", action="store_true",
                           help="Download collections and their content "
                           "recursively")
            self.parser["get"] = p

    def help_get(self):
        """Print a help message for the `get' command
        """
        self._register_get()
        self.println(self.parser["get"].format_help())

    def do_get(self, line):
        """Download collection(s) or data object(s) from iRODS
        """
        self._register_get()
        try:
            opts, args = self.parse_command("get", "rf")
        except self._IShellError:
            return
        recursive = opts["recursive"]
        request_confirmation = not opts["force"]

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
                self.errorln("get: target `{:}' is not a directory",
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
                        self.errorln("get: omitting collection `{:}'",
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
                    newsrcs = [self.get_path(src, base=base)
                               for src in content.keys()]
                    download(newsrcs, target, True)
                else:
                    if not self.session.data_objects.exists(src):
                        self.errorln("get: cannot stat `{:}': No such data "
                                     "object or collection",
                                     irods_basename(src))
                        raise self._IShellError()

                    if os.path.exists(target) and request_confirmation:
                        if not self.ask_for_confirmation(
                                "get: overwrite file `{:}'?", basename):
                            continue

                    dmgr = self.session.data_objects
                    obj = dmgr.get(src)
                    size = obj.size
                    done = 0
                    t0 = t1 = time.time()
                    if self.interactive:
                        red, blue, reset = "\033[91m", "\033[94m", "\033[0m"
                    else:
                        red, blue, reset = "", "", ""
                    self.printfmt("Downloading {:}{:}{:} ...",
                                  red, irods_basename(src), reset),
                    sys.stdout.flush()
                    try:
                        with open(target, "wb") as f, dmgr.open(
                                src, "r", forceFlag=True) as o:
                            for chunk in chunks(o, READ_BUFFER_SIZE):
                                f.write(chunk)

                                n_chunk = len(chunk)
                                done += n_chunk
                                if done < size:
                                    status = int(100 * done / float(size))
                                    t2 = time.time()
                                    dt, t1 = t2 - t1, t2
                                    self.printfmt(
                                        "\rDownloading {:}{:}{:} ({:2d}%), "
                                        "size={:}{:}{:}, speed={:}{:}/s{:}",
                                        red, irods_basename(src), reset, status,
                                        blue, self._hrdb(done), reset,
                                        blue, self._hrdb(n_chunk / dt),
                                        reset),
                                    sys.stdout.flush()
                            dt = time.time() - t0
                            self.println(
                                "\rDownloaded {:}{:}{:} as {:} ({:}{:}{:} at "
                                "{:}{:}/s{:})", red, irods_basename(src), reset,
                                target, blue, self._hrdb(done), reset,
                                blue, self._hrdb(done / dt), reset)
                    except KeyboardInterrupt:
                        print("^C")
                        raise self._IShellError
                    except EOFError:
                        print("^D")
                        raise self._IShellError

        srcs = [self.get_path(src) for src in srcs]
        try:
            download(srcs, dst, isdir)
        except self._IShellError:
            return

    def _register_shell(self):
        if "shell" not in self.parser:
            p = argparse.ArgumentParser(
                prog="shell", description="escape with a local shell command.")
            p.add_argument("args", metavar="command", type=str, nargs=1,
                           help="the local command")
            p.add_argument("args", metavar="argument", type=str, nargs="*",
                           help="the argument(s) of the local command",
                           action="append")
            self.parser["shell"] = p

    def help_shell(self):
        """Print a help message for the `get' command
        """
        self._register_shell()
        self.println(self.parser["shell"].format_help())

    def do_shell(self, line):
        """Escape with a local shell command
        """
        self._register_shell()
        args = line.split(None, 1)
        if args and (args[0] == "cd"):
            os.chdir(args[1])
        else:
            p = subprocess.Popen(line, shell=True)
            p.communicate()

    def do_EOF(self, line):
        """Exit to the OS
        """
        return True

    def do_exit(self, line):
        """Exit to the OS
        """
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
        print()

        # Finalise the session
        self.finalise()

    def initialise(self):
        """Start an iRODS session and initialise the environment
        """
        # Start the iRODS session
        environment = os.path.expanduser("~/.irods/irods_environment.json")
        self.session = iRODSSession(irods_env_file=environment)

        # Fetch the environment
        env = self.session.get_irods_env(environment)
        self.home = env["irods_home"]
        self.user = env["irods_user_name"]
        self.host = env["irods_host"]
        self.prompt_prefix = "\033[91m{:}@{:}\033[0m".format(
            self.host.split(".", 1)[0], self.user)

        # Go to the home directory
        self._command = ["cd"]
        self.do_cd("")

    def finalise(self):
        """Close the current iRODS session
        """
        self.session.cleanup()
        self.session = None
