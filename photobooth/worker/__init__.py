#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Photobooth - a flexible photo booth software
# Copyright (C) 2018  Balthasar Reuter <photobooth at re - web dot eu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import logging
import os.path
import dropbox
import six
import sys
import contextlib
from time import localtime, strftime, time

from .PictureList import PictureList
from .. import StateMachine
from ..Threading import Workers

class WorkerTask:

    def __init__(self, **kwargs):

        assert not kwargs

    def do(self, picture):

        raise NotImplementedError()


class PictureSaver(WorkerTask):

    def __init__(self, basename, dbx):

        super().__init__()
        self._dbx = dbx
        self._pic_list = PictureList(basename)
            
    def do(self, picture):

        filename = self._pic_list.getNext()
        logging.info('Saving picture as %s', filename)
        with open(filename, 'wb') as f:
            f.write(picture.getbuffer())
        
        if self._dbx is not None:
            print('upload to dropbox', filename, dropbox.files.WriteMode.add)
            with open(filename, 'rb') as f:
                data = f.read()
            try:
                res = self._dbx.files_upload(data, os.path.join('/', filename), dropbox.files.WriteMode.add)
            except:
                print('Dropbox upload error', sys.exc_info()[0])
            else:
                print('Dropbox upload ok', filename)

class Worker:

    def __init__(self, config, comm):
        self._comm = comm
        dropbox_api_key = config.get('Storage', 'dropbox_api_key')
        dbx=None
        if len(dropbox_api_key) > 0:
            dbx = dropbox.Dropbox(dropbox_api_key)
        
        self.initPostprocessTasks(config, dbx)
        self.initPictureTasks(config, dbx)
        
    def initPostprocessTasks(self, config, dbx):

        self._postprocess_tasks = []

        # PictureSaver for assembled pictures
        path = os.path.join(config.get('Storage', 'basedir'),
                            config.get('Storage', 'basename'))
        basename = strftime(path, localtime())
        self._postprocess_tasks.append(PictureSaver(basename, dbx))

    def initPictureTasks(self, config, dbx):

        self._picture_tasks = []

        # PictureSaver for single shots
        path = os.path.join(config.get('Storage', 'basedir'),
                            config.get('Storage', 'basename') + '_shot_')
        basename = strftime(path, localtime())
        self._picture_tasks.append(PictureSaver(basename, dbx))

    def run(self):

        for state in self._comm.iter(Workers.WORKER):
            self.handleState(state)

        return True

    def handleState(self, state):

        if isinstance(state, StateMachine.TeardownState):
            self.teardown(state)
        elif isinstance(state, StateMachine.ReviewState):
            self.doPostprocessTasks(state.picture)
        elif isinstance(state, StateMachine.CameraEvent):
            if state.name == 'capture':
                self.doPictureTasks(state.picture)
            else:
                raise ValueError('Unknown CameraEvent "{}"'.format(state))

    def teardown(self, state):

        pass

    def doPostprocessTasks(self, picture):

        for task in self._postprocess_tasks:
            task.do(picture)

    def doPictureTasks(self, picture):

        for task in self._picture_tasks:
            task.do(picture)
