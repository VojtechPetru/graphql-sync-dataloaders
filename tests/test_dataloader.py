import threading
from unittest import mock
from unittest.mock import Mock
from functools import partial

from graphql import (
    graphql_sync,
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLField,
    GraphQLArgument,
    GraphQLString,
    GraphQLList,
    GraphQLNonNull,
    GraphQLUnionType,
)

from graphql_sync_dataloaders import DeferredExecutionContext, SyncDataLoader

graphql_sync_deferred = partial(graphql_sync, execution_context_class=DeferredExecutionContext)


def test_deferred_execution():
    NAMES = {
        "1": "Sarah",
        "2": "Lucy",
        "3": "Geoff",
        "5": "Dave",
    }

    def load_fn(keys):
        return [NAMES[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_name(_, __, key):
        return dataloader.load(key)

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "name": GraphQLField(
                    GraphQLString,
                    args={
                        "key": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_name,
                )
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            name1: name(key: "1")
            name2: name(key: "2")
        }
        """,
    )

    assert not result.errors
    assert result.data == {"name1": "Sarah", "name2": "Lucy"}
    assert mock_load_fn.call_count == 1


def test_nested_deferred_execution():
    USERS = {
        "1": {
            "name": "Laura",
            "bestFriend": "2",
        },
        "2": {
            "name": "Sarah",
            "bestFriend": None,
        },
        "3": {
            "name": "Dave",
            "bestFriend": "2",
        },
    }

    def load_fn(keys):
        return [USERS[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_user(_, __, id):
        return dataloader.load(id)

    def resolve_best_friend(user, _):
        return dataloader.load(user["bestFriend"])

    user = GraphQLObjectType(
        name="User",
        fields=lambda: {
            "name": GraphQLField(GraphQLString),
            "bestFriend": GraphQLField(user, resolve=resolve_best_friend),
        },
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "user": GraphQLField(
                    user,
                    args={
                        "id": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_user,
                )
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            user1: user(id: "1") {
                name
                bestFriend {
                    name
                }
            }
            user2: user(id: "3") {
                name
                bestFriend {
                    name
                }
            }
        }
        """,
    )

    assert not result.errors
    assert result.data == {
        "user1": {
            "name": "Laura",
            "bestFriend": {
                "name": "Sarah",
            },
        },
        "user2": {
            "name": "Dave",
            "bestFriend": {
                "name": "Sarah",
            },
        },
    }
    assert mock_load_fn.call_count == 2


def test_deferred_execution_list():
    USERS = {
        "1": {
            "name": "Laura",
            "bestFriend": "2",
        },
        "2": {
            "name": "Sarah",
            "bestFriend": None,
        },
        "3": {
            "name": "Dave",
            "bestFriend": "2",
        },
    }

    def load_fn(keys):
        return [USERS[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_users(_, __):
        return [dataloader.load(id) for id in USERS]

    def resolve_best_friend(user, _):
        if user["bestFriend"]:
            return dataloader.load(user["bestFriend"])
        return None

    user = GraphQLObjectType(
        name="User",
        fields=lambda: {
            "name": GraphQLField(GraphQLString),
            "bestFriend": GraphQLField(user, resolve=resolve_best_friend),
        },
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "users": GraphQLField(
                    GraphQLList(user),
                    resolve=resolve_users,
                )
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            users {
                name
                bestFriend {
                    name
                }
            }
        }
        """,
    )

    if result.errors:
        original_error = result.errors[0].original_error
        if not original_error:
            raise result.errors[0]
        raise original_error
    assert not result.errors
    assert result.data == {
        "users": [
            {
                "name": "Laura",
                "bestFriend": {
                    "name": "Sarah",
                },
            },
            {
                "name": "Sarah",
                "bestFriend": None,
            },
            {
                "name": "Dave",
                "bestFriend": {
                    "name": "Sarah",
                },
            },
        ],
    }
    assert mock_load_fn.call_count == 1


def test_deferred_execution_errors():
    USERS = {
        "1": {
            "name": "Laura",
            "bestFriend": "2",
        },
        "2": ValueError("Sarah has left"),
        "3": {
            "name": "Dave",
            "bestFriend": "2",
        },
    }

    def load_fn(keys):
        return [USERS[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_users(_, __):
        return [dataloader.load(id) for id in USERS]

    def resolve_best_friend(user, _):
        if user["bestFriend"]:
            return dataloader.load(user["bestFriend"])
        return None

    user = GraphQLObjectType(
        name="User",
        fields=lambda: {
            "name": GraphQLField(GraphQLString),
            "bestFriend": GraphQLField(user, resolve=resolve_best_friend),
        },
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "users": GraphQLField(
                    GraphQLList(user),
                    resolve=resolve_users,
                )
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            users {
                name
                bestFriend {
                    name
                }
            }
        }
        """,
    )

    assert result.errors == [
        {"message": "Sarah has left", "locations": [(3, 13)], "path": ["users", 1]},
        {
            "message": "Sarah has left",
            "locations": [(5, 17)],
            "path": ["users", 0, "bestFriend"],
        },
        {
            "message": "Sarah has left",
            "locations": [(5, 17)],
            "path": ["users", 2, "bestFriend"],
        },
    ]
    assert result.data == {
        "users": [
            {
                "name": "Laura",
                "bestFriend": None,
            },
            None,
            {
                "name": "Dave",
                "bestFriend": None,
            },
        ],
    }
    assert mock_load_fn.call_count == 1


def test_result_field_ordering():
    NAMES = {
        "1": "Sarah",
        "2": "Lucy",
        "3": "Geoff",
        "5": "Dave",
    }

    def load_fn(keys):
        return [NAMES[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_name(_, __, key):
        return dataloader.load(key)

    def resolve_hello(_, __, name):
        return f"hello {name}"

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "name": GraphQLField(
                    GraphQLString,
                    args={
                        "key": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_name,
                ),
                "hello": GraphQLField(
                    GraphQLString,
                    args={
                        "name": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_hello,
                ),
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            name1: name(key: "1")
            hello1: hello(name: "grace")
            name2: name(key: "2")
            hello2: hello(name: "lucy")
        }
        """,
    )

    assert not result.errors
    assert result.data
    assert result.data == {
        "name1": "Sarah",
        "hello1": "hello grace",
        "name2": "Lucy",
        "hello2": "hello lucy",
    }
    keys = list(result.data.keys())
    assert keys == ["name1", "hello1", "name2", "hello2"]
    assert mock_load_fn.call_count == 1


def test_chaining_dataloader():
    USERS = {
        "1": {
            "name": "Sarah",
            "best_friend": "2",
        },
        "2": {
            "name": "Lucy",
            "best_friend": "3",
        },
        "3": {
            "name": "Geoff",
        },
        "5": {
            "name": "Dave",
        },
    }

    def load_fn(keys):
        return [USERS[key] if key in USERS else None for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_name(_, __, userId):
        return dataloader.load(userId).then(lambda user: user["name"])

    def resolve_best_friend_name(_, __, userId):
        return (
            dataloader.load(userId)
            .then(lambda user: dataloader.load(user["best_friend"]))
            .then(lambda user: user["name"])
        )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "name": GraphQLField(
                    GraphQLString,
                    args={
                        "userId": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_name,
                ),
                "bestFriendName": GraphQLField(
                    GraphQLString,
                    args={
                        "userId": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_best_friend_name,
                ),
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            name1: name(userId: "1")
            name2: name(userId: "2")
            bestFriend1: bestFriendName(userId: "1")
            bestFriend2: bestFriendName(userId: "2")
        }
        """,
    )

    assert not result.errors
    assert result.data == {
        "name1": "Sarah",
        "name2": "Lucy",
        "bestFriend1": "Lucy",
        "bestFriend2": "Geoff",
    }
    assert mock_load_fn.call_count == 2
    assert mock_load_fn.call_args_list[0].args[0] == ["1", "2"]
    assert mock_load_fn.call_args_list[1].args[0] == ["3"]


def test_concurrent_threads_are_isolated():
    """DataloaderBatchCallbacks must isolate callbacks per thread.

    Without thread-local callback storage, _callbacks is a plain list shared
    across all threads. When two threads add callbacks concurrently, both
    threads see the combined list. One thread's run_all_callbacks then steals
    the other's callbacks, leaving SyncFutures permanently PENDING.

    This test verifies isolation at the DataloaderBatchCallbacks level:
    each thread should only see callbacks it added itself.
    """
    from graphql_sync_dataloaders.sync_dataloader import dataloader_batch_callbacks

    add_barrier = threading.Barrier(2, timeout=5)
    check_barrier = threading.Barrier(2, timeout=5)
    visible_counts = {}

    def thread_fn(name):
        # Each thread adds exactly one callback
        dataloader_batch_callbacks.add_callback(lambda: name)
        # Wait until both threads have added their callback
        add_barrier.wait()
        # Check how many callbacks are visible from this thread
        visible_counts[name] = len(dataloader_batch_callbacks._callbacks)
        check_barrier.wait()
        # Clean up: drain this thread's callbacks so they don't leak
        dataloader_batch_callbacks.run_all_callbacks()

    t1 = threading.Thread(target=thread_fn, args=("t1",))
    t2 = threading.Thread(target=thread_fn, args=("t2",))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    # Without thread-local: both threads see 2 (shared list)
    # With thread-local: each thread sees only 1 (its own)
    assert visible_counts["t1"] == 1, (
        f"t1 saw {visible_counts['t1']} callbacks, expected 1 — callbacks are leaking across threads"
    )
    assert visible_counts["t2"] == 1, (
        f"t2 saw {visible_counts['t2']} callbacks, expected 1 — callbacks are leaking across threads"
    )


def test_non_null_field_with_null_from_dataloader_reports_error():
    """A non-null field whose value is supplied by a dataloader that resolves
    to None must surface the real "Cannot return null for non-nullable field"
    error, matching standard graphql-core execution. It must not be hidden
    behind the generic "deferred execution failed to complete" message.
    """
    dataloader = SyncDataLoader(lambda keys: [None for _ in keys])

    def resolve_value(_, __, key):
        return dataloader.load(key)

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "value": GraphQLField(
                    GraphQLNonNull(GraphQLString),
                    args={"key": GraphQLArgument(GraphQLString)},
                    resolve=resolve_value,
                ),
            },
        )
    )

    result = graphql_sync_deferred(schema, '{ value(key: "1") }')

    assert result.data is None
    assert result.errors is not None
    assert len(result.errors) == 1
    assert (
        result.errors[0].message
        == "Cannot return null for non-nullable field Query.value."
    )
    assert result.errors[0].path == ["value"]


def test_non_null_field_with_wrong_type_from_dataloader_reports_error():
    """When a dataloader returns a value of the wrong type for a non-null
    object field (its is_type_of check fails), the real type error must be
    surfaced instead of being swallowed behind the generic deferred-execution
    failure message.
    """
    dataloader = SyncDataLoader(lambda keys: [{"name": "wrong"} for _ in keys])

    user = GraphQLObjectType(
        name="User",
        fields={"name": GraphQLField(GraphQLString)},
        is_type_of=lambda obj, info: False,
    )

    def resolve_user(_, __, key):
        return dataloader.load(key)

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "user": GraphQLField(
                    GraphQLNonNull(user),
                    args={"key": GraphQLArgument(GraphQLString)},
                    resolve=resolve_user,
                ),
            },
        )
    )

    result = graphql_sync_deferred(schema, '{ user(key: "1") { name } }')

    assert result.data is None
    assert result.errors is not None
    assert len(result.errors) == 1
    assert "Expected value of type 'User'" in result.errors[0].message
    assert result.errors[0].path == ["user"]


def test_list_with_nullable_items_reports_error_for_failing_item_only():
    """In a list of nullable items, a single item whose dataloader errors is
    reported as null while the surrounding items keep their values.
    """
    values = {"1": "a", "2": ValueError("boom"), "3": "c"}
    dataloader = SyncDataLoader(lambda keys: [values[key] for key in keys])

    def resolve_items(_, __):
        return [dataloader.load(key) for key in ("1", "2", "3")]

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "items": GraphQLField(
                    GraphQLList(GraphQLString), resolve=resolve_items
                ),
            },
        )
    )

    result = graphql_sync_deferred(schema, "{ items }")

    assert result.data == {"items": ["a", None, "c"]}
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].message == "boom"
    assert result.errors[0].path == ["items", 1]


def test_list_of_non_null_items_with_wrong_type_reports_error():
    """A wrong-typed object supplied for a non-null list item reports the type
    error and nullifies only the nullable list that contains it. Sibling
    fields of the operation keep their values, matching standard graphql-core.
    """
    users = {
        "1": {"kind": "user", "name": "ok"},
        "2": {"kind": "address", "name": "bad"},
    }
    dataloader = SyncDataLoader(lambda keys: [users[key] for key in keys])

    user = GraphQLObjectType(
        name="User",
        fields={"name": GraphQLField(GraphQLString)},
        is_type_of=lambda obj, info: obj.get("kind") == "user",
    )

    def resolve_users(_, __):
        return [dataloader.load(key) for key in ("1", "2")]

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "users": GraphQLField(
                    GraphQLList(GraphQLNonNull(user)), resolve=resolve_users
                ),
                "status": GraphQLField(GraphQLString, resolve=lambda *_: "ok"),
            },
        )
    )

    result = graphql_sync_deferred(schema, "{ users { name } status }")

    assert result.data == {"users": None, "status": "ok"}
    assert result.errors is not None
    assert len(result.errors) == 1
    assert "Expected value of type 'User'" in result.errors[0].message
    assert result.errors[0].path == ["users", 1]


def test_non_null_child_error_nullifies_only_nullable_parent():
    """A non-null field backed by a dataloader that resolves to null nullifies
    only its nearest nullable ancestor (the parent object), not the whole
    operation. Sibling fields keep their values, matching standard
    graphql-core.
    """
    dataloader = SyncDataLoader(lambda keys: [None for _ in keys])

    def resolve_name(_, __):
        return dataloader.load("k")

    user = GraphQLObjectType(
        name="User",
        fields={
            "name": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_name),
        },
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "user": GraphQLField(user, resolve=lambda *_: {}),
                "status": GraphQLField(GraphQLString, resolve=lambda *_: "ok"),
            },
        )
    )

    result = graphql_sync_deferred(schema, "{ user { name } status }")

    assert result.data == {"user": None, "status": "ok"}
    assert result.errors is not None
    assert len(result.errors) == 1
    assert (
        result.errors[0].message
        == "Cannot return null for non-nullable field User.name."
    )
    assert result.errors[0].path == ["user", "name"]


def test_non_null_list_with_null_item_reports_error():
    """A non-null list of non-null items that receives a null item from a
    dataloader reports the non-null violation as a GraphQL error.
    """
    values = {"1": "a", "2": None}
    dataloader = SyncDataLoader(lambda keys: [values[key] for key in keys])

    def resolve_items(_, __):
        return [dataloader.load(key) for key in ("1", "2")]

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "items": GraphQLField(
                    GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLString))),
                    resolve=resolve_items,
                ),
            },
        )
    )

    result = graphql_sync_deferred(schema, "{ items }")

    assert result.data is None
    assert result.errors is not None
    assert len(result.errors) == 1
    assert (
        result.errors[0].message
        == "Cannot return null for non-nullable field Query.items."
    )
    assert result.errors[0].path == ["items", 1]


def test_nullable_union_returning_type_outside_union_reports_error():
    """A nullable union field whose dataloader returns an object matching none
    of the union members reports the abstract-type resolution error and nulls
    just that field.
    """
    a = GraphQLObjectType(
        "A", {"a": GraphQLField(GraphQLString)},
        is_type_of=lambda obj, info: obj.get("kind") == "a",
    )
    b = GraphQLObjectType(
        "B", {"b": GraphQLField(GraphQLString)},
        is_type_of=lambda obj, info: obj.get("kind") == "b",
    )
    ab = GraphQLUnionType("AB", [a, b])

    dataloader = SyncDataLoader(lambda keys: [{"kind": "c"} for _ in keys])

    def resolve_thing(_, __, key):
        return dataloader.load(key)

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "thing": GraphQLField(
                    ab,
                    args={"key": GraphQLArgument(GraphQLString)},
                    resolve=resolve_thing,
                ),
            },
        )
    )

    result = graphql_sync_deferred(schema, '{ thing(key: "1") { __typename } }')

    assert result.data == {"thing": None}
    assert result.errors is not None
    assert len(result.errors) == 1
    assert "Abstract type 'AB' must resolve to an Object type" in result.errors[0].message
    assert result.errors[0].path == ["thing"]


def test_non_null_union_returning_type_outside_union_reports_error():
    """A non-null union field whose dataloader returns an object matching none
    of the union members reports the abstract-type resolution error instead of
    hanging the operation.
    """
    a = GraphQLObjectType(
        "A", {"a": GraphQLField(GraphQLString)},
        is_type_of=lambda obj, info: obj.get("kind") == "a",
    )
    b = GraphQLObjectType(
        "B", {"b": GraphQLField(GraphQLString)},
        is_type_of=lambda obj, info: obj.get("kind") == "b",
    )
    ab = GraphQLUnionType("AB", [a, b])

    dataloader = SyncDataLoader(lambda keys: [{"kind": "c"} for _ in keys])

    def resolve_thing(_, __, key):
        return dataloader.load(key)

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "thing": GraphQLField(
                    GraphQLNonNull(ab),
                    args={"key": GraphQLArgument(GraphQLString)},
                    resolve=resolve_thing,
                ),
            },
        )
    )

    result = graphql_sync_deferred(schema, '{ thing(key: "1") { __typename } }')

    assert result.data is None
    assert result.errors is not None
    assert len(result.errors) == 1
    assert "Abstract type 'AB' must resolve to an Object type" in result.errors[0].message
    assert result.errors[0].path == ["thing"]


def test_nullable_object_field_with_wrong_type_reports_error():
    """A nullable object field whose dataloader returns a value of the wrong
    type (its is_type_of check fails) reports the type error and nulls just
    that field.
    """
    user = GraphQLObjectType(
        name="User",
        fields={"name": GraphQLField(GraphQLString)},
        is_type_of=lambda obj, info: False,
    )

    dataloader = SyncDataLoader(lambda keys: [{"name": "x"} for _ in keys])

    def resolve_user(_, __, key):
        return dataloader.load(key)

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "user": GraphQLField(
                    user,
                    args={"key": GraphQLArgument(GraphQLString)},
                    resolve=resolve_user,
                ),
            },
        )
    )

    result = graphql_sync_deferred(schema, '{ user(key: "1") { name } }')

    assert result.data == {"user": None}
    assert result.errors is not None
    assert len(result.errors) == 1
    assert "Expected value of type 'User'" in result.errors[0].message
    assert result.errors[0].path == ["user"]
