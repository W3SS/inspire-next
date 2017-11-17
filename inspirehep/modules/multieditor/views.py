# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2014-2017 CERN.
#
# INSPIRE is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# INSPIRE is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Module for backend of multi record editor used in http://inspirehep.net."""

from __future__ import absolute_import, print_function, division

from flask import Blueprint, request, jsonify, session
from jsonschema import ValidationError
from inspirehep.modules.records.json_ref_loader import load_resolved_schema
from inspire_schemas.api import validate
from inspirehep.modules.multieditor import tasks
from inspirehep.modules.migrator.tasks import chunker
from . import actions
from . import queries

blueprint = Blueprint(
    'inspirehep_multieditor',
    __name__,
    url_prefix='/multieditor',
)


@blueprint.route("/update", methods=['POST'])
def update():
    """Apply the user actions to the database records."""
    user_actions = request.json['userActions']
    checked_ids = request.json['ids']
    searched_records = session.get('multieditor_searched_records', [])
    if searched_records:
        ids = searched_records['ids']
        index = searched_records['schema']
        schema = load_resolved_schema(index)
        ids = filter(lambda x: x not in checked_ids, ids)
    for i, chunk in enumerate(chunker(ids, 20)):
        tasks.process_records.delay(records_ids=chunk, user_actions=user_actions, schema=schema)

    return jsonify({'message': 'Records have been updated successfully'})


@blueprint.route("/preview", methods=['POST'])
def preview():
    """Preview the user actions in the first (page size) records."""
    errors = []
    user_actions = request.json['userActions']
    query_string = request.json['queryString']
    page_size = int(request.json['pageSize'])
    page_num = request.json['pageNum']
    searched_records = session.get('multieditor_searched_records', [])
    if searched_records:
        index = searched_records['schema']
    schema = load_resolved_schema(index)
    records = queries.get_records_from_query(query_string, page_size, page_num, index)['json_records']
    actions.process_records_no_db(user_actions, records, schema)
    for record in records:
        try:
            validate(record, schema)
        except ValidationError as e:
            errors.append(e.message)
        else:
            errors.append(None)
    return jsonify({'json_records': records, 'errors': errors})


@blueprint.route("/search", methods=['GET'])
def search():
    """Search for records using the query and store the result's ids"""
    query_string = request.args.get('queryString', '')
    page_num = int(request.args.get('pageNum', 1))
    page_size = int(request.args.get('pageSize', 1))
    index = request.args.get('index', '')
    session['multieditor_searched_records'] = {
        'ids': queries.get_record_ids_from_query(query_string, index),
        'schema': index
    }
    return jsonify(queries.get_records_from_query(query_string, page_size, page_num, index))
