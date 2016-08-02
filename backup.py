#!python
"""
Backup utility

Allows the user to choose which files are backed up with a tree-based UI, complete with note-taking abilities.

Selected files are copied to the output directory, along with a few generated files:
* FILES.csv - listing of all files copied with attributes (size, etc.)
* README.txt - other data about the copy operation, including notes added in the selection step

Job data can be saved to disk for later use.  Loading job data is often faster than re-scanning the directory.

"""

from __future__ import print_function
from abc import abstractmethod, ABCMeta
from csv import DictReader, DictWriter
from datetime import datetime
from optparse import OptionParser
import json
import os
import subprocess
import sys
import tempfile
import time
import Tkinter as tk
import ttk
import tkFont as tkf


def parse_command_line():

    parser = OptionParser(
        usage='%prog [options] SOURCE_DIR DEST_DIR'
    )

    # options

    parser.add_option(
        '--job', dest='job_path', default=None,
        help='path to job data',
    )

    parser.add_option(
        '-n', '--dry-run', dest='dry_run', default=False, action='store_true',
        help='do a dry run (don\'t copy anything)',
    )

    parser.add_option(
        '-q', '--quiet', dest='quiet', default=False, action='store_true',
        help='Non-interactive mode. (Don\'t show file chooser)',
    )

    (options, args) = parser.parse_args()

    # args

    """
    if len(args) < 1:
        parser.print_usage()
        sys.exit(1)
    """

    return (options, args)


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

FILTER_INCLUDE_ALL = 'I'
FILTER_EXCLUDE_ALL = 'E'
FILTER_PARTIAL = 'P'

FILE_LIST_NAME = 'FILES.csv'


def friendly_decimal(num):
    num = round(num, 1)
    if int(num * 10) % 10 == 0:
        return '%d' % (num,)
    return '%.1f' % (num,)


def friendly_file_size(num):
    for unit in ('bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB'):
        if abs(num) < 1024:
            return "%s %s" % (friendly_decimal(num), unit)
        num /= 1024.0
    return "%f %s" % (friendly_decimal(num), 'YB')


class DirTree:
    filter_changed = None

    def __init__(self, name, is_directory, parent=None):
        self.__name = name
        self.__is_directory = is_directory
        self.__parent = parent
        self.__children = []
        self.__size = 0
        self.__filtered_size = 0
        self.__filter = FILTER_INCLUDE_ALL
        self.treeview_iid = None
        self.notes = None

    @property
    def name(self):
        return self.__name

    @property
    def is_directory(self):
        return self.__is_directory

    @property
    def parent(self):
        return self.__parent

    @property
    def children(self):
        return tuple(self.__children)

    @property
    def size(self):
        return self.__size

    @property
    def filter(self):
        return self.__filter

    @property
    def filtered_size(self):
        return self.__filtered_size

    @property
    def path(self):
        if self.parent:
            return os.path.join(self.parent.path, self.name)
        return self.name

    def __set_filter(self, f, update_parent, update_children):
        if update_children:
            for child in self.children:
                child.__set_filter(f, False, True)

        self.__filter = f
        if f is FILTER_EXCLUDE_ALL:
            self.__filtered_size = 0
        elif f is FILTER_INCLUDE_ALL:
            self.__filtered_size = self.size
        else:
            self.__filtered_size = sum(child.filtered_size for child in self.children)

        if DirTree.filter_changed:
            DirTree.filter_changed(self)

        if update_parent:
            parent = self.parent
            while parent:
                if all(child.filter == FILTER_EXCLUDE_ALL for child in parent.children):
                    parent.__set_filter(FILTER_EXCLUDE_ALL, False, False)
                elif all(child.filter == FILTER_INCLUDE_ALL for child in parent.children):
                    parent.__set_filter(FILTER_INCLUDE_ALL, False, False)
                else:
                    parent.__set_filter(FILTER_PARTIAL, False, False)
                parent = parent.parent

    def exclude_all(self):
        self.__set_filter(FILTER_EXCLUDE_ALL, update_parent=True, update_children=True)

    def include_all(self):
        self.__set_filter(FILTER_INCLUDE_ALL, update_parent=True, update_children=True)

    def save(self, path):
        with open(path, 'w') as fout:
            fields = (
                'id',
                'name',
                'is_directory',
                'parent',
                'size',
                'filter',
                'filtered_size',
                'notes',
            )
            print(json.dumps(fields), file=fout)
            self.__save(fields, fout)

    def __save(self, fields, fout):
        data = dict(
            id=id(self),
            name=self.name,
            is_directory=self.is_directory,
            parent=id(self.parent) if self.parent else None,
            size=self.size,
            filter=self.filter,
            filtered_size=self.filtered_size,
            notes=self.notes if self.notes else ''
        )
        values = [data[k] for k in fields]
        print(json.dumps(values), file=fout)
        for child in self.children:
            child.__save(fields, fout)

    def sort_by_name(self):
        self.__children.sort(key=lambda x: x.name.lower())
        for child in self.__children:
            child.sort_by_name()

    @staticmethod
    def load(path):
        root = None
        with open(path, 'r') as fin:
            tree_by_id=dict()
            fields = json.loads(fin.readline())
            for line in fin:
                values = json.loads(line)
                data = dict()
                for i in range(len(values)):
                    data[fields[i]] = values[i]
                parent = tree_by_id[data['parent']] if data['parent'] else None
                tree = DirTree(
                    name=data['name'],
                    is_directory=data['is_directory'],
                    parent=parent,
                )
                tree.__size = data['size']
                tree.__filter = data['filter'].strip()[0]
                tree.__filtered_size = data['filtered_size']
                tree.notes = data.get('notes', '').strip()
                if parent:
                    parent.__children.append(tree)
                else:
                    root = tree
                tree_by_id[data['id']] = tree
        return root

    @staticmethod
    def ls(path):
        tree = DirTree.__ls(path, True)
        tree.__name = path + '/'
        return tree

    @staticmethod
    def __ls(path, is_directory, parent=None):
        tree = DirTree(os.path.basename(path) + ('/' if is_directory else ''), is_directory, parent)
        if is_directory:
            try:
                for name in os.listdir(path):
                    abspath = os.path.join(path, name)
                    child = DirTree.__ls(abspath, os.path.isdir(abspath), tree)
                    tree.__children.append(child)
                    tree.__size += child.size
                tree.__children.sort(reverse=True, key=lambda x: x.size)
            except OSError:
                pass
        else:
            try:
                tree.__size = os.path.getsize(path)
            except OSError:
                pass
        tree.__filtered_size = tree.size
        return tree


class FileChooser(tk.Frame):
    __HAS_NOTES_STRING = '*'

    def __init__(self, parent, tree):
        tk.Frame.__init__(self, parent, background="white")
        self.__parent = parent
        self.__tree_by_iid = dict()
        self.__expanded_by_iid = dict()
        self.__focus_tree = None

        self.__parent.title("Choose Files")
        self.__center_window()

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.pack(fill=tk.BOTH, expand=True)

        self.__treeview = ttk.Treeview(self, columns=('size', 'filtered_size', 'notes'))
        ysb = ttk.Scrollbar(self, orient='vertical', command=self.__treeview.yview)
        xsb = ttk.Scrollbar(self, orient='horizontal', command=self.__treeview.xview)
        self.__treeview.configure(yscroll=ysb.set, xscroll=xsb.set)
        self.__treeview.configure(yscroll=ysb.set)
        self.__treeview.heading('#0', text='Path', anchor='w')
        self.__treeview.heading('size', text='Size', anchor='e')
        self.__treeview.heading('filtered_size', text='Filtered Size', anchor='e')
        self.__treeview.heading('notes', text='Notes')
        self.__treeview.column('#0', stretch=True)
        self.__treeview.column('size', anchor='e', width=100, stretch=False)
        self.__treeview.column('filtered_size', anchor='e', width=100, stretch=False)
        self.__treeview.column('notes', width=40, anchor=tk.CENTER, stretch=False)
        self.__treeview.tag_configure('exclude', foreground='gray')

        self.__treeview.bind('<Button-2>', self.__treeview_rightclick)
        self.__treeview.bind('<Button-3>', self.__treeview_rightclick)
        self.__treeview.bind('<KeyPress>', self.__treeview_keypress)
        self.__treeview.bind('<<TreeviewSelect>>', self.__treeview_select)
        self.__treeview.bind('<<TreeviewOpen>>', self.__treeview_open)
        self.__treeview.bind('<<TreeviewClose>>', self.__treeview_close)

        self.__treeview.grid(row=0, column=0, sticky='nsew')
        ysb.grid(row=0, column=1, sticky='ns')
        xsb.grid(row=1, column=0, sticky='ew')

        details_frame = tk.Frame(self)
        details_frame.grid(row=0, column=2, rowspan=2, sticky='ne', padx=5, pady=5)
        tk.Label(details_frame, text='Details', font=tkf.Font(weight='bold')).pack()
        tk.Label(details_frame, text='Full Path:').pack(anchor='w')
        self.__path_text = tk.Entry(details_frame, width=40, highlightthickness=0, relief=tk.FLAT, state='readonly')
        self.__path_text.pack(fill=tk.X)
        tk.Label(details_frame, text='Notes:').pack(anchor='w')
        self.__notes_text = tk.Text(details_frame, width=40, height=15, bd=2, relief=tk.SUNKEN, highlightthickness=0)
        self.__notes_text.pack(fill=tk.X)
        tk.Button(details_frame, text='Show File', command=self.__show_button_pressed).pack(ipady=20)

        self.__process_tree(tree)
        DirTree.filter_changed = self.__tree_filter_changed

    def __center_window(self):
        w = 1280
        h = 768
        sw = self.__parent.winfo_screenwidth()
        sh = self.__parent.winfo_screenheight()
        x = (sw - w)/2
        y = (sh - h)/2
        self.__parent.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def __process_tree(self, tree, view_parent=None):
        iid = self.__treeview.insert(
            '' if view_parent is None else view_parent,
            'end',
            text=tree.name,
            open=(view_parent is None),
            tags=('exclude',) if tree.filter == FILTER_EXCLUDE_ALL else tuple(),
            values=(
                friendly_file_size(tree.size),
                friendly_file_size(tree.filtered_size),
                FileChooser.__HAS_NOTES_STRING if tree.notes else ''
            )
        )
        self.__expanded_by_iid[iid] = (view_parent is None)
        self.__tree_by_iid[iid] = tree
        tree.treeview_iid = iid

        for child in tree.children:
            self.__process_tree(child, iid)

    def __treeview_rightclick(self, event):
        # select row under mouse
        iid = self.__treeview.identify_row(event.y)
        if iid:
            # mouse pointer over item
            self.__treeview.selection_set(iid)
            tree = self.__tree_by_iid[iid]
            if tree.filter is FILTER_EXCLUDE_ALL:
                tree.include_all()
            else:
                tree.exclude_all()
        else:
            # mouse pointer not over item
            # occurs when items do not fill frame
            # no action required
            pass

    def __treeview_keypress(self, event):
        if event.char == 'e':
            for iid in self.__treeview.selection():
                tree = self.__tree_by_iid[iid]
                tree.exclude_all()
        elif event.char == 'i':
            for iid in self.__treeview.selection():
                tree = self.__tree_by_iid[iid]
                tree.include_all()

    def __treeview_select(self, event):
        self.commit()
        iid = self.__treeview.focus()
        tree = self.__tree_by_iid[iid]
        self.__focus_tree = tree
        self.__path_text.config(state=tk.NORMAL)
        self.__path_text.delete(0, tk.END)
        self.__path_text.insert(tk.END, tree.path)
        self.__path_text.config(state='readonly')
        self.__notes_text.delete(0.0, tk.END)
        self.__notes_text.insert(tk.END, tree.notes if tree.notes else '')

    def commit(self):
        if self.__focus_tree:
            self.__focus_tree.notes = self.__notes_text.get(1.0, tk.END).strip()
            self.__update_treeview_item(self.__focus_tree)

    def __treeview_open(self, event):
        iid = self.__treeview.focus()
        self.__expanded_by_iid[iid] = True
        tree = self.__tree_by_iid[iid]
        self.__update_treeview(tree)

    def __treeview_close(self, event):
        iid = self.__treeview.focus()
        self.__expanded_by_iid[iid] = False

    def __update_treeview(self, tree):
        updated = self.__tree_filter_changed(tree)
        if updated:
            for child in tree.children:
                self.__update_treeview(child)

    def __tree_filter_changed(self, tree, force=False):
        if tree.treeview_iid:
            parent_iid = self.__treeview.parent(tree.treeview_iid)
            is_visible = self.__expanded_by_iid[parent_iid] if parent_iid else True
            if is_visible or force:
                self.__update_treeview_item(tree)
                return True
        return False

    def __update_treeview_item(self, tree):
        self.__treeview.item(
            tree.treeview_iid,
            tags=('exclude',) if tree.filter == FILTER_EXCLUDE_ALL else tuple(),
            values=(
                friendly_file_size(tree.size),
                friendly_file_size(tree.filtered_size),
                FileChooser.__HAS_NOTES_STRING if tree.notes else ''
            )
        )

    def __show_button_pressed(self):
        if self.__focus_tree:
            show_file(self.__focus_tree.path)


def write_file_list(tree, writer, relpath='', recurse=True):
    if tree.filter != FILTER_EXCLUDE_ALL:
        data = dict(
            path=relpath.encode('ascii', errors='replace'),
            size=tree.filtered_size,
            is_directory=tree.is_directory,
        )
        writer.writerow(data)
    if recurse:
        for child in tree.children:
            write_file_list(child, writer, os.path.join(relpath, child.name))


def write_readme(tree, fout, source_dir_path, parent_path=None):
    if parent_path is None:
        print('Overview', file=fout)
        print('========', file=fout)
        print('', file=fout)
        now = datetime.now()
        print('Files in this directory were copied using backup.py on %s at %s.' % (
            now.strftime('%b %-d, %Y'),
            now.strftime('%-I:%M %p'),
        ), file=fout)
        print('', file=fout)
        print('Source directory: %s' % (source_dir_path,), file=fout)
        print('Total size: %s' % (friendly_file_size(tree.filtered_size),), file=fout)
        print('', file=fout)
        print('A full list of files can be found in %s' % (FILE_LIST_NAME), file=fout)
        print('', file=fout)
        print('', file=fout)
        print('File Notes', file=fout)
        print('==========', file=fout)
    path = ''
    if parent_path is not None:
        path = os.path.join(parent_path, tree.name)
    if tree.notes and tree.filter != FILTER_EXCLUDE_ALL:
        print('', file=fout)
        print(path, file=fout)
        print('', file=fout)
        for line in tree.notes.split('\n'):
            line = line.strip()
            print('    ' + line, file=fout)
    for child in tree.children:
        write_readme(child, fout, None, path)


def show_file(path):
    if os.uname()[0] == 'Darwin':  # Mac
        subprocess.call(["open", "-R", path])


def copy_tree(tree, src_root, dst_root, exclusions_path):
    if os.uname()[0] != 'Darwin':
        raise NotImplementedError('Platform not supported')

    with open(exclusions_path, 'w') as f:
        def write_exclusions(tree, relpath='/'):
            if tree.filter == FILTER_EXCLUDE_ALL:
                print(relpath.replace('[', '\\[').replace(']', '\\]').replace('?', '\\?'), file=f)
                return
            for child in tree.children:
                write_exclusions(child, os.path.join(relpath, child.name))
        write_exclusions(tree)

    # -v, --verbose               increase verbosity
    # -r, --recursive             recurse into directories
    # -l, --links                 copy symlinks as symlinks
    # -p, --perms                 preserve permissions
    # -t, --times                 preserve modification times
    # -g, --group                 preserve group
    # -o, --owner                 preserve owner (super-user only)
    # -D                          same as --devices --specials
    #     --devices               preserve device files (super-user only)
    #     --specials              preserve special files
    #     --safe-links            ignore symlinks that point outside the tree
    # -W, --whole-file            copy files whole (w/o delta-xfer algorithm)

    proc = subprocess.Popen([
        'rsync',
        '-vrlptgoD',
        '--safe-links',
        '--exclude-from=' + exclusions_path,
        #'--whole-file',
        src_root + '/',
        dst_root + '/',
    ])
    ret = proc.wait()
    if ret != 0:
        raise OSError('Copy failed!  Return code = %d' % (ret,))


if __name__ == '__main__':
    (options, args) = parse_command_line()

    tree_file_path = None
    file_list_path = None
    if options.job_path:
        if not os.path.exists(options.job_path):
            os.makedirs(options.job_path)
        tree_file_path = os.path.join(options.job_path, 'tree.dat')

    start_time = time.time()

    if tree_file_path and os.path.exists(tree_file_path):
        print('Loading directory tree ...')
        tree = DirTree.load(tree_file_path)
    else:
        print('Scanning directory ...')
        source_dir_path = os.path.abspath(args[0])
        tree = DirTree.ls(source_dir_path)

    elapsed_time = time.time() - start_time
    print('Completed in %.1f seconds' % (elapsed_time,))

    if not options.quiet:
        root = tk.Tk()

        print('Launching file chooser ...')
        start_time = time.time()
        chooser = FileChooser(root, tree)
        elapsed_time = time.time() - start_time
        print('Completed in %.1f seconds' % (elapsed_time,))

        def close_handler():
            chooser.commit()
            root.destroy()

        root.protocol('WM_DELETE_WINDOW', close_handler)
        root.mainloop()

        if tree_file_path:
            print('Saving directory tree ...')
            start_time = time.time()
            tree.save(tree_file_path)
            elapsed_time = time.time() - start_time
            print('Completed in %.1f seconds' % (elapsed_time,))

    if not options.dry_run:
        print('Copying files ...')
        start_time = time.time()
        source_dir_path = os.path.abspath(args[0])
        dest_dir_path = os.path.abspath(args[1])

        if not os.path.exists(dest_dir_path):
            os.makedirs(dest_dir_path)

        tree.sort_by_name()

        readme_path = os.path.join(dest_dir_path, 'README.txt')
        with open(readme_path, 'w') as f:
            write_readme(tree, f, source_dir_path)

        file_list_path = os.path.join(dest_dir_path, FILE_LIST_NAME)

        with open(file_list_path, 'wb') as file_list_file:
            file_list_writer = DictWriter(file_list_file, fieldnames=(
                'path',
                'is_directory',
                'size',
            ))
            file_list_writer.writeheader()
            write_file_list(tree, file_list_writer)

        copy_tree(
            tree,
            source_dir_path,
            dest_dir_path,
            os.path.join(options.job_path if options.job_path else tempfile.gettempdir(), 'exclusions.txt'))

        elapsed_time = time.time() - start_time
        print('Completed in %.1f seconds' % (elapsed_time,))