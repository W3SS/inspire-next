# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2017 CERN.
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

import re


class Action(object):
    def __init__(self, keys, value=None, match_type=None, value_to_check=None,
                 conditions=None):
        self.keys = keys
        self.value = value
        self.match_type = match_type
        self.value_to_check = value_to_check
        self.conditions = conditions
        self.changed = False

    def progress_keys(self, record, schema, position, checked):
        key = self.keys[position]
        condition_failed = False
        new_schema = {}
        if schema:  # for testing purposes
            if schema['type'] == 'object':
                new_schema = schema['properties'][key]
            elif schema['type'] == 'array':
                new_schema = schema['items']['properties'][key]
        if self.conditions:
            for condition in self.conditions:
                if position < len(condition.get('keys')) and\
                        (key != condition.get('keys')[position] and
                            (position == 0 or self.keys[position - 1] == condition.get('keys')[position - 1]) or
                            (key == condition.get('keys')[position] and position == len(condition.get('keys')) - 1)):
                    # if the main key is different from the condition key for the first time
                    # or the condition is checking the same path that the action is applied
                    if not check_value(record=record, keys=condition.get('keys'),
                                       value_to_check=condition.get('value', ''),
                                       match_type=condition.get('match_type', ''), position=position):
                        condition_failed = True
                    checked = checked + 1  # number of conditions that passed successfully
        return new_schema, checked, key, condition_failed


class Addition(Action):

    def apply_action(self, record, schema, position=0, checked=0):
        """Recursive function to add a record object."""
        new_schema, checked, key, condition_failed = self.progress_keys(record, schema, position, checked)
        if condition_failed:  # if the condition check was negative stop the action
            return
        if not record.get(key):
            if self.conditions and checked < len(self.conditions):
                return  # if the conditions that passed are less
                #  than the total ones the subrecord of the condition is missing and the action wont be applied
            creation_keys = self.keys[position:]
            record.update(create_schema_record(schema, creation_keys, self.value))
            self.changed = True
            return
        if position == len(self.keys) - 1:
            if isinstance(record[key], list):
                record[key].append(self.value)
                self.changed = True
        else:
            if isinstance(record[key], list):
                for array_record in record[key]:
                    self.apply_action(array_record, new_schema, position + 1, checked)
            else:
                self.apply_action(record[key], new_schema, position + 1, checked)


class Deletion(Action):

    def apply_action(self, record, schema, position=0, checked=0):
        """Recursive function to delete a record primitive key."""
        new_schema, checked, key, condition_failed = self.progress_keys(record, schema, position, checked)
        if condition_failed:
            return
        if not record.get(key):
            return
        if position == len(self.keys) - 1:
            if isinstance(record[key], list):
                if self.match_type == 'regex':
                        record[key] = filter(lambda x: (not re.search(
                            re.escape(self.value_to_check),
                            x)), record[key])

                elif self.match_type == 'equal':
                    record[key] = filter(lambda x: not x == self.value_to_check, record[key])

                elif self.match_type == 'contains':
                    record[key] = filter(lambda x: self.value_to_check not in x, record[key])

            else:
                if self.match_type == 'equal' and record[key] == self.value_to_check:
                    del record[key]

                elif self.match_type == 'regex' and re.search(
                        re.escape(self.value_to_check),
                        record[key]):
                            del record[key]
                elif self.match_type == 'contains' and self.value_to_check in record[key]:
                    del record[key]

                self.changed = True
                return
        else:
            if isinstance(record[key], list):
                for array_record in record[key]:
                    self.apply_action(array_record, new_schema, position + 1, checked)
            else:
                self.apply_action(record[key], new_schema, position + 1, checked)
        if isinstance(record[key], list):
            record[key] = [item for item in record[key] if item not in [{}, '', []]]
        if record[key] in [{}, '', []]:
            del record[key]


class Update(Action):

    def apply_action(self, record, schema, position=0, checked=0):
        """Recursive function to update a record primitive key."""
        new_schema, checked, key, condition_failed = self.progress_keys(record, schema, position, checked)
        if condition_failed:
            return
        if not record.get(key):
            return
        if position == len(self.keys) - 1:
            if isinstance(record[key], list):
                if self.match_type == 'regex':
                    record[key] = [self.value if re.search(
                        re.escape(self.value_to_check),
                        x) else x for x in record[key]]

                elif self.match_type == 'equal':
                    record[key] = [self.value if x == self.value_to_check else x for x in record[key]]

                elif self.match_type == 'contains':
                    record[key] = [self.value if self.value_to_check in x else x for x in record[key]]
                self.changed = True
            else:
                if self.match_type == 'equal' and record[key] == self.value_to_check:
                    record[key] = self.value
                if self.match_type == 'regex' and re.search(
                        re.escape(self.value_to_check),
                        record[key]):
                            record[key] = self.value
                elif self.match_type == 'contains' and self.value_to_check in record[key]:
                    record[key] = self.value
                self.changed = True
                return
        else:
            if isinstance(record[key], list):
                for array_record in record[key]:
                    self.apply_action(array_record, new_schema, position + 1, checked)
            else:
                self.apply_action(record[key], new_schema, position + 1, checked)


def create_schema_record(schema, path, value):
    """Object creation in par with the schema."""
    record = {}
    temp_record = record
    new_schema = schema
    if new_schema['type'] == 'array':
        new_schema = new_schema['items']['properties']
    elif new_schema['type'] == 'object':
        new_schema = new_schema['properties']
    for key in path:
        new_schema = new_schema[key]
        if new_schema['type'] == 'object':
            new_schema = new_schema['properties']
            temp_record[key] = {}
            temp_record = temp_record[key]

        elif new_schema['type'] == 'array':
            if new_schema['items']['type'] == 'object':
                new_schema = new_schema['items']['properties']
            if len(path) == 1:
                temp_record[key] = [value]
                return record
            else:
                temp_record[key] = [{}]
                temp_record = temp_record[key][0]
    temp_record[path[-1]] = value
    return record


def check_value(record, match_type, keys, value_to_check, position):
    """Function that checks the validity of the condition."""
    key = keys[position]
    if not record.get(key):
        return match_type == 'missing'
    temp_record = record[key]
    if isinstance(temp_record, list):
        for index, array_record in enumerate(temp_record):
            if position + 1 == len(keys):
                if match_type == 'equal' and array_record == value_to_check:
                    return True
                elif match_type == 'contains' and value_to_check in array_record:
                    return True
                elif match_type == 'regex'and re.search(
                        re.escape(value_to_check),
                        array_record):
                        return True
            else:
                if check_value(array_record, match_type,
                               keys, value_to_check, position + 1):
                    return True
    else:
        if position + 1 == len(keys):
            if match_type == 'equal' and temp_record == value_to_check:
                return True
            elif match_type == 'contains' and value_to_check in temp_record:
                return True
            elif match_type == 'regex' and re.search(
                    re.escape(value_to_check),
                    temp_record):
                return True
        else:
            return check_value(temp_record, match_type,
                               keys, value_to_check, position + 1)
    return False


def get_actions(user_actions):
    class_actions = []
    conditions = []
    if not user_actions:
        return

    for action in user_actions.get('conditions',[]):
        if not action['key']:
            continue
        keys = action['key'].split('/')
        condition = {'value': action['value'],
                     'keys': keys,
                     'match_type': action['matchType']}
        conditions.append(condition)

    for user_action in user_actions.get('actions', []):
        keys = user_action.get('mainKey').split('/')
        if not keys:
            return
        if user_action.get('actionName') == 'Addition':
            class_actions.append(Addition(keys=keys, value=user_action.get('value'),
                                          match_type=user_action.get('matchType'),
                                          conditions=conditions))
        elif user_action.get('actionName') == 'Deletion':
            class_actions.append(Deletion(keys=keys, value=user_action.get('value'),
                                          value_to_check=user_action.get('updateValue'),
                                          match_type=user_action.get('matchType'),
                                          conditions=conditions))
        elif user_action.get('actionName') == 'Update':
            class_actions.append(Update(keys=keys, value=user_action.get('value'),
                                        match_type=user_action.get('matchType'),
                                        value_to_check=user_action.get('updateValue'),
                                        conditions=conditions))
    return class_actions


def process_records_no_db(user_actions, records, schema):  # fixme name convention
    class_actions = get_actions(user_actions)
    for record in records:
        for class_action in class_actions:
            class_action.apply_action(record, schema)
    return records
