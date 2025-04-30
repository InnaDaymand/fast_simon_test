# This is a sample Python script.

# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.


import os

from flask import Flask, request
from google.cloud import datastore
from google.cloud.datastore.query import PropertyFilter
from datetime import datetime

app = Flask(__name__)


datastore_client = datastore.Client()


@app.route("/set", methods=["GET"])
def set():
    params = request.args.to_dict()
    name = params.get('name')
    value = params.get('value')
    if value is None or name is None or value == "" or name == '':
        return 'Wrong format', 400
    prev_value = set_operation(name, value)
    stack_operation_key = datastore_client.key('stack_operation')
    stack_operation_entity = datastore_client.entity(key=stack_operation_key)
    stack_operation_entity['name'] = name
    stack_operation_entity['prev_value'] = prev_value
    stack_operation_entity['value'] = value
    stack_operation_entity['name_operation'] = 'set'
    stack_operation_entity['undo_true'] = '0'
    stack_operation_entity['timestamp'] = int(datetime.timestamp(datetime.now()))
    if prev_value is None:
        stack_operation_entity['name_operation'] = 'unset'
    datastore_client.put(entity=stack_operation_entity)
    return '{}={}'.format(name, value), 200


def set_operation(name, value):
    main_key = datastore_client.key('list_variable')
    list_entity = list(datastore_client.query(kind='list_variable').fetch())
    entity = datastore.Entity(key=main_key)
    prev_value = None
    if len(list_entity) > 0:
        ret_list = list(
            datastore_client.query(kind='list_variable').add_filter(filter=PropertyFilter('name', '=', name)).fetch())
        if len(ret_list) > 0:
            entity = ret_list[0]
    if value is not None:
        prev_value = entity.get('value')
        entity['value'] = value
        entity['name'] = name
    datastore_client.put(entity)
    return prev_value


@app.route("/get", methods=["GET"])
def get():
    params = request.args.to_dict()
    name = params.get('name')
    if name is None or name == '':
        return 'Wrong format', 400
    entity_list = list(
        datastore_client.query(kind='list_variable').add_filter(filter=PropertyFilter('name', '=', name)).fetch())
    if len(entity_list) > 0:
        value = entity_list[0]['value']
    else:
        value = 'None'
    return '{}'.format(value), 200


@app.route("/numequalto", methods=["GET"])
def numequalto():
    params = request.args.to_dict()
    value = params.get('value')
    if value is None or value == '':
        return 'Wrong format', 400
    query = datastore_client.query(kind='list_variable')
    query_filter = query.add_filter(filter=PropertyFilter('value', '=', value))
    res = list(query_filter.fetch())
    return '{}'.format(len(res)), 200


@app.route("/unset", methods=["GET"])
def unset():
    params = request.args.to_dict()
    name = params.get('name')
    if name is None:
        return 'Wrong format', 400
    prev_value = unset_operation(name)
    if prev_value is not None:
        stack_operation_key = datastore_client.key('stack_operation')
        stack_operation_entity = datastore_client.entity(key=stack_operation_key)
        stack_operation_entity['name'] = name
        stack_operation_entity['prev_value'] = prev_value
        stack_operation_entity['value'] = None
        stack_operation_entity['name_operation'] = 'set'
        stack_operation_entity['undo_true'] = '0'
        stack_operation_entity['timestamp'] = int(datetime.timestamp(datetime.now()))
        datastore_client.put(entity=stack_operation_entity)
    return '{} = None'.format(name), 200


def unset_operation(name):
    query = datastore_client.query(kind='list_variable')
    query_filter = query.add_filter(filter=PropertyFilter('name', '=', name))
    list_res = list(query_filter.fetch())
    prev_value = None
    if len(list_res) > 0:
        entity = list(query_filter.fetch())[0]
        prev_value = entity['value']
        datastore_client.delete(key=entity.key)
    return prev_value


@app.route("/end")
def end():
    all_entities = list(datastore_client.query(kind='list_variable').fetch())
    for entity in all_entities:
        datastore_client.delete(key=entity.key)
    all_entities = list(datastore_client.query(kind='stack_operation').fetch())
    for entity in all_entities:
        datastore_client.delete(key=entity.key)
    return 'CLEANED', 200


@app.route("/undo")
def undo():
    query = datastore_client.query(kind='stack_operation')
    query.order = ['timestamp']
    all_entities = list(query.add_filter(filter=PropertyFilter('undo_true', '=', '0')).fetch())
    name = None
    prev_value = None
    if len(all_entities) > 0:
        last_operation = all_entities[len(all_entities) - 1]
        operation = last_operation['name_operation']
        prev_value = last_operation['prev_value']
        name = last_operation['name']
        if operation == 'set':
            _ = set_operation(name, prev_value)
        if operation == 'unset':
            _ = unset_operation(name)
            last_operation['name_operation'] = 'set'
        last_operation['undo_true'] = '1'
        last_operation['timestamp'] = datetime.timestamp(datetime.now())
        datastore_client.put(entity=last_operation)
    if name is not None:
        return '{}={}'.format(name, prev_value), 200
    else:
        return 'NO COMMANDS', 200


@app.route("/redo")
def redo():
    query = datastore_client.query(kind='stack_operation')
    query.order = ['timestamp']
    all_entities = list(query.add_filter(filter=PropertyFilter('undo_true', '=', '1')).fetch())
    name = None
    value = None
    if len(all_entities) > 0:
        last_operation = all_entities[len(all_entities) - 1]
        operation = last_operation['name_operation']
        value = last_operation['value']
        name = last_operation['name']
        if operation == 'set':
            _ = set_operation(name, value)
        if operation == 'unset':
            _ = unset_operation(name)
            last_operation['name_operation'] = 'set'
        last_operation['undo_true'] = '0'
        last_operation['timestamp'] = datetime.timestamp(datetime.now())
        datastore_client.put(entity=last_operation)
    if name is not None:
        return '{}={}'.format(name, value), 200
    else:
        return 'NO COMMANDS', 200


@app.route("/")
def root():
    """Example Hello World route."""
    name = os.environ.get("NAME", "World")
    return f"Hello {name}!"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
# See PyCharm help at https://www.jetbrains.com/help/pycharm/
