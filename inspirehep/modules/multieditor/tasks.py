# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2014-2017 CERN.
#
# INSPIRE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INSPIRE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.


from __future__ import absolute_import, print_function, division

from celery import shared_task
from invenio_records.api import Record
from invenio_db import db
from inspirehep.modules.multieditor.actions import (
    get_actions
)
from jsonschema import ValidationError


@shared_task(ignore_result=True)
def process_records(records_ids, user_actions, schema):
    commit_record = False
    errors = []
    records = Record.get_records(records_ids)
    class_actions = get_actions(user_actions)
    for record in records:
        for class_action in class_actions:
            class_action.apply_action(record=record, schema=schema)
            if class_action.changed:
                commit_record = True
                class_action.changed = False
        if commit_record:
            try:
                record.commit()
            except (ValidationError, Exception) as e:
                errors.append(e.message)
            commit_record = False
    db.session.commit()
